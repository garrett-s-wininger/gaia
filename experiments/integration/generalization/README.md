# Frozen reuse on additional upstream projects

This continuation tests whether the earlier Ninja result survives different target graphs. The [freeze record](freeze.json) pins the existing reuse implementation, limits and scenarios before source acquisition. The scheduling overlay changes backend handoff, not reuse eligibility. The human interpretation and measured tables live in the [research report](../../../research/integration/generalization/README.md).

The projects are xxHash 0.8.3 (`xxhsum`), spdlog 1.16.0 (`example`, with bundled fmt), re2c 4.2 (`re2c`, with upstream syntax generation enabled), and curl 8.16.0 (`curl`, static libcurl with discovered system dependencies). These are pinned versions rather than claims about current releases. Tests, unrelated examples and unused alternative targets are outside the selected target graphs. The adapter admits each target's observed source/header closure; it does not ingest the entire repository or model arbitrary future headers.

## Reproduce

Acquire the official archives listed in the [acquisition manifest](acquisition.json), verify their SHA-256 values, and extract them under `experiments/_work/generalization/sources/`. Verify the CMake archive against its official SHA-256 manifest before extracting. Acquisition uses official [xxHash](https://github.com/Cyan4973/xxHash/releases), [spdlog](https://github.com/gabime/spdlog/releases/tag/v1.16.0), [re2c](https://github.com/skvadrik/re2c/releases/tag/4.2), [curl](https://curl.se/download/), and [CMake](https://github.com/Kitware/CMake/releases/tag/v4.1.2) sources.

Use the Clang 22 and comparison-tool preparation described in the [workspace reproduction guide](../workspace/README.md). CMake 4.1.2 is local to the ignored cache. No system installation is required. Build the frozen serial host with [the existing generator](../refinements/refine_host.py); its generated source must match the pinned SHA-256 in the research report. Paths in these commands are relative to the repository root.

```sh
python3 -B experiments/integration/generalization/prepare.py
python3 -B experiments/integration/generalization/queue_host.py \
  --source experiments/_work/refinements/host-final.cpp \
  --passes experiments/science/compiler/process_passes.inc \
  --output experiments/_work/generalization/queue.cpp
/usr/lib/llvm22/bin/clang++ -O2 -std=c++17 \
  -I/usr/lib/llvm22/include \
  -Iexperiments/compiler/_work/toolchain/usr/lib/llvm22/include \
  experiments/_work/generalization/queue.cpp \
  -L/usr/lib/llvm22/lib -Wl,-rpath,/usr/lib/llvm22/lib \
  -lclang-cpp -lLLVM-22 -pthread \
  -o experiments/_work/generalization/queue
GAIA_QUEUE_HOST="$PWD/experiments/_work/generalization/queue" \
  python3 -B -m unittest discover \
  -s experiments/integration/generalization -p 'test_*.py' -v
python3 -B experiments/integration/generalization/run.py \
  --trials 3 --output experiments/_work/generalization/matrix-v2
python3 -B experiments/integration/generalization/startup.py \
  --trials 3 --output experiments/_work/generalization/startup-v2.json \
  --resources experiments/_work/generalization/resources-v2.json
python3 -B experiments/integration/generalization/summarize.py \
  --input experiments/_work/generalization/matrix-v2 \
  --output research/integration/generalization
python3 -B experiments/integration/generalization/summarize_lifecycle.py \
  --startup experiments/_work/generalization/startup-v2.json \
  --resources experiments/_work/generalization/resources-v2.json \
  --output research/integration/generalization
```

The replay temporarily changes ignored upstream sources, Ninja flags and compiler launchers, restoring them on exit. Run it exclusively against these generated builds, using new output names and their corresponding fresh cache namespaces. Primary timings, first-request timing and instrumented resource diagnostics must run sequentially. The runner uses the fixed serial host and a queue executable under the ignored work directory; the freeze record checks their expected serial implementation pins. Regenerating a compiler binary on a different toolchain changes its binary hash and requires recording a new environment, rather than claiming byte-identical reproduction.

## Compared paths and limits

The serial path shares frontend observations, complete declaration facts and objects. The queue path allows one backend child to overlap the next frontend in a single parent process. Ninja + ccache builds with `-j1` while a separate cached frontend indexes with the same frozen reuse rules; its maximum active worker budget is two, matching the queue. Serial shared work uses one. There is no claimed comparison with Ninja using all available laptop cores.

The queue is a Linux, trusted fixed-toolchain fork experiment. It checks that its parent is single-threaded before forking, uses copy-on-write state and private object staging, resets child signal handlers, drains child IPC before waiting, and publishes an object only after successful completion. It supports an explicit object-only argument subset; rejected options fall back to serial execution and are recorded. Source edits and scans require a drain first. The replay submits distinct target outputs until the drain; it does not submit competing requests for one output, PCH/module builds, plugins, arbitrary compiler side effects or cancellation.

Frontend events are useful before object completion. An acknowledgement with `backend_pending: true` is not build success. The final drain propagates backend failures before archive/link commands run. Tests cover physical object equality, deferred failure/recovery, admission rejection while pending, and shutdown cleanup. Existing compatibility and reuse tests also run against the overlay with deferred scheduling disabled.

The host still has a 4 MiB request limit, a 64 MiB/10,000-file admitted source limit, and 256 result entries with eight versions per group and 128 MiB counted payload. Initial admission uses bounded chunks; a single oversized source is rejected. These limits are not total process memory quotas. The helper does not tune them to the new projects.

## Measurement scope

Each trace starts with a populated initial version and a fresh ccache directory for that trial. The adapter verifies the rendered upstream compiler commands actually invoke ccache and that priming produces cache calls and stored results. A separate real-CMake regression test deletes an object and requires a genuine cache hit with identical bytes. Ccache uses direct mode, compression, a 5 GiB disk limit, content-based compiler checks and no sloppiness; base-directory rewriting is disabled to preserve the original compiler's path semantics. Its disk cache and the native bounded in-memory history are different cache topologies and budgets.

The trace includes no-op, controlled source/header comment and declaration additions, an unused numeric definition, removal of `NDEBUG`, an optimization-level change and return to an earlier state. The header is selected by greatest observed source-header fanout before timing. These probes are controlled invalidation classes, not sampled natural development histories. Removing `NDEBUG` does not guarantee that every target's emitted code changes.

Only re2c has the explicit generated-input case. Its actual `stx2cpp.py` command runs through the upstream Ninja rule; generator work and subsequent admission are included. Bootstrap source copies are upstream build behavior. Other projects are marked not applicable rather than assigned synthetic generator work.

The main clock includes changed physical source writes, generator preparation, source admission, reuse checks, required compilation/indexing, output restoration and archive/link commands. Facts readiness is a separate component clock beginning at its scan, excluding preceding admission and generation. Setup is reported separately. Oracle work, correctness hashes and result-file writes are outside the primary clock. Alternate trial orders reduce a fixed order bias; three observations are descriptive, not a statistical population estimate.

The matrix's priming procedure initializes the physical build and independent index sequentially. It is not a fair startup estimate. The separate first-request study starts fresh processes and compilation caches on a prepared graph with generated inputs retained, and runs the physical build and index concurrently. It includes process creation and admission, while excluding download/configuration and cold storage. These first requests do not establish amortization over repeated complete sessions; cache history changes across those sessions.

With `--resources`, the final first-request trial also runs an instrumented removal-of-`NDEBUG` operation after its timing clock stops. This reuses the initialized process without including sampling in the first-request measurement. Aggregate descendant PSS, controller PSS and process-tree CPU are separate diagnostic outputs; resource-case objects and facts must also agree with the physical control. The standalone [diagnostic runner](diagnose.py) can repeat that resource scenario independently with a new output/cache name. Sampled peaks are observations, not memory bounds, and this one scenario is not a peak-memory measurement of every replay operation.

Before replay, every state is checked with physical Clang objects and a separate uncached physical frontend. Replayed object bytes, dependency-file bytes and complete fact digests must agree; every required link command must succeed. The independent index is checked against those same complete facts. This does not establish correctness outside the admitted target graphs, fixed SDK, tested states and argument contract.

The consumer remains the existing declaration-summary and `gaia_` prefix probe. It verifies complete record digests and the controlled additions, but it is not a sample of real editor queries, source-map updates or full-index transfer. New projects broaden compilation and invalidation structure; they do not by themselves broaden that consumer workload. A production editor or analyzer remains a separate integration test.
