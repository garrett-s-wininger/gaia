// Synthetic disk-snapshot sanity check: pure in-memory metadata, no live handles.
'use strict';
const startupSnapshot = require('node:v8').startupSnapshot;
const count = Number(process.env.GAIA_GRAPH_COUNT || '0');
const rows = Array.from({length: count}, (_, i) => ({
  name: `module_${i}`, path: `/packages/${i % 127}/module_${i}.js`,
  flags: i % 8, dependencies: [i % 31, i % 113],
}));
const index = new Map(rows.map((row) => [row.name, row]));
function main() {
  let checksum = 0;
  for (let i = 0; i < rows.length; i += 997) {
    const row = index.get(`module_${i}`);
    if (!row || row.flags !== i % 8) throw Error('restored metadata differs');
    checksum += row.dependencies[0] + row.dependencies[1];
  }
  process.stdout.write(JSON.stringify({count: rows.length, checksum,
    token: process.env.GAIA_REQUEST_TOKEN, argvToken: process.argv[process.argv.length - 1],
    rss: process.memoryUsage().rss}) + '\n');
}
if (startupSnapshot.isBuildingSnapshot()) startupSnapshot.setDeserializeMainFunction(main);
else main();
