# Created headers need a correct cache boundary

The first integration control failed its output oracle when an optional header appeared. Removing the object forced Ninja to invoke ccache, but the existing direct manifest still returned the previous absent-header object and depfile. The run was rejected before making a performance comparison.

A controlled replay with ccache 4.14.1 confirms a logged `direct_cache_hit` whose object differs from uncached Clang. Preprocessor mode (`CCACHE_NODIRECT=true`) produces the stock object and a depfile containing the new optional header. [Summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json).

The corrected integration uses preprocessor mode only for the fixture's declared membership changes: optional appearance/removal and include shadowing. Ordinary edits retain direct mode. It also invalidates the known probe TU output so Ninja actually invokes the cache. These are explicit fixture hints, not a general filesystem-discovery implementation. This result does not establish that all ccache configurations have the same behavior.

[probe_cache.py](../../probe_cache.py) accepts a prepared project/cache immediately after the failed created-header operation. The ignored raw retains command arguments and both detailed cache logs. For reproduction from scratch, use the [workspace fixture](../../README.md), seed its baseline, then replay source, include rewiring, unused-header and active-header changes before creating `gaia/early/gaia_optional.h`. Preserve the direct manifest until running the diagnostic. A corrected complete run is not that failure-state fixture.
