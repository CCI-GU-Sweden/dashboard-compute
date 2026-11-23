const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../dashboard_compute/static/dashboard_compute/charts.js'), 'utf8');
async function exercise(kind, data) {
  const calls = [];
  const handlers = {};
  const chart = {on: (name, cb) => { handlers[name] = cb; }, removeAllListeners: () => {}};
  const metric = {value: 'cpu', addEventListener: (name, cb) => { handlers.metric = cb; }};
  const grouping = {value: 'workload', addEventListener: (name, cb) => { handlers.grouping = cb; }};
  const empty = {hidden: false};
  const nodes = {'compute-chart-data': {textContent: JSON.stringify(data)}, 'compute-metric': metric,
    'compute-grouping': grouping, [`compute-${kind}-chart`]: chart, [`compute-${kind}-empty`]: empty};
  let navigated = null;
  const Plotly = {react: async (...args) => { calls.push(args); }};
  const window = {Plotly, location: {assign: url => { navigated = url; }}};
  vm.runInNewContext(source, {window, Plotly, document: {getElementById: id => nodes[id]}, Intl, Date, Map, JSON, String});
  await new Promise(resolve => setImmediate(resolve));
  return {calls, handlers, metric, grouping, empty, get navigated() { return navigated; }};
}

(async () => {
  const month = await exercise('month', {currency: '', rows: [
    {day:'2026-11-23', url:'/compute/day/2026-11-23/', namespace:'test', group:'CCI', key:'pod:a', name:'job', cpu:2, memory:3, cost:null},
    {day:'2026-11-23', url:'/compute/day/2026-11-23/', namespace:'test', group:'CCI', key:'pod:b', name:'job', cpu:4, memory:5, cost:null},
  ]});
  assert.equal(month.calls[0][1].length, 2);
  month.handlers.plotly_click({points: [{customdata: '/compute/day/2026-11-23/'}]});
  assert.equal(month.navigated, '/compute/day/2026-11-23/');
  month.grouping.value = 'group';
  await month.handlers.grouping();
  assert.equal(month.calls[1][1].length, 1);
  assert.equal(month.calls[1][1][0].y[0], 6);
  const day = await exercise('day', {timezone:'Europe/Stockholm', times:['2026-11-23T10:00:00Z','2026-11-23T10:01:00Z'], series:[
    {name:'web', group:'CCI', key:'Deployment:web', cpu:[1,null], memory:[2,null]},
    {name:'job', group:'CCI', key:'pod:a', cpu:[3,null], memory:[4,null]},
  ]});
  assert.equal(day.calls[0][1][1].y[0], 4);
  assert.equal(day.calls[0][1][1].y[1], null);
  assert.equal(day.calls[0][1][1].customdata[0][0], 3);
  day.metric.value = 'memory';
  day.handlers.metric();
  assert.equal(day.calls[1][1][1].y[0], 6);
  console.log('compute charts frontend passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
