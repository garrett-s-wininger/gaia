// Clang 22 C++ API boundary. Odin owns the input mapping through this call.
#include <clang/Basic/DiagnosticOptions.h>
#include <clang/Basic/FileManager.h>
#include <clang/CodeGen/CodeGenAction.h>
#include <clang/Frontend/CompilerInstance.h>
#include <clang/Frontend/TextDiagnosticPrinter.h>
#include <clang/Tooling/Tooling.h>
#include <llvm/Support/MemoryBuffer.h>
#include <llvm/Support/SHA256.h>
#include <llvm/Support/TargetSelect.h>
#include <llvm/Support/VirtualFileSystem.h>
#include <chrono>
#include <cstring>
#include <set>
#include <string>

struct Stats {
    uint64_t setup_ns, compile_ns, dispose_ns, input_files, input_bytes;
    uint64_t compiled, errors, warnings;
};
static uint64_t now() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}
struct Diagnostics : clang::TextDiagnosticPrinter {
    Stats &stats;
    Diagnostics(clang::DiagnosticOptions &options, Stats &s)
        : TextDiagnosticPrinter(llvm::errs(), options), stats(s) {}
    void HandleDiagnostic(clang::DiagnosticsEngine::Level level, const clang::Diagnostic &info) override {
        if (level >= clang::DiagnosticsEngine::Error) ++stats.errors;
        if (level == clang::DiagnosticsEngine::Warning) ++stats.warnings;
        TextDiagnosticPrinter::HandleDiagnostic(level, info);
    }
};
struct ObjectAction : clang::EmitObjAction {
    bool PrepareToExecuteAction(clang::CompilerInstance &compiler) override {
        // A reusable process must dispose each request, even where CLI defaults
        // deliberately leave allocation reclamation to process termination.
        compiler.getFrontendOpts().DisableFree = false;
        compiler.getCodeGenOpts().DisableFree = false;
        return EmitObjAction::PrepareToExecuteAction(compiler);
    }
};
static uint64_t integer(const uint8_t *p, unsigned n) {
    uint64_t result=0;
    for (unsigned i=0;i<n;++i) result |= uint64_t(p[i]) << (i*8);
    return result;
}
static bool load(llvm::vfs::InMemoryFileSystem &fs, const char *root,
                 const uint8_t *data, size_t size, const char *pin, Stats &s) {
    if (size<16 || size>64*1024*1024 || memcmp(data,"GAIACIN1",8)) return false;
    auto digest=llvm::SHA256::hash(llvm::ArrayRef<uint8_t>(data,size));
    const char *digits="0123456789abcdef";
    std::string hex;
    for (auto v:digest) {hex+=digits[v>>4];hex+=digits[v&15];}
    if (hex!=pin) return false;
    uint64_t count=integer(data+8,8);
    if (count>100000 || count>(size-16)/14) return false;
    size_t offset=16;
    std::set<std::string> names;
    for (uint64_t i=0;i<count;++i) {
        if (size-offset<12) return false;
        auto n=integer(data+offset,4), bytes=integer(data+offset+4,8);offset+=12;
        if (!n || n>4096 || n>=size-offset) return false;
        std::string name(reinterpret_cast<const char *>(data+offset),n);offset+=n;
        if (data[offset++]!=0 || name.find_first_of("/\\\0",0,3)!=std::string::npos ||
            name=="." || name==".." || !names.insert(name).second) return false;
        if (bytes>=size-offset || data[offset+bytes]!=0) return false;
        std::string path=std::string(root)+"/"+name;
        auto buffer=llvm::MemoryBuffer::getMemBuffer(
            llvm::StringRef(reinterpret_cast<const char *>(data+offset),bytes),path,true);
        if (!fs.addFile(path,0,std::move(buffer))) return false;
        offset+=bytes+1;s.input_bytes+=bytes;++s.input_files;
    }
    return offset==size;
}

extern "C" int gaia_compile(int memory, const char *clang, const char *root,
                            const char *output, int requests, const uint8_t *data,
                            size_t size, const char *pin, Stats *stats) {
    *stats={};auto start=now();
    if (requests<1 || requests>64) return 2;
    llvm::InitializeNativeTarget();
    llvm::InitializeNativeTargetAsmPrinter();
    llvm::InitializeNativeTargetAsmParser();
    llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> filesystem;
    if (memory) {
        auto *fs=new llvm::vfs::InMemoryFileSystem;
        filesystem=fs;
        if (!load(*fs,root,data,size,pin,*stats)) return 3;
        // Deliberately no real-filesystem fallback for compiler inputs.
        if (auto error=fs->setCurrentWorkingDirectory("/")) return 4;
    } else filesystem=llvm::vfs::getRealFileSystem();
    auto configured=now();stats->setup_ns=configured-start;
    int status=0;
    for (int i=0;i<requests;++i) {
        std::vector<std::string> args={clang,"--target=x86_64-unknown-linux-gnu","-x","c",
            "-std=c11","-O2","-ffreestanding","-nostdinc","-fno-ident","-fno-addrsig",
            "-fno-stack-protector","-c",std::string(root)+"/unit"+std::to_string(i)+".c",
            "-o",std::string(output)+"/unit"+std::to_string(i)+".o"};
        llvm::IntrusiveRefCntPtr<clang::FileManager> files=
            new clang::FileManager(clang::FileSystemOptions{},filesystem);
        clang::DiagnosticOptions options;
        Diagnostics diagnostics(options,*stats);
        clang::tooling::ToolInvocation invocation(args,std::make_unique<ObjectAction>(),files.get());
        invocation.setDiagnosticOptions(&options);
        invocation.setDiagnosticConsumer(&diagnostics);
        if (!invocation.run()) {status=5;break;}
        ++stats->compiled;
    }
    auto finished=now();stats->compile_ns=finished-configured;
    filesystem.reset();stats->dispose_ns=now()-finished;
    return status;
}
