# SIMD unions for dependency invalidation

The native operation unions the target masks of changed observations. It is the reusable set operation behind an inverted dependency relation, rather than a complete compiler timing. The current captured project has 33 targets; wider generated cases test scaling explicitly.

## Reproduce

Use Linux x86-64, Odin and a C/C++ toolchain. From the repository root, with absolute caller-selected paths:

```sh
mkdir -p "$TOOLS"
odin build experiments/integration/simd/union.odin -file -build-mode:obj \
  -reloc-mode:pic -o:speed -out:"$TOOLS/union.o"
cc -shared "$TOOLS/union.o" -o "$TOOLS/union.so" -lm
"$CLANGXX" -O3 -std=c++17 -march=native experiments/integration/simd/bench.cpp \
  -ldl -o "$TOOLS/simd-bench"
GAIA_UNION_LIBRARY="$TOOLS/union.so" \
  python3 -B -m unittest discover -s experiments/integration/simd -p 'test_*.py' -v
python3 -B experiments/integration/simd/run.py --library "$TOOLS/union.so" \
  --bench "$TOOLS/simd-bench" --relation "$WORKSPACE_RELATION" \
  --work "$WORK" --output "$OUTPUT" --lock "$MEASUREMENT_LOCK"
```

`WORKSPACE_RELATION` is the `relation.json` produced from actual warmup observations by the workspace integration. It must be regenerated locally. Omit `--relation` for generated-only tests. `WORK` must not exist. To test the strongest compiler auto-vectorization control, rebuild the Odin object with `-microarch:native`, link a separate library and rerun with a fresh work/output directory. That native build targets the measurement CPU and is not a portable fallback binary.

## Controls and execution

The same bitmask layout feeds a compiler-optimized row loop, a compiler-optimized word-tiled loop, explicit four-lane and eight-lane integer unions with AVX2/AVX-512 feature guards. The portable loop may auto-vectorize; it is not labelled a strict scalar baseline. A native C++ CSR list union supplies a stronger representation control on sparse data, including output clearing. CSR construction and retained representation bytes are recorded separately.

The generic Odin object uses per-function target features. Object-mode C linking does not invoke Odin `@init` routines: callers must run `gaia_init` once before worker threads. It checks CPUID and OS XCR0 state; unsupported explicit modes fail instead of silently emulating. Queries use separate caller-owned read-only rows/IDs and writable output buffers with no overlap. Input dimensions/IDs are validated before writes. SIMD tails use the scalar word loop; unaligned vector loads/stores are intentional.

A native harness calls opaque shared-library function pointers, cycles 64 prepared query sets, and consumes an output word after each operation. Every output word for every query/mode is checked against an independent union outside timing. Timed batches amortize language-ABI crossings and measure warm repeated kernels, including dispatch, clearing, validation and a small checksum. They are not single Python-call latencies or cold workflows. Seven blocks shuffle mode order within each fixture. Fixture preparation, CSR construction and code generation are not hidden as per-query work.

The recorded relation is sparse and small; generated dimensions/densities are labelled. Changed-path sets are generated queries even for the captured relation, rather than a timed real edit trace. A vector win against one loop does not establish a win over sparse traversal or a complete build improvement. Compare the native auto-vectorized control and the representation costs before selecting a production path.

[Build evidence](builds.json) records native instruction widths. The generic build lowers the eight-lane operation into narrower instructions; its feature annotation alone does not establish 512-bit execution. The native build contains ZMM instructions. These static counts are not dynamic instruction measurements.
