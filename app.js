(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const D = window.HOSPITAL_DATA, L = window.HospitalLogic;
  const esc = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  if(!D || !L) { $('formError').hidden=false; $('formError').textContent='本地数据未能加载。请先按复现说明运行 build_data.py，再重新打开看板。'; return; }
  const rows=L.rowsFrom(D), hospitals=D.meta.hospitals;
  const studyStart=D.meta.studyStart, studyEnd=D.meta.studyEnd;
  const fmt=(v,n=2)=>L.valid(v)?v.toLocaleString('zh-CN',{minimumFractionDigits:n,maximumFractionDigits:n}):'—';
  const sign=(v,n=2)=>(v>0?'+':'')+fmt(v,n);
  const displayDate=s=>s.replaceAll('-','/');
  let state={hospital:'CGH',start:'2024-05-02',end:'2024-05-08'}, current, showAll=false;
  $('hospital').innerHTML=hospitals.map(h=>`<option value="${esc(h)}">${esc(h)}${h==='AH'?' · Urgent Care':''}</option>`).join('');
  $('hospital').value='CGH';
  for(const id of ['start','end']) { $(id).min=studyStart; $(id).max=studyEnd; }
  $('dataStamp').textContent='数据截至 '+displayDate(studyEnd);
  $('datasetSummary').textContent=`${D.quality.dateCount.toLocaleString()}个日期 · ${hospitals.length}家机构 · ${D.quality.rowCount.toLocaleString()}条医院日记录`;
  const sourceLabels={ed:'急诊就诊量',bor:'床位占用率',wait:'入院等待中位数',ed_attendances:'急诊就诊量',bor_ratio:'床位占用率',admission_wait_p50_hours:'入院等待中位数'};
  $('sources').innerHTML=D.meta.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">MOH · ${esc(sourceLabels[s.metric]||s.metric)}</a></li>`).join('');
  function deltaText(metric,kind) {
    if(!metric.current.complete) return `已知 ${metric.current.validDays}/${metric.current.expectedDays} 天 · 缺失不填零`;
    if(!metric.previous.complete) return `本期完整；前期仅有 ${metric.previous.validDays}/${metric.previous.expectedDays} 天，暂不比较`;
    if(kind==='bor') return `较前期 ${sign(metric.delta*100)} 个百分点`;
    if(kind==='ed') return `较前期 ${sign(metric.delta,0)} 次${metric.relative===null?'（前期为0）':`（${sign(metric.relative*100,1)}%）`}`;
    return `较前期 ${sign(metric.delta)} 小时`;
  }
  function renderCards() {
    const definitions=[['admission_wait_p50_hours','等待中位数 · 区间均值','小时','wait'],['ed_attendances','急诊就诊量 · 区间合计','次','ed'],['bor_ratio','午夜床位占用率 · 区间均值','%','bor']];
    $('kpis').innerHTML=definitions.map(([field,label,unit,kind])=>{
      const m=current.metrics[field];
      const value=kind==='bor'?m.current.value*100:m.current.value;
      return `<article class="kpi"><div class="kpi-label">${label}</div><div class="kpi-value${m.current.complete?'':' incomplete'}">${m.current.complete?fmt(value,kind==='ed'?0:2):'数据不足'}${m.current.complete?`<small>${unit}</small>`:''}</div><div class="kpi-delta${m.delta>0?' up':''}">${deltaText(m,kind)}</div></article>`;
    }).join('');
  }
  function renderReference() {
    const r=L.historicalReference(rows,state.hospital,state.start,state.end);
    let title,body,kind='neutral';
    if(r.status==='not_seven_days') {title='当前为区间趋势观察';body='选择7天窗口，可查看与此前8个连续7天窗口的历史对照。此处不使用不等长区间作周规则判断。';}
    else if(r.status==='current_incomplete') {title='当前等待数据不足，暂不判断';body=`所选7天只有${r.validDays}天等待记录。保留已知数据，缺失不等于等待为零。`;}
    else if(r.status==='baseline_incomplete') {title='历史参照不足，暂不判断';body='此前连续8个7天窗口中存在缺失或超出本数据范围；没有跳过缺失周去补更早的记录。';}
    else {kind=r.status==='above'?'attention':'';title=r.status==='above'?'高于此前8周最高值，值得进一步复核':'未超过本次历史参照；仍需结合趋势跟踪';body=`本期 ${fmt(r.current)} 小时，前8周最高 ${fmt(r.maximum)} 小时、均值 ${fmt(r.priorMean)} 小时；本期 ${r.daysAbove}/7 天高于各自此前8周同星期几的均值。参照：${displayDate(r.start)}—${displayDate(r.end)}。未触发不等于恢复或安全。`;}
    $('reference').className='reference '+kind;
    $('reference').innerHTML=`<span class="signal" aria-hidden="true">${kind==='attention'?'↗':'◌'}</span><div><strong>${title}</strong><p>${body}</p><p>探索性历史对照 · 用于组织复核线索，不是临床或自动调度规则。</p></div>`;
  }
  function drawChart(id,records,field,options={}) {
    const container=$(id), width=Math.max(250,container.clientWidth),height=container.clientHeight;
    const left=42,right=14,top=15,bottom=33,w=width-left-right,h=height-top-bottom;
    const scale=options.scale||1, values=records.map(r=>L.valid(r[field])?r[field]*scale:null);
    const available=values.filter(L.valid), rolling=options.rolling?L.rollingSeven(records,field):null;
    if(!available.length) {container.innerHTML=`<svg role="img" aria-label="此范围没有有效数值" width="${width}" height="${height}"><text x="${width/2}" y="${height/2}" text-anchor="middle">此范围没有有效数值</text></svg>`;return;}
    const maximum=Math.max(...available), unit=field==='bor_ratio'?20:maximum<=5?1:maximum<=30?5:maximum<=100?20:100;
    const ymax=Math.max(unit,Math.ceil(maximum/unit)*unit);
    const x=i=>left+(records.length===1?w/2:i*w/(records.length-1)),y=v=>top+h-(v/ymax)*h;
    const startIndex=Math.max(0,records.findIndex(r=>r.date>=state.start));
    let svg=`<svg role="img" aria-label="${esc(options.label)}；${records.length}个日期，其中${available.length}个有效值；阴影为所选区间" width="${width}" height="${height}"><title>${esc(options.label)}</title><rect x="${x(startIndex)}" y="${top}" width="${Math.max(0,left+w-x(startIndex))}" height="${h}" fill="#edf6f4"/>`;
    for(let i=0;i<=4;i++) {const v=ymax*i/4,yy=y(v);svg+=`<line x1="${left}" y1="${yy}" x2="${left+w}" y2="${yy}" stroke="#e5ecef"/><text x="${left-8}" y="${yy+4}" text-anchor="end">${fmt(v,v%1===0?0:1)}</text>`;}
    const ticks=width<450?3:5;
    for(let t=0;t<ticks;t++){const i=Math.round(t*(records.length-1)/(ticks-1));svg+=`<text x="${x(i)}" y="${height-8}" text-anchor="${t===0?'start':t===ticks-1?'end':'middle'}">${records[i].date.slice(5).replace('-','/')}</text>`;}
    function path(vs,color,lineWidth) {let p='',active=false;vs.forEach((v,i)=>{if(!L.valid(v)){active=false;return;}p+=(active?'L':'M')+x(i).toFixed(2)+','+y(v).toFixed(2)+' ';active=true;});return `<path d="${p}" fill="none" stroke="${color}" stroke-width="${lineWidth}" stroke-linecap="round" stroke-linejoin="round"/>`;}
    svg+=path(values,options.rolling?'#a5beca':(options.color||'#39768a'),options.rolling?1.4:1.8);
    if(rolling) svg+=path(rolling,'#137a83',2.7);
    values.forEach((v,i)=>{if(!L.valid(v))return;svg+=`<circle cx="${x(i)}" cy="${y(v)}" r="${records.length>160?2.3:3}" fill="${options.rolling?'#789dab':(options.color||'#39768a')}" opacity="${records.length>160?.25:.5}"><title>${records[i].date} · ${fmt(v,field==='ed_attendances'?0:2)} ${esc(options.unit||'')}</title></circle>`;});
    container.innerHTML=svg+'</svg>';
  }
  function renderCharts() {
    const contextStart=state.start> L.addDays(studyStart,56)?L.addDays(state.start,-56):studyStart;
    const contextRows=L.series(rows,state.hospital,contextStart,state.end);
    $('chartRange').textContent=`${displayDate(contextStart)}—${displayDate(state.end)}`;
    drawChart('waitChart',contextRows,'admission_wait_p50_hours',{rolling:true,label:'每日入院等待中位数及连续7天均值',unit:'小时'});
    drawChart('edChart',contextRows,'ed_attendances',{label:'每日急诊就诊量',unit:'次',color:'#537ca1'});
    drawChart('borChart',contextRows,'bor_ratio',{scale:100,label:'每日午夜床位占用率',unit:'%',color:'#a67942'});
  }
  function renderPeers() {
    $('peers').innerHTML=['CGH','KTPH','NTFGH','NUH(A)','SGH','SKH','TTSH'].map(h=>{
      const s=L.summarize(rows,h,state.start,state.end),m=s.metrics.admission_wait_p50_hours;
      return `<tr class="${h===state.hospital?'row-selected':''}"><td><button type="button" class="hospital-link" data-hospital="${esc(h)}">${esc(h)}</button></td><td>${m.current.validDays}/${s.days}</td><td>${fmt(m.current.value)}</td><td>${fmt(m.previous.value)}</td><td>${L.valid(m.delta)?sign(m.delta):'—'}</td></tr>`;
    }).join('');
  }
  function renderDetails() {
    const detail=current.currentRows, visible=showAll?detail:detail.slice(0,14);
    $('detailSummary').textContent=`${detail.length}个日期 · ${current.completeDays}天三项完整。空值显示“—”；BOR导出保留原始比例。`;
    $('details').innerHTML=visible.map(r=>`<tr><td>${r.date}</td><td>${fmt(r.ed_attendances,0)}</td><td>${L.valid(r.bor_ratio)?fmt(r.bor_ratio*100):'—'}</td><td>${fmt(r.admission_wait_p50_hours)}</td><td class="${r.availability==='三项有值'?'':'missing'}">${esc(r.availability)}</td><td>${esc([r.ed_source||'无记录',r.bor_source||'无记录',r.wait_source||'无记录'].join(' / '))}</td></tr>`).join('');
    $('more').hidden=detail.length<=14;
    $('more').textContent=showAll?'收起明细':`显示全部 ${detail.length} 天`;
  }
  function update() {
    const hospital=$('hospital').value,start=$('start').value,end=$('end').value;
    let error='';
    if(!hospitals.includes(hospital)||!start||!end) error='请选择医院和完整的起止日期。';
    else if(start>end) error='开始日期不能晚于结束日期。';
    else if(start<studyStart||end>studyEnd) error=`本快照覆盖${studyStart}至${studyEnd}，请选择范围内的日期。`;
    $('formError').hidden=!error;
    $('formError').textContent=error;
    if(error) return;
    state={hospital,start,end}; showAll=false;
    current=L.summarize(rows,hospital,start,end);
    $('mainContent').hidden=false;
    $('selectionTitle').textContent=`${hospital} · ${displayDate(start)}—${displayDate(end)}`;
    $('comparisonRange').textContent=`前期参照：${displayDate(current.previousStart)}—${displayDate(current.previousEnd)}（相同${current.days}天长度）`;
    $('coverage').textContent=`三项完整 ${current.completeDays}/${current.days} 天`;
    renderCards();renderReference();renderCharts();renderPeers();renderDetails();
  }
  $('filters').addEventListener('submit',e=>{e.preventDefault();update();});
  document.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>{
    if(b.dataset.preset==='case'){ $('hospital').value='CGH';$('start').value='2024-05-02';$('end').value='2024-05-08'; }
    if(b.dataset.preset==='latest'){ $('start').value=L.addDays(studyEnd,-6);$('end').value=studyEnd; }
    if(b.dataset.preset==='year'){ $('start').value='2024-01-01';$('end').value='2024-12-31'; }
    update();
  }));
  $('peers').addEventListener('click',e=>{const b=e.target.closest('[data-hospital]');if(b){$('hospital').value=b.dataset.hospital;update();}});
  $('more').addEventListener('click',()=>{showAll=!showAll;renderDetails();});
  $('export').addEventListener('click',()=>{
    const blob=new Blob([L.csv(current.currentRows)],{type:'text/csv;charset=utf-8;'}), url=URL.createObjectURL(blob),a=document.createElement('a');
    a.href=url;a.download=`${state.hospital}_${state.start}_${state.end}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  let resizeTimer;
  window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(current)renderCharts();},150);});
  update();
})();
