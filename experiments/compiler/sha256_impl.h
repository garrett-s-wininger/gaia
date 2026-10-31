// SHA-256 provider selection preserves identities. BLAKE3 query/snapshot
// selection requires the explicitly versioned GAIACIN3/GAIAJR02 contracts.
// Select only between serial requests, before any compiler workers are started.
#include <array>
#include <llvm/Support/BLAKE3.h>
#ifdef GAIA_SHA256_OPENSSL
#include <openssl/sha.h>
#endif
static bool gaia_fast_sha256=false;
static bool gaia_blake3_requested=false;
extern "C" void gaia_blake3_backend(int enabled) {gaia_blake3_requested=enabled!=0;}
extern "C" int gaia_sha256_backend(int accelerated) {
#ifndef GAIA_SHA256_OPENSSL
    if(accelerated) return 1;
#endif
    gaia_fast_sha256=accelerated!=0;return 0;
}
static std::array<uint8_t,32> gaia_sha256(llvm::ArrayRef<uint8_t> data) {
#ifdef GAIA_SHA256_OPENSSL
    if(gaia_fast_sha256) {
        std::array<uint8_t,32> out;
        if(!SHA256(data.data(),data.size(),out.data())) std::abort();return out;
    }
#endif
    return llvm::SHA256::hash(data);
}
static std::array<uint8_t,32> gaia_query_digest(llvm::ArrayRef<uint8_t> data) {
    return gaia_blake3_requested?llvm::BLAKE3::hash(data):gaia_sha256(data);
}
