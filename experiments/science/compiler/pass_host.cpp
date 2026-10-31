// Experimental Clang 22 single-frontend host; no stable AST/IR ABI is implied.
#include <clang/AST/ASTContext.h>
#include <clang/AST/Decl.h>
#include <clang/Basic/TargetInfo.h>
#include <clang/Basic/DiagnosticFrontend.h>
#include <clang/CodeGen/BackendUtil.h>
#include <clang/CodeGen/ModuleBuilder.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/MultiplexConsumer.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/DiagnosticInfo.h>
#include <llvm/IR/DiagnosticPrinter.h>
#include <llvm/IR/Dominators.h>
#include <llvm/Analysis/LoopInfo.h>
#include <llvm/Analysis/PostDominators.h>
#include <llvm/Support/JSON.h>
#include <llvm/Support/SHA256.h>
#include <llvm/Support/TargetSelect.h>
#include <llvm/Support/raw_ostream.h>
#include <llvm/Support/VirtualFileSystem.h>
#include <llvm/Support/MemoryBuffer.h>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <vector>
#include <functional>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
using Clock=std::chrono::steady_clock;
static double seconds(Clock::time_point start){return std::chrono::duration<double>(Clock::now()-start).count();}
static std::string hash(llvm::StringRef s){auto b=llvm::SHA256::hash(llvm::arrayRefFromStringRef(s));const char*h="0123456789abcdef";std::string r;for(auto c:b){r+=h[c>>4];r+=h[c&15];}return r;}
static std::string read(const std::string&p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
static void write(const std::string&p,const std::string&b){std::ofstream f(p,std::ios::binary);f.write(b.data(),b.size());if(!f)throw std::runtime_error("output write failed");}
struct Entry{std::string key,object;};
struct SourceFS:llvm::vfs::ProxyFileSystem{
 std::string root;llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> memory;
 SourceFS(std::string r,llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> m):ProxyFileSystem(llvm::vfs::getRealFileSystem()),root(std::move(r)),memory(m){}
 std::string absolute(const llvm::Twine&p){return std::filesystem::absolute(p.str()).lexically_normal().string();}
 llvm::vfs::FileSystem&select(const std::string&p){return p==root||p.rfind(root+"/",0)==0?*memory:getUnderlyingFS();}
 llvm::ErrorOr<llvm::vfs::Status>status(const llvm::Twine&p)override{auto a=absolute(p);return select(a).status(a);}
 bool exists(const llvm::Twine&p)override{auto a=absolute(p);return select(a).exists(a);}
 llvm::ErrorOr<std::unique_ptr<llvm::vfs::File>>openFileForRead(const llvm::Twine&p)override{auto a=absolute(p);return select(a).openFileForRead(a);}
 llvm::vfs::directory_iterator dir_begin(const llvm::Twine&p,std::error_code&e)override{auto a=absolute(p);return select(a).dir_begin(a,e);}
 std::error_code getRealPath(const llvm::Twine&p,llvm::SmallVectorImpl<char>&out)override{auto a=absolute(p);return select(a).getRealPath(a,out);}
 std::error_code isLocal(const llvm::Twine&p,bool&r)override{auto a=absolute(p);return select(a).isLocal(a,r);}
};
struct State{
 std::map<std::string,Entry> cache; std::string context,output,key,mode,analysis; bool hit=false,store=false;double frontend=0,screen=0,backend=0,analysis_seconds=0;size_t ir_bytes=0;uint64_t analysis_count=0,backend_diagnostics=0;Clock::time_point start;
 std::map<std::string,std::shared_ptr<std::string>> source_files;std::string source_root;uint64_t generation=0;llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> filesystem;
 std::string pipeline="off",dom_digest,post_digest;bool speculate=false,canceled=false;uint64_t dom=0,loops=0,postdom=0;double fork_seconds=0,children_cpu=0;
};
#include "process_passes.inc"
// Detached records avoid concurrent access to mutable/lazy Clang AST internals.
static uint64_t analyze(const std::vector<std::string>&names){uint64_t count=0;for(const auto&name:names){auto h=hash(name);count+=h[0]=='0';}return count;}
struct OnlyAnalysis:clang::ASTConsumer{
 State&s;OnlyAnalysis(State&state):s(state){}
 void HandleTranslationUnit(clang::ASTContext&ast)override{
  s.frontend=seconds(s.start);auto start=Clock::now();std::vector<std::string>names;for(auto*d:ast.getTranslationUnitDecl()->decls())if(auto*n=llvm::dyn_cast<clang::NamedDecl>(d))names.push_back(n->getQualifiedNameAsString());s.analysis_count=analyze(names);s.analysis_seconds=seconds(start);
 }
};
struct BackendDiagnostics{clang::CompilerInstance&ci;State&s;};
static void backendDiagnostic(const llvm::DiagnosticInfo*info,void*opaque){
 if(info->getSeverity()==llvm::DS_Remark)return; // Optimization remarks are outside this prototype's supported request contract.
 auto&d=*static_cast<BackendDiagnostics*>(opaque);std::string text;llvm::raw_string_ostream stream(text);llvm::DiagnosticPrinterRawOStream printer(stream);info->print(printer);stream.flush();++d.s.backend_diagnostics;
 auto level=info->getSeverity()==llvm::DS_Error?clang::DiagnosticsEngine::Error:info->getSeverity()==llvm::DS_Warning?clang::DiagnosticsEngine::Warning:clang::DiagnosticsEngine::Note;
 auto id=d.ci.getDiagnostics().getCustomDiagID(level,"backend: %0");d.ci.getDiagnostics().Report(id)<<text;
}
static void emit_current_backend(clang::CompilerInstance&ci,clang::ASTContext&ast,llvm::Module&module,State&s,const std::string&output){
 ci.getFrontendOpts().OutputFile=output;
 // The speculative path is already private staging. A second hidden Clang
 // temporary would survive termination before clearOutputFiles can run.
 auto out=s.speculate?ci.createOutputFile(output,true,false,false):ci.createDefaultOutputFile(true,ci.getFrontendOpts().Inputs[0].getFile(),"o");if(!out)throw std::runtime_error("cannot create output");
 BackendDiagnostics diagnostics{ci,s};auto previous=module.getContext().getDiagnosticHandler();auto handler=std::make_unique<llvm::DiagnosticHandler>(&diagnostics);handler->DiagHandlerCallback=backendDiagnostic;module.getContext().setDiagnosticHandler(std::move(handler),true);
 clang::emitBackendOutput(ci,ci.getCodeGenOpts(),ast.getTargetInfo().getDataLayoutString(),&module,clang::Backend_EmitObj,ci.getVirtualFileSystemPtr(),std::move(out));module.getContext().setDiagnosticHandler(std::move(previous));
}
struct Finish:clang::ASTConsumer{
 clang::CompilerInstance&ci;clang::CodeGenerator&gen;State&s;
 Finish(clang::CompilerInstance&c,clang::CodeGenerator&g,State&state):ci(c),gen(g),s(state){}
 void HandleTranslationUnit(clang::ASTContext&ast)override{
  s.frontend=seconds(s.start);auto*m=gen.GetModule();if(!m||ci.getDiagnostics().hasErrorOccurred())return;
  StagingFile staging;Child dom_child,post_child,backend_child;
  if(s.pipeline=="serial"){
   auto counts=dominators(*m);auto post=postdominators(*m);s.dom=counts.first;s.loops=counts.second;s.postdom=post.first;s.dom_digest=counts.digest;s.post_digest=post.digest;
  }else if(s.pipeline=="parallel"){
   auto start=Clock::now();dom_child.start([&]{auto c=dominators(*m);return json_text(llvm::json::Object{{"dom",(int64_t)c.first},{"loops",(int64_t)c.second},{"digest",c.digest}});});
   post_child.start([&]{auto p=postdominators(*m);return json_text(llvm::json::Object{{"postdom",(int64_t)p.first},{"digest",p.digest}});});s.fork_seconds+=seconds(start);
  }
  std::string scratch;std::unique_ptr<FILE,decltype(&fclose)> child_errors(nullptr,fclose);
  if(s.speculate){
   staging.create(s.output);scratch=staging.path;
   child_errors.reset(tmpfile());if(!child_errors)throw std::runtime_error("diagnostic staging failed");auto begin=Clock::now();
   backend_child.start([&]{auto begin=Clock::now();emit_current_backend(ci,ast,*m,s,scratch);ci.clearOutputFiles(ci.getDiagnostics().hasErrorOccurred());return json_text(llvm::json::Object{{"ok",!ci.getDiagnostics().hasErrorOccurred()},{"seconds",seconds(begin)},{"diagnostics",(int64_t)s.backend_diagnostics}});},fileno(child_errors.get()));s.fork_seconds+=seconds(begin);
  }
  std::vector<std::string> names;
  if(s.analysis!="off")for(auto*d:ast.getTranslationUnitDecl()->decls())if(auto*n=llvm::dyn_cast<clang::NamedDecl>(d))names.push_back(n->getQualifiedNameAsString());
  auto astart=Clock::now();std::future<uint64_t> future;
  if(s.analysis=="parallel")future=std::async(std::launch::async,[names=std::move(names)]{return analyze(names);});
  else if(s.analysis=="serial")s.analysis_count=analyze(names);
  if(s.analysis=="serial")s.analysis_seconds=seconds(astart);
  auto screen=Clock::now();
  if(s.mode=="ir"){
   std::string ir;llvm::raw_string_ostream stream(ir);m->print(stream,nullptr);stream.flush();s.ir_bytes=ir.size();s.key=hash(ir);
   auto found=s.cache.find(s.context);
   s.hit=found!=s.cache.end()&&found->second.key==s.key;
  }
  s.screen=seconds(screen);auto backend=Clock::now();
  if(s.hit){
   if(s.speculate){backend_child.finish(true);s.canceled=true;s.children_cpu+=backend_child.cpu();}
   write(s.output,s.cache.at(s.context).object);
  }
  else if(s.speculate){
   auto data=backend_child.finish();s.children_cpu+=backend_child.cpu();auto parsed=llvm::json::parse(data);auto*row=parsed?parsed->getAsObject():nullptr;
   if(!backend_child.success()||!row||!row->getBoolean("ok").value_or(false)){
    auto id=ci.getDiagnostics().getCustomDiagID(clang::DiagnosticsEngine::Error,"speculative backend failed");ci.getDiagnostics().Report(id);
   }else if(std::rename(scratch.c_str(),s.output.c_str())!=0)throw std::runtime_error("speculative publication failed");
   if(row){s.backend_diagnostics=(uint64_t)row->getInteger("diagnostics").value_or(0);}
   std::cerr<<file_text(child_errors.get());
  }
  else {
   emit_current_backend(ci,ast,*m,s,s.output);
  }
  s.backend=seconds(backend);
  if(s.pipeline=="parallel"){
   auto left=dom_child.finish();auto right=post_child.finish();s.children_cpu+=dom_child.cpu()+post_child.cpu();
   if(!dom_child.success()||!post_child.success())throw std::runtime_error("analysis child failed");
   auto l=llvm::json::parse(left),r=llvm::json::parse(right);if(!l||!r||!l->getAsObject()||!r->getAsObject())throw std::runtime_error("analysis response");
   s.dom=l->getAsObject()->getInteger("dom").value_or(-1);s.loops=l->getAsObject()->getInteger("loops").value_or(-1);s.postdom=r->getAsObject()->getInteger("postdom").value_or(-1);s.dom_digest=l->getAsObject()->getString("digest").value_or("").str();s.post_digest=r->getAsObject()->getString("digest").value_or("").str();
  }
  if(future.valid()){s.analysis_count=future.get();s.analysis_seconds=seconds(astart);}
 }
};
struct Action:clang::ASTFrontendAction{
 State&s;llvm::LLVMContext context;Action(State&state):s(state){}
 bool PrepareToExecuteAction(clang::CompilerInstance&ci)override{ci.getFrontendOpts().DisableFree=false;ci.getCodeGenOpts().DisableFree=false;return true;}
 std::unique_ptr<clang::ASTConsumer>CreateASTConsumer(clang::CompilerInstance&ci,llvm::StringRef file)override{
  if(s.mode=="analysis")return std::make_unique<OnlyAnalysis>(s);
  context.setDefaultTargetCPU(ci.getTargetOpts().CPU);context.setDefaultTargetFeatures(llvm::join(ci.getTargetOpts().Features,","));
  auto gen=clang::CreateLLVMCodeGen(ci,file,context);auto*ptr=gen.get();std::vector<std::unique_ptr<clang::ASTConsumer>> consumers;consumers.push_back(std::move(gen));consumers.push_back(std::make_unique<Finish>(ci,*ptr,s));return std::make_unique<clang::MultiplexConsumer>(std::move(consumers));
 }
};
int main(){
 llvm::InitializeNativeTarget();llvm::InitializeNativeTargetAsmPrinter();llvm::InitializeNativeTargetAsmParser();State s;
 std::string line;while(std::getline(std::cin,line)){
  auto start=Clock::now();s.hit=false;s.frontend=s.screen=s.backend=s.analysis_seconds=0;s.ir_bytes=s.analysis_count=s.backend_diagnostics=0;
  s.dom=s.loops=s.postdom=0;s.children_cpu=s.fork_seconds=0;s.canceled=false;s.dom_digest.clear();s.post_digest.clear();
  try{
   if(line.size()>4*1024*1024)throw std::runtime_error("request bound");auto parsed=llvm::json::parse(line);if(!parsed)throw std::runtime_error("JSON parse");auto*obj=parsed->getAsObject();if(!obj)throw std::runtime_error("request object");
   if(auto*edits=obj->getObject("edits")){
    auto root=obj->getString("source_root");if(!root||!std::filesystem::path(root->str()).is_absolute())throw std::runtime_error("source root");
    if(!s.source_root.empty()&&s.source_root!=root->str())throw std::runtime_error("source root changed");
    if(auto expected=obj->getInteger("expected_generation");expected&&*expected!=(int64_t)s.generation)throw std::runtime_error("generation conflict");
    auto next=s.source_files;size_t total=0;for(const auto&pair:*edits){std::string name=pair.first.str();if(name.rfind(root->str()+"/",0)!=0||std::filesystem::path(name).lexically_normal().string()!=name)throw std::runtime_error("source path");if(pair.second.getAsNull())next.erase(name);else{auto b=pair.second.getAsString();if(!b)throw std::runtime_error("source body");next[name]=std::make_shared<std::string>(b->str());}}
    for(const auto&pair:next)total+=pair.second->size();if(next.size()>10000||total>64*1024*1024)throw std::runtime_error("source collection bound");
    llvm::IntrusiveRefCntPtr<llvm::vfs::InMemoryFileSystem>mem=new llvm::vfs::InMemoryFileSystem;
    for(const auto&pair:next)if(!mem->addFile(pair.first,0,llvm::MemoryBuffer::getMemBuffer(*pair.second,pair.first,true)))throw std::runtime_error("source add");
    s.filesystem=new SourceFS(root->str(),mem);s.source_files=std::move(next);s.source_root=root->str();++s.generation;
    llvm::json::Object response{{"ok",true},{"generation",(int64_t)s.generation},{"files",(int64_t)s.source_files.size()},{"bytes",(int64_t)total},{"seconds",seconds(start)}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;continue;
   }
   if(auto path=obj->getString("inspect")){auto found=s.source_files.find(path->str());llvm::json::Object response{{"ok",true},{"generation",(int64_t)s.generation},{"present",found!=s.source_files.end()}};if(found!=s.source_files.end())response["sha256"]=hash(*found->second);std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;continue;}
   auto cwd=obj->getString("cwd"),output=obj->getString("output"),mode=obj->getString("mode"),ctx=obj->getString("context"),analysis=obj->getString("analysis");auto*args=obj->getArray("args");if(!cwd||!output||!mode||!ctx||!args||args->size()>4096)throw std::runtime_error("request fields");
   if(auto expected=obj->getInteger("generation");expected&&*expected!=(int64_t)s.generation)throw std::runtime_error("stale compilation generation");
   s.mode=mode->str();s.context=ctx->str();s.output=output->str();s.analysis=analysis?analysis->str():"off";s.store=obj->getBoolean("store").value_or(false);if(s.mode!="ir"&&s.mode!="native"&&s.mode!="analysis")throw std::runtime_error("mode");if(s.analysis!="off"&&s.analysis!="serial"&&s.analysis!="parallel")throw std::runtime_error("analysis mode");
   s.pipeline=obj->getString("pipeline").value_or("off").str();s.speculate=obj->getBoolean("speculate").value_or(false);
   if(s.pipeline!="off"&&s.pipeline!="serial"&&s.pipeline!="parallel")throw std::runtime_error("pipeline mode");
   if((s.pipeline!="off"||s.speculate)&&s.analysis!="off")throw std::runtime_error("forked passes require detached-name analysis off");
   std::vector<std::string> command;for(auto&a:*args){auto str=a.getAsString();if(!str)throw std::runtime_error("argument string");if(str->starts_with("-R"))throw std::runtime_error("optimization remarks unsupported");command.push_back(str->str());}
   if(s.pipeline!="off"||s.speculate)require_object_only(command);
   std::string command_key=cwd->str();bool output_seen=false;
   for(size_t i=0;i<command.size();++i){if(command[i]=="-o"&&i+1<command.size()){if(command[++i]!=s.output)throw std::runtime_error("output argument mismatch");output_seen=true;continue;}command_key+=std::to_string(command[i].size())+":"+command[i];}
   if(!output_seen)throw std::runtime_error("explicit output required");s.context+=hash(command_key);
   std::filesystem::current_path(cwd->str());bool logical=obj->getBoolean("logical").value_or(false);if(logical&&!s.filesystem)throw std::runtime_error("missing source generation");llvm::IntrusiveRefCntPtr<clang::FileManager>files=new clang::FileManager(clang::FileSystemOptions{},logical?s.filesystem:llvm::vfs::getRealFileSystem());s.start=Clock::now();
   clang::tooling::ToolInvocation invocation(command,std::make_unique<Action>(s),files.get());bool ok=invocation.run();
   if(ok&&!s.hit&&s.mode=="ir"&&s.store&&s.backend_diagnostics==0){if(s.cache.size()>64)s.cache.clear();auto bytes=read(s.output);if(bytes.empty()||bytes.size()>32*1024*1024)throw std::runtime_error("object bound");s.cache[s.context]={s.key,std::move(bytes)};}
   llvm::json::Object response{{"ok",ok},{"hit",s.hit},{"generation",(int64_t)s.generation},{"frontend_seconds",s.frontend},{"screen_seconds",s.screen},{"backend_seconds",s.backend},{"analysis_seconds",s.analysis_seconds},{"analysis_count",(int64_t)s.analysis_count},{"backend_diagnostics",(int64_t)s.backend_diagnostics},{"ir_bytes",(int64_t)s.ir_bytes},{"seconds",seconds(start)},{"dom",(int64_t)s.dom},{"loops",(int64_t)s.loops},{"postdom",(int64_t)s.postdom},{"dom_sha256",s.dom_digest},{"postdom_sha256",s.post_digest},{"fork_seconds",s.fork_seconds},{"children_cpu_seconds",s.children_cpu},{"speculation_canceled",s.canceled}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;
  }catch(const std::exception&e){llvm::json::Object response{{"ok",false},{"error",e.what()}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;}
 }
 return 0;
}
