// Reuse the ABI, winning Odin kernel adapter, and independent set oracle.
#define GAIA_LIVENESS_LIBRARY_ONLY
#include "../host.cpp"
#include <llvm/Transforms/Utils/Cloning.h>
#include <map>
#include <memory>

namespace retained {
using Words = std::vector<uint64_t>;
using IDs = std::vector<uint32_t>;
enum Mode { Native, Eager, Lazy };
static const char *names[] = {"native_cached", "compact_eager", "compact_lazy"};
static const char *events[] = {"initial", "explore", "unchanged", "operand_edit",
    "value_renumber", "cfg_split", "add_function", "remove_function", "context_refresh", "final_hit"};
struct Index {
    std::vector<const llvm::Value*> nodes;
    llvm::DenseMap<const llvm::Value*, uint32_t> ids, ssa;
    llvm::DenseMap<const llvm::BasicBlock*, uint32_t> blocks;
    explicit Index(llvm::Function &f) {
        auto node=[&](const llvm::Value *v) { ids[v]=nodes.size(); nodes.push_back(v); };
        for (auto &arg:f.args()) { node(&arg); ssa[&arg]=ssa.size(); }
        for (auto &b:f) {
            blocks[&b]=blocks.size();
            for (auto &i:b) { node(&i); if(!i.getType()->isVoidTy())ssa[&i]=ssa.size(); }
        }
    }
};
struct Graph { IDs offsets, edges; };
// All policies share this producer. Eager additionally emits def-use edges
// during the same operand walk. No textual operand names are produced.
static Facts produce(llvm::Function &f, const Index &ix, Graph *graph) {
    Facts facts; facts.name=f.getName().str(); facts.values=ix.ssa.size();
    facts.successors.resize(f.size()); facts.defs.resize(f.size()); facts.uses.resize(f.size());
    Rows users(graph ? ix.nodes.size() : 0);
    IDs defined_in(ix.ssa.size(),UINT32_MAX);
    for(auto &b:f) {
        auto bid=ix.blocks.lookup(&b);
        for(auto *s:llvm::successors(&b))facts.successors[bid].push_back(ix.blocks.lookup(s));
        for(auto &i:b) {
            auto def=ix.ssa.find(&i);
            if(def!=ix.ssa.end())facts.defs[bid].push_back(def->second);
            if(llvm::isa<llvm::DbgInfoIntrinsic>(i)) {
                if(def!=ix.ssa.end())defined_in[def->second]=bid;
                continue;
            }
            auto *phi=llvm::dyn_cast<llvm::PHINode>(&i);
            if(phi)++facts.phis;
            for(unsigned k=0;k<i.getNumOperands();++k) {
                auto *v=i.getOperand(k);
                if(graph) {
                    auto node=ix.ids.find(v);
                    if(node!=ix.ids.end())users[node->second].push_back(ix.ids.lookup(&i));
                }
                auto operand=ix.ssa.find(v); if(operand==ix.ssa.end())continue;
                // Preserve instruction order even in unreachable blocks.
                // PHI uses belong to incoming blocks.
                auto *use_block=phi ? phi->getIncomingBlock(k) : &b;
                const auto *instruction=llvm::dyn_cast<llvm::Instruction>(v);
                if(phi ? (!instruction || instruction->getParent()!=use_block) : defined_in[operand->second]!=bid)
                    facts.uses[ix.blocks.lookup(use_block)].push_back(operand->second);
                if(phi)++facts.phi_operands;
            }
            if(def!=ix.ssa.end())defined_in[def->second]=bid;
        }
    }
    uniqueRows(facts.successors); uniqueRows(facts.defs); uniqueRows(facts.uses);
    if(graph) { uniqueRows(users); csr(users,graph->offsets,graph->edges); }
    return facts;
}
static Graph graphOnly(llvm::Function &f,const Index &ix) {
    Rows users(ix.nodes.size());
    for(auto &b:f)for(auto &i:b)if(!llvm::isa<llvm::DbgInfoIntrinsic>(i))
        for(auto &operand:i.operands()) {
            auto node=ix.ids.find(operand.get());
            if(node!=ix.ids.end())users[node->second].push_back(ix.ids.lookup(&i));
        }
    uniqueRows(users); Graph graph; csr(users,graph.offsets,graph.edges); return graph;
}
static IDs slice(llvm::Function &f,const Index &ix,unsigned arg,const Graph *graph) {
    IDs queue{ix.ids.lookup(f.getArg(arg))}; std::vector<uint8_t> seen(ix.nodes.size()); seen[queue[0]]=1;
    auto visit=[&](uint32_t id) { if(!seen[id]) { seen[id]=1; queue.push_back(id); } };
    for(size_t pos=0;pos<queue.size();++pos) {
        auto id=queue[pos];
        if(graph) { for(auto k=graph->offsets[id];k<graph->offsets[id+1];++k)visit(graph->edges[k]); }
        else for(auto *user:ix.nodes[id]->users()) {
            const auto *i=llvm::dyn_cast<llvm::Instruction>(user);
            if(!i || i->getFunction()!=&f || llvm::isa<llvm::DbgInfoIntrinsic>(i))continue;
            visit(ix.ids.lookup(i));
        }
    }
    std::sort(queue.begin(),queue.end()); return queue;
}
// Oracle scans operands to a fixed point; it uses neither use lists nor CSR.
static IDs sliceOracle(llvm::Function &f,unsigned arg) {
    Index ix(f); std::set<const llvm::Value*> reached{f.getArg(arg)};
    bool changed=true;
    while(changed) {
        changed=false;
        for(auto &b:f)for(auto &i:b) {
            if(llvm::isa<llvm::DbgInfoIntrinsic>(i) || reached.count(&i))continue;
            for(auto &operand:i.operands())if(reached.count(operand.get())) {
                reached.insert(&i); changed=true; break;
            }
        }
    }
    IDs result; for(uint32_t id=0;id<ix.nodes.size();++id)if(reached.count(ix.nodes[id]))result.push_back(id);
    return result;
}
struct Counters {
    uint64_t productions=0, solves=0, graphs=0, slice_misses=0, live_hits=0, slice_hits=0;
    llvm::json::Object json() const { return llvm::json::Object{{"productions",int64_t(productions)},{"solves",int64_t(solves)},
        {"graphs",int64_t(graphs)},{"slice_misses",int64_t(slice_misses)},
        {"live_hits",int64_t(live_hits)},{"slice_hits",int64_t(slice_hits)}}; }
};
struct Record {
    Index index; Graph graph; bool has_graph=false;
    std::shared_ptr<const Words> live;
    std::map<unsigned,std::shared_ptr<const IDs>> slices;
    explicit Record(llvm::Function &f):index(f){}
};
struct Session {
    Mode mode; Kernel kernel; uint64_t generation=1; Counters counts;
    std::map<llvm::Function*,std::unique_ptr<Record>> records;
    Session(Mode m,Kernel k):mode(m),kernel(k){}
    void admit(uint64_t token) const { if(token!=generation)throw std::runtime_error("stale generation"); }
    void invalidate(llvm::Function *f=nullptr) {
        ++generation; if(f)records.erase(f); else records.clear();
    }
    Record &record(llvm::Function &f) {
        auto &r=records[&f]; if(!r)r=std::make_unique<Record>(f); return *r;
    }
    std::shared_ptr<const Words> liveness(llvm::Function &f,uint64_t token) {
        admit(token); auto &r=record(f);
        if(r.live) { ++counts.live_hits; return r.live; }
        bool build_graph=mode==Eager && !r.has_graph;
        auto facts=produce(f,r.index,build_graph?&r.graph:nullptr); ++counts.productions;
        if(build_graph) { r.has_graph=true; ++counts.graphs; }
        Prepared prepared(facts,0); prepared.solve(0,kernel); ++counts.solves;
        r.live=std::make_shared<const Words>(std::move(prepared.output)); return r.live;
    }
    std::shared_ptr<const IDs> query(llvm::Function &f,unsigned arg,uint64_t token) {
        admit(token); if(arg>=f.arg_size())throw std::runtime_error("invalid argument");
        auto &r=record(f); auto found=r.slices.find(arg);
        if(found!=r.slices.end()) { ++counts.slice_hits; return found->second; }
        if(mode!=Native && !r.has_graph) { r.graph=graphOnly(f,r.index); r.has_graph=true; ++counts.graphs; }
        ++counts.slice_misses;
        auto result=std::make_shared<const IDs>(slice(f,r.index,arg,mode==Native?nullptr:&r.graph));
        r.slices[arg]=result; return result;
    }
    // Logical element bytes only; excludes maps, allocation overhead/capacity,
    // and resident LLVM IR. These omissions are explicit in every report.
    uint64_t payload() const {
        uint64_t bytes=0;
        for(auto &[f,r]:records) {
            bytes+=r->index.nodes.size()*sizeof(void*);
            bytes+=(r->index.ids.size()+r->index.ssa.size()+r->index.blocks.size())*(sizeof(void*)+4);
            bytes+=4ull*(r->graph.offsets.size()+r->graph.edges.size());
            if(r->live)bytes+=8ull*r->live->size();
            for(auto &[arg,result]:r->slices)bytes+=4ull*result->size();
        }
        return bytes;
    }
};
struct Plan { std::string target; unsigned arg; std::vector<std::string> explore; };
static Plan plan(llvm::Module &m) {
    std::vector<llvm::Function*> functions;
    for(auto &f:m)if(!f.isDeclaration() && !f.arg_empty())functions.push_back(&f);
    std::stable_sort(functions.begin(),functions.end(),[](auto *a,auto *b){return a->getInstructionCount()>b->getInstructionCount();});
    Plan p;
    for(auto *f:functions) {
        if(p.explore.size()<3)p.explore.push_back(f->getName().str());
        if(!p.target.empty())continue;
        for(auto &arg:f->args())if(arg.getType()->isIntegerTy()) {
            bool used=false;
            for(auto *user:arg.users())if(auto *i=llvm::dyn_cast<llvm::Instruction>(user))
                used|=!llvm::isa<llvm::PHINode>(i) && !llvm::isa<llvm::DbgInfoIntrinsic>(i);
            if(used) { p.target=f->getName().str(); p.arg=arg.getArgNo(); break; }
        }
    }
    if(p.target.empty())throw std::runtime_error("trace needs an integer parameter with a non-PHI use");
    if(m.getFunction("gaia_trace_added"))throw std::runtime_error("reserved function already exists");
    return p;
}
static void mutate(llvm::Module &m,const Plan &p,unsigned event,Session *session) {
    auto *f=m.getFunction(p.target); auto *arg=f->getArg(p.arg);
    if(event>=3 && event<=5) {
        if(session)session->invalidate(f);
        if(event==3) {
            for(auto &b:*f)for(auto &i:b)if(!llvm::isa<llvm::PHINode>(i) && !llvm::isa<llvm::DbgInfoIntrinsic>(i))
                for(auto &op:i.operands())if(op.get()==arg) { op.set(llvm::ConstantInt::get(arg->getType(),0)); return; }
            throw std::runtime_error("missing operand edit");
        }
        if(event==4)llvm::BinaryOperator::CreateAdd(arg,llvm::ConstantInt::get(arg->getType(),0),"gaia.renumber",f->getEntryBlock().getFirstInsertionPt());
        if(event==5)f->getEntryBlock().splitBasicBlock(f->getEntryBlock().getTerminator(),"gaia.split");
    } else if(event==6) {
        auto *ty=llvm::Type::getInt64Ty(m.getContext());
        auto *added=llvm::Function::Create(llvm::FunctionType::get(ty,{ty},false),llvm::GlobalValue::InternalLinkage,"gaia_trace_added",m);
        auto *b=llvm::BasicBlock::Create(m.getContext(),"entry",added);
        auto *value=llvm::BinaryOperator::CreateXor(added->getArg(0),llvm::ConstantInt::get(ty,3),"value",b);
        llvm::ReturnInst::Create(m.getContext(),value,b);
        if(session) { ++session->generation; }
    } else if(event==7) {
        auto *added=m.getFunction("gaia_trace_added");
        if(!added || !added->use_empty())throw std::runtime_error("unsafe removal");
        if(session)session->invalidate(added);
        added->eraseFromParent();
    } else if(event==8 && session)session->invalidate();
}
using Query = std::pair<std::string,unsigned>;
static std::vector<Query> queries(llvm::Module &m,const Plan &p,unsigned event) {
    std::vector<Query> result{{p.target,p.arg}};
    if(event)for(auto &name:p.explore) {
        auto *f=m.getFunction(name);
        for(unsigned a=0;a<std::min<size_t>(8,f->arg_size());++a)
            if(name!=p.target || a!=p.arg)result.emplace_back(name,a);
    }
    if(event==6)result.emplace_back("gaia_trace_added",0);
    return result;
}
struct Expected { std::map<std::string,Words> live; std::map<Query,IDs> slices; };
static std::vector<Expected> reference(llvm::Module &original,const Plan &p) {
    auto m=llvm::CloneModule(original); std::vector<Expected> result;
    for(unsigned event=0;event<std::size(events);++event) {
        mutate(*m,p,event,nullptr);
        if(llvm::verifyModule(*m,&llvm::errs()))throw std::runtime_error("invalid reference edit");
        Expected expected;
        for(auto &f:extract(*m)) {
            auto live=oracle(f); uint32_t words=(f.values+63)/64; Words bits(f.successors.size()*words);
            for(size_t b=0;b<live.size();++b)for(auto v:live[b])bits[b*words+v/64]|=1ull<<(v%64);
            expected.live[f.name]=std::move(bits);
        }
        for(auto &q:queries(*m,p,event))expected.slices[q]=sliceOracle(*m->getFunction(q.first),q.second);
        result.push_back(std::move(expected));
    }
    return result;
}
static uint64_t hashWords(uint64_t h,const Words &words) { for(auto w:words)h=(h^w)*1099511628211ull; return h; }
struct Response {
    std::vector<std::pair<std::string,std::shared_ptr<const Words>>> live;
    std::vector<std::pair<Query,std::shared_ptr<const IDs>>> slices;
};
static llvm::json::Array trace(llvm::Module &original,const Plan &p,const std::vector<Expected> &expected,Mode mode,Kernel kernel,unsigned block) {
    auto start=Clock::now(); auto m=llvm::CloneModule(original); auto clone_ns=elapsed(start);
    Session session(mode,kernel); llvm::json::Array rows; uint64_t sink=0;
    std::shared_ptr<const Words> held; Words held_copy;
    for(unsigned event=0;event<std::size(events);++event) {
        const auto before=session.counts; const auto old_generation=session.generation;
        start=Clock::now();
        mutate(*m,p,event,&session);
        auto mutation_ns=elapsed(start); auto phase=Clock::now();
        Response response;
        for(auto &f:*m)if(!f.isDeclaration()) {
            auto live=session.liveness(f,session.generation); sink=hashWords(sink,*live);
            response.live.emplace_back(f.getName().str(),std::move(live));
        }
        auto liveness_ns=elapsed(phase); phase=Clock::now();
        for(auto &q:queries(*m,p,event)) {
            auto result=session.query(*m->getFunction(q.first),q.second,session.generation);
            for(auto id:*result)sink=(sink^id)*1099511628211ull;
            response.slices.emplace_back(q,std::move(result));
        }
        auto queries_ns=elapsed(phase);
        auto ns=elapsed(start);
        // Exact checking and LLVM verification are outside request clocks.
        if(llvm::verifyModule(*m,&llvm::errs()))throw std::runtime_error("invalid measured edit");
        if(response.live.size()!=expected[event].live.size() || response.slices.size()!=expected[event].slices.size())
            throw std::runtime_error("membership mismatch");
        for(auto &[name,words]:response.live)if(*words!=expected[event].live.at(name))throw std::runtime_error("live mismatch "+name);
        for(auto &[q,ids]:response.slices)if(*ids!=expected[event].slices.at(q))throw std::runtime_error("slice mismatch "+q.first);
        if(event==0) { held=session.liveness(*m->getFunction(p.target),session.generation); --session.counts.live_hits; held_copy=*held; }
        if(*held!=held_copy)throw std::runtime_error("retained immutable result mutated");
        if(old_generation!=session.generation) {
            bool rejected=false;
            try { session.query(*m->getFunction(p.target),p.arg,old_generation); } catch(const std::runtime_error &) { rejected=true; }
            if(!rejected)throw std::runtime_error("stale request accepted");
        }
        bool rejected=false;
        auto *target=m->getFunction(p.target);
        try { session.query(*target,target->arg_size(),session.generation); } catch(const std::runtime_error &) { rejected=true; }
        if(!rejected)throw std::runtime_error("out of range query accepted");
        if((event==2 || event==9) && (session.counts.productions!=before.productions || session.counts.slice_misses!=before.slice_misses))
            throw std::runtime_error("unchanged request recomputed");
        auto delta=session.counts;
        delta.productions-=before.productions; delta.solves-=before.solves; delta.graphs-=before.graphs;
        delta.slice_misses-=before.slice_misses; delta.live_hits-=before.live_hits; delta.slice_hits-=before.slice_hits;
        rows.push_back(llvm::json::Object{{"block",block},{"mode",names[mode]},{"event",events[event]},
            {"ns",int64_t(ns)},{"clone_ns_excluded",int64_t(clone_ns)},{"generation",int64_t(session.generation)},
            {"mutation_ns",int64_t(mutation_ns)},{"liveness_ns",int64_t(liveness_ns)},{"queries_ns",int64_t(queries_ns)},
            {"payload_bytes",int64_t(session.payload())},{"counts",delta.json()},
            {"functions",int64_t(response.live.size())},{"queries",int64_t(response.slices.size())},{"digest",std::to_string(sink)}});
    }
    return rows;
}
}
int main(int argc,char **argv) {
    try {
        if(argc!=5 && argc!=6)throw std::runtime_error("usage: retained-host IR LIBRARY BLOCKS SEED [--dump-slices]");
        if(argc==6 && std::string(argv[5])!="--dump-slices")throw std::runtime_error("invalid flag");
        unsigned blocks=std::stoul(argv[3]), seed=std::stoul(argv[4]);
        if(!blocks || blocks>100)throw std::runtime_error("invalid block count");
        void *lib=dlopen(argv[2],RTLD_NOW|RTLD_LOCAL); if(!lib)throw std::runtime_error(dlerror());
        auto kernel=reinterpret_cast<Kernel>(dlsym(lib,"gaia_liveness")); if(!kernel)throw std::runtime_error("missing kernel");
        llvm::LLVMContext context; llvm::SMDiagnostic diagnostic;
        auto module=llvm::parseIRFile(argv[1],diagnostic,context);
        if(!module) { diagnostic.print(argv[0],llvm::errs()); return 2; }
        if(llvm::verifyModule(*module,&llvm::errs()))throw std::runtime_error("invalid input");
        auto p=retained::plan(*module); auto expected=retained::reference(*module,p);
        llvm::json::Array observations, exploration; std::mt19937 rng(seed);
        for(auto &name:p.explore)exploration.push_back(name);
        for(unsigned block=0;block<blocks;++block) {
            std::vector<unsigned> order{0,1,2}; std::shuffle(order.begin(),order.end(),rng);
            for(auto mode:order)for(auto &row:retained::trace(*module,p,expected,retained::Mode(mode),kernel,block))observations.push_back(std::move(row));
        }
        llvm::json::Object result{{"schema_version",1},{"target",p.target},{"target_argument",p.arg},{"explore",std::move(exploration)},
            {"blocks",blocks},{"seed",seed},{"exact_all_outputs",true},{"stale_requests_rejected",true},
            {"immutable_old_results",true},{"unchanged_no_recomputation",true},{"observations",std::move(observations)}};
        if(argc==6) {
            llvm::json::Array slices;
            for(unsigned mode=0;mode<3;++mode) {
                retained::Session session(retained::Mode(mode),kernel);
                retained::Session query_first(retained::Mode(mode),kernel);
                for(auto &f:*module)if(!f.isDeclaration()) {
                    for(unsigned arg=0;arg<f.arg_size();++arg)query_first.query(f,arg,query_first.generation);
                    query_first.liveness(f,query_first.generation);
                    session.liveness(f,session.generation);
                    for(unsigned arg=0;arg<f.arg_size();++arg) {
                        auto ids=session.query(f,arg,session.generation);
                        if(*ids!=retained::sliceOracle(f,arg))throw std::runtime_error("fixture slice mismatch");
                        if(*ids!=*query_first.query(f,arg,query_first.generation))throw std::runtime_error("query-first mismatch");
                        llvm::json::Array values; for(auto id:*ids)values.push_back(id);
                        slices.push_back(llvm::json::Object{{"mode",retained::names[mode]},
                            {"function",f.getName().str()},{"argument",arg},{"nodes",std::move(values)}});
                    }
                }
            }
            result["fixture_slices"]=std::move(slices);
        }
        llvm::outs()<<llvm::formatv("{0:2}\n",llvm::json::Value(std::move(result)));
        dlclose(lib);
    } catch(const std::exception &e) { std::cerr<<e.what()<<'\n'; return 1; }
}
