const test=require('node:test');
const assert=require('node:assert/strict');
const plan=require('../public/assets/dispatch-route.js');
const depot={lat:0,lon:0};
test('one stop includes the return leg',()=>{
  const result=plan(depot,[{lat:0,lon:1}]);
  assert.equal(result.stops.length,1);
  assert.ok(Math.abs(result.metres-222389.85)<1);
});
test('exact plan improves a suboptimal nearest-neighbour tour',()=>{
  const stops=[[0,2],[0,3],[1,0],[1,2]].map(([lat,lon])=>({lat,lon}));
  const result=plan(depot,stops);
  assert.match(result.method,/Exact/);
  assert.equal(new Set(result.stops).size,4);
  assert.ok(result.metres<result.baselineMetres);
});
test('large plan covers each stop and never worsens baseline',()=>{
  const stops=Array.from({length:20},(_,i)=>({lat:i/10,lon:(i%3)/10}));
  const result=plan(depot,stops);
  assert.match(result.method,/Heuristic/);
  assert.equal(new Set(result.stops).size,20);
  assert.ok(result.metres<=result.baselineMetres+1e-6);
});
test('no pickups and invalid coordinates are rejected',()=>{
  assert.throws(()=>plan(depot,[]));
  assert.throws(()=>plan(depot,[{lat:100,lon:1}]));
});
