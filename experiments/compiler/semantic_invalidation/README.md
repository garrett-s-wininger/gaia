# Does a source edit require a different object?

This is a bounded first experiment in semantic invalidation. It asks whether a compiler-visible representation can avoid optimizing and generating an object when changed source bytes would produce the same object. It keeps the existing text-hash fast path.

Four modes share one baseline candidate:

- `text` recompiles changed source.
- `ast` compares a normalized Clang diagnostic AST dump. This is deliberately an unsafe control: locations/ranges are omitted and process-local declaration IDs are renamed.
- `guarded-ast` requires both the AST candidate and exact pre-optimization LLVM IR to match.
- `ir` skips AST construction and compares that exact IR directly.

IR keeps source filename, module flags, target attributes, inline assembly, debug metadata and even textual comments. Equal IR is a stronger experimental guard, not a general production cache theorem. Tool/SDK/options/backend state must still match, and emitted side products and diagnostics have their own contracts. This prototype reuses only `.o` bytes and measures successful fixed-context commands. It does not preserve changed-source warnings on cache hits.

The native helper uses LLVM's JSON parser and streaming OpenSSL SHA-256 with a versioned token encoding. It avoids the Python JSON object walk/serialization bridge, but still reads a large externally dumped AST. Neither bridge measures the floor of an in-process compiler API. Native/Python encodings intentionally differ; tests check structural invariants rather than identical digest bytes.

## Reproduce

Prepare the pinned Zstandard/toolchain/request inputs through the [compiler experiment](../README.md), producing the logical-inputs `results.json`. Supply its path below; no absolute machine path is required. LLVM development headers and shared library must match the selected compiler version (measured LLVM 22.1.8), with OpenSSL development headers and a C++17 compiler. Generated assets go in ignored `_work`; a symlink to a volume with sufficient space is supported.

```sh
c++ -O2 -std=c++17 -I"$LLVM_INCLUDE" ast_fingerprint.cpp \
  -L"$LLVM_LIB" -Wl,-rpath,"$LLVM_LIB" -lLLVM-22 -lcrypto \
  -o _work/ast-fingerprint
GAIA_AST_HELPER="$PWD/_work/ast-fingerprint" python3 -m unittest discover -s . -p 'test_*.py'
python3 boundaries.py --clang "$CLANG" --ast-helper _work/ast-fingerprint --output _work/native-boundaries.json
python3 benchmark.py --inputs "$LOGICAL_RESULTS" --ast-helper _work/ast-fingerprint --output _work/native-main --trials 3
```

The harness clones a private project, preserves each exact compile request and inherited environment identity, and pins all other project files, the initial compiler dependency closure, compiler binary, linked libraries and symlink bindings before and after each source's experiment. Hashes are reread. The helper is pinned too. These checks are outside request timings and reported separately. They assume no racing writer; they neither capture every possible SDK lookup nor authenticate a mutable filesystem atomically. A production system needs admitted immutable inputs and backend identity.

Every scenario gets an independently compiled CLI object oracle; every measured output is compared byte-for-byte through SHA-256. The baseline seed and all oracle compilation costs are separate from requests. There is no hidden insertion of edited results, so each operation starts from the same baseline candidate. Initial object, AST and IR preparation stages are reported individually; only the representation needed by a chosen mode would be required in a real cache.

The boundary probes include packing, target attributes, inline assembly, debug lines, line-number values, macro stringification and a C++ template instantiation. A match from the unsafe AST mode is allowed to be wrong so the falsifying evidence survives. Stronger modes fail the run on an object mismatch. Main measurements use unchanged upstream Zstandard translation units plus clearly appended probes: unchanged, comment, leading blank lines, unused macro and a real emitted semantic change.

[Clang's AST introduction](https://clang.llvm.org/docs/IntroductionToTheClangAST.html) describes its source-oriented representation and AST dump. The [compiler command guide](https://clang.llvm.org/docs/CommandGuide/clang.html) describes its compilation stages. We infer no object-cache equivalence promise from either document; the counterexamples and independent objects determine the boundary here.

## Direct frontend candidate

The follow-up replaces diagnostic JSON entirely with a Clang `ASTFrontendAction`. It visits ordered translation-unit declarations (including headers), hashes declaration kinds/names and Clang `ODRHash` summaries, and separately reports frontend and AST walk time. Functions include bodies; record and enum definitions use their dedicated ODR routines. This is still a deliberately lossy candidate: each ODR summary is only 32 bits, and some code-generation details are absent. Combining those values with SHA-256 does not recover lost information. Exact current IR remains required before reuse.

```sh
c++ -O2 -std=c++17 -I"$CLANG_INCLUDE" -I"$LLVM_INCLUDE" direct_ast.cpp \
  -L"$LLVM_LIB" -Wl,-rpath,"$LLVM_LIB" -lclang-cpp -lLLVM-22 -lcrypto \
  -o _work/direct-ast
python3 boundaries.py --clang "$CLANG" --direct-ast-helper _work/direct-ast --output _work/direct-boundaries.json
python3 benchmark.py --inputs "$LOGICAL_RESULTS" --direct-ast-helper _work/direct-ast \
  --modes text guarded-ast ir ccache --scenarios unchanged comment unused-macro unused-type semantic \
  --ccache "$CCACHE" \
  --output _work/direct-main --trials 3
```

This first proof operates at translation-unit/object granularity. It neither patches individual functions nor proves that a source-level declaration edit has no downstream optimization or ABI effects. A compiler-native pipeline could reuse the just-built frontend/IR on a miss; this CLI prototype invokes a fresh full compiler after a failed guard, paying the frontend twice.

The comparison here is text invalidation versus semantic screening, not ccache competitiveness. [Ccache](https://ccache.dev/manual/latest.html#_the_preprocessor_mode) already uses preprocessed-input reuse and normally discards comments. A later matched control must distinguish that existing capability from reuse requiring deeper compiler representations.

The matched ccache control uses a fresh private cache per source, content-based compiler checks, default compression, and a baseline prime. Before each measured ccache request it restores that exact seed outside the timer, preventing repeated-edit cache hits. Direct/preprocessed-hit and miss counter deltas are retained; reset and priming costs are separate. Its dependency loader directory is supplied identically to every mode. The unused-typedef probe changes preprocessed bytes while potentially preserving emitted IR/object bytes, distinguishing deeper reuse from comment preprocessing.
