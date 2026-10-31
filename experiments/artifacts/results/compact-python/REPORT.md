# Retained binary metadata with matched packed/ZIP integrity

Run `20261031T021308.848988Z`; five randomized blocks after one correctness warmup. All 48 end-to-end operations pass, with 40 retained timing observations.

## Result

The prior packed startup regression was largely avoidable metadata construction. A retained mapped binary index reduces reader setup from **52.71 to 1.20 ms** cold and **53.20 to 1.19 ms** on reuse. Full Python child time falls **333.03→285.32 ms cold** and **329.71→284.89 ms reuse**, with compact pack beating old pack in every paired process observation. Reuse acquisition/install plus execution improves **368.05→325.16 ms**, also five of five paired wins.

That work has a real cold cost. Creating and validating the retained index takes approximately **96.96 ms** for pack and **92.29 ms** for ZIP. Packed cold complete cost rises **410.23→475.94 ms**, losing all five comparisons with the original pack. Production of the retained consumer index is charged during installation, not moved outside the clock.

Under **matched SHA-256 plus CRC32 on every read**, compact pack and compact ZIP process times are close: cold **285.32/293.56 ms**, reuse **284.89/280.81 ms**. Pack wins only three of five cold process pairs and two of five reuse pairs. It loses **complete** acquisition/install+execution to compact ZIP in every cold and reuse block. Removing JSON/table reconstruction closes the startup gap; it does not demonstrate an intrinsic container-format startup advantage.

## What changed

The old loader reparses its logical-name JSON lock and local locator index, reconstructs entry/module maps and walks every logical path to rebuild directory tables on each process. The separate [constructor diagnostic](setup-profile.json) records 28,773 parent-iteration operations and 24,755 parsed-path constructions in that path-heavy setup. Its intrusive cumulative times overlap and are not benchmark contributions. Separate uninstrumented diagnostic lock parse/cache load are 10.46/8.52 ms; the randomized setup medians above are the comparison evidence.

The new versioned consumer index retains fixed-width file/module/directory/child tables and a UTF-8 pool. Lazy mappings use binary search without constructing thousands of Python records at open. Both ZIP and pack use the **same reader**, mapped payload access, module/resource provider, per-read SHA-256 and CRC32, full-index pin, expected lock binding and local stat identity checks. One immutable open lifetime lasts through the normal workload and shutdown. The original ZIP/CRC and pack/SHA implementations remain explicitly separate controls.

## Complete observations

Milliseconds; independent medians need not add. “Install” includes acquisition. “Process” includes fresh Python startup, common adapter preparation, real workload validation, provider cleanup and normal interpreter shutdown. No early-exit shortcut is used.

| Profile / reader | Install | Full process | Complete total | Reader setup |
| --- | ---: | ---: | ---: | ---: |
| cold / old-zip | 44.65 | 287.67 | 331.39 | 4.73 |
| cold / old-pack | 77.13 | 333.03 | 410.23 | 52.71 |
| cold / compact-zip | 138.18 | 293.56 | 430.36 | 1.17 |
| cold / compact-pack | 180.23 | 285.32 | 475.94 | 1.20 |
| reuse / old-zip | 16.66 | 266.02 | 282.66 | 4.76 |
| reuse / old-pack | 39.33 | 329.71 | 368.05 | 53.20 |
| reuse / compact-zip | 16.15 | 280.81 | 297.02 | 1.15 |
| reuse / compact-pack | 39.93 | 284.89 | 325.16 | 1.19 |

The old ZIP uses its prior CRC-checked reader; old pack uses its prior SHA-checked reader. Those rows show the effect on existing implementations and are not a matched integrity-policy pair. Compact ZIP adds SHA-256 checks and lazy mapped-table lookups versus old ZIP. Its reuse process is 280.81 versus 266.02 ms, losing all five pairs. That difference cannot be assigned wholly to SHA-256: compact lookup/provider code also differs.

Both matched compact consumers make **475 reads / 6,063,442 bytes** and execute the same **455 dependency modules**. Their read clocks (file lookup plus mapped copy) are about **4.65/4.25 ms pack/ZIP**, and SHA-256+CRC clocks about **4.81/4.73 ms**. These subclocks exclude earlier module-finder lookups, code unmarshalling/execution and framework work. The field name `native_timings` is inherited from the existing worker compatibility API; this implementation is Python, not native.

## Integrity and admission boundaries

Acquisition still verifies the trusted logical/package lock, checks cached content, requests only missing hashes, verifies returned bytes, seals/publishes representations and writes a complete receipt. No remote collection manifest is requested. Compact-index installation uses the trusted logical lock and admitted representation, verifies each distinct logical content hash, computes CRCs, constructs bounded tables and fully validates the derived index before publishing its trusted pin receipt. On later opens the full compact index is rehashed, header geometry and expected lock are checked, and all data descriptors must match local stat identities. Table/string/data accesses remain bounded. Both compact variants then validate SHA-256 and CRC32 for **every** imported/resource read; no admitted-session mode skips these checks.

Full cold install includes that index construction and validation. Reuse verifies the acquisition cache and reopens the retained index; zero network requests are permitted, with the endpoint deliberately unavailable. Pack acquisition still parses a 599,421-byte file/hash lock and its JSON cache locators, versus a 770-byte two-artifact ZIP lock. Their content transfers remain **28,590,229 versus 29,661,933 bytes**. Whole-operation pack minus compact ZIP is **+19 to +65 ms cold** and **+16 to +43 ms reuse** across paired blocks, despite near-parity child startup. The remaining gap is primarily before the child, not removed by the consumer index.

## Scope, stability and follow-up

The same pinned Django REST bytecode inputs, application, expected versions/resources and prior worktree fixture are used. There are 4,018 logical files, 3,931 distinct content hashes and 1,026 available modules. The compact index is approximately 673 KiB for either representation. Input bytecode/ZIP/index production and server admission are excluded pre-existing producer setup; new consumer-index construction remains included. Payloads are served from separate-process loopback memory and filesystem pages are warm. This is not WAN or cold-storage evidence.

Each case has five shuffled block observations. Full-process max/min ratios range **1.04–1.16**, much smaller than the [preserved prior drifting run](../locked-python/REPORT.md), but still relevant for small differences. [Paired deltas](summary.json) retain every block; no universal pack-versus-ZIP startup win is claimed. Prior negative data is neither rewritten nor pooled.

Tests cover mapped lookups/resources/children, ownership after close, index pin/lock binding/version/truncation, changed data identity, corruption during an open session, equivalent pack/ZIP bytes and independent enforcement of both SHA-256 and CRC32. All **65 tests** pass. The [full-suite log](correctness-tests.txt), [independent compact tests](compact-correctness-tests.txt) and [validation](validation.json) retain correctness evidence. Raw observations and frozen measured sources stay ignored and are identified by the evidence manifest.

This remains a bounded regular pure-Python/compatible-bytecode consumer, not a general installer. Local immutable admission assumes no hostile concurrent writer; hashes are identities, not authentication. Atomic rename is used without fsync, and retained indexes bind local stat identities and need rebuilding after representation replacement/compaction. Native/namespace wheels, arbitrary host-path consumers, uploads, eviction and production crash recovery are unimplemented.

The next useful optimization target is the **acquisition descriptor/cache metadata path**, while preserving all requested-content verification and publication. An end-to-end compact descriptor/locator contract could avoid reparsing thousands of JSON objects for an already pinned hash set. A native implementation is justified only after that complete-operation boundary is measured; another container rewrite alone has no demonstrated startup benefit.
