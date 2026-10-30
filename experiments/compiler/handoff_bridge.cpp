// Linux/LLVM-22 research adapter. The old pool remains the default build.
#define GAIA_DIRECT_HANDOFF 1
#include <dlfcn.h>
#include <atomic>
#include <optional>
#include <unordered_map>
#include "pool_bridge.cpp"
