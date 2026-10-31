// Focused real-parser probe. No mock admission/LLVM filesystem implementation.
#include "project_bridge.cpp"
#include <vector>
#include <memory>
struct InputView {std::string name;llvm::StringRef bytes;std::array<uint8_t,32> digest{};bool retained_digest=false;};
#include "shared_inputs.h"
struct ProbeCollection {GaiaSharedCollection shared;std::vector<InputView> inputs;uint64_t bytes=0;};
extern "C" void *gaia_shared_probe_open(const uint8_t *data,size_t size,const char *pin) {
    auto probe=std::make_unique<ProbeCollection>();
    if(!gaia_shared_inputs(data,size,pin,probe->inputs,probe->shared,probe->bytes)) return nullptr;
    return probe.release();
}
extern "C" void gaia_shared_probe_close(void *handle) {delete static_cast<ProbeCollection *>(handle);}
extern "C" uint64_t gaia_shared_probe_stat(void *handle,int field) {
    auto *probe=static_cast<ProbeCollection *>(handle);
    if(field>=0 && field<7) return probe->shared.stats[field];
    if(field==7) return probe->bytes;if(field==8) return probe->inputs.size();
    if(field==9) return gaia_shared_cache_bytes();if(field==10) return gaia_shared_cache.size();return 0;
}
extern "C" const char *gaia_shared_probe_name(void *handle,size_t index) {
    auto *probe=static_cast<ProbeCollection *>(handle);return index<probe->inputs.size()?probe->inputs[index].name.c_str():nullptr;
}
extern "C" const uint8_t *gaia_shared_probe_bytes(void *handle,size_t index,size_t *size) {
    auto *probe=static_cast<ProbeCollection *>(handle);*size=0;if(index>=probe->inputs.size()) return nullptr;
    const auto &body=probe->inputs[index].bytes;*size=body.size();return reinterpret_cast<const uint8_t *>(body.data());
}
extern "C" const uint8_t *gaia_shared_probe_digest(void *handle,size_t index) {
    auto *probe=static_cast<ProbeCollection *>(handle);return index<probe->inputs.size()?probe->inputs[index].digest.data():nullptr;
}
extern "C" void gaia_shared_probe_hash(const uint8_t *data,size_t size,uint8_t *out) {
    auto digest=llvm::BLAKE3::hash(llvm::ArrayRef<uint8_t>(data,size));memcpy(out,digest.data(),32);
}
