# An explicit information model separates useful IDs from protocol overhead

The counting model assumes a known client inventory of N keys, known target cardinality and known added/removed counts. Unknown added IDs are uniformly selected from the remaining 256-bit universe. Its conditional information is:

`log2(C(2^256 - N, added) * C(N, removed))`.

For N=3,931 and three additions/three removals, that is 798.65 bits, approximately 99.83 bytes. The measured prototype encodings send 251,632 bytes for full inventories, 9,030 for the hierarchy and 608 for IBLT. This quantifies room between a particular information model and each representation; it does not prove an optimal implementable protocol.

The model excludes authentication, framing, summary construction, other shared dictionaries, payload encoding and computational cost. Test IDs are deterministic hashes, not measured independent entropy. Different side information changes the bound. No latency or physical problem floor follows, and payload transfer may itself communicate information.

All 36 encoding/model comparisons remain above the declared model bound. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), [reproduce](../../README.md).
