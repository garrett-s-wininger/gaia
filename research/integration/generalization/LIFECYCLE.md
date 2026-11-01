# First requests and separate resource diagnostics

These clocks are separate from the edit replay. See [the report](README.md) for source scope, rejected attempts and queue fallbacks.

## First request

Seconds, median [minimum–maximum], three fresh-process/empty-compilation-cache observations on a prepared graph. OS page cache is warm; download/configuration are excluded. Build and independent index run concurrently in the control.

| Target | Shared serial | Shared queue | Ninja + ccache + index |
| --- | ---: | ---: | ---: |
| xxhash | 0.752 [0.707–0.759] | 0.675 [0.667–0.682] | 1.023 [1.012–1.103] |
| spdlog | 11.621 [11.308–11.740] | 9.444 [9.290–9.642] | 12.597 [12.242–12.815] |
| re2c | 23.831 [23.567–23.946] | 23.989 [23.540–24.289] | 30.340 [30.036–30.550] |
| curl | 17.194 [17.082–17.227] | 16.475 [16.451–16.656] | 30.175 [30.149–30.493] |

## Resource scenario

One instrumented removal of `NDEBUG` after the final first-request observation. Sampling begins after its startup clock stops. These are observed aggregate descendant PSS peaks, not memory bounds or full-session peaks. The controller is separate. CPU includes the native provider, waited backend children and completed linker/build subprocesses; process tick precision is limited.

| Target / path | Descendant PSS (MiB) | Controller PSS (MiB) | Process-tree CPU (s) |
| --- | ---: | ---: | ---: |
| xxhash / serial | 149.5 | 20.6 | 0.69 |
| xxhash / queue | 115.0 | 20.6 | 0.74 |
| xxhash / ninja-ccache | 132.2 | 20.7 | 0.70 |
| spdlog / serial | 340.4 | 22.2 | 11.31 |
| spdlog / queue | 428.0 | 22.5 | 12.68 |
| spdlog / ninja-ccache | 393.1 | 22.7 | 17.51 |
| re2c / serial | 236.2 | 28.4 | 25.30 |
| re2c / queue | 236.2 | 28.6 | 25.15 |
| re2c / ninja-ccache | 178.3 | 28.4 | 20.78 |
| curl / serial | 515.0 | 42.3 | 18.72 |
| curl / queue | 508.0 | 42.3 | 28.97 |
| curl / ninja-ccache | 514.6 | 42.3 | 40.98 |

The sampler walks child lists for every process task, including worker-thread subprocesses. Raw timestamps, sample counts and actual intervals are retained. re2c’s queue path is serial fallback. Only one resource observation per path is collected; it is not a distribution or a cold-disk test.
