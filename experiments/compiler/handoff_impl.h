// Included after pool types, only in the direct-handoff build. LLD 22 still
// performs its ordinary readFile bookkeeping and owns each borrowed-buffer
// wrapper. The pool retains the payloads through lldMain/context destruction.
struct BufferObjectAction : ObjectAction {
    JobResult &result;
    explicit BufferObjectAction(JobResult &r):result(r) {}
    bool PrepareToExecuteAction(clang::CompilerInstance &ci) override {
        if(!ObjectAction::PrepareToExecuteAction(ci)) return false;
        result.object.reserve(16384);
        ci.setOutputStream(std::make_unique<llvm::raw_svector_ostream>(result.object));
        return true;
    }
};
static std::string object_path(Pool *pool,int index) {
    const auto &args=pool->commands[index];
    auto out=std::find(args.begin(),args.end(),"-o");
    if(out==args.end() || ++out==args.end()) return {};
    return out->front()=='/'?*out:pool->output+"/"+*out;
}
struct ObjectView {llvm::StringRef bytes;std::string name;};
struct HandoffMap {
    std::unordered_map<std::string,ObjectView> objects;
    std::atomic<uint64_t> hits{0},bytes{0},misses{0};
};
static std::atomic<HandoffMap *> active_handoff{nullptr};
static uint64_t last_hits=0,last_bytes=0,last_misses=0;
struct HandoffScope {
    HandoffMap map;bool enabled=false;
    explicit HandoffScope(Pool *pool) {
        last_hits=last_bytes=last_misses=0;
        if(pool->handoff!=2) return;
        for(size_t i=0;i<pool->results.size();++i) {
            auto path=object_path(pool,i);auto &r=pool->results[i];
            ObjectView view{llvm::StringRef(r.object.data(),r.object_size),path};
            map.objects.emplace(path,view);
            map.objects.emplace(path.substr(path.find_last_of('/')+1),view);
        }
        // Link calls are serialized and compilers are quiescent. This read-only
        // map is published for any linker input-reading threads.
        if(active_handoff.exchange(&map)) std::abort();
        enabled=true;
    }
    ~HandoffScope() {
        if(enabled) {
            active_handoff.store(nullptr);last_hits=map.hits.load();last_bytes=map.bytes.load();last_misses=map.misses.load();
        }
    }
};

// Clang/LLD have no public object-provider callback in this installed version.
// Linux executable symbol interposition substitutes only this public LLVM
// factory during the serialized link. Otherwise the original library function
// is called. The exact mangled symbol/toolchain is pinned and recorded.
llvm::ErrorOr<std::unique_ptr<llvm::MemoryBuffer>> llvm::MemoryBuffer::getFile(
    const llvm::Twine &filename,bool text,bool nul,bool vol,std::optional<llvm::Align> alignment) {
    if(auto *map=active_handoff.load()) {
        std::string name=filename.str();auto found=map->objects.find(name);
        if(found!=map->objects.end()) {
            ++map->hits;map->bytes+=found->second.bytes.size();
            return llvm::MemoryBuffer::getMemBuffer(found->second.bytes,found->second.name,nul);
        }
        // Never satisfy an absent object from stale physical outputs.
        if(llvm::StringRef(name).ends_with(".o")) {++map->misses;return std::make_error_code(std::errc::no_such_file_or_directory);}
    }
    using Function=llvm::ErrorOr<std::unique_ptr<llvm::MemoryBuffer>> (*)(const llvm::Twine &,bool,bool,bool,std::optional<llvm::Align>);
    static auto original=reinterpret_cast<Function>(dlsym(RTLD_NEXT,"_ZN4llvm12MemoryBuffer7getFileERKNS_5TwineEbbbSt8optionalINS_5AlignEE"));
    if(!original) std::abort();
    return original(filename,text,nul,vol,alignment);
}
extern "C" void gaia_handoff_mode(void *handle,int mode) {static_cast<Pool *>(handle)->handoff=mode;}
extern "C" uint64_t gaia_handoff_stat(void *handle,int field,int index) {
    auto *pool=static_cast<Pool *>(handle);
    if(field==0) return pool->results[index].object_size;
    if(field==1) return pool->results[index].export_ns;
    if(field==2) return last_hits;
    if(field==3) return last_bytes;
    if(field==4) return last_misses;
    return 0;
}
extern "C" void gaia_handoff_digest(void *handle,int index,char *out) {
    auto &r=static_cast<Pool *>(handle)->results[index];
    auto hash=gaia_sha256(llvm::ArrayRef<uint8_t>(reinterpret_cast<uint8_t *>(r.object.data()),r.object_size));
    const char *hex="0123456789abcdef";
    for(size_t i=0;i<hash.size();++i) {out[2*i]=hex[hash[i]>>4];out[2*i+1]=hex[hash[i]&15];}
    out[64]=0;
}
extern "C" int gaia_handoff_export(void *handle) {
    auto *pool=static_cast<Pool *>(handle);
    for(size_t i=0;i<pool->results.size();++i) {
        auto &r=pool->results[i];if(!r.okay) return 1;
        std::error_code error;llvm::raw_fd_ostream out(object_path(pool,i),error);
        if(error) return 1;out.write(r.object.data(),r.object_size);out.close();
        if(out.has_error()) {out.clear_error();return 1;}
    }
    return 0;
}
