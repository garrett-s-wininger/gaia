# Cancel queued obsolete analysis and reject stale publication

An actual one-worker Python executor receives a controlled burst of twelve admitted generations of a real source module. Every executed job parses/compiles its captured changed source and queries detached facts. An explicit barrier lets the entire burst queue before work starts, making cancellation deterministic.

| Policy | Complete burst median | Timed jobs executed | Queued jobs cancelled | Stale completed results rejected |
| --- | ---: | ---: | ---: | ---: |
| FIFO | 278.45 ms | 12 | 0 | 11 |
| Cancel obsolete queued requests | 26.69 ms | 1 | 11 | 0 |

Five blocks preserve exactly one current accepted publication, generation twelve. Two after-clock guard queries per operation additionally prove that a captured running result is rejected after a newer edit, a current syntax error is returned, and an update with the old expected generation fails. The raw counters distinguish those guard queries from timed tasks.

This demonstrates real queued-work avoidance and current-result validation. It is not a natural typing trace, a percentile result, arbitrary preemption, a GUI/LSP implementation or cancellation of operations with external/durable effects. Initial base admission/fact preparation is reported separately; the burst clock includes byte updates, scheduling, worker analysis, replies and executor shutdown. Already-running work still requires a generation check even when queued futures can cancel.

The selective-work mechanism is more important than parsing speed in this deliberately queued case. A production scheduler must also measure mixed clients, fairness and starvation, and preserve required durable operations. [Reproduction](../../README.md), [summary](summary.json), [validation](validation.json), [provenance](provenance.json), [raw identity](raw-identity.json), ignored [observations](results.json).
