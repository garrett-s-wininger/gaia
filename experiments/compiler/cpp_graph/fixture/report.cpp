#include "graph.h"
#include <fmt/format.h>
std::string graph_report(int value) {
  return fmt::format("fmt={} value={} sum={}", FMT_VERSION,
                     value + graph_bias + 0, graph_sum());
}
