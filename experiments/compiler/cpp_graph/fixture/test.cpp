#include "graph.h"
#include <cstdio>
int main() {
  auto report = graph_report(7);
  if (graph_sum() != 6 + graph_bias || report.find("fmt=120200") != 0) return 2;
  std::printf("ok:%s bias=%d\n", report.c_str(), graph_bias);
}
