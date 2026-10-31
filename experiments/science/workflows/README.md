# Shared preparation in adjacent workflows

This study tests five adjacent operations: PNG processing, declared native-module replacement, private source workspaces, current editor feedback and actual upstream documentation tests. These are bounded implementations using existing ffmpeg, Python and Odin APIs. They do not define production services or public protocols.

See the [human findings](../../../research/science/workflows/findings.md), [next questions](../../../research/science/workflows/prospects.md) and [run index](../../../research/science/workflows/experiments.json). Raw `results.json` files remain ignored; reports, validation, identities and small diagnostics are versioned.

## Build and run

Requirements: Linux, Odin, a C linker driver, ffmpeg and Python 3.14 with the installed standard-library sources. No Pillow, vips, ImageMagick, pytest or external database server is used. The source corpus is sixteen named CPython files; another runtime/source version is a new measurement. Asset inputs are actual system PNGs from QEMU, GnuTLS and Ogg documentation; input hashes are recorded, rather than copying vendor files into this repository.

Run from the repository root. Choose an absolute disposable `WORK` directory and a shared advisory `LOCK`. Generated object files, libraries, image outputs and copied namespaces belong outside source history.

```sh
mkdir -p "$WORK"
odin build experiments/science/workflows/module_host.odin -file -o:speed -build-mode:obj -out:"$WORK/module-host.o"
cc "$WORK/module-host.o" -o "$WORK/module-host" -lm -ldl
odin build experiments/science/workflows/module.odin -file -o:speed -reloc-mode:pic -build-mode:obj -define:VERSION=1 -define:FACTOR=2 -out:"$WORK/v1.o"
cc -shared "$WORK/v1.o" -o "$WORK/v1.so" -lm
odin build experiments/science/workflows/module.odin -file -o:speed -reloc-mode:pic -build-mode:obj -define:VERSION=2 -define:FACTOR=3 -out:"$WORK/v2.o"
cc -shared "$WORK/v2.o" -o "$WORK/v2.so" -lm
odin build experiments/science/workflows/module.odin -file -o:speed -reloc-mode:pic -build-mode:obj -define:ABI=2 -define:VERSION=3 -out:"$WORK/bad.o"
cc -shared "$WORK/bad.o" -o "$WORK/bad.so" -lm
python3 -B -m unittest discover -s experiments/science/workflows -p 'test_*.py'
python3 -B experiments/science/workflows/run.py --work "$WORK/run" --output "$OUTPUT" --native "$WORK" --lock "$LOCK" --trials 5
```

One complete measured operation acquires/releases the lock; preparation and output authentication do not monopolize the whole matrix. The lock coordinates research timings but does not reserve the entire host against unrelated work. Source/tool checks detect accidental changes across each matrix. They are not an atomic admission guarantee against hostile writers or system upgrades.

## Assets: compare a competent combined pipeline

Three actual installed PNG assets produce 128, 256 and 384-pixel square outputs through the same bilinear/RGBA/PNG settings. The operation includes child startup, input reads, transformations, encoding and output files. Four arrangements compare independent sequential processes, three independent parallel processes, ffmpeg's existing multi-output filter graph, and decoding RGBA once before copying it to three parallel encoder processes.

Decoded RGBA output hashes must match. PNG encoding metadata is not required to be byte-identical. Oracle decoding/hash work is outside all timing clocks. The raw-buffer path charges decoder startup, Python-owned buffer retention and pipe copying; it does not pretend those copies are free. Its retained payload count excludes native/process/transient memory. The images are icons/diagrams, not a photographic/video performance claim. There is no new native image codec here.

`hardware.py` attempts actual CUDA initialization and Vulkan upload/scale/download, retaining failure diagnostics. A backend listed by ffmpeg is not evidence of an accessible device, and a successful software Vulkan provider would not establish GPU performance. No driver settings or device permissions are changed.

## Native execution: a declared replacement boundary

The Odin host loads modules with an explicit scalar ABI, version and operation. Host-owned integer state survives two compatible replacements in a 48-request serial trace. Controls start a fresh host per request, feed the same complete trace through one existing batched host, or send requests online to a retained host. Each arrangement starts with the same declared state and produces identical results.

The host validates ABI/version/symbol availability before selecting a candidate. Missing libraries, incompatible ABI and wrong expected version leave the prior module/state usable. Modules are trusted and pure apart from the declared state pointer; loading arbitrary code can execute constructors before validation. This does not demonstrate rollback of external effects, live pointers/callbacks, concurrent calls or state migration. Replacement happens at serial quiescent points. Initial module/host compilation and linking are preparation, outside these execution clocks.

## Workspaces: shared facts versus private reconstruction

Four scripted actors consume sixteen actual CPython source files. Queries use detached immutable names/locations and actual Python parse/compile validation. Each actor performs four private changes. The controls are:

- Independent materialized namespaces with private incremental per-content fact caches.
- Materialized namespaces using immutable hardlinks, atomic copy-on-write replacement and a shared content/fact cache.
- Logical private overlays using a shared immutable base/fact cache.

The hardlinked shared-cache control avoids attributing its existing sharing capability to a new provider. Ordinary-file namespaces and logical views have different compatibility contracts; omitted full materialization is not free access for an unchanged filesystem-only tool. Source changes are explicitly reported in every arrangement. No adapter discovers unreported filesystem changes.

Initialization, updates and queries are measured. Required physical cleanup is reported separately and can be added for the complete cycle; file-footprint diagnostics and independent identity checks are outside operation clocks. Logical cached payload bytes count entries, not unique Python allocation or process RSS. A separate fresh-process diagnostic reports Python traced peak and whole-process high-water RSS, including transient parsing work. Those instrumented runs do not supply latency claims.

All four actors are hosted in one Python provider process. This is a private-workspace service boundary with deterministic clients, not a measurement of several complete AI agents or four separate process heaps. The trace retains a bounded number of changed-result cache entries; it does not establish a long-lived retention policy.

## Editor feedback: cancel queued work and reject stale publication

An actual `ThreadPoolExecutor` receives twelve successive input generations. One explicit barrier holds the worker while the burst queues. The ordinary control executes all requests; the cancellation policy cancels obsolete queued futures. Every executed task parses/compiles its captured changed source and queries current facts. Only the current generation may publish, and a later edit invalidates the stored publication under the workspace lock.

The barrier makes a queue scenario deterministic. It is not natural typing, a latency percentile, a GUI/LSP implementation or arbitrary-effect cancellation. Running work still needs a generation check even when queued futures can cancel. Syntax-error observations and conflicting expected-generation updates are correctness controls.

## Real upstream tests: retain an existing API

The workload runs installed CPython `difflib`, `statistics` and `fractions` documentation examples: 189 attempts per complete module pass, with the same explicit Decimal context. Nine requests produce three complete passes per session. Compare fresh interpreters per request, one existing batched `doctest` API process, and an online retained process.

All expected examples must pass and counts/tokens match. A stale source pin is rejected; a deliberately failing example is followed by successful real examples in the same process. This is a genuine upstream documentation-test subset, not the complete CPython regression suite or a production application. Doctest copies example globals; the experiment does not establish reset of arbitrary framework/database/network state. Existing batch execution is the strong control for preparation sharing.
