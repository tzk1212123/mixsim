'use strict';
const $ = id => document.getElementById(id);
let state = null, running = false, busy = false, toastTimer;
const fmt = (v, n=2) => Number(v).toFixed(n);
const rgbCSS = rgb => `rgb(${rgb.map(v=>Math.round(v)).join(',')})`;
const validNumber = id => { const raw=$(id).value; const value=Number(raw); if(raw.trim()===''||!Number.isFinite(value)) throw Error(`Enter a finite number: ${id}`); return value; };
function toast(message,error=false){$('toast').textContent=message;$('toast').className=`show${error?' error':''}`;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').className='',5000);}
async function action(name,params={}){
  const response=await fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:name,params,source:'ui'})});
  const data=await response.json();
  if(!response.ok||!data.ok)throw Error(`${data.error?.code||response.status}: ${data.error?.message||data.error}`);
  return data.result;
}
async function refresh(){
  try{const r=await fetch('/api/state');if(!r.ok)throw Error('HTTP '+r.status);state=await r.json();render();$('connection').textContent='CONNECTED';$('connection-dot').style.background='#2a9a78';}
  catch(e){$('connection').textContent='DISCONNECTED';$('connection-dot').style.background='#b34e43';}
}
function lockUI(){
  const completed=Boolean(state?.final_record);
  ['new','step','run','write','manual','clog','clear','reset','advance','best','finalize'].forEach(id=>$(id).disabled=busy||running||!state);
  ['step','best','finalize'].forEach(id=>{if(completed)$(id).disabled=true;});
  $('manual').textContent=completed?'New session to run':'▶ Run trial';
  $('run').textContent=completed?'New session to run':'▶ Run campaign';
  $('session-hint').textContent=completed?'Complete · export results before starting a new session.':'';
  if(!state?.records.some(r=>r.kind==='trial'&&r.status==='ok'))$('best').disabled=true;
  if(!state?.recommendation)$('finalize').disabled=true;
  document.querySelectorAll('.record-pick').forEach(b=>b.disabled=busy||running||completed);
}
async function perform(fn,message){if(busy||running)return;busy=true;lockUI();try{await fn();if(message)toast(message);}catch(e){toast(e.message,true);}finally{busy=false;await refresh();lockUI();}}
function render(){
  const r=state.rig, config=state.config, records=state.records;
  $('time').textContent=fmt(r.time_s,1)+' s';
  $('pressure').replaceChildren(document.createTextNode(fmt(r.daq.pressure_kpa)),Object.assign(document.createElement('small'),{textContent:' kPa'}));
  $('trip-value').textContent=fmt(config.pressure_trip_kpa,0);
  $('pressure-meter').style.width=Math.min(100,r.daq.pressure_kpa/config.pressure_trip_kpa*100)+'%';
  $('pressure-meter').style.background=r.interlock?'#b34e43':'#177f72';
  $('temperature').textContent=fmt(r.daq.temperature_c,1);
  $('status').textContent=r.interlock?'INTERLOCK':r.stopped?'READY':'PUMPING';
  $('status').className=r.interlock?'status-fault':'status-ready';
  $('status-detail').textContent=r.interlock?`${r.interlock} · latched`:state.final_record?'Complete':r.stopped?'Stopped':'Active';
  const syringeCapacity=(state.syringe_specification?.capacity_ml*1000)||config.syringe_capacity_ul;
  ['a','b'].forEach((name,i)=>{$('pump-'+name).replaceChildren(document.createTextNode(fmt(r.commanded_ul_min[i],1)+' '),Object.assign(document.createElement('small'),{textContent:'µL/min'}));$('volume-'+name).textContent=fmt(r.remaining_ul[i]/1000)+' mL left';$('reservoir-'+name).style.width=(r.remaining_ul[i]/syringeCapacity*100)+'%';});
  $('target-color').style.background=rgbCSS(state.target_rgb);$('target-rgb').textContent='RGB '+state.target_rgb.map(v=>Math.round(v)).join(' / ');
  $('flow-state').textContent=`${r.stopped?'Stopped':'Active'} · clog ×${fmt(r.clog_factor,0)}`;
  const last=records.at(-1);
  if(last){$('sample-color').style.background=rgbCSS(last.rgb);$('camera-label').textContent=`RUN ${last.id} / ${last.frames} FRAMES`;$('error').replaceChildren(document.createTextNode(fmt(last.error_rgb_dn)),Object.assign(document.createElement('small'),{textContent:' DN'}));$('error-detail').textContent=last.status==='aborted'?'Aborted':last.kind==='replicate'?'Final replicate':'Trial';}
  else{$('sample-color').style.background='#dce8e0';$('camera-label').textContent='NO SAMPLE';$('error').textContent='—';$('error-detail').textContent='Awaiting measurement';}
  const recommendation=records.find(x=>x.id===state.recommendation);
  $('recommend-detail').textContent=recommendation?`#${recommendation.id} · A ${fmt(recommendation.a_ul_min,1)} / B ${fmt(recommendation.b_ul_min,1)} µL/min`:'No setting selected';
  const final=records.find(x=>x.id===state.final_record);
  $('delivered').replaceChildren(document.createTextNode(final?fmt(final.error_rgb_dn):'—'),Object.assign(document.createElement('small'),{textContent:' RGB DN'}));
  $('final-status').textContent=final?`#${final.id} · ${final.error_rgb_dn<=3?'Within 3 DN':'Above 3 DN'}`:'';
  $('record-count').textContent=records.length+' RUNS';
  const tbody=$('records');tbody.replaceChildren();
  if(!records.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=7;td.className='empty';td.textContent='No trials';tr.append(td);tbody.append(tr);}
  records.slice().reverse().forEach(record=>{
    const tr=document.createElement('tr');if(record.kind==='replicate')tr.className='row-replicate';
    const columns=[String(record.id).padStart(2,'0'),record.kind==='replicate'?'REPLICATE':record.label,`${fmt(record.a_ul_min,1)} / ${fmt(record.b_ul_min,1)}`,'',fmt(record.error_rgb_dn),record.status.toUpperCase(),''];
    columns.forEach((text,index)=>{const td=document.createElement('td');td.textContent=text;if(index===3){const swatch=document.createElement('i');swatch.className='swatch';swatch.style.background=rgbCSS(record.rgb);td.append(swatch,record.rgb.map(v=>Math.round(v)).join('/'));}if(index===6&&record.kind==='trial'&&record.status==='ok'){const b=document.createElement('button');b.className='record-pick';b.textContent=record.id===state.recommendation?'✓ SELECTED':'SELECT';b.addEventListener('click',()=>perform(()=>action('recommend',{record_id:record.id}),'Recommendation selected'));td.append(b);}tr.append(td);});tbody.append(tr);
  });
  const events=state.events.slice(-15).reverse();$('events').replaceChildren();
  if(!events.length)$('events').textContent='No events';
  events.forEach(event=>{const line=document.createElement('div');if(['rejected','interlock'].includes(event.kind))line.className='event-fault';const detail=Object.entries(event).filter(([key])=>!['time_s','kind'].includes(key)).map(([k,v])=>`${k}=${typeof v==='number'?fmt(v):JSON.stringify(v)}`).join(' ');line.textContent=`[${fmt(event.time_s,1)} s] ${event.kind} ${detail}`;$('events').append(line);});
  $('chart-caption').textContent=records.length?`${records.filter(x=>x.kind==='trial').length} trials · ${records.filter(x=>x.kind==='replicate').length} replicate`:'';
  chart();lockUI();
}
function chart(){
  const canvas=$('chart'),ctx=canvas.getContext('2d'),w=canvas.clientWidth,h=canvas.clientHeight,dpr=window.devicePixelRatio||1;
  canvas.width=w*dpr;canvas.height=h*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);
  const records=state?.records||[],left=45,right=w-23,top=23,bottom=h-31;
  const ymax=Math.max(12,...records.map(r=>r.error_rgb_dn))*1.12;
  const x=i=>left+(right-left)*(i/Math.max(records.length-1,1)),y=v=>bottom-(bottom-top)*v/ymax;
  ctx.font='9px Consolas, monospace';ctx.fillStyle='#82938b';ctx.strokeStyle='#e9efea';ctx.lineWidth=1;
  for(let i=0;i<=3;i++){const value=ymax*i/3;ctx.beginPath();ctx.moveTo(left,y(value));ctx.lineTo(right,y(value));ctx.stroke();ctx.fillText(value.toFixed(0),13,y(value)+3);}
  ctx.setLineDash([4,4]);ctx.strokeStyle='#a5baad';ctx.beginPath();ctx.moveTo(left,y(3));ctx.lineTo(right,y(3));ctx.stroke();ctx.setLineDash([]);
  if(records.length){ctx.beginPath();records.forEach((r,i)=>{if(i===0)ctx.moveTo(x(i),y(r.error_rgb_dn));else ctx.lineTo(x(i),y(r.error_rgb_dn));});ctx.strokeStyle='#278e7f';ctx.lineWidth=1.8;ctx.stroke();
    records.forEach((r,i)=>{ctx.beginPath();ctx.arc(x(i),y(r.error_rgb_dn),r.kind==='replicate'?5:3.5,0,2*Math.PI);ctx.fillStyle=r.status==='aborted'?'#b34e43':r.kind==='replicate'?'#d67542':'#177f72';ctx.fill();if(records.length<16||i%2===0){ctx.fillStyle='#82938b';ctx.fillText(String(r.id),x(i)-3,bottom+17);}});
  }else{ctx.fillStyle='#98a89f';ctx.textAlign='center';ctx.fillText('No data',w/2,h/2);ctx.textAlign='left';}
}
function baselineParams(){return{planner:$('planner').value,total_ul_min:validNumber('total'),settle_s:validNumber('settle')};}
function newSession(){return action('new_session',{seed:validNumber('seed'),target_fraction:validNumber('target')/100});}
function updateManualTotal(){const a=$('flow-a').value,b=$('flow-b').value;const sum=Number(a)+Number(b);$('manual-total').textContent=a.trim()&&b.trim()&&Number.isFinite(sum)?fmt(sum,2).replace(/\.?0+$/,''):'—';}
['flow-a','flow-b'].forEach(id=>$(id).addEventListener('input',updateManualTotal));
updateManualTotal();
$('target').addEventListener('input',()=>$('target-label').textContent=$('target').value+'%');
$('new').addEventListener('click',()=>perform(newSession,'New session created'));
$('step').addEventListener('click',()=>perform(async()=>{const r=await action('baseline_step',baselineParams());if(r.status==='aborted')throw Error('Run aborted: '+r.interlock);}));
$('run').addEventListener('click',async()=>{
  if(running||busy)return;
  if(state?.final_record){await perform(newSession,'New session ready · click Run campaign');return;}
  let count,params;try{count=validNumber('trials');params=baselineParams();if(!Number.isInteger(count)||count<1||count>20)throw Error('Trial budget must be an integer from 1 to 20');}catch(e){toast(e.message,true);return;}
  running=true;lockUI();let completed=false;
  try{for(let i=0;i<count&&running;i++){const result=await action('baseline_step',params);await refresh();if(result.status!=='ok')throw Error('Interlock triggered: '+result.interlock);await new Promise(resolve=>setTimeout(resolve,500));}
    if(running){const candidates=state.records.filter(r=>r.kind==='trial'&&r.status==='ok');const best=candidates.reduce((a,b)=>a.error_rgb_dn<b.error_rgb_dn?a:b);await action('recommend',{record_id:best.id});if(running){const final=await action('finalize');if(final.status!=='ok')throw Error('Replicate aborted: '+final.interlock);completed=true;}}
    toast(completed?'Campaign complete':'Stopped · records retained');
  }catch(e){toast(e.message,true);}finally{running=false;await refresh();lockUI();}
});
$('stop').addEventListener('click',async()=>{running=false;try{await action('stop');toast('Both virtual pumps stopped');}catch(e){toast(e.message,true);}await refresh();});
$('write').addEventListener('click',()=>perform(()=>action('set_flows',{a_ul_min:validNumber('flow-a'),b_ul_min:validNumber('flow-b')}),'Flows set · advance time to start'));
$('manual').addEventListener('click',()=>{
  if(state?.final_record){perform(newSession,'New session ready · click Run trial');return;}
  perform(async()=>{const result=await action('experiment',{a_ul_min:validNumber('flow-a'),b_ul_min:validNumber('flow-b'),settle_s:validNumber('settle'),label:'Manual trial'});if(result.status!=='ok')throw Error('Interlock triggered: '+result.interlock);});
});
$('advance').addEventListener('click',()=>perform(()=>action('advance',{seconds:10})));
$('clog').addEventListener('click',()=>perform(()=>action('inject_clog',{factor:6}),'Clog ×6 injected'));
$('clear').addEventListener('click',()=>perform(()=>action('inject_clog',{factor:1}),'Clog cleared · reset required'));
$('reset').addEventListener('click',()=>perform(()=>action('reset_interlock'),'Interlock reset'));
$('best').addEventListener('click',()=>perform(()=>{const candidates=state.records.filter(r=>r.kind==='trial'&&r.status==='ok');const best=candidates.reduce((a,b)=>a.error_rgb_dn<b.error_rgb_dn?a:b);return action('recommend',{record_id:best.id});},'Recommendation selected'));
$('finalize').addEventListener('click',()=>perform(async()=>{const r=await action('finalize');if(r.status!=='ok')throw Error('Replicate aborted: '+r.interlock);},'Replicate complete'));
document.querySelectorAll('[data-ref]').forEach(b=>b.addEventListener('click',async()=>{try{const r=await action('reference',{device:b.dataset.ref});$('reference-text').textContent=r.text;$('reference').showModal();}catch(e){toast(e.message,true);}}));
$('close-reference').addEventListener('click',()=>$('reference').close());
function alignPumpTubing(){
  const svg=document.querySelector('.flow-diagram svg');
  const transform=svg.getScreenCTM();
  if(!transform)return;
  const inverse=transform.inverse();
  ['a','b'].forEach((name,index)=>{
    const outlet=document.querySelectorAll('.pump-outlet')[index].getBoundingClientRect();
    const point=svg.createSVGPoint();
    // Overlap the outlet by one screen pixel to avoid an antialiasing seam.
    point.x=outlet.right-1;point.y=outlet.top+outlet.height/2;
    const start=point.matrixTransform(inverse);
    const end=name==='a'?' H128':'';
    svg.querySelector('.pipe-'+name).setAttribute('d',
      `M${start.x} ${start.y} H58 C85 ${start.y} 85 125 102 125${end}`);
  });
}
const tubingObserver=new ResizeObserver(alignPumpTubing);
['.bench','.pumps','.flow-diagram svg'].forEach(selector=>tubingObserver.observe(document.querySelector(selector)));
document.fonts.ready.then(alignPumpTubing);
window.addEventListener('resize',()=>{if(state)chart();alignPumpTubing();});
refresh();setInterval(refresh,1000);
