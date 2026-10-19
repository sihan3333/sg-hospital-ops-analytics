// Run with: node verify_dashboard.cjs
// Known-case checks cover the business calculations and consequential missing-data cases.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const L = require('./logic.js');
const data = JSON.parse(fs.readFileSync(path.join(__dirname,'data/dashboard-data.json'),'utf8'));
const rows = L.rowsFrom(data);
const near = (actual,expected) => assert.ok(Math.abs(actual-expected)<1e-8,`${actual} != ${expected}`);
const checks = [];
function check(name,fn) { fn(); checks.push(name); }

check('CGH published-case calculations',()=>{
  const s=L.summarize(rows,'CGH','2024-05-02','2024-05-08');
  assert.equal(s.completeDays,7);
  near(s.metrics.admission_wait_p50_hours.current.value,21.52738095238095);
  near(s.metrics.admission_wait_p50_hours.previous.value,11.93928571428571);
  assert.equal(s.metrics.ed_attendances.current.value,2608);
  assert.equal(s.metrics.ed_attendances.previous.value,2577);
  assert.equal((s.metrics.bor_ratio.current.value*100).toFixed(2),'90.96');
  assert.equal((s.metrics.bor_ratio.delta*100).toFixed(2),'1.54');
  const r=L.historicalReference(rows,'CGH','2024-05-02','2024-05-08');
  assert.equal(r.status,'above'); near(r.maximum,13.44761904761905);
  near(r.priorMean,10.050892857142857); assert.equal(r.daysAbove,7);
});
check('Seven-hospital changes match the historical case',()=>{
  const hs=['CGH','KTPH','NTFGH','NUH(A)','SGH','SKH','TTSH'];
  const changes=hs.map(h=>L.summarize(rows,h,'2024-05-02','2024-05-08').metrics.admission_wait_p50_hours.delta);
  assert.equal(changes.filter(v=>v>0).length,6);
  assert.equal(changes.filter(v=>v<0).length,1);
  assert.ok(changes[1]<0);
});
check('BOR survives the missing ED and waiting week',()=>{
  const s=L.summarize(rows,'CGH','2026-08-02','2026-08-08');
  assert.equal(s.currentRows.length,7);
  assert.equal(s.metrics.ed_attendances.current.value,null);
  assert.equal(s.metrics.admission_wait_p50_hours.current.value,null);
  assert.equal(s.metrics.bor_ratio.current.complete,true);
  assert.equal((s.metrics.bor_ratio.current.value*100).toFixed(2),'77.54');
  assert.equal(L.historicalReference(rows,'CGH',s.start,s.end).status,'current_incomplete');
  assert.ok(s.currentRows.every(r=>r.ed_source===null&&r.wait_source===null&&r.bor_source));
  const csv=L.csv(s.currentRows);
  assert.ok(csv.startsWith('\uFEFFdate,')); assert.equal(csv.split('\r\n').length,8);
  assert.ok(csv.split('\r\n')[1].includes('"2026-08-02","CGH",,'));
});
check('Absent WH data and genuine zero waiting remain distinct',()=>{
  const absent=L.summarize(rows,'WH','2024-05-02','2024-05-08');
  assert.equal(absent.completeDays,0);
  assert.equal(absent.metrics.admission_wait_p50_hours.current.value,null);
  for(const date of ['2025-12-22','2025-12-29']) {
    const s=L.summarize(rows,'WH',date,date);
    assert.equal(s.metrics.admission_wait_p50_hours.current.value,0);
    assert.equal(s.metrics.admission_wait_p50_hours.current.validDays,1);
  }
});
check('Incomplete calendar windows do not become complete averages',()=>{
  const seq=L.series(rows,'CGH','2026-07-26','2026-08-15');
  const rolling=L.rollingSeven(seq,'admission_wait_p50_hours');
  assert.ok(L.valid(rolling[seq.findIndex(r=>r.date==='2026-08-01')]));
  for(let i=0;i<seq.length;i++) if(seq[i].date>='2026-08-02'&&seq[i].date<='2026-08-14') assert.equal(rolling[i],null);
  assert.ok(L.valid(rolling.at(-1)));
  assert.equal(L.historicalReference(rows,'CGH','2024-01-01','2024-01-07').status,'baseline_incomplete');
  assert.equal(L.historicalReference(rows,'CGH','2024-01-01','2024-12-31').status,'not_seven_days');
  const fullYear=L.summarize(rows,'CGH','2024-01-01','2024-12-31');
  assert.equal(fullYear.days,366); assert.equal(fullYear.metrics.admission_wait_p50_hours.delta,null);
});
check('An untriggered later week is not labelled recovery',()=>{
  const r=L.historicalReference(rows,'CGH','2024-05-09','2024-05-15');
  assert.equal(r.status,'not_above'); near(r.current,16.05833333333333);
  assert.ok(r.current>13.44761904761905);
});
console.log(JSON.stringify({result:'passed',count:checks.length,checks},null,2));
