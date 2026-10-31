// Host adapter: no Node perf_hooks object is serialized into the blob.
const snapshotAPI = require('node:v8').startupSnapshot;
const preparingSnapshot = snapshotAPI.isBuildingSnapshot();
let currentPerformance = preparingSnapshot ? undefined : require('node:perf_hooks').performance;
const forwardedPerformance = {
  get timeOrigin() { return currentPerformance ? currentPerformance.timeOrigin : 0; },
  now() { return currentPerformance ? currentPerformance.now() : 0; },
  mark(...args) { if (currentPerformance) return currentPerformance.mark(...args); },
  measure(...args) { if (currentPerformance) return currentPerformance.measure(...args); },
  clearMarks(...args) { if (currentPerformance) return currentPerformance.clearMarks(...args); },
  clearMeasures(...args) { if (currentPerformance) return currentPerformance.clearMeasures(...args); },
};
function compilerRequire(name) {
  if (name === 'perf_hooks' || name === 'node:perf_hooks') return {performance: forwardedPerformance};
  return require(name);
}
function bindCurrentPerformance() { currentPerformance = require('node:perf_hooks').performance; }
