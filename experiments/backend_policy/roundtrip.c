/* Deterministic experimental workload, not the upstream conformance suite. */
#define ZSTD_STATIC_LINKING_ONLY
#include "zstd.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void check(size_t result) {
    if (ZSTD_isError(result)) { fprintf(stderr, "%s\n", ZSTD_getErrorName(result)); exit(2); }
}
static uint32_t random32(uint32_t *state) {
    *state ^= *state << 13; *state ^= *state >> 17; *state ^= *state << 5; return *state;
}
int main(int argc, char **argv) {
    if (argc != 4) return 2;
    unsigned repeats = (unsigned)strtoul(argv[3], NULL, 10);
    if (!repeats || repeats > 100) return 2;
    FILE *input = fopen(argv[1], "rb"), *frames = fopen(argv[2], "wb");
    if (!input || !frames) return 2;
    unsigned char corpus[131072]; size_t corpus_size = fread(corpus, 1, sizeof(corpus), input);
    if (ferror(input) || !corpus_size || fclose(input)) return 2;
    enum { CAP = 65536 };
    unsigned char *data = malloc(CAP), *decoded = malloc(CAP), *compressed = malloc(ZSTD_compressBound(CAP));
    ZSTD_CCtx *cc = ZSTD_createCCtx(); ZSTD_DCtx *dc = ZSTD_createDCtx();
    if (!data || !decoded || !compressed || !cc || !dc) return 2;
    const size_t sizes[] = {0, 31, 4096, CAP};
    const ZSTD_strategy strategies[] = {ZSTD_greedy, ZSTD_lazy, ZSTD_lazy2, ZSTD_btlazy2};
    uint64_t cases = 0, input_bytes = 0, compressed_bytes = 0;
    for (unsigned repeat = 0; repeat < repeats; ++repeat) {
        for (unsigned kind = 0; kind < 3; ++kind) {
            uint32_t state = 1234567;
            for (size_t i = 0; i < CAP; ++i) {
                unsigned char r = (unsigned char)random32(&state);
                if (kind == 0) data[i] = corpus[i % corpus_size];
                else if (kind == 1) data[i] = i % 97 < 80 ? corpus[(i % 97) % corpus_size] : r;
                else data[i] = i % 4096 < 32 ? corpus[i % 32] : r;
            }
            for (unsigned length = 0; length < 4; ++length)
            for (unsigned strategy = 0; strategy < 4; ++strategy)
            for (unsigned row = 0; row < (strategy == 3 ? 1u : 2u); ++row)
            for (unsigned dict = 0; dict < 2; ++dict) {
                size_t n = sizes[length];
                check(ZSTD_CCtx_reset(cc, ZSTD_reset_session_and_parameters));
                check(ZSTD_CCtx_setParameter(cc, ZSTD_c_compressionLevel, 6));
                check(ZSTD_CCtx_setParameter(cc, ZSTD_c_strategy, strategies[strategy]));
                check(ZSTD_CCtx_setParameter(cc, ZSTD_c_searchLog, 6));
                check(ZSTD_CCtx_setParameter(cc, ZSTD_c_useRowMatchFinder, row ? ZSTD_ps_enable : ZSTD_ps_disable));
                check(ZSTD_CCtx_loadDictionary(cc, dict ? corpus : NULL, dict ? 8192 : 0));
                size_t c = ZSTD_compress2(cc, compressed, ZSTD_compressBound(CAP), data, n); check(c);
                size_t d = ZSTD_decompress_usingDict(dc, decoded, CAP, compressed, c, dict ? corpus : NULL, dict ? 8192 : 0);
                check(d);
                if (d != n || memcmp(data, decoded, n)) { fprintf(stderr, "round trip differs\n"); return 3; }
                if (!repeat) {
                    uint64_t bytes = c;
                    if (fwrite(&bytes, sizeof(bytes), 1, frames) != 1 || fwrite(compressed, 1, c, frames) != c) return 2;
                }
                ++cases; input_bytes += n; compressed_bytes += c;
            }
        }
    }
    if (fclose(frames)) return 2;
    check(ZSTD_freeCCtx(cc)); check(ZSTD_freeDCtx(dc)); free(data); free(decoded); free(compressed);
    printf("{\"cases\":%llu,\"input_bytes\":%llu,\"compressed_bytes\":%llu,\"repeats\":%u}\n",
        (unsigned long long)cases, (unsigned long long)input_bytes, (unsigned long long)compressed_bytes, repeats);
    return 0;
}
