// Loaded at invocation time for every stock/API/bundle/snapshot control.
const fs = require('node:fs');
const performance = require('node:perf_hooks').performance;
const marker = process.env.GAIA_METADATA_PATH;
if (!marker || !process.env.GAIA_REQUEST_TOKEN) throw Error('missing probe request identity');
const started = performance.now();
process.on('exit', (status) => {
  fs.writeFileSync(marker, JSON.stringify({status,token:process.env.GAIA_REQUEST_TOKEN,cwd:process.cwd(),
    argv:process.argv,memory:process.memoryUsage(),performance:{timeOrigin:performance.timeOrigin,
      start:started,end:performance.now()},compiler:globalThis.__gaiaCompiler}));
});
