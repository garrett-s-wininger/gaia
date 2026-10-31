# JVM startup research

The current experiment asks whether supplied framework knowledge can improve regular JVM bytecode startup without a full application training pass or native compilation.

- [Findings](findings.md): measured class metadata reuse, linking tradeoffs, framework initialization and honest parser controls.
- [Prospects](prospects.md): how to separate reusable framework data from fresh runtime state.
- [Code and reproduction](../../experiments/java/startup/README.md).
- [Run index](experiments.json).

This research does not select a new JVM, claim arbitrary heap snapshots are safe, or establish a startup floor.
