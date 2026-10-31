#include "graph.h"
#include <cstdio>
int main() {
  auto report = graph_report(42);
  std::printf("%s bias=%d\n", report.c_str(), graph_bias);
}
