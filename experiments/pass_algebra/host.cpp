// LLVM extraction and measurement adapter; all three native kernels are Odin.
#include <llvm/ADT/DenseMap.h>
#include <llvm/IR/CFG.h>
#include <llvm/IR/Instructions.h>
#include <llvm/IR/IntrinsicInst.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/Verifier.h>
#include <llvm/IRReader/IRReader.h>
#include <llvm/Support/JSON.h>
#include <llvm/Support/SourceMgr.h>
#include <llvm/Support/raw_ostream.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <dlfcn.h>
#include <iostream>
#include <numeric>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using Clock = std::chrono::steady_clock;
using Rows = std::vector<std::vector<uint32_t>>;
static uint64_t elapsed(Clock::time_point t) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-t).count();
}
struct Input {
    uint32_t blocks, values, words, reserved;
    const uint32_t *succ_offsets, *successors, *pred_offsets, *predecessors;
    const uint64_t *generate, *kill;
    const uint32_t *seed_offsets, *seeds;
};
struct Scratch { uint64_t *output, *alternate; uint32_t *queue; uint8_t *queued; };
using Kernel = uint64_t (*)(uint32_t, const Input*, Scratch*);
struct Facts {
    std::string name;
    uint32_t values = 0, phis = 0, phi_operands = 0;
    Rows successors, defs, uses;
    std::vector<std::string> block_names, value_names;
};
static std::string operandName(const llvm::Value &v) {
    std::string text; llvm::raw_string_ostream out(text); v.printAsOperand(out, false); return text;
}
static void uniqueRows(Rows &rows) {
    for (auto &row: rows) { std::sort(row.begin(),row.end()); row.erase(std::unique(row.begin(),row.end()),row.end()); }
}
static std::vector<Facts> extract(llvm::Module &module, bool include_names=false) {
    std::vector<Facts> result;
    for (auto &function: module) {
        if (function.isDeclaration()) continue;
        Facts f; f.name = function.getName().str();
        llvm::DenseMap<const llvm::BasicBlock*,uint32_t> blocks;
        llvm::DenseMap<const llvm::Value*,uint32_t> values;
        for (auto &block: function) {
            blocks[&block]=blocks.size();
            if(include_names) f.block_names.push_back(operandName(block));
        }
        auto addValue = [&](const llvm::Value &v) {
            values[&v]=values.size();
            if(include_names) f.value_names.push_back(operandName(v));
        };
        for (auto &arg: function.args()) addValue(arg);
        for (auto &block: function) for (auto &inst: block)
            if (!inst.getType()->isVoidTy()) addValue(inst);
        f.values=values.size();
        f.successors.resize(blocks.size()); f.defs.resize(blocks.size()); f.uses.resize(blocks.size());
        for (auto &block: function) {
            const auto b=blocks.lookup(&block);
            for (const auto *successor: llvm::successors(&block)) f.successors[b].push_back(blocks.lookup(successor));
            std::set<uint32_t> defined;
            for (auto &inst: block) {
                if (auto *phi=llvm::dyn_cast<llvm::PHINode>(&inst)) {
                    ++f.phis;
                    for (unsigned i=0;i<phi->getNumIncomingValues();++i) {
                        auto found=values.find(phi->getIncomingValue(i));
                        if (found!=values.end()) {
                            // PHI operands are used on incoming edges. Add to
                            // predecessor seeds only if not defined there.
                            auto *pred=phi->getIncomingBlock(i); const auto *def=llvm::dyn_cast<llvm::Instruction>(found->first);
                            if (!def || def->getParent()!=pred) f.uses[blocks.lookup(pred)].push_back(found->second);
                            ++f.phi_operands;
                        }
                    }
                } else if (!llvm::isa<llvm::DbgInfoIntrinsic>(inst)) {
                    for (const auto &operand: inst.operands()) {
                        auto found=values.find(operand.get());
                        if (found!=values.end() && !defined.count(found->second)) f.uses[b].push_back(found->second);
                    }
                }
                auto found=values.find(&inst);
                if (found!=values.end()) { defined.insert(found->second); f.defs[b].push_back(found->second); }
            }
        }
        uniqueRows(f.successors); uniqueRows(f.defs); uniqueRows(f.uses);
        result.push_back(std::move(f));
    }
    return result;
}

static void csr(const Rows &rows,std::vector<uint32_t> &offsets,std::vector<uint32_t> &ids) {
    offsets.push_back(0);
    for (const auto &row:rows) { ids.insert(ids.end(),row.begin(),row.end()); offsets.push_back(ids.size()); }
}
struct Prepared {
    uint32_t n, values, words;
    std::vector<uint32_t> so, si, po, pi, vo, vi, queue;
    std::vector<uint64_t> gen, kill, output, alternate;
    std::vector<uint8_t> queued;
    Prepared(const Facts &f, unsigned mode): n(f.successors.size()), values(f.values), words((values+63)/64) {
        const uint64_t cells=uint64_t(n)*words;
        if (cells > (128ull<<20)/8) throw std::runtime_error("per-function matrix exceeds 128 MiB bound");
        kill.resize(cells); output.resize(cells);
        if (mode!=1) queue.resize(n);
        for (uint32_t b=0;b<n;++b) for (auto v:f.defs[b]) kill[b*words+v/64]|=1ull<<(v%64);
        if (mode!=1) {
            Rows predecessors(n);
            for (uint32_t b=0;b<n;++b) for (auto s:f.successors[b]) predecessors[s].push_back(b);
            csr(predecessors,po,pi);
        }
        if (mode==2) {
            Rows seeds(values);
            for (uint32_t b=0;b<n;++b) for (auto v:f.uses[b]) seeds[v].push_back(b);
            csr(seeds,vo,vi);
        } else {
            csr(f.successors,so,si); gen.resize(cells);
            for (uint32_t b=0;b<n;++b) for (auto v:f.uses[b]) gen[b*words+v/64]|=1ull<<(v%64);
            alternate.resize(mode==1?cells:words);
            if (mode==0) queued.resize(n);
        }
    }
    uint64_t solve(unsigned mode,Kernel kernel) {
        Input in{n,values,words,0,so.data(),si.data(),po.data(),pi.data(),gen.data(),kill.data(),vo.data(),vi.data()};
        Scratch scratch{output.data(),alternate.data(),queue.data(),queued.data()};
        auto work=kernel(mode,&in,&scratch);
        if (work==UINT64_MAX) throw std::runtime_error("kernel rejected request or failed convergence bound");
        return work;
    }
    uint64_t bytes() const {
        return 4ull*(so.size()+si.size()+po.size()+pi.size()+vo.size()+vi.size()+queue.size())
             +8ull*(gen.size()+kill.size()+output.size()+alternate.size())+queued.size();
    }
};

// Independent ordered-set, synchronous full recomputation. No bit matrices,
// transpose seeds, worklist or native kernel code is used by this oracle.
static std::vector<std::set<uint32_t>> oracle(const Facts &f) {
    std::vector<std::set<uint32_t>> live(f.successors.size());
    bool changed=true;
    while (changed) {
        auto next=live; changed=false;
        for (size_t b=0;b<live.size();++b) {
            std::set<uint32_t> row(f.uses[b].begin(),f.uses[b].end());
            for (auto s:f.successors[b]) for (auto v:live[s])
                if (!std::binary_search(f.defs[b].begin(),f.defs[b].end(),v)) row.insert(v);
            changed|=row!=live[b]; next[b]=std::move(row);
        }
        live=std::move(next);
    }
    return live;
}
static void check(const Facts &f,const Prepared &p,const std::vector<std::set<uint32_t>> &expected) {
    for (size_t b=0;b<expected.size();++b) {
        for (uint32_t v=0;v<f.values;++v)
            if (bool(p.output[b*p.words+v/64]&(1ull<<(v%64)))!=bool(expected[b].count(v)))
                throw std::runtime_error("liveness disagreement in "+f.name);
        if (p.words && f.values%64 && (p.output[b*p.words+p.words-1]>>(f.values%64)))
            throw std::runtime_error("nonzero padding");
    }
}
static uint64_t digest(const std::vector<Prepared> &prepared) {
    uint64_t hash=1469598103934665603ull;
    for (const auto &p:prepared) { hash=(hash^p.n)*1099511628211ull; hash=(hash^p.values)*1099511628211ull;
        for (auto word:p.output) hash=(hash^word)*1099511628211ull; }
    return hash;
}
static llvm::json::Array rowsJSON(const Rows &rows) {
    llvm::json::Array result;
    for (const auto &row:rows) { llvm::json::Array a; for(auto v:row)a.push_back(int64_t(v)); result.push_back(std::move(a)); }
    return result;
}
static llvm::json::Array stringsJSON(const std::vector<std::string> &strings) {
    llvm::json::Array a; for(const auto &s:strings)a.push_back(s); return a;
}
static llvm::json::Object dump(llvm::Module &module,Kernel kernel) {
    llvm::json::Array functions;
    for (const auto &f:extract(module,true)) {
        auto expected=oracle(f); Rows live;
        for (const auto &row:expected) live.emplace_back(row.begin(),row.end());
        for (unsigned mode=0;mode<3;++mode) { Prepared p(f,mode); p.solve(mode,kernel); check(f,p,expected); }
        functions.push_back(llvm::json::Object{{"name",f.name},{"blocks",stringsJSON(f.block_names)},
            {"values",stringsJSON(f.value_names)},{"successors",rowsJSON(f.successors)},
            {"defs",rowsJSON(f.defs)},{"generate",rowsJSON(f.uses)},{"live_in",rowsJSON(live)}});
    }
    return llvm::json::Object{{"functions",std::move(functions)},{"validated",true}};
}
static llvm::json::Object benchmark(llvm::Module &module,Kernel kernel,unsigned blocks,unsigned repetitions) {
    auto start=Clock::now(); auto facts=extract(module); auto extraction_ns=elapsed(start);
    std::vector<std::vector<std::set<uint32_t>>> expected;
    for (const auto &f:facts) expected.push_back(oracle(f));
    llvm::json::Array shape;
    uint64_t live_facts=0;
    for (size_t i=0;i<facts.size();++i) {
        auto &f=facts[i]; uint64_t edges=0, seeds=0, live=0;
        for(auto &r:f.successors)edges+=r.size(); for(auto &r:f.uses)seeds+=r.size();
        for(auto &r:expected[i])live+=r.size(); live_facts+=live;
        shape.push_back(llvm::json::Object{{"name",f.name},{"blocks",int64_t(f.successors.size())},
            {"values",f.values},{"edges",int64_t(edges)},{"seed_facts",int64_t(seeds)},
            {"live_facts",int64_t(live)},{"phis",f.phis},{"phi_operands",f.phi_operands}});
    }
    llvm::json::Array observations, preparation;
    std::vector<std::vector<Prepared>> ready(3);
    uint64_t expected_digest=0;
    for (unsigned mode=0;mode<3;++mode) {
        start=Clock::now(); for (auto &f:facts)ready[mode].emplace_back(f,mode); auto ns=elapsed(start);
        uint64_t memory=0, work=0;
        for(size_t i=0;i<facts.size();++i) { auto &p=ready[mode][i]; work+=p.solve(mode,kernel); memory+=p.bytes(); check(facts[i],p,expected[i]); }
        auto hash=digest(ready[mode]); if(mode && hash!=expected_digest)throw std::runtime_error("digest mismatch"); expected_digest=hash;
        preparation.push_back(llvm::json::Object{{"mode",mode},{"layout_ns",int64_t(ns)},
            {"retained_payload_and_scratch_bytes",int64_t(memory)},{"work_units",int64_t(work)}});
    }
    std::mt19937 rng(4417);
    volatile uint64_t sink=0;
    for(unsigned block=0;block<blocks;++block) {
        // Shuffle both timing boundaries as well as formulations per block.
        std::vector<unsigned> cases{0,1,2,3,4,5}; std::shuffle(cases.begin(),cases.end(),rng);
        for(auto item:cases) {
            unsigned mode=item%3; bool complete=item>=3;
            uint64_t work=0; start=Clock::now();
            for(unsigned rep=0;rep<repetitions;++rep) {
                if(complete) {
                    auto current=extract(module); std::vector<Prepared> operation;
                    for(auto &f:current) { operation.emplace_back(f,mode); work+=operation.back().solve(mode,kernel); }
                    auto hash=digest(operation); sink=sink^hash;
                    if(hash!=expected_digest)throw std::runtime_error("complete result changed");
                } else {
                    for(auto &p:ready[mode])work+=p.solve(mode,kernel);
                    // Opaque dlsym call plus a consumed result defeats dead-code elimination.
                    sink=sink^work;
                }
            }
            auto ns=elapsed(start);
            if(!complete) for(size_t i=0;i<facts.size();++i)check(facts[i],ready[mode][i],expected[i]);
            observations.push_back(llvm::json::Object{{"block",block},{"mode",mode},{"boundary",complete?"resident_ir_to_result":"prepared_kernel"},
                {"repetitions",repetitions},{"ns",int64_t(ns)},{"work_units",int64_t(work)}});
        }
    }
    return llvm::json::Object{{"functions",std::move(shape)},{"initial_extraction_ns",int64_t(extraction_ns)},
        {"preparation",std::move(preparation)},{"observations",std::move(observations)},
        {"oracle_live_facts",int64_t(live_facts)},{"oracle_validated_all_bits",true},
        {"result_digest",std::to_string(expected_digest)},{"sink",std::to_string(sink)}};
}
#ifndef GAIA_LIVENESS_LIBRARY_ONLY
int main(int argc,char **argv) {
    try {
        if(argc!=4 && argc!=6)throw std::runtime_error("usage: host dump|bench IR LIBRARY [BLOCKS REPETITIONS]");
        void *library=dlopen(argv[3],RTLD_NOW|RTLD_LOCAL); if(!library)throw std::runtime_error(dlerror());
        auto kernel=reinterpret_cast<Kernel>(dlsym(library,"gaia_liveness")); if(!kernel)throw std::runtime_error("missing kernel symbol");
        llvm::LLVMContext context; llvm::SMDiagnostic diagnostic; auto start=Clock::now();
        auto module=llvm::parseIRFile(argv[2],diagnostic,context);
        if(!module) { diagnostic.print(argv[0],llvm::errs()); return 2; }
        if(llvm::verifyModule(*module,&llvm::errs()))throw std::runtime_error("invalid LLVM IR");
        auto parse_ns=elapsed(start);
        llvm::json::Object result;
        if(std::string(argv[1])=="dump" && argc==4)result=dump(*module,kernel);
        else if(std::string(argv[1])=="bench" && argc==6) {
            auto blocks=std::stoul(argv[4]), reps=std::stoul(argv[5]);
            if(!blocks || !reps || blocks>1000 || reps>10000)throw std::runtime_error("invalid benchmark counts");
            result=benchmark(*module,kernel,blocks,reps);
        } else throw std::runtime_error("invalid mode/arguments");
        result["parse_and_verify_ns"]=int64_t(parse_ns);
        llvm::outs()<<llvm::formatv("{0:2}\n",llvm::json::Value(std::move(result)));
        dlclose(library); return 0;
} catch(const std::exception &e) { std::cerr<<e.what()<<'\n'; return 1; }
}
#endif
