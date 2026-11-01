"""Scheduling-only overlay on the frozen generated host. Linux fork prototype."""
import argparse
from pathlib import Path

def transform(s,passes):
 def replace(old,new):
  nonlocal s
  if s.count(old)!=1:raise ValueError('host shape changed: '+old[:100])
  s=s.replace(old,new)
 replace('#include <chrono>','#include <chrono>\n#include <sys/wait.h>\n#include <sys/resource.h>\n#include <signal.h>\n#include <unistd.h>\n#include <fcntl.h>\n#include <functional>')
 replace('struct State{','struct PendingBackend;\nstruct State{\n std::shared_ptr<PendingBackend> pending;bool defer_backend=false,current_pending=false;double child_cpu=0;uint64_t children=0;')
 helper=passes[passes.index('#include <cerrno>'):passes.index('struct FactResult')]
 helper=helper.replace('a=="--target"','a=="--target"||a=="-MF"||a=="-MT"||a=="-MQ"').replace('a=="--no-default-config"','a=="-MD"||a=="-MMD"||a=="-DNDEBUG"||a=="-fno-exceptions"||a=="-fno-rtti"||a=="-fvisibility-inlines-hidden"||a=="--no-default-config"')
 helper+='''
struct PendingBackend{
 StagingFile stage;Child child;std::unique_ptr<FILE,decltype(&fclose)> errors{nullptr,fclose};
 ObservedEntry entry;Projection projection;std::string output,context,key;bool retain_entry=false,retain_ir=false;
};
static void complete_backend(State&s){
 if(!s.pending)return;auto job=std::move(s.pending);auto raw=job->child.finish();s.child_cpu+=job->child.cpu();
 auto parsed=llvm::json::parse(raw);auto*record=parsed?parsed->getAsObject():nullptr;
 if(!job->child.success()||!record||!record->getBoolean("ok").value_or(false)){
  fflush(job->errors.get());rewind(job->errors.get());char b[4096];size_t n;while((n=fread(b,1,sizeof(b),job->errors.get())))llvm::errs().write(b,n);
  throw std::runtime_error("queued backend failed; object not published");
 }
 auto bytes=read(job->stage.path);if(bytes.empty()||bytes.size()>32*1024*1024)throw std::runtime_error("queued object bound");
 s.published.erase(job->output+":build");std::filesystem::rename(job->stage.path,job->output);job->stage.path.clear();
 if(job->retain_ir&&record->getInteger("diagnostics").value_or(1)==0){if(s.cache.size()>64)s.cache.clear();s.cache[job->context]={job->key,bytes};}
 if(job->retain_entry&&record->getInteger("diagnostics").value_or(1)==0){
  job->entry.object=std::move(bytes);auto previous=s.projection;s.projection=job->projection;
  try{retain(s,std::move(job->entry));if(auto*stored=lookup(s,s.projection))s.published[job->output+":build"]=stored->id;}
  catch(...){s.projection=previous;throw;}s.projection=previous;
 }
}
'''
 replace('struct BackendDiagnostics{',helper+'\nstruct BackendDiagnostics{')
 old='''   auto out=ci.createDefaultOutputFile(true,ci.getFrontendOpts().Inputs[0].getFile(),"o");
   if(!out)throw std::runtime_error("cannot create output");'''
 new='''   if(s.defer_backend){
    complete_backend(s);auto job=std::make_shared<PendingBackend>();job->stage.create(s.output);job->errors.reset(tmpfile());if(!job->errors)throw std::runtime_error("queued diagnostics file");
    job->output=s.output;job->context=s.context;job->key=s.key;job->projection=s.projection;
    job->child.start([&]{auto begin=Clock::now();ci.getFrontendOpts().OutputFile=job->stage.path;
     auto out=ci.createOutputFile(job->stage.path,true,false,false);if(!out)throw std::runtime_error("queued output");
     BackendDiagnostics diagnostics{ci,s};auto previous=m->getContext().getDiagnosticHandler();auto handler=std::make_unique<llvm::DiagnosticHandler>(&diagnostics);handler->DiagHandlerCallback=backendDiagnostic;m->getContext().setDiagnosticHandler(std::move(handler),true);
     clang::emitBackendOutput(ci,ci.getCodeGenOpts(),ast.getTargetInfo().getDataLayoutString(),m,clang::Backend_EmitObj,ci.getVirtualFileSystemPtr(),std::move(out));m->getContext().setDiagnosticHandler(std::move(previous));
     ci.clearOutputFiles(ci.getDiagnostics().hasErrorOccurred());return json_text(llvm::json::Object{{"ok",!ci.getDiagnostics().hasErrorOccurred()},{"diagnostics",(int64_t)s.backend_diagnostics},{"seconds",seconds(begin)}});
    },fileno(job->errors.get()));s.pending=std::move(job);s.current_pending=true;++s.children;
   }else{
   auto out=ci.createDefaultOutputFile(true,ci.getFrontendOpts().Inputs[0].getFile(),"o");
   if(!out)throw std::runtime_error("cannot create output");'''
 replace(old,new)
 replace('  s.backend=seconds(backend);','   }\n  s.backend=seconds(backend);')
 replace('   if(auto*edits=obj->getObject("edits")){','''   if(obj->getBoolean("drain").value_or(false)){complete_backend(s);std::cout<<json_text(llvm::json::Object{{"ok",true},{"backend_pending",false},{"children",(int64_t)s.children},{"child_cpu",s.child_cpu}})<<std::endl;continue;}
   if(auto*edits=obj->getObject("edits")){
    if(s.pending)throw std::runtime_error("drain before source admission");''')
 replace('   if(auto*targets=obj->getArray("scan")){','   if(auto*targets=obj->getArray("scan")){\n    if(s.pending)throw std::runtime_error("drain before scan");')
 replace('   std::string command_key=cwd->str();bool output_seen=false;','''   s.current_pending=false;s.defer_backend=obj->getBoolean("defer_backend").value_or(false);
   if(s.defer_backend){if(s.analysis_only||s.analysis!="off")throw std::runtime_error("queue requires object build without detached analysis");require_object_only(command);}else complete_backend(s);
   std::string command_key=cwd->str();bool output_seen=false;''')
 replace('   if(ok&&!s.hit&&s.mode=="ir"&&s.store&&s.backend_diagnostics==0){','   if(!s.current_pending&&ok&&!s.hit&&s.mode=="ir"&&s.store&&s.backend_diagnostics==0){')
 replace('   if(observed_mode&&ok&&diagnostics.messages==0&&s.backend_diagnostics==0&&!s.volatile_macro){','   if(!s.current_pending&&observed_mode&&ok&&diagnostics.messages==0&&s.backend_diagnostics==0&&!s.volatile_macro){')
 replace('   llvm::json::Array observations;for(const auto&o:s.watch.records)', '''   if(s.current_pending){auto&job=*s.pending;job.retain_ir=ok&&s.mode=="ir"&&s.store;job.retain_entry=observed_mode&&ok&&diagnostics.messages==0&&!s.volatile_macro;
    job.entry=ObservedEntry{"",s.watch.records,{},s.facts,s.target,s.space,s.facts_info,s.lexical,s.projection.definitions};
    for(const auto&path:sideproducts){auto content=read(path);if(content.empty()||content.size()>1024*1024)throw std::runtime_error("dependency sideproduct unavailable");job.entry.sideproducts[path]=content;}
   }
   llvm::json::Array observations;for(const auto&o:s.watch.records)''')
 replace('response{{"ok",ok},{"facts"','response{{"ok",ok},{"backend_pending",s.current_pending},{"artifact_ready",ok&&!s.current_pending},{"facts"')
 return s

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--passes',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(transform(a.source.read_text(),a.passes.read_text()))
