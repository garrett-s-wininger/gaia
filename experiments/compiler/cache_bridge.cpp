// Cache policy, keys, entry validation and publication live in Odin.
// This shim only installs explicit per-request compiler views and transfers
// native object bytes into/out of the existing captured-object pool.
#include "handoff_bridge.cpp"
#ifdef GAIA_DEPENDENCY_JOURNAL
#include "dependency_impl.h"
#endif
extern "C" void *gaia_cache_worker_open(void *handle) {
    return new Worker{static_cast<Pool *>(handle),nullptr};
}
extern "C" int gaia_cache_compile(void *handle,int index,const uint64_t *masks,size_t count,const char *cwd) {
    auto *worker=static_cast<Worker *>(handle);auto *pool=worker->pool;
    if(!pool->memory || index<0 || size_t(index)>=pool->results.size() || count!=pool->inputs.size()) return 7;
#ifdef GAIA_DEPENDENCY_JOURNAL
    return gaia_dep_execute(worker,index);
#else
    auto *fs=new llvm::vfs::InMemoryFileSystem;worker->fs=fs;
    for(size_t i=0;i<count;++i) if(masks[i]&(uint64_t(1)<<index)) {
        const auto &in=pool->inputs[i];
        if(!fs->addFile(in.name,0,llvm::MemoryBuffer::getMemBuffer(in.bytes,in.name,true))) return 7;
    }
    if(fs->setCurrentWorkingDirectory(cwd)) return 7;
    return gaia_worker_compile(worker,index);
#endif
}
extern "C" int gaia_cache_import(void *handle,int index,const uint8_t *data,size_t size) {
    auto *pool=static_cast<Pool *>(handle);
    if(index<0 || size_t(index)>=pool->results.size() || !size || size>64*1024*1024) return 7;
    auto &r=pool->results[index];if(r.okay) return 7;
    r.object.assign(reinterpret_cast<const char *>(data),reinterpret_cast<const char *>(data)+size);
    r.object_size=size;r.object.push_back(0);r.okay=true;return 0;
}
extern "C" const uint8_t *gaia_cache_object(void *handle,int index,size_t *size) {
    auto &r=static_cast<Pool *>(handle)->results[index];*size=r.object_size;
    return reinterpret_cast<const uint8_t *>(r.object.data());
}
