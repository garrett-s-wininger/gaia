// Appended unchanged to ordinary-require and single-entry bundled controls.
// The prepare boundary retains the real TypeScript API, not request results.
const snapshotAPI = require('node:v8').startupSnapshot;
const initializationState = Object.freeze({
  marker: process.env.GAIA_INITIALIZATION_MARKER,
  pid: process.pid,
  version: ts.version,
  exports: Object.keys(ts).length,
});
function main() {
  const fs = require('node:fs');
  const crypto = require('node:crypto');
  const request = JSON.parse(fs.readFileSync(0, 'utf8'));
  if (request.token !== process.env.GAIA_REQUEST_TOKEN ||
      request.token !== process.argv[process.argv.length - 1]) {
    throw Error('runtime request identity mismatch');
  }
  // Register at invocation time: process resources are not prepared in snapshot.
  process.on('exit', (code) => {
    if (code !== 0) throw Error('unexpected exit status');
    fs.writeFileSync(request.exitMarker, request.token);
  });
  const operations = [];
  for (const row of request.sources) {
    const parsed = ts.createSourceFile(row.name, row.text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
    let nodes = 0;
    function visit(node) { nodes++; ts.forEachChild(node, visit); }
    visit(parsed);
    const emitted = ts.transpileModule(row.text, {
      fileName: row.name,
      reportDiagnostics: true,
      compilerOptions: {target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS,
        sourceMap: true, strict: true},
    });
    const diagnostics = emitted.diagnostics.map((d) => ({
      code: d.code, category: d.category, start: d.start, length: d.length,
      message: ts.flattenDiagnosticMessageText(d.messageText, '\n'),
    }));
    operations.push({name: row.name, nodes, diagnostics,
      outputSHA256: crypto.createHash('sha256').update(emitted.outputText).digest('hex'),
      mapSHA256: crypto.createHash('sha256').update(emitted.sourceMapText).digest('hex'),
      outputBytes: Buffer.byteLength(emitted.outputText)});
  }
  process.stdout.write(JSON.stringify({
    state: initializationState, operations,
    token: request.token, cwd: process.cwd(), compilerCwd: ts.sys.getCurrentDirectory(),
    memory: process.memoryUsage(),
  }) + '\n');
}
if (snapshotAPI.isBuildingSnapshot()) snapshotAPI.setDeserializeMainFunction(main);
else main();
