// Appended after the unmodified compiler body (or ordinary compiler require).
const compilerInitialization = Object.freeze({
  marker: process.env.GAIA_INITIALIZATION_MARKER,
  version: ts.version,
  exports: Object.keys(ts).length,
});
function bindRuntime() {
  bindCurrentPerformance();
  if (process.env.NODE_ENV !== 'production' ||
      Object.keys(process.env).some(key => key.startsWith('TSC_WATCH') || key.startsWith('TSC_NONPOLLING'))) {
    throw Error('unsupported mutable compiler environment');
  }
  if (process.env.GAIA_EXPECTED_TYPESCRIPT !== ts.version) throw Error('compiler version context mismatch');
  // These were captured at module initialization in TypeScript's Node system.
  // No project program, host or watcher has been created in the blob.
  ts.sys.args = process.argv.slice(preparingSnapshot ? 1 : 2);
  ts.sys.getCurrentDirectory = () => process.cwd();
  if (ts.sys.setBlocking) ts.sys.setBlocking();
  ts.performance.disable();
  ts.performance.clearMarks();
  ts.performance.clearMeasures();
}
function main() {
  // Normal entry uses the same adapter as the deserialized entry.
  bindRuntime();
  const args = ts.sys.args;
  if (ts.sys.getEnvironmentVariable('GAIA_REQUEST_TOKEN') !== process.env.GAIA_REQUEST_TOKEN) {
    throw Error('compiler environment is stale');
  }
  const blocked = ['--watch', '-w', '--build', '-b', '--incremental', '--generateTrace', '--generateCpuProfile'];
  if (args.some(arg => blocked.includes(arg))) throw Error('unsupported persistent/resource CLI mode');
  const current = require('node:perf_hooks').performance;
  const beforeStamp = current.now();
  const stamp = ts.timestamp();
  const afterStamp = current.now();
  if (stamp < beforeStamp-0.1 || stamp > afterStamp+0.1) throw Error('compiler timestamp is stale after restoration');
  ts.performance.enable();
  const nativeStart = current.now();
  ts.performance.mark('gaia-start');
  const before = current.now();
  while (current.now()-before < 0.5) { /* bounded real clock probe */ }
  ts.performance.mark('gaia-end');
  ts.performance.measure('gaia-elapsed', 'gaia-start', 'gaia-end');
  const measured = ts.performance.getDuration('gaia-elapsed');
  if (!(measured >= 0.4 && measured <= current.now()-nativeStart+5)) throw Error('compiler performance duration is stale');
  ts.performance.disable();
  globalThis.__gaiaCompiler = {state: compilerInitialization, performanceProbe: {durationMs:measured,
    currentTimeOrigin:current.timeOrigin, compilerTimeOrigin:ts.tryGetNativePerformanceHooks().performance.timeOrigin}};
  if (globalThis.__gaiaCompiler.performanceProbe.currentTimeOrigin !==
      globalThis.__gaiaCompiler.performanceProbe.compilerTimeOrigin) throw Error('performance epoch is stale');
  // Genuine upstream CLI argument/config/discovery/check/emit pipeline.
  ts.executeCommandLine(ts.sys, (programOrBuilder) => {
    const program = programOrBuilder.getProgram ? programOrBuilder.getProgram() : programOrBuilder;
    const sources = program.getSourceFiles();
    globalThis.__gaiaCompiler.program = {files:sources.map(file => file.fileName),
      target:program.getCompilerOptions().target,
      libraryFiles:sources.filter(file => program.isSourceFileDefaultLibrary(file)).length,
      projectFiles:sources.filter(file => !file.isDeclarationFile).length};
  }, args);
}
if (preparingSnapshot) {
  snapshotAPI.addDeserializeCallback(bindRuntime);
  snapshotAPI.setDeserializeMainFunction(main);
} else main();
