'use strict';
const portal = document.body.dataset.portal;
const root = document.querySelector('#app');
const logout = document.querySelector('#logout');
const toast = document.querySelector('#toast');
const title = portal === 'resident' ? 'Resident' : 'Collection';
document.querySelector('#workspace').textContent = title;
const statuses = {requested:'Requested',assigned:'Assigned',arrived:'Crew arrived',collected:'Collected',unavailable:'Couldn’t collect',cancelled:'Cancelled'};
const active = new Set(['requested','assigned','arrived']);
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const badge = status => '<span class="chip '+esc(status)+'">'+esc(statuses[status])+'</span>';
const fmt = timestamp => new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}).format(timestamp*1000);
const navLink = p => 'https://www.openstreetmap.org/?mlat='+Number(p.lat)+'&mlon='+Number(p.lon)+'#map=18/'+Number(p.lat)+'/'+Number(p.lon);
let routePlan;
let dispatchOpen=false, dispatchResult=null, depotDraft={lat:'',lon:''};
let state, signature, editing = false, busy = false, timer, refreshID = 0;

async function api(path,data) {
  let response;
  try {
    response = await fetch('/api/'+path,data===undefined?{cache:'no-store'}:{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  } catch { throw Error('Connection lost. Check your connection and try again.'); }
  let result;
  try {result=await response.json();} catch {throw Error('Server response unavailable. Try again.');}
  if(!response.ok) throw Object.assign(Error(result.error||'Something went wrong.'),{status:response.status});
  return result;
}
function message(value) {
  clearTimeout(timer); toast.textContent=value; toast.hidden=false;
  timer=setTimeout(()=>{toast.hidden=true;},5000);
}
function signIn(reason='') {
  state=null; signature=null; routePlan=null; dispatchOpen=false; dispatchResult=null; depotDraft={lat:'',lon:''}; editing=false; logout.hidden=true;
  root.innerHTML='<section class="card login stack"><h1>'+title+' sign in</h1><form class="stack" data-form="login">'+
    '<label>Email<input name="email" type="email" required autocomplete="username" maxlength="254"></label>'+
    '<label>Password<input name="password" type="password" required autocomplete="current-password" maxlength="128"></label>'+
    '<p class="form-msg" role="alert" '+(reason?'':'hidden')+'>'+esc(reason)+'</p><button class="primary">Sign in</button></form></section>';
}
async function refresh(force=false) {
  const id=++refreshID;
  try {
    const next=await api('state');
    if(id!==refreshID)return;
    const matches=(next.user.role==='resident')===(portal==='resident');
    logout.hidden=false;
    if(!matches){
      state=next;signature=null;
      root.innerHTML='<section class="card login stack"><h1>Switch workspace</h1><a class="button primary" href="'+(next.user.role==='resident'?'/resident/':'/collection/')+'">Open your workspace</a><button data-action="logout">Use another account</button></section>';
      return;
    }
    const key=JSON.stringify(next); state=next;
    if(force || key!==signature){signature=key; render();}
  } catch(e) {
    if(id!==refreshID)return;
    if(e.status===401){ if(state||!root.querySelector('[data-form="login"]')) signIn(state?'Session expired. Sign in again.':''); }
    else if(!state) root.innerHTML='<section class="card login stack"><h1>Connection unavailable</h1><p class="body-text">'+esc(e.message)+'</p><button data-action="refresh">Retry</button></section>';
    else if(force) throw e;
  } finally {if(id===refreshID)root.setAttribute('aria-busy','false');}
}
function render() {
  root.innerHTML=portal==='resident'?resident():collection();
}
function resident() {
  const p=state.pickups.find(x=>active.has(x.status));
  const loc=state.location;
  const primary=p?badge(p.status):'<span class="chip">No active request</span>';
  const detail=p?'<p class="body-text">'+esc(p.point)+' · '+esc(p.unit)+'</p>':loc?'<p class="body-text">'+esc(loc.point)+' · '+esc(loc.unit)+'</p>':'<p class="body-text muted">Set your pickup point to continue.</p>';
  const action=p?(p.status==='requested'?'<button data-action="cancel" data-id="'+esc(p.id)+'">Cancel request</button>':''):(loc?'<button class="primary" data-action="request">Request pickup</button>':'<button class="primary" data-action="edit">Set pickup point</button>');
  const history=state.pickups.filter(x=>!active.has(x.status));
  return '<div class="page-head"><div><h1>Your pickups</h1><p>'+esc(state.user.name)+'</p></div></div>'+
   '<div class="grid"><section class="card stack"><div class="row wrap"><h2>Current pickup</h2>'+primary+'</div>'+detail+'<div class="actions">'+action+'</div></section>'+
   '<section class="card stack"><div class="row wrap"><h2>Pickup point</h2>'+(loc&&!editing?'<button class="quiet" data-action="edit">Edit</button>':'')+'</div>'+
   (editing?locationForm(loc):loc?'<div class="location-lines"><strong>'+esc(loc.point)+'</strong><span class="subline">'+esc(loc.unit)+(loc.note?' · '+esc(loc.note):'')+'</span></div><a href="'+navLink(loc)+'" target="_blank" rel="noopener noreferrer">View map ↗</a>':'<p class="muted body-text">No saved point</p>')+
   '</section></div><section class="card history stack"><h2>Pickup history</h2>'+
   (history.length?history.map(x=>'<div class="list-item"><div><strong>'+esc(x.point)+'</strong><p class="subline">'+esc(fmt(x.updated))+(x.reason?' · '+esc(x.reason):'')+'</p></div>'+badge(x.status)+'</div>').join(''):'<p class="muted body-text">No completed requests</p>')+'</section>';
}
function locationForm(loc) {
  const val=k=>esc(loc?.[k]);
  return '<form class="stack" data-form="location">'+
   '<label>Gate or pickup point<input name="point" maxlength="80" required value="'+val('point')+'"></label>'+
   '<label>House / flat<input name="unit" maxlength="40" required value="'+val('unit')+'"></label>'+
   '<label>Landmark <small>Optional</small><input name="note" maxlength="160" value="'+val('note')+'"></label>'+
   '<div class="actions"><button type="button" data-action="gps">Use current location</button><button type="button" data-action="map">Pick on map</button></div>'+
   '<div id="pickup-map" class="map" hidden aria-label="Pickup point map"></div>'+
   '<div class="pair"><label>Latitude<input name="lat" required type="number" step="any" min="-90" max="90" value="'+val('lat')+'"></label><label>Longitude<input name="lon" required type="number" step="any" min="-180" max="180" value="'+val('lon')+'"></label></div>'+
   '<p class="form-msg" role="alert" hidden></p><div class="actions"><button class="primary">Save pickup point</button><button type="button" data-action="close">Cancel</button></div></form>';
}
function collection() {
  const dispatcher=state.user.role==='coordinator';
  const pending=state.pickups.filter(p=>active.has(p.status));
  const complete=state.pickups.filter(p=>!active.has(p.status));
  const groups=new Map();
  for(const p of pending) {
    const key=JSON.stringify([p.point.trim().toLowerCase(),p.lat,p.lon]);
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(p);
  }
  const stat=(count,label)=>'<div class="stat"><strong>'+count+'</strong><span>'+label+'</span></div>';
  return '<div class="page-head"><div><h1>'+(dispatcher?'Dispatch':'Your stops')+'</h1><p>'+esc(state.user.name)+'</p></div><div class="actions">'+(dispatcher?'<button class="primary" data-action="dispatch-open" aria-controls="dispatch-planner" aria-expanded="'+dispatchOpen+'">Generate route</button>':'')+'<button data-action="refresh">Refresh</button></div></div>'+
    '<div class="stats">'+stat(groups.size,'Active stops')+stat(pending.length,'Open pickups')+stat(complete.filter(x=>x.status==='collected').length,'Collected · recent')+'</div>'+
    (dispatcher?dispatchPanel():routeTools())+'<h2>Pickup queue</h2>'+
    (groups.size?[...groups.values()].map(group=>'<section class="card stop"><div class="row wrap"><div><h3>'+esc(group[0].point)+'</h3><p class="subline">'+group.length+' '+(group.length===1?'household':'households')+'</p></div>'+
      '<a class="button quiet" href="'+navLink(group[0])+'" target="_blank" rel="noopener noreferrer">Open map ↗</a></div>'+group.map(p=>stopRow(p,dispatcher)).join('')+'</section>').join(''):'<p class="empty stop">No pickups in the queue</p>')+
    '<section class="card history stack"><h2>Recent outcomes</h2>'+
    (complete.length?complete.map(p=>'<div class="list-item"><div><strong>'+esc(p.point)+'</strong><p class="subline">'+esc(p.unit)+' · '+esc(fmt(p.updated))+(p.reason?' · '+esc(p.reason):'')+'</p></div>'+badge(p.status)+'</div>').join(''):'<p class="muted body-text">No recent outcomes</p>')+'</section>';
}
function dispatchStops() {
  const points=new Map();
  for(const p of state.pickups.filter(p=>p.status==='requested'||p.status==='assigned')){
    const key=JSON.stringify([p.point.trim().toLowerCase(),p.lat,p.lon]);
    if(!points.has(key))points.set(key,{point:p.point,lat:p.lat,lon:p.lon});
  }
  return [...points.values()];
}
function dispatchPanel() {
  const stops=dispatchStops();
  const signature=JSON.stringify(stops);
  const plan=dispatchResult?.signature===signature?dispatchResult.plan:null;
  const km=metres=>(metres/1000).toFixed(2)+' km';
  return '<section id="dispatch-planner" class="card stack" style="margin-bottom:18px" '+(dispatchOpen?'':'hidden')+'>'+
    '<div class="row wrap"><h2>Route planner</h2><span class="chip">'+stops.length+' pending stops</span></div>'+
    '<p class="subline">One round trip for pending pickups. Estimates use straight-line distances, not roads.</p>'+
    '<form class="stack" data-form="dispatch-route"><div class="pair">'+
    '<label>Depot latitude<input name="lat" type="number" step="any" min="-90" max="90" required value="'+esc(depotDraft.lat)+'"></label>'+
    '<label>Depot longitude<input name="lon" type="number" step="any" min="-180" max="180" required value="'+esc(depotDraft.lon)+'"></label></div>'+
    '<div class="actions"><button class="primary" '+(!stops.length?'disabled':'')+'>Calculate route</button></div></form>'+
    (!stops.length?'<p class="subline">No requested or assigned pickups to plan.</p>':'')+
    (dispatchResult&&!plan?'<p class="subline">The queue changed. Calculate a new route.</p>':'')+
    (plan?'<div class="stack" role="status"><h3>Suggested stop order</h3><p class="body-text"><strong>'+km(plan.metres)+'</strong> round trip · '+esc(plan.method)+'</p>'+
    '<p class="subline">Nearest-stop baseline: '+km(plan.baselineMetres)+'</p><ol><li>Start at depot</li>'+
    plan.stops.map(p=>'<li><a href="'+navLink(p)+'" target="_blank" rel="noopener noreferrer">'+esc(p.point)+'</a></li>').join('')+
    '<li>Return to depot</li></ol></div>':'')+'</section>';
}
root.addEventListener('input',e=>{
  if(e.target.closest('[data-form="dispatch-route"]')){
    depotDraft[e.target.name]=e.target.value;
    dispatchResult=null;
    e.target.closest('#dispatch-planner').querySelector('[role="status"]')?.remove();
  }
});
function assignedStops() {
  const distinct = new Map();
  if(state?.user.role!=='crew')return distinct;
  for(const p of state.pickups.filter(p=>p.status==='assigned')) {
    const key=JSON.stringify([p.point.trim().toLowerCase(),p.lat,p.lon]);
    const old=distinct.get(key);
    if(!old||p.id<old.id)distinct.set(key,p);
  }
  return new Map([...distinct.values()].map(p=>[p.id,p]));
}
function routeMatches(report, stops) {
  if(report?.schema!==1||!Array.isArray(report.plans)||!Array.isArray(report.unrouted))return false;
  const plan=report.plans[1];
  if(!Array.isArray(plan?.stops)||!Number.isSafeInteger(plan.seconds)||plan.seconds<0)return false;
  const ids=[...plan.stops,...report.unrouted].map(p=>p?.id);
  return ids.length===stops.size&&new Set(ids).size===ids.length&&ids.every(id=>stops.has(id));
}
function routeTools() {
  const stops=assignedStops();
  const plan=routeMatches(routePlan,stops)?routePlan.plans[1]:null;
  const body=plan?'<p class="body-text">'+plan.seconds+' s estimated travel · '+plan.stops.length+'/'+stops.size+' stops routed</p>'+
    '<ol>'+plan.stops.map(p=>'<li>'+esc(stops.get(p.id).point)+'</li>').join('')+'</ol>'+
    (routePlan.unrouted.length?'<p class="subline">Unrouted: '+routePlan.unrouted.map(p=>esc(stops.get(p.id).point)).join(', ')+'</p>':''):'';
  return '<details class="card history" style="margin:0 0 18px" '+(plan?'open':'')+'><summary>Route tools</summary>'+
    '<div class="stack" style="margin-top:12px"><p class="subline">Export assigned stops, run the C++ planner, then load its JSON report.</p>'+
    '<div class="actions"><button data-action="route-export" '+(stops.size?'':'disabled')+'>Export stops</button>'+
    '<label>Load route plan<input type="file" id="route-import" accept=".json,application/json" '+(stops.size?'':'disabled')+'></label></div>'+body+'</div></details>';
}
function exportStops() {
  const stops=assignedStops();
  if(!stops.size)throw Error('No assigned stops to export.');
  const field=value=>String(value).replace(/[\t\r\n]+/g,' ');
  const rows=['id\tlabel\tlatitude\tlongitude',...[...stops.values()].map(p=>[p.id,field(p.point),p.lat,p.lon].join('\t'))];
  const url=URL.createObjectURL(new Blob([rows.join('\n')+'\n'],{type:'text/tab-separated-values;charset=utf-8'}));
  const link=document.createElement('a');
  link.href=url;link.download='greenloop-stops.tsv';
  link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
root.addEventListener('change',async e=>{
  if(e.target.id!=='route-import'||!e.target.files.length)return;
  try{
    const file=e.target.files[0];
    if(file.size>262144)throw Error('Route file is too large.');
    const report=JSON.parse(await file.text());
    if(!routeMatches(report,assignedStops()))throw Error('This route does not match your current assigned stops. Export them again.');
    routePlan=report;render();message('Route plan loaded.');
  }catch(error){message(error instanceof SyntaxError?'Choose a valid route-plan.json file.':error.message);}
});
function stopRow(p,dispatcher) {
  let controls='';
  if(dispatcher && (p.status==='requested'||p.status==='assigned')){
    controls=state.crew.length?'<form class="control-form" data-form="assign" data-id="'+esc(p.id)+'"><label>Collection crew<select name="crew" required><option value="">Select crew</option>'+state.crew.map(c=>'<option value="'+esc(c.id)+'" '+(c.id===p.assigned_to?'selected':'')+'>'+esc(c.name)+'</option>').join('')+'</select></label><button class="primary">Assign</button></form>':'<p class="subline">No crew accounts</p>';
  } else if(p.status==='assigned') {
    controls='<button class="primary" data-action="status" data-status="arrived" data-id="'+esc(p.id)+'">Mark arrived</button>';
  } else if(p.status==='arrived'&&!dispatcher) {
    controls='<div class="actions"><button class="primary" data-action="status" data-status="collected" data-id="'+esc(p.id)+'">Mark collected</button></div>'+
      '<details><summary>Couldn’t collect</summary><form class="control-form" data-form="unavailable" data-id="'+esc(p.id)+'"><label>Reason<select name="reason" required><option value="">Choose a reason</option><option>Waste not ready</option><option>Access blocked</option><option>Incorrect pickup point</option></select></label><button>Save outcome</button></form></details>';
  }
  return '<div class="list-item"><div class="row wrap"><div><strong>'+esc(p.resident)+' · '+esc(p.unit)+'</strong><p class="subline">'+esc([p.note,p.crew].filter(Boolean).join(' · '))+'</p></div>'+badge(p.status)+'</div><div>'+controls+'</div></div>';
}

let leaflet;
function getLeaflet() {
  if(window.L)return Promise.resolve(window.L);
  if(leaflet)return leaflet;
  const css=document.createElement('link');css.rel='stylesheet';css.href='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css';
  css.integrity='sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';css.crossOrigin='anonymous';document.head.append(css);
  leaflet=new Promise((resolve,reject)=>{
    const script=document.createElement('script');script.src='https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js';
    script.integrity='sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';script.crossOrigin='anonymous';
    script.onload=()=>window.L?resolve(window.L):reject(Error('Map unavailable.'));
    script.onerror=()=>{leaflet=null;reject(Error('Map unavailable. Enter coordinates instead.'));};document.head.append(script);
  });
  return leaflet;
}
function coordinates(form) {
  if(!form.elements.lat.value||!form.elements.lon.value||!form.elements.lat.validity.valid||!form.elements.lon.validity.valid)return null;
  return [Number(form.elements.lat.value),Number(form.elements.lon.value)];
}
function setCoordinates(form,lat,lon) {
  form.elements.lat.value=Number(lat).toFixed(6);
  form.elements.lon.value=Number(lon).toFixed(6);
  form.dispatchEvent(new Event('greenloop:pin'));
}
async function showMap(button) {
  const form=button.closest('form'), box=form.querySelector('.map');
  if(!box.hidden)return;
  const L=await getLeaflet();
  if(!box.isConnected)return;
  box.hidden=false;
  const pin=coordinates(form);
  const map=L.map(box).setView(pin||[22.5,79],pin?17:4);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'}).addTo(map);
  let marker;
  function move(center=false) {
    const pos=coordinates(form); if(!pos)return;
    if(!marker)marker=L.circleMarker(pos,{radius:8,color:'#fff',weight:3,fillColor:'#18553f',fillOpacity:1}).addTo(map);
    else marker.setLatLng(pos);
    if(center)map.setView(pos,17);
  }
  move(); form.addEventListener('greenloop:pin',()=>move(true));
  map.on('click',e=>{
    form.elements.lat.value=e.latlng.lat.toFixed(6);
    form.elements.lon.value=(((e.latlng.lng+180)%360+360)%360-180).toFixed(6);
    move();
  });
}
async function act(path,data,success) {
  await api(path,data);
  try {await refresh(true);}
  catch {message('Saved. Refresh to see the latest status.');return;}
  if(success)message(success);
}
async function doLogout(){await api('logout',{});++refreshID;signIn();}
logout.addEventListener('click',()=>doLogout().catch(e=>message(e.message)));
root.addEventListener('click',async e=>{
  const b=e.target.closest('button[data-action]'); if(!b||busy)return;
  const {action,id,status}=b.dataset;
  if(action==='edit'||action==='close'){editing=action==='edit';render();if(editing)root.querySelector('[name="point"]').focus();return;}
  busy=true;b.disabled=true;
  try {
    if(action==='logout')await doLogout();
    if(action==='refresh')await refresh(true);
    if(action==='dispatch-open'){
      dispatchOpen=!dispatchOpen;render();
      root.querySelector(dispatchOpen?'[data-form="dispatch-route"] [name="lat"]':'[data-action="dispatch-open"]').focus();
    }
    if(action==='route-export')exportStops();
    if(action==='request')await act('request',{},'Pickup requested.');
    if(action==='cancel')await act('cancel',{id},'Request cancelled.');
    if(action==='status')await act('status',{id,status},status==='arrived'?'Arrival recorded.':'Pickup completed.');
    if(action==='map')await showMap(b);
    if(action==='gps'){
      if(!navigator.geolocation)throw Error('Location is unavailable. Pick on map or enter coordinates.');
      const form=b.closest('form');
      const position=await new Promise((resolve,reject)=>navigator.geolocation.getCurrentPosition(resolve,()=>reject(Error('Location unavailable. Pick on map or enter coordinates.')),{enableHighAccuracy:true,timeout:12000,maximumAge:0}));
      if(form.isConnected){setCoordinates(form,position.coords.latitude,position.coords.longitude);message('Check the pin before saving.');}
    }
  } catch(e){message(e.message);if(e.status===401)signIn();}
  finally{busy=false;b.disabled=false;}
});
root.addEventListener('submit',async e=>{
  const form=e.target.closest('form[data-form]'); if(!form)return;
  e.preventDefault();if(busy)return;
  busy=true;const button=form.querySelector('button:not([type="button"])');button.disabled=true;
  const values=Object.fromEntries(new FormData(form)); const id=form.dataset.id;
  try {
    if(form.dataset.form==='login'){await api('login',{...values,portal});await refresh(true);}
    if(form.dataset.form==='location'){
      await api('location',values);editing=false;
      try{await refresh(true);message('Pickup point saved.');}catch{message('Saved. Reload to see the updated pickup point.');}
    }
    if(form.dataset.form==='dispatch-route'&&state.user.role==='coordinator'){
      const stops=dispatchStops();
      depotDraft={lat:values.lat,lon:values.lon};
      dispatchResult={signature:JSON.stringify(stops),plan:dispatchRoute({lat:Number(values.lat),lon:Number(values.lon)},stops)};
      render();
    }
    if(form.dataset.form==='assign')await act('assign',{id,crew:values.crew},'Crew assigned.');
    if(form.dataset.form==='unavailable')await act('status',{id,status:'unavailable',reason:values.reason},'Outcome recorded.');
  } catch(e){
    const error=form.querySelector('.form-msg');
    if(error){error.textContent=e.message;error.hidden=false;}else message(e.message);
    if(e.status===401 && form.dataset.form!=='login')signIn();
  } finally{busy=false;button.disabled=false;}
});
refresh();
setInterval(()=>{if(state&&!document.hidden&&!busy&&!editing&&!root.contains(document.activeElement))refresh();},15000);
