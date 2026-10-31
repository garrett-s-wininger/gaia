#include "graph.h"
#include <array>
#include <numeric>
int graph_sum() {
  std::array<int, 3> values{{1, 2, 3}};
  return std::accumulate(values.begin(), values.end(), graph_bias);
}
