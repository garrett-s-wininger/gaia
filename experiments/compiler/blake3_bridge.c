// One-shot FFI: caller owns all buffers; no library-private structs cross it.
#include <blake3.h>
#include <stddef.h>
#include <stdint.h>
void gaia_blake3(const uint8_t *data,size_t size,uint8_t out[32]) {
    blake3_hasher hasher;
    blake3_hasher_init(&hasher);
    blake3_hasher_update(&hasher,data,size);
    blake3_hasher_finalize(&hasher,out,32);
}
