// Generic per-request arguments and absolute named inputs, shared with the
// synthetic adapter's diagnostics/action/lifetime behavior. No project names.
#include "bridge.cpp"

static bool absolute_inputs(llvm::vfs::InMemoryFileSystem &fs,
                            const uint8_t *data, size_t size, const char *pin, Stats &s) {
    if (size<16 || size>64*1024*1024 || memcmp(data,"GAIACIN2",8)) return false;
    auto digest=llvm::SHA256::hash(llvm::ArrayRef<uint8_t>(data,size));
    const char *digits="0123456789abcdef";std::string hex;
    for (auto v:digest) {hex+=digits[v>>4];hex+=digits[v&15];}
    if (hex!=pin) return false;
    uint64_t count=integer(data+8,8);
    if (count>100000 || count>(size-16)/14) return false;
    size_t offset=16;std::set<std::string> names;
    for (uint64_t i=0;i<count;++i) {
        if (size-offset<12) return false;
        auto n=integer(data+offset,4), bytes=integer(data+offset+4,8);offset+=12;
        if (!n || n>4096 || n>=size-offset) return false;
        std::string name(reinterpret_cast<const char *>(data+offset),n);offset+=n;
        if (data[offset++]!=0 || name[0]!='/' || name.back()=='/' ||
            name.find('\0')!=std::string::npos || name.find('\\')!=std::string::npos ||
            name.find("//")!=std::string::npos || name.find("/../")!=std::string::npos ||
            name.find("/./")!=std::string::npos || name.size()<2 ||
            name.compare(name.size()-2,2,"/.")==0 ||
            (name.size()>=3 && name.compare(name.size()-3,3,"/..")==0) ||
            !names.insert(name).second) return false;
        if (bytes>=size-offset || data[offset+bytes]!=0) return false;
        auto buffer=llvm::MemoryBuffer::getMemBuffer(
            llvm::StringRef(reinterpret_cast<const char *>(data+offset),bytes),name,true);
        if (!fs.addFile(name,0,std::move(buffer))) return false;
        offset+=bytes+1;s.input_bytes+=bytes;++s.input_files;
    }
    return offset==size;
}

static bool requests(const uint8_t *data,size_t size,const char *clang,
                     std::vector<std::vector<std::string>> &result) {
    if (size<16 || size>4*1024*1024 || memcmp(data,"GAIACRQ1",8)) return false;
    auto count=integer(data+8,8);if (!count || count>64) return false;
    size_t offset=16;
    for (uint64_t i=0;i<count;++i) {
        if (size-offset<4) return false;
        auto argc=integer(data+offset,4);offset+=4;
        if (argc<2 || argc>4096) return false;
        std::vector<std::string> args;
        for (uint64_t a=0;a<argc;++a) {
            if (size-offset<4) return false;
            auto n=integer(data+offset,4);offset+=4;
            if (!n || n>4096 || n>size-offset) return false;
            std::string arg(reinterpret_cast<const char *>(data+offset),n);offset+=n;
            if (arg.find('\0')!=std::string::npos) return false;
            args.push_back(std::move(arg));
        }
        if (args[0]!=clang) return false;
        result.push_back(std::move(args));
    }
    return offset==size;
}

extern "C" int gaia_compile_plan(int memory,const char *clang,const char *root,
                                 const char *output,const uint8_t *data,size_t size,
                                 const char *pin,const uint8_t *plan,size_t plan_size,Stats *stats) {
    *stats={};auto start=now();
    std::vector<std::vector<std::string>> commands;
    if (!requests(plan,plan_size,clang,commands)) return 2;
    llvm::InitializeNativeTarget();llvm::InitializeNativeTargetAsmPrinter();llvm::InitializeNativeTargetAsmParser();
    llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> filesystem;
    if (memory) {
        auto *fs=new llvm::vfs::InMemoryFileSystem;filesystem=fs;
        if (!absolute_inputs(*fs,data,size,pin,*stats)) return 3;
        fs->addFile(output,0,nullptr);
        if (fs->setCurrentWorkingDirectory(output)) return 4;
    } else filesystem=llvm::vfs::getRealFileSystem();
    auto configured=now();stats->setup_ns=configured-start;int status=0;
    for (const auto &args:commands) {
        llvm::IntrusiveRefCntPtr<clang::FileManager> files=
            new clang::FileManager(clang::FileSystemOptions{},filesystem);
        clang::DiagnosticOptions options;Diagnostics diagnostics(options,*stats);
        clang::tooling::ToolInvocation invocation(args,std::make_unique<ObjectAction>(),files.get());
        invocation.setDiagnosticOptions(&options);invocation.setDiagnosticConsumer(&diagnostics);
        if (!invocation.run()) {status=5;break;}
        ++stats->compiled;
    }
    auto finished=now();stats->compile_ns=finished-configured;
    filesystem.reset();stats->dispose_ns=now()-finished;
    return status;
}
