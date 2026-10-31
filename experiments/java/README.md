# Java ecosystem research

Two tracks use regular JVM bytecode with different preparation boundaries:

| Track | Question | Human review |
| --- | --- | --- |
| [Framework startup](startup/README.md) | How much can supplied Groovy/Picocli class knowledge and prepared framework data reduce fresh startup? | [Findings and prospects](../../research/java/README.md) |
| [Managed compilation](compiler/README.md) | What do a compact runtime, a trained compiler cache and bounded whole-target workers buy over CLI compilation? | [Findings and prospects](../../research/compiler/jvm/README.md) |

Framework startup uses supplied class knowledge without application training. Compiler research separately permits a compiler training pass. The compiler continuation also tests Native Image as a separate endpoint with an explicit target SDK. Framework and compiler research have independent reports, clocks and lifecycle costs; their improvements cannot be added together.
