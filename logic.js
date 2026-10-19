(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.HospitalLogic = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const dayMs = 86400000;
  const valid = v => typeof v === 'number' && Number.isFinite(v);
  const addDays = (s, n) => new Date(Date.parse(s + 'T00:00:00Z') + n * dayMs).toISOString().slice(0, 10);
  const dayCount = (a, b) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / dayMs) + 1;
  function rowsFrom(payload) { return payload.rows.map(r => Object.fromEntries(payload.fields.map((f, i) => [f, r[i]]))); }
  function series(rows, hospital, start, end) {
    const lookup = new Map(rows.filter(r => r.hospital_code === hospital).map(r => [r.date, r]));
    const result = [];
    for (let d = start; d <= end; d = addDays(d, 1)) result.push(lookup.get(d) || {date:d, hospital_code:hospital, ed_attendances:null, bor_ratio:null, admission_wait_p50_hours:null, availability:'来源范围外', ed_source:null, bor_source:null, wait_source:null});
    return result;
  }
  function aggregate(records, field, type = 'mean') {
    const values = records.map(r => r[field]).filter(valid);
    const complete = records.length > 0 && values.length === records.length;
    const sum = values.reduce((a, b) => a + b, 0);
    return {validDays:values.length, expectedDays:records.length, complete, value:complete ? (type === 'sum' ? sum : sum / values.length) : null};
  }
  function summarize(rows, hospital, start, end) {
    const n = dayCount(start, end);
    const currentRows = series(rows, hospital, start, end);
    const previousStart = addDays(start, -n), previousEnd = addDays(start, -1);
    const previousRows = series(rows, hospital, previousStart, previousEnd);
    const result = {hospital, start, end, days:n, previousStart, previousEnd, currentRows, previousRows, metrics:{}};
    for (const [key, type] of [['admission_wait_p50_hours','mean'], ['ed_attendances','sum'], ['bor_ratio','mean']]) {
      const current = aggregate(currentRows,key,type), previous = aggregate(previousRows,key,type);
      const delta = current.complete && previous.complete ? current.value - previous.value : null;
      result.metrics[key] = {current,previous,delta, relative:delta !== null && previous.value !== 0 ? delta / previous.value : null};
    }
    result.completeDays = currentRows.filter(r => ['admission_wait_p50_hours','ed_attendances','bor_ratio'].every(k => valid(r[k]))).length;
    return result;
  }
  function historicalReference(rows, hospital, start, end) {
    if (dayCount(start,end) !== 7) return {status:'not_seven_days'};
    const currentRows = series(rows,hospital,start,end), current = aggregate(currentRows,'admission_wait_p50_hours');
    if (!current.complete) return {status:'current_incomplete', validDays:current.validDays};
    const windows = [];
    for (let i = 8; i >= 1; i--) {
      const s = addDays(start,-7*i), e=addDays(s,6), r=series(rows,hospital,s,e);
      windows.push({start:s,end:e,rows:r,...aggregate(r,'admission_wait_p50_hours')});
    }
    if (windows.some(w=>!w.complete)) return {status:'baseline_incomplete'};
    const maximum = Math.max(...windows.map(w=>w.value));
    const priorMean = windows.reduce((s,w)=>s+w.value,0)/8;
    let daysAbove = 0;
    for(let i=0;i<7;i++) {
      const reference = windows.reduce((sum,w)=>sum+w.rows[i].admission_wait_p50_hours,0)/8;
      if(currentRows[i].admission_wait_p50_hours > reference) daysAbove++;
    }
    return {status:current.value>maximum?'above':'not_above', maximum, priorMean, current:current.value, daysAbove, start:windows[0].start, end:windows[7].end};
  }
  function rollingSeven(records, field) {
    return records.map((r,i)=> {
      if(i<6) return null;
      const window = records.slice(i-6,i+1);
      if(dayCount(window[0].date,r.date)!==7) return null;
      return aggregate(window,field).value;
    });
  }
  function csv(records) {
    const fields=['date','hospital_code','ed_attendances','bor_ratio','admission_wait_p50_hours','availability','ed_source','bor_source','wait_source'];
    const escape = value => value===null||value===undefined?'':('"'+String(value).replace(/"/g,'""')+'"');
    return '\uFEFF'+[fields.join(','),...records.map(r=>fields.map(f=>escape(r[f])).join(','))].join('\r\n');
  }
  return {valid,addDays,dayCount,rowsFrom,series,aggregate,summarize,historicalReference,rollingSeven,csv};
});
