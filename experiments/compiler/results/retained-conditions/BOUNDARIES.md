# Retained-producer boundary checks

One matched observation per engine and scenario, using the final shared sized-reader implementation. These are correctness/work-count checks, not a statistical speed comparison.

The high-fanout-header case recompiles 26 readers; flags and clean cases compile all 31 objects. Clean resets the retained producer to empty before timing, exercising reconstruction. Every actual retained export is byte-equal to the original reference index. All six libraries and 186 object checks match independent CLI references, runtime probes and expected work counts.

See [compact observations](boundary-summary.json), [validation](boundary-validation.json) and the [main report](REPORT.md). Raw observations are the ignored local artifact `boundary-raw/results.json`, registered in the repository evidence manifest.
