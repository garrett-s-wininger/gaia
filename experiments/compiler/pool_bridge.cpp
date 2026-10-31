// The queue/worker lifecycle is Odin-owned. Every worker has a private VFS and
// every job a private CompilerInstance/LLVMContext. Only admitted bytes/args share.
#include "project_bridge.cpp"
#include <lld/Common/Driver.h>
#include <lld/Common/ErrorHandler.h>
#include <llvm/Support/raw_ostream.h>
#include <algorithm>
#ifdef GAIA_COMPILER_PROFILE
#include <llvm/Support/TimeProfiler.h>
#endif

LLD_HAS_DRIVER(elf)

struct InputView {std::string name;llvm::StringRef bytes;std::array<uint8_t,32> digest{};bool retained_digest=false;};
#include "shared_inputs.h"
struct JobResult {uint64_t start=0,end=0,errors=0,warnings=0;bool okay=false;std::string diagnostics;
#ifdef GAIA_DIRECT_HANDOFF
    llvm::SmallVector<char,0> object;size_t object_size=0;uint64_t export_ns=0;
#endif
};
struct Pool {
    uint64_t start=now(),setup=0,link_ns=0,input_bytes=0;
    bool memory=false,can_run_again=true;unsigned link_calls=0;int link_result=0;
    std::string output,linker,link_diagnostics;
    std::vector<std::vector<std::string>> commands,links;
    std::vector<InputView> inputs;
    GaiaSharedCollection shared;
    std::vector<JobResult> results;
#ifdef GAIA_DIRECT_HANDOFF
    int handoff=0;
#endif
};
struct Worker {Pool *pool;llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> fs;};
struct PoolStats {
    uint64_t compiled,errors,warnings,setup_ns,link_ns,input_files,input_bytes;
    uint64_t job_count,peak_active,link_calls,link_result,can_run_again;
};
struct QuietDiagnostics : clang::DiagnosticConsumer {
    JobResult &result;
    explicit QuietDiagnostics(JobResult &r):result(r) {}
    void HandleDiagnostic(clang::DiagnosticsEngine::Level level,const clang::Diagnostic &info) override {
        clang::DiagnosticConsumer::HandleDiagnostic(level,info);
        if(level>=clang::DiagnosticsEngine::Error) ++result.errors;
        if(level==clang::DiagnosticsEngine::Warning) ++result.warnings;
        llvm::SmallString<256> message;info.FormatDiagnostic(message);
        result.diagnostics+=message.str().str()+"\n";
    }
};

#ifdef GAIA_DIRECT_HANDOFF
#include "handoff_impl.h"
#endif

extern "C" void *gaia_pool_open(int memory,const char *clang,const char *output,
    const uint8_t *data,size_t size,const char *pin,const uint8_t *plan,size_t plan_size,
    const char *linker,const uint8_t *link,size_t link_size) {
    auto pool=std::make_unique<Pool>();pool->memory=memory;pool->output=output;pool->linker=linker;
#ifdef GAIA_COMPILER_PROFILE
    llvm::timeTraceProfilerInitialize(100,"gaia-compiler-profile");
#endif
    if(!requests(plan,plan_size,clang,pool->commands) || !requests(link,link_size,linker,pool->links) || pool->links.size()!=1) return nullptr;
    llvm::InitializeNativeTarget();llvm::InitializeNativeTargetAsmPrinter();llvm::InitializeNativeTargetAsmParser();
    if(memory && size>=8 && !memcmp(data,"GAIACIN4",8)) {
        if(!gaia_shared_inputs(data,size,pin,pool->inputs,pool->shared,pool->input_bytes)) return nullptr;
    } else if(memory) {
        // Authenticate/validate once, then retain borrowed descriptors. Worker
        // trees are private and do not share mutable VFS state or payload copies.
        llvm::vfs::InMemoryFileSystem validation;Stats s{};
        if(!absolute_inputs(validation,data,size,pin,s)) return nullptr;
        pool->input_bytes=s.input_bytes;size_t offset=16;
        for(uint64_t i=0;i<s.input_files;++i) {
            auto n=integer(data+offset,4),bytes=integer(data+offset+4,8);offset+=12;
            std::string name(reinterpret_cast<const char *>(data+offset),n);offset+=n+1;
            pool->inputs.push_back({name,llvm::StringRef(reinterpret_cast<const char *>(data+offset),bytes)});
            offset+=bytes+1;
        }
    }
    pool->results.resize(pool->commands.size());pool->setup=now()-pool->start;
    return pool.release();
}

extern "C" uint64_t gaia_shared_input_stat(void *handle,int field) {
    auto *pool=static_cast<Pool *>(handle);return field>=0 && field<7?pool->shared.stats[field]:0;
}

extern "C" int gaia_pool_count(void *handle) {return static_cast<Pool *>(handle)->commands.size();}
extern "C" void *gaia_worker_open(void *handle) {
#ifdef GAIA_COMPILER_PROFILE
    llvm::timeTraceProfilerInitialize(100,"gaia-compiler-worker");
#endif
    auto *pool=static_cast<Pool *>(handle);auto worker=std::make_unique<Worker>();worker->pool=pool;
    if(pool->memory) {
        auto *fs=new llvm::vfs::InMemoryFileSystem;worker->fs=fs;
        for(const auto &input:pool->inputs)
            if(!fs->addFile(input.name,0,llvm::MemoryBuffer::getMemBuffer(input.bytes,input.name,true))) return nullptr;
        fs->addFile(pool->output,0,nullptr);
    } else worker->fs=llvm::vfs::createPhysicalFileSystem().release();
    if(worker->fs->setCurrentWorkingDirectory(pool->output)) return nullptr;
    return worker.release();
}
extern "C" int gaia_worker_compile(void *handle,int index) {
    auto *worker=static_cast<Worker *>(handle);auto *pool=worker->pool;
    if(index<0 || size_t(index)>=pool->commands.size()) return 2;
    auto &result=pool->results[index];result.start=now()-pool->start;
#ifdef GAIA_COMPILER_PROFILE
    llvm::TimeTraceScope job_scope("GaiaJob",std::to_string(index));
#endif
    {
        llvm::IntrusiveRefCntPtr<clang::FileManager> files=
            new clang::FileManager(clang::FileSystemOptions{},worker->fs);
        clang::DiagnosticOptions options;QuietDiagnostics diagnostics(result);
        std::unique_ptr<clang::FrontendAction> action;
#ifdef GAIA_DIRECT_HANDOFF
        if(pool->handoff) action=std::make_unique<BufferObjectAction>(result);
        else
#endif
            action=std::make_unique<ObjectAction>();
        clang::tooling::ToolInvocation invocation(pool->commands[index],std::move(action),files.get());
        invocation.setDiagnosticOptions(&options);invocation.setDiagnosticConsumer(&diagnostics);
        result.okay=invocation.run() && result.errors==0;
    }
#ifdef GAIA_DIRECT_HANDOFF
    if(result.okay && pool->handoff) {
        result.object_size=result.object.size();result.object.push_back(0);
        if(pool->handoff==1) {
            auto begin=now();std::error_code error;
            llvm::raw_fd_ostream out(object_path(pool,index),error);
            if(error) {++result.errors;result.okay=false;result.diagnostics+=error.message();}
            else {out.write(result.object.data(),result.object_size);out.close();
                if(out.has_error()) {++result.errors;result.okay=false;result.diagnostics+="object export failed\n";out.clear_error();}}
            result.export_ns=now()-begin;
        }
    }
#endif
    result.end=now()-pool->start;return result.okay?0:5;
}
extern "C" void gaia_worker_close(void *handle) {
    delete static_cast<Worker *>(handle);
#ifdef GAIA_COMPILER_PROFILE
    llvm::timeTraceProfilerFinishThread();
#endif
}

extern "C" int gaia_pool_link(void *handle,int invalid) {
    auto *pool=static_cast<Pool *>(handle);
    // This API is called only after the host joins every compiler worker.
    for(const auto &result:pool->results) if(!result.okay || result.errors) return 6;
    auto strings=pool->links[0];if(invalid) strings.push_back("--gaia-invalid-link-option");
    std::vector<const char *> args;for(const auto &s:strings) args.push_back(s.c_str());
    llvm::raw_string_ostream errors(pool->link_diagnostics);std::string text;
    llvm::raw_string_ostream output(text);
    const lld::DriverDef drivers[]={{lld::Gnu,&lld::elf::link}};
#ifdef GAIA_DIRECT_HANDOFF
    HandoffScope handoff(pool);
#endif
    ++pool->link_calls;auto begin=now();
    auto result=lld::lldMain(args,output,errors,drivers);pool->link_ns+=now()-begin;
    pool->link_result=result.retCode;pool->can_run_again=result.canRunAgain;
    if(!result.canRunAgain) lld::exitLld(result.retCode);
    return result.retCode;
}
extern "C" void gaia_pool_stats(void *handle,PoolStats *out) {
    auto *pool=static_cast<Pool *>(handle);*out={};std::vector<std::pair<uint64_t,int>> events;
    for(const auto &r:pool->results) {
        out->compiled+=r.okay;out->errors+=r.errors;out->warnings+=r.warnings;
        if(r.start && r.end) {events.push_back({r.start,1});events.push_back({r.end,-1});}
    }
    std::sort(events.begin(),events.end());int active=0;
    for(auto event:events) {active+=event.second;out->peak_active=std::max(out->peak_active,uint64_t(active));}
    out->setup_ns=pool->setup;out->link_ns=pool->link_ns;out->input_files=pool->inputs.size();out->input_bytes=pool->input_bytes;
    out->job_count=pool->commands.size();out->link_calls=pool->link_calls;out->link_result=pool->link_result;out->can_run_again=pool->can_run_again;
}
extern "C" uint64_t gaia_pool_job_time(void *handle,int index,int end) {
    auto &r=static_cast<Pool *>(handle)->results[index];return end?r.end:r.start;
}
extern "C" const char *gaia_pool_messages(void *handle) {
    auto *pool=static_cast<Pool *>(handle);
    for(size_t i=0;i<pool->results.size();++i)
        if(!pool->results[i].diagnostics.empty()) pool->link_diagnostics+="job "+std::to_string(i)+": "+pool->results[i].diagnostics;
    return pool->link_diagnostics.c_str();
}
extern "C" void gaia_pool_close(void *handle) {
#ifdef GAIA_COMPILER_PROFILE
    auto *pool=static_cast<Pool *>(handle);
    if(auto error=llvm::timeTraceProfilerWrite(pool->output+"/compiler-trace.json","")) llvm::consumeError(std::move(error));
    llvm::timeTraceProfilerCleanup();
#endif
    delete static_cast<Pool *>(handle);
}
