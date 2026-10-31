# Ruby tool startup: RuboCop loading and precompiled code

This experiment compares the real pinned RuboCop CLI under normal loading, warmed Bootsnap and a producer-built require catalog/ISeq pack. Every invocation disables RuboCop's server and lint-result cache, inspects changing Ruby source, emits JSON offenses and exits normally.

The pack is an interpreter-specific code artifact. It retains compiled Ruby instructions and availability metadata, not initialized cops, parsed lint inputs or lint results. Native extensions, source inspection and config/resources continue to use their ordinary loaders/files. Its package-source roots are admitted as immutable; rebuilding is required when those inputs/runtime/options change. It is not an editable-gem invalidation implementation or a standard archive format.

Generated gems, native extension builds, code/cache artifacts and full observations live in ignored `_work`. The repository may use a local `_work` symlink to an ignored SSD cache; this is environment setup, not a required absolute destination.

## Reproduce

Use Ruby 3.4.10 with its native extension build prerequisites. The acquisition manifest records RuboCop 1.92.2, Bootsnap 1.26.1 and resolved archive pins. Acquire exact archives and install into an isolated directory, then measure:

```sh
python3 -B experiments/ruby_startup/fetch_gems.py --destination /path/to/research
python3 -B experiments/ruby_startup/benchmark.py \
  --gems /path/to/research/gems --trials 7 \
  --output /path/to/new/ruby-run
```

Use a new output directory. The driver constructs/precompiles its pack separately, records first Bootsnap cache creation, warms all controls and then runs randomized matched blocks. All clocks include fresh Ruby startup, loader setup, actual RuboCop work, observations, normal exit and parent wait. Parent JSON/offense/feature comparisons are outside the clock. The filesystem page cache is warm; first compile-cache creation is distinct from storage-cold operation.

`packed_loader.rb` verifies the complete pinned pack before interpreting its trusted Marshal index or ISeq bytes. Header/size/index/entry/runtime/compile-option checks reject incompatible artifacts. An unknown earlier load-path directory forces normal resolution; changing load-path strings invalidates the positive lookup cache. This is deliberately a bounded immutable-input experiment, not arbitrary Ruby require compatibility.

The [report](results/initial/REPORT.md) preserves the original negative comparison and OpenSSL provider refinement. Both pack modes verify identical complete bytes and SHA-256 pins; OpenSSL initialization stays inside the child clock. [Guard tests](test_loader.py), [bytecode equivalence](check_bytecode.rb) and [stage diagnosis](profile_loader.py) accompany the matched observations.

For optional diagnostics and guards against a custom run location:

```sh
python3 -B experiments/ruby_startup/profile_loader.py \
  --gems /path/to/research/gems --source /path/to/new/ruby-run \
  --output /path/to/new/profile
GEM_HOME=/path/to/research/gems GEM_PATH=/path/to/research/gems \
  ruby experiments/ruby_startup/check_bytecode.rb /path/to/new/ruby-run
GAIA_RUBY_TEST_RUN=/path/to/new/ruby-run GAIA_RUBY_GEM_HOME=/path/to/research/gems \
  python3 -B -m unittest discover -s experiments/ruby_startup -p 'test_*.py' -v
```

The profile is intrusive and must not be mixed with main latency samples. Interpreter instructions and native extensions must be regenerated for the machine/runtime being tested. The recorded original profile has its own frozen source hashes.

[Experiment notes](FINDINGS.md) retain the detailed comparisons behind the linked research review and reports.
