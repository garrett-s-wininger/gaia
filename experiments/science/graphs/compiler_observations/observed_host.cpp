// Experimental Clang 22 single-frontend host; no stable AST/IR ABI is implied.
#include <clang/AST/ASTContext.h>
#include <clang/AST/Decl.h>
#include <clang/Basic/TargetInfo.h>
#include <clang/Basic/Diagnostic.h>
#include <clang/Basic/DiagnosticFrontend.h>
#include <clang/CodeGen/BackendUtil.h>
#include <clang/CodeGen/ModuleBuilder.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/MultiplexConsumer.h>
#include <clang/Lex/PPCallbacks.h>
#include <clang/Lex/Preprocessor.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/IR/LLVMContext.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/DiagnosticInfo.h>
#include <llvm/IR/DiagnosticPrinter.h>
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
#include <set>
#include <sstream>
#include <string>
#include <vector>
using Clock=std::chrono::steady_clock;
static double seconds(Clock::time_point start){return std::chrono::duration<double>(Clock::now()-start).count();}
static std::string hash(llvm::StringRef s){auto b=llvm::SHA256::hash(llvm::arrayRefFromStringRef(s));const char*h="0123456789abcdef";std::string r;for(auto c:b){r+=h[c>>4];r+=h[c&15];}return r;}
static std::string read(const std::string&p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
static void write(const std::string&p,const std::string&b){std::ofstream f(p,std::ios::binary);f.write(b.data(),b.size());if(!f)throw std::runtime_error("output write failed");}
struct Entry{std::string key,object;};
using SourceBodies=std::map<std::string,std::shared_ptr<std::string>>;
struct Observation{std::string kind,path,value;};
struct Watch{
 const SourceBodies*source=nullptr;std::vector<Observation> records;std::set<std::pair<std::string,std::string>>seen;
 std::string describe(const std::string&kind,const std::string&path)const{
  auto exact=source->find(path);if(exact!=source->end())return "file:"+hash(*exact->second);
  std::string prefix=path+"/";auto first=source->lower_bound(prefix);
  if(first==source->end()||first->first.rfind(prefix,0)!=0)return "absent";
  if(kind!="listing")return "directory";
  std::set<std::string>children;
  for(auto it=first;it!=source->end()&&it->first.rfind(prefix,0)==0;++it){auto rest=it->first.substr(prefix.size());auto slash=rest.find('/');children.insert((slash==std::string::npos?"file:":"directory:")+rest.substr(0,slash));}
  std::string encoded;for(const auto&child:children)encoded+=std::to_string(child.size())+":"+child;
  return "listing:"+hash(encoded);
 }
 void record(const std::string&kind,const std::string&path){if(seen.insert({kind,path}).second)records.push_back({kind,path,describe(kind,path)});}
 void clear(){records.clear();seen.clear();}
 bool valid(const std::vector<Observation>&old)const{for(const auto&o:old)if(describe(o.kind,o.path)!=o.value)return false;return true;}
};
struct ObservedEntry{std::string object;std::vector<Observation>observations;std::map<std::string,std::string>sideproducts;};
struct CountDiagnostics:clang::DiagnosticConsumer{
 uint64_t warnings=0,errors=0,messages=0;
 void HandleDiagnostic(clang::DiagnosticsEngine::Level level,const clang::Diagnostic&info)override{
  clang::DiagnosticConsumer::HandleDiagnostic(level,info);++messages;if(level==clang::DiagnosticsEngine::Warning)++warnings;if(level>=clang::DiagnosticsEngine::Error)++errors;
  llvm::SmallString<256>message;info.FormatDiagnostic(message);llvm::errs()<<"diagnostic: "<<message<<"\n";
 }
};
struct SourceFS:llvm::vfs::ProxyFileSystem{
 std::string root;llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> memory;Watch*watch;
 SourceFS(std::string r,llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> m,Watch*w):ProxyFileSystem(llvm::vfs::getRealFileSystem()),root(std::move(r)),memory(m),watch(w){}
 std::string absolute(const llvm::Twine&p){return std::filesystem::absolute(p.str()).lexically_normal().string();}
 bool inside(const std::string&p){return p==root||p.rfind(root+"/",0)==0;}
 llvm::vfs::FileSystem&select(const std::string&p){return inside(p)?*memory:getUnderlyingFS();}
 void track(const std::string&kind,const std::string&p){if(inside(p))watch->record(kind,p);}
 llvm::ErrorOr<llvm::vfs::Status>status(const llvm::Twine&p)override{auto a=absolute(p);track("status",a);return select(a).status(a);}
 bool exists(const llvm::Twine&p)override{auto a=absolute(p);track("exists",a);return select(a).exists(a);}
 llvm::ErrorOr<std::unique_ptr<llvm::vfs::File>>openFileForRead(const llvm::Twine&p)override{auto a=absolute(p);track("content",a);return select(a).openFileForRead(a);}
 llvm::vfs::directory_iterator dir_begin(const llvm::Twine&p,std::error_code&e)override{auto a=absolute(p);track("listing",a);return select(a).dir_begin(a,e);}
 std::error_code getRealPath(const llvm::Twine&p,llvm::SmallVectorImpl<char>&out)override{auto a=absolute(p);track("realpath",a);return select(a).getRealPath(a,out);}
 std::error_code isLocal(const llvm::Twine&p,bool&r)override{auto a=absolute(p);return select(a).isLocal(a,r);}
};
struct State{
 std::map<std::string,Entry> cache; std::string context,output,key,mode,analysis; bool hit=false,store=false;double frontend=0,screen=0,backend=0,analysis_seconds=0;size_t ir_bytes=0;uint64_t analysis_count=0,backend_diagnostics=0;Clock::time_point start;
 std::map<std::string,std::shared_ptr<std::string>> source_files;std::string source_root;uint64_t generation=0;llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> filesystem;
 Watch watch;std::map<std::string,ObservedEntry>observed;
 bool volatile_macro=false;
};
struct VolatileMacros:clang::PPCallbacks{
 State&s;VolatileMacros(State&state):s(state){}
 void MacroExpands(const clang::Token&token,const clang::MacroDefinition&,clang::SourceRange,const clang::MacroArgs*)override{
  if(auto*id=token.getIdentifierInfo()){auto name=id->getName();if(name=="__DATE__"||name=="__TIME__"||name=="__TIMESTAMP__")s.volatile_macro=true;}
 }
};
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
struct Finish:clang::ASTConsumer{
 clang::CompilerInstance&ci;clang::CodeGenerator&gen;State&s;
 Finish(clang::CompilerInstance&c,clang::CodeGenerator&g,State&state):ci(c),gen(g),s(state){}
 void HandleTranslationUnit(clang::ASTContext&ast)override{
  s.frontend=seconds(s.start);auto*m=gen.GetModule();if(!m||ci.getDiagnostics().hasErrorOccurred())return;
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
  if(s.hit)write(s.output,s.cache.at(s.context).object);
  else {
   auto out=ci.createDefaultOutputFile(true,ci.getFrontendOpts().Inputs[0].getFile(),"o");
   if(!out)throw std::runtime_error("cannot create output");
   BackendDiagnostics diagnostics{ci,s};auto previous=m->getContext().getDiagnosticHandler();auto handler=std::make_unique<llvm::DiagnosticHandler>(&diagnostics);handler->DiagHandlerCallback=backendDiagnostic;m->getContext().setDiagnosticHandler(std::move(handler),true);
   clang::emitBackendOutput(ci,ci.getCodeGenOpts(),ast.getTargetInfo().getDataLayoutString(),m,clang::Backend_EmitObj,ci.getVirtualFileSystemPtr(),std::move(out));m->getContext().setDiagnosticHandler(std::move(previous));
  }
  s.backend=seconds(backend);
  if(future.valid()){s.analysis_count=future.get();s.analysis_seconds=seconds(astart);}
 }
};
struct Action:clang::ASTFrontendAction{
 State&s;llvm::LLVMContext context;Action(State&state):s(state){}
 bool PrepareToExecuteAction(clang::CompilerInstance&ci)override{ci.getFrontendOpts().DisableFree=false;ci.getCodeGenOpts().DisableFree=false;return true;}
 std::unique_ptr<clang::ASTConsumer>CreateASTConsumer(clang::CompilerInstance&ci,llvm::StringRef file)override{
  ci.getPreprocessor().addPPCallbacks(std::make_unique<VolatileMacros>(s));
  if(s.mode=="analysis")return std::make_unique<OnlyAnalysis>(s);
  context.setDefaultTargetCPU(ci.getTargetOpts().CPU);context.setDefaultTargetFeatures(llvm::join(ci.getTargetOpts().Features,","));
  auto gen=clang::CreateLLVMCodeGen(ci,file,context);auto*ptr=gen.get();std::vector<std::unique_ptr<clang::ASTConsumer>> consumers;consumers.push_back(std::move(gen));consumers.push_back(std::make_unique<Finish>(ci,*ptr,s));return std::make_unique<clang::MultiplexConsumer>(std::move(consumers));
 }
};
int main(){
 llvm::InitializeNativeTarget();llvm::InitializeNativeTargetAsmPrinter();llvm::InitializeNativeTargetAsmParser();State s;s.watch.source=&s.source_files;
 std::string line;while(std::getline(std::cin,line)){
  auto start=Clock::now();s.hit=false;s.frontend=s.screen=s.backend=s.analysis_seconds=0;s.ir_bytes=s.analysis_count=s.backend_diagnostics=0;
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
    s.filesystem=new SourceFS(root->str(),mem,&s.watch);s.source_files=std::move(next);s.source_root=root->str();++s.generation;
    llvm::json::Object response{{"ok",true},{"generation",(int64_t)s.generation},{"files",(int64_t)s.source_files.size()},{"bytes",(int64_t)total},{"seconds",seconds(start)}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;continue;
   }
   if(auto path=obj->getString("inspect")){auto found=s.source_files.find(path->str());llvm::json::Object response{{"ok",true},{"generation",(int64_t)s.generation},{"present",found!=s.source_files.end()}};if(found!=s.source_files.end())response["sha256"]=hash(*found->second);std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;continue;}
   if(auto path=obj->getString("probe_directory")){
    if(!s.filesystem||path->str().rfind(s.source_root+"/",0)!=0)throw std::runtime_error("directory probe outside namespace");
    s.watch.clear();std::error_code error;auto it=s.filesystem->dir_begin(path->str(),error);llvm::json::Array names;for(auto end=llvm::vfs::directory_iterator();it!=end;it.increment(error)){if(error)break;names.push_back(it->path().str());}
    llvm::json::Object response{{"ok",!error},{"generation",(int64_t)s.generation},{"names",std::move(names)},{"value",s.watch.describe("listing",path->str())}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;continue;
   }
   auto cwd=obj->getString("cwd"),output=obj->getString("output"),mode=obj->getString("mode"),ctx=obj->getString("context"),analysis=obj->getString("analysis");auto*args=obj->getArray("args");if(!cwd||!output||!mode||!ctx||!args||args->size()>4096)throw std::runtime_error("request fields");
   if(auto expected=obj->getInteger("generation");expected&&*expected!=(int64_t)s.generation)throw std::runtime_error("stale compilation generation");
   s.mode=mode->str();bool observed_mode=s.mode=="observed";if(observed_mode)s.mode="ir";s.context=ctx->str();s.output=output->str();s.analysis=analysis?analysis->str():"off";s.store=obj->getBoolean("store").value_or(false);if(s.mode!="ir"&&s.mode!="native"&&s.mode!="analysis")throw std::runtime_error("mode");if(s.analysis!="off"&&s.analysis!="serial"&&s.analysis!="parallel")throw std::runtime_error("analysis mode");
   std::vector<std::string> command;for(auto&a:*args){auto str=a.getAsString();if(!str)throw std::runtime_error("argument string");if(str->starts_with("-R"))throw std::runtime_error("optimization remarks unsupported");command.push_back(str->str());}
   std::string command_key=cwd->str();bool output_seen=false;
   for(size_t i=0;i<command.size();++i){if(command[i]=="-o"&&i+1<command.size()){if(command[++i]!=s.output)throw std::runtime_error("output argument mismatch");output_seen=true;continue;}command_key+=std::to_string(command[i].size())+":"+command[i];}
   if(!output_seen)throw std::runtime_error("explicit output required");s.context+=hash(command_key);std::filesystem::current_path(cwd->str());
   std::vector<std::string>sideproducts;for(size_t i=0;i+1<command.size();++i)if(command[i]=="-MF")sideproducts.push_back(command[i+1]);
   if(observed_mode){
    if(!obj->getBoolean("logical").value_or(false)||s.analysis!="off")throw std::runtime_error("observed reuse requires logical namespace and no detached analysis");
    std::string input;for(size_t i=0;i+1<command.size();++i)if(command[i]=="-c")input=std::filesystem::absolute(command[i+1]).lexically_normal().string();
    if(input.empty()||input.rfind(s.source_root+"/",0)!=0)throw std::runtime_error("observed reuse requires explicit admitted -c input");
    auto cached=s.observed.find(s.context);
    if(cached!=s.observed.end()&&s.watch.valid(cached->second.observations)){
     write(s.output,cached->second.object);for(const auto&product:cached->second.sideproducts)write(product.first,product.second);
     llvm::json::Object response{{"ok",true},{"validation_hit",true},{"hit",false},{"generation",(int64_t)s.generation},{"observation_count",(int64_t)cached->second.observations.size()},{"seconds",seconds(start)}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;continue;
    }
   }
   std::filesystem::current_path(cwd->str());bool logical=obj->getBoolean("logical").value_or(false);if(logical&&!s.filesystem)throw std::runtime_error("missing source generation");llvm::IntrusiveRefCntPtr<clang::FileManager>files=new clang::FileManager(clang::FileSystemOptions{},logical?s.filesystem:llvm::vfs::getRealFileSystem());s.start=Clock::now();
   s.watch.clear();s.volatile_macro=false;CountDiagnostics diagnostics;
   clang::tooling::ToolInvocation invocation(command,std::make_unique<Action>(s),files.get());invocation.setDiagnosticConsumer(&diagnostics);bool ok=invocation.run();
   if(ok&&!s.hit&&s.mode=="ir"&&s.store&&s.backend_diagnostics==0){if(s.cache.size()>64)s.cache.clear();auto bytes=read(s.output);if(bytes.empty()||bytes.size()>32*1024*1024)throw std::runtime_error("object bound");s.cache[s.context]={s.key,std::move(bytes)};}
   if(observed_mode&&ok&&diagnostics.messages==0&&s.backend_diagnostics==0&&!s.volatile_macro){
    ObservedEntry entry{read(s.output),s.watch.records,{}};if(entry.object.empty()||entry.object.size()>32*1024*1024)throw std::runtime_error("observed object bound");
    for(const auto&path:sideproducts){auto content=read(path);if(content.empty()||content.size()>1024*1024)throw std::runtime_error("dependency sideproduct unavailable");entry.sideproducts[path]=content;}
    if(s.observed.size()>=64)s.observed.clear();s.observed[s.context]=std::move(entry);
   }else if(observed_mode)s.observed.erase(s.context);
   llvm::json::Array observations;for(const auto&o:s.watch.records)observations.push_back(llvm::json::Object{{"kind",o.kind},{"path",o.path},{"value",o.value}});
   llvm::json::Object response{{"ok",ok},{"validation_hit",false},{"hit",s.hit},{"generation",(int64_t)s.generation},{"observations",std::move(observations)},{"observation_count",(int64_t)s.watch.records.size()},{"diagnostic_messages",(int64_t)diagnostics.messages},{"volatile_macro",s.volatile_macro},{"warnings",(int64_t)diagnostics.warnings},{"errors",(int64_t)diagnostics.errors},{"frontend_seconds",s.frontend},{"screen_seconds",s.screen},{"backend_seconds",s.backend},{"analysis_seconds",s.analysis_seconds},{"analysis_count",(int64_t)s.analysis_count},{"backend_diagnostics",(int64_t)s.backend_diagnostics},{"ir_bytes",(int64_t)s.ir_bytes},{"seconds",seconds(start)}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;
  }catch(const std::exception&e){llvm::json::Object response{{"ok",false},{"error",e.what()}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;}
 }
}
