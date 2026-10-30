#include "handoff_bridge.cpp"
// Linux steady_clock and Python perf_counter share CLOCK_MONOTONIC here.
extern "C" uint64_t gaia_lifecycle_clock() {return now();}
