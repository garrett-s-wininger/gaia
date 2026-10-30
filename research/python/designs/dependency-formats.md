# Python research design: dependency formats and the consumer load path

Classification: **Python-specific dependency-format/loading research**. This document preserves the original experiment design. Start with the [current review](../dependency-formats.md), [evidence register](../experiments.json), and [follow-up queue](../follow-up.md). Version resolution is a [separate Python track](../resolution.md); compiler invocation has its [own experiment](../../compiler/README.md).


Status: the first synthetic experiment has been implemented and run. Its design and limitations are below; [findings and measurements](../../../experiments/python/dependency_bundles/FINDINGS.md) report the observed outcome and [reproduction instructions](../../../experiments/python/dependency_bundles/README.md) describe the harness. This is not a claim of the best long-term ecosystem/format or a demonstrated platform-wide speedup. [PLATFORM_DESIGN.md](../../../docs/platform.md) owns the broader framing; source-control milestones remain separately scoped.

## Question and initial target

Can immutable dependency contents be loaded with fewer filesystem operations and less materialization cost, while preserving consumer behavior and compatibility?

Start with a small fixed set of pure-Python regular packages. Use an ordinary ZIP archive and the interpreter's built-in `zipimport` path. Python already imports `.py`/`.pyc` from ZIP, so this first attempt needs no new interpreter or archive format. Native extension modules are outside this archive path. [Python documentation](https://docs.python.org/3/library/zipimport.html).

Start with controlled fixtures containing imports, subpackages, relative imports, and package resources, followed by a small pinned real dependency set. Use the same interpreter and already resolved dependency versions in every layout. Do not implement version solving or installation hooks. Native implementation components remain Odin; a Python-specific harness/adapter naturally uses Python integration APIs. Existing standard tooling is acceptable for creating the first fixture before a native packer is justified.

## Loading integration

| Layer | Initial approach |
| --- | --- |
| Distribution input | A known already prepared pure-Python package set, with recorded origins/versions and required license/metadata files |
| Container | Standard ZIP; preserve logical package names and source/resource bytes |
| Module loading | Put the bundle on the controlled import search path and use the existing ZIP path-entry loader |
| Resource loading | Exercise `importlib.resources` reads through the package loader, without requiring ordinary paths |
| Custom integration | Introduce an `importlib` finder/loader/resource adapter only for a demonstrated gap or a later bundle implementation |
| Legacy escape hatch | Materialize an ordinary directory tree when a consumer genuinely needs host files, and account for that cost |

This is the required consumer hookup: packing inputs is insufficient if the measured program still imports from an unpacked directory. Verify loaded module origins and resource bytes so unrelated installed packages cannot silently satisfy the workload.

Python exposes finder/loader hooks through [importlib](https://docs.python.org/3/library/importlib.html). [Resource access](https://docs.python.org/3/library/importlib.resources.html) can read package data without physical directories; requesting an actual filesystem path may extract data. Measure such materialization explicitly. This experiment validates one loader surface, not arbitrary code that assumes `__file__` names a normal disk file.

## Keep the first pass small

Support regular packages and agreed module/resource cases first. Exclude native extensions, arbitrary install/build scripts, editable/live dependencies, namespace-package edge cases, entry-point discovery, and global environment replacement until needed. Record unsupported behavior rather than silently exporting every package back to loose files.

A ZIP bundle is a consumption fixture, not a claim that arbitrary wheel files can be concatenated or imported unchanged. Wheel installation includes semantics beyond archive membership; direct wheel import is discouraged by its specification. Preserve selected inputs without guessing distribution/install transformations. [Wheel specification discussion](https://peps.python.org/pep-0427/#is-it-possible-to-import-python-code-directly-from-a-wheel-file).

No FUSE mount, syscall interception, new package resolver/registry, new RPC stack, compiler fork, or permanent new bundle format is needed for this first attempt. Those additions must solve measured problems. A local filesystem still stores the bundle and runs the process; the experiment targets the dependency-discovery/read boundary.

## Comparison and measurements

| Case | Purpose |
| --- | --- |
| Existing extracted package directory | Compatible baseline with the same logical contents |
| Standard ZIP through built-in loading | Simplest direct-consumption path; compare uncompressed and supported compressed storage where useful |
| Export/materialization from bundle | Compatibility cost, reported separately and in an end-to-end scenario |
| Shared-resource ZIP loader | Implemented follow-up to repeated resource setup: reuse one resource archive handle while retaining stock module loading and the same container bytes |
| Persistent ZIP module/resource provider | Implemented process-lifetime follow-up: one open archive, retained index, metadata lookup without code reads, one read per imported module |
| Generic byte-access boundary | Implemented follow-up over the same stored bytes: common ZipFile/positional/mapped/resident reader, CRC-preserving access-only measurements, and fixed-loader comparison |
| Precomputed range index | Producer-validated JSON sidecar with names/ranges/CRCs/directories, pinned by a caller-supplied digest; compare per-open whole-bundle hashing with trusted local admission, retaining mapped read CRCs and the same language loader |
| Binary index encoding | Compare JSON with fixed little-endian records and a UTF-8 directory/basename pool, keeping bundle verification, payload checks and Python lookup structures fixed; experimental encoding only |
| Native accessor | Linux Odin prototype over the existing binary sidecar: named/ordinal scans, mapped views/copied bytes, compared with known-path file reads and controlled ZIP-index rebuilding |
| CPython/Odin byte provider | In-process C-extension shim connects Odin reads to the existing Python module/resource loader; compare synthetic imports and real offline pip resolution across directory, Python and Odin readers |
| Resolution diagnostics | Isolate module name/path discovery without code execution; profile compilation/import work and the separate pip dependency-version resolver including metadata/provider callbacks |
| New native container/Odin compiler integration | Deferred; access still uses standard ZIP and experimental sidecars; no Odin compiler-input hookup exists |

Measure preparation/packaging, storage footprint/file count, loading/import/resource time, CPU, peak memory, metadata/open/read operations, and application behavior. Report packaging-inclusive one-shot cost and repeated reuse separately. Include import-only and a small representative application operation to expose the fraction of time actually affected.

Use fresh interpreter processes for repeated import trials so `sys.modules` does not remove the work. Distinguish fresh-process and cold-storage conditions. Record Python version, machine/filesystem, cache policy, bytecode state, archive compression, and package sizes/counts. Do not claim cold cache without controlling it.

Bytecode is a material confounder: a source-only ZIP does not write `.pyc` back into itself. First compare identical source-only inputs with no pre-existing bytecode and no generated-bytecode advantage for the directory case; then optionally compare compatible precompiled inputs in both layouts. Keep bytecode generation cost and interpreter specificity visible. [ZIP loader behavior](https://docs.python.org/3/library/zipimport.html).

Count bytes as well as calls. Archive decompression, indexing/startup, copying, resource extraction, and Python execution can offset reduced filesystem metadata overhead. Instrumentation may perturb timings; use separate traced and untraced runs where needed. Small fixtures need no new native tool just to collect first evidence.

## Correctness and success criteria

- The intended modules load from the intended layout, with relative imports and source/resource contents equivalent.
- Missing modules/resources fail clearly; archive errors or unsupported cases do not silently fall back to an unmeasured tree.
- Logical origins remain useful for diagnostics even when no ordinary file exists; exact path strings need not match across layouts.
- Packing/export preserves the selected input set and rejects ambiguous duplicate/colliding names rather than choosing arbitrary entries.
- The comparison includes preparation/compatibility costs and records cases that do not improve.
- Report whether fewer filesystem operations improve actual latency, memory, or disk footprint on the available laptop. No speedup is assumed in advance.

A useful negative result is acceptable: it can show that startup, source compilation, decompression, or application work dominates. The next design step follows evidence, not a commitment to replace ZIP regardless of results.

## What this informs next

The experiment should identify which information a consumer needs beyond path/bytes: module identity, resource access, origin/diagnostic names, dependency metadata, and optional host-path materialization. Generalize only demonstrated needs into an open input-access contract. An Odin source collection, a compiler input provider, or another ecosystem can then be the next independent consumer.

The wider protocol must eventually support batched access and compiler/tool sessions where beneficial; copying POSIX one-file-at-a-time calls into RPC is not the desired endpoint. This first ZIP/loader attempt establishes a behavioral/performance baseline rather than freezing that protocol.
