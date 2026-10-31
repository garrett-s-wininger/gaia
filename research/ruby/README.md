# Ruby startup research

The first experiment runs the real RuboCop CLI under ordinary loading, warmed Bootsnap and an immutable indexed ISeq pack. It separates generic loading/verification work from lint-result reuse and retains normal process exit.

- [Findings](findings.md): results and their practical limits.
- [Prospects](prospects.md): useful bounded next questions.
- [Run index](experiments.json): reports, validation and local raw identities.
- [Code and reproduction](../../experiments/ruby_startup/README.md).

This is Ruby-specific runtime/cache evidence. It selects no portable dependency or bytecode protocol.
