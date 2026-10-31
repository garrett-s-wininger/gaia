# Ruby startup findings

Warmed Bootsnap is a strong existing baseline. On the pinned real RuboCop inspection, normal require takes 538.41 ms and Bootsnap 428.23 ms. The first archive implementation still takes 486.03 ms in the matched comparison. One file and a precomputed catalog do not automatically improve the complete tool.

Profiling exposes a generic implementation cost: Ruby Digest spends about 61 ms verifying a 26.54 MB pack. The exact same full SHA-256 verification through OpenSSL takes about 12 ms in an isolated check. Charging OpenSSL loading and actual tool work, the refined pack takes 437.63 ms—about 48 ms below its Digest control, but still slower than Bootsnap in six of seven blocks. This is a hash-provider improvement, not a container win.

The producer retains 2,792 available bytecode entries, while the command uses about 996 and requests only 6.68 MB of payload. It still reads/verifies all available bytes and reconstructs index metadata. Peak RSS is roughly 93 MiB versus Bootsnap's 65 MiB. These facts motivate lazy representation research without establishing where another win will come from.

Offenses, source-feature identity and lifecycle agree under changing inputs. Representative direct, Bootsnap and packed instruction trees and binary hashes are identical under the same VM flags. The pack assumes immutable code inputs and private Ruby bytecode compatibility; it retains full verification and is not an editable-gem replacement.

See the [report](../../experiments/ruby_startup/results/initial/REPORT.md), [profile](../../experiments/ruby_startup/results/initial/loader-profile.json) and [validation](../../experiments/ruby_startup/results/initial/validation.json). Results are one Ruby tool/workload on warm filesystem pages, not a universal startup floor.
