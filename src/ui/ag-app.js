'use strict';
// AFTERPLAY · Afterglow interface. One file, no framework: screens render from
// `state` (polled from the local API) and keep media elements alive between polls.
window.afterplayErrors=[];
window.addEventListener('error',e=>{window.afterplayErrors.push(String(e.message));window.afterplayErrors.splice(0,Math.max(0,window.afterplayErrors.length-20))});
window.addEventListener('unhandledrejection',e=>{window.afterplayErrors.push(String(e.reason?.message||e.reason));window.afterplayErrors.splice(0,Math.max(0,window.afterplayErrors.length-20))});

const token=location.pathname.split('/')[1],base=`/${token}/`;
const $=(s,r=document)=>r.querySelector(s),$$=(s,r=document)=>[...r.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// Interface text goes through the English catalog when it is enabled (ui/i18n.js).
const tr=s=>window.afterplayI18n?.text(s)??s;
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
const pad=(n,w=2)=>String(n).padStart(w,'0');
var state={clips:[],jobs:[],settings:{},replay:null,updates:null,auto_record:null,storage:null};

async function api(action,args={}){
 const r=await fetch(base+'api',{method:'POST',headers:{'Content-Type':'application/json','X-App-Token':token},body:JSON.stringify({action,args})});
 const x=await r.json();if(!r.ok||x?.error)throw Error(x?.error||'Ошибка запроса');return x;
}

// ---------- Icons (stroke, 24px grid)
const P={
 film:'<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4M17 8h4m-4 8h4"/>',
 clock:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
 rec:'<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3.5" fill="currentColor" stroke="none"/>',
 scissors:'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M20 4 8.1 15.9M14.5 14.5 20 20M8.1 8.1 12 12"/>',
 heart:'<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
 user:'<rect x="3" y="4" width="18" height="14" rx="2"/><path d="M8 21h8M12 18v3"/>',
 gear:'<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
 back:'<path d="M15 6l-6 6 6 6"/>',next:'<path d="M9 6l6 6-6 6"/>',
 x:'<path d="M6 6l12 12M18 6 6 18"/>',
 save:'<path d="M12 4v11m-5-5 5 5 5-5M5 19h14"/>',
 stop:'<rect x="7" y="7" width="10" height="10" rx="2"/>',
 folder:'<path d="M3 7V5a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
 trash:'<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
 full:'<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
 copy:'<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
 frameBack:'<path d="M14 6l-6 6 6 6"/><path d="M18 6v12"/>',frameFwd:'<path d="M10 6l6 6-6 6"/><path d="M6 6v12"/>',
 refresh:'<path d="M20 8a8 8 0 1 0 0 8M20 3v6h-6"/>',plus:'<path d="M12 5v14M5 12h14"/>',
 speaker:'<path d="M4 9v6h4l5 4V5L8 9z"/>',
};
const ic=(n,extra='')=>`<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra}>${P[n]||''}</svg>`;
const playIc='<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';
const pauseIc='<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>';

// ---------- Formatting
const clock=s=>{s=Math.max(0,Math.floor(Number(s)||0));return pad(Math.floor(s/3600))+':'+pad(Math.floor(s/60)%60)+':'+pad(s%60)};
const short=s=>{s=Math.max(0,Math.floor(Number(s)||0));return (s>=3600?Math.floor(s/3600)+':'+pad(Math.floor(s/60)%60):pad(Math.floor(s/60)))+':'+pad(s%60)};
const precise=s=>{s=Math.max(0,Number(s)||0);const w=Math.floor(s);return clock(w)+'.'+pad(Math.round((s-w)*1000)%1000,3)};
const bytes=n=>n>=1073741824?(n/1073741824).toFixed(1).replace('.',',')+' ГБ':n>=1048576?Math.max(1,Math.round(n/1048576))+' МБ':Math.max(1,Math.round((n||0)/1024))+' КБ';
const secondsText=s=>s>=60&&s%60===0?(s/60)+' мин':s+' с';
const months=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
function dayLabel(ts){
 const d=new Date(ts*1000),now=new Date(),day=new Date(now.getFullYear(),now.getMonth(),now.getDate());
 const diff=Math.floor((day-new Date(d.getFullYear(),d.getMonth(),d.getDate()))/86400000);
 if(diff<=0)return 'Сегодня';if(diff===1)return 'Вчера';if(diff<7)return 'На этой неделе';
 return '';
}
function monthName(ts){const d=new Date(ts*1000);return ['Январь','Февраль','Март','Апрель','Май','Июнь','Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь'][d.getMonth()]+(d.getFullYear()!==new Date().getFullYear()?' '+d.getFullYear():'')}
function groupOf(ts){const l=dayLabel(ts);return ['Сегодня','Вчера','На этой неделе'].includes(l)?l:monthName(ts)}
function timeOf(ts){const d=new Date(ts*1000),g=dayLabel(ts);const hm=pad(d.getHours())+':'+pad(d.getMinutes());return g==='Сегодня'||g==='Вчера'?g+', '+hm:d.getDate()+' '+months[d.getMonth()]+', '+hm}

// ---------- Clip helpers
const keyOf=v=>String(v||'').replaceAll('/','\\').toLowerCase();
function kindOf(c){
 if(/^Повтор-/i.test(c.name))return 'replay';
 if(/^Запись-/i.test(c.name))return 'record';
 const dir=keyOf(state.storage?.recordings_dir);
 return dir&&keyOf(c.path).startsWith(dir)?'clip':'video';
}
const kindLabel={replay:'Повтор',record:'Запись',clip:'Клип',video:'Видео'};
const isGif=c=>/\.gif$/i.test(c?.name||'');
// A GIF is labelled as GIF everywhere, never as "Видео".
const kindText=c=>{const k=kindOf(c);return isGif(c)?(k==='video'?'GIF':kindLabel[k]+' · GIF'):kindLabel[k]};
function nameOf(c){
 const stem=c.name.replace(/\.(mp4|mkv|mov|avi|webm|m4v|ts|gif)$/i,'');
 const m=stem.match(/^(Повтор|Запись)-(\d{4})-(\d\d)-(\d\d)_(\d\d)-(\d\d)-\d\d-[0-9a-f]{4}$/i);
 if(m)return tr(m[1]+' · '+Number(m[4])+' '+months[Number(m[3])-1]+', '+m[5]+':'+m[6]);
 return stem;
}
const gameOf=c=>state.settings.clip_games?.[c.id]||'';
function marksOf(c){try{const v=JSON.parse(c.marks||'[]');return Array.isArray(v)?v.filter(Number.isFinite):[]}catch{return []}}
const clipById=id=>state.clips.find(c=>c.id===id);
const thumbUrl=c=>base+'thumb/'+encodeURIComponent(c.id);
const initials=t=>String(t||'?').split(/\s+/).map(w=>w[0]).join('').slice(0,2).toUpperCase();
async function saveClipMeta(c,patch){
 await api('clip_save',{id:c.id,tags:c.tags||'',note:c.note||'',favorite:!!c.favorite,marks:marksOf(c),...patch});
 Object.assign(c,{favorite:patch.favorite??c.favorite,marks:patch.marks?JSON.stringify(patch.marks):c.marks});
}

// ---------- Toasts and confirm
function toast(text,error=false,sub=''){
 const box=$('#toasts'),el=document.createElement('div');el.className='toast'+(error?' err':'');el.setAttribute('role',error?'alert':'status');
 el.innerHTML=`<i aria-hidden="true"></i><span><b>${esc(text)}</b>${sub?` <span class="hint">${esc(sub)}</span>`:''}</span>`;
 box.append(el);while(box.children.length>3)box.firstChild.remove();
 setTimeout(()=>el.remove(),error?7000:4200);
}
function confirmBox(title,text,ok='Удалить',danger=true){
 return chooseBox(title,`<p>${esc(text)}</p>`,[{v:'yes',label:ok,cls:danger?'danger solid':'primary',focus:true}]).then(v=>v==='yes');
}
// Modal with Cancel plus the given choices; resolves to the chosen value or null.
function chooseBox(title,body,choices){
 return new Promise(resolve=>{
  const d=$('#confirm');d.innerHTML=`<h2>${esc(title)}</h2>${body}<div class="row"><button type="button" class="btn" data-dlg="">Отмена</button>${choices.map(c=>`<button type="button" class="btn ${c.cls||''}" data-dlg="${esc(c.v)}">${esc(c.label)}</button>`).join('')}</div>`;
  const done=v=>{d.close();resolve(v||null)};
  d.onclick=e=>{const b=e.target.closest('[data-dlg]');if(b)done(b.dataset.dlg)};
  d.oncancel=e=>{e.preventDefault();done(null)};
  d.showModal();const f=choices.find(c=>c.focus);$(`[data-dlg="${f?f.v:''}"]`,d).focus();
 });
}
const fail=e=>toast(e?.message||String(e),true);

// ---------- Jobs
const watchers=new Map();let jobTimer=0;
async function task(action,args={},cb={}){
 const r=await api(action,args);watchers.set(r.job,cb);cb.started?.(r.job);
 if(!jobTimer)jobTimer=setInterval(()=>{if(!watchers.size){clearInterval(jobTimer);jobTimer=0;return}pollState(true)},600);
 return r.job;
}
function processJobs(){
 for(const job of state.jobs){
  const cb=watchers.get(job.id);if(!cb)continue;
  if(job.status==='running'){cb.progress?.(job);continue}
  watchers.delete(job.id);
  if(job.status==='done')cb.done?.(job.result,job);
  else if(job.status==='cancelled')cb.cancelled?.(job);
  else{cb.error?cb.error(job):toast(job.message||'Операция не выполнена',true)}
 }
}

// ---------- Appearance
const ACCENTS=[['#FF8A3D','Янтарь'],['#2DD4BF','Бирюза'],['#A78BFA','Фиалка'],['#A3E635','Лайм'],['#F472B6','Роза']];
const custom=()=>state.settings.customization||{};
function accent(){const v=String(custom().afterglow_accent||'').toLowerCase();return (ACCENTS.find(a=>a[0].toLowerCase()===v)||ACCENTS[0])[0]}
let appliedLook='';
function applyLook(){
 const a=accent(),c=custom(),card=clamp(Number(c.card_size)||240,180,460),off=c.animation==='off';
 const key=[a,card,off].join('|');if(key===appliedLook)return;appliedLook=key;
 const rgb=a.slice(1).match(/../g).map(h=>parseInt(h,16)).join(',');
 const root=document.documentElement.style;root.setProperty('--accent',a);root.setProperty('--accent-rgb',rgb);root.setProperty('--card',card+'px');
 document.body.classList.toggle('no-motion',off);
 syncChrome(true);
}
let chromeKey='',chromeBusy=false;
async function syncChrome(force=false){
 // The native title bar sits above the WebView; give it our colors and live status.
 if(chromeBusy||document.hidden||window.customNativeHidden)return;
 const r=state.replay||{};const key=[accent(),r.phase,r.continuous,r.replay_enabled,r.phase==='recording'?Math.floor(Date.now()/1000):0].join('|');
 if(!force&&key===chromeKey)return;chromeBusy=true;
 try{const result=await api('window_chrome_config',{colors:{background:'#0b0c0f',panel:'#131519',text:'#f2f3f5',muted:'#a3a9b4',accent:accent().toLowerCase()}});if(result.styled||!result.native)chromeKey=key}
 catch{}finally{chromeBusy=false}
}

// ---------- Router
let view={screen:'library'};const backStack=[],fwdStack=[];
function go(next,push=true){
 if(push){backStack.push(view);if(backStack.length>50)backStack.shift();fwdStack.length=0}
 leave();view=next;enter();
}
window.historyDirection=d=>{
 if(d<0&&backStack.length){fwdStack.push(view);leave();view=backStack.pop();enter()}
 else if(d>0&&fwdStack.length){backStack.push(view);leave();view=fwdStack.pop();enter()}
};
function leave(){
 if(view.screen==='viewer')viewer.close();
 if(view.screen==='editor')editor.close();
 if(view.screen==='settings')settingsUI.leave();
}
function enter(){
 const staged=view.screen==='viewer'||view.screen==='editor';
 $('#stage').hidden=!staged;$('#app').inert=staged;
 if(view.screen==='viewer')return viewer.open(view.id,view.at);
 if(view.screen==='editor')return editor.open(view.id);
 window.scrollTo(0,0);render();
}

// ---------- Shell
const NAV=[['all','Все записи','film'],['replay','Повторы','clock'],['record','Записи','rec'],['clip','Клипы','scissors']];
function renderShell(){
 const counts={all:state.clips.length,replay:0,record:0,clip:0};
 for(const c of state.clips){const k=kindOf(c);if(k in counts)counts[k]++}
 const lib=view.screen==='library';
 $('#nav').innerHTML=NAV.map(([id,label,icon])=>`<button type="button" data-act="nav" data-kind="${id}" ${lib&&libUI.kind===id?'aria-current="page"':''}>${ic(icon)}<span>${label}</span><span class="count">${counts[id]}</span></button>`).join('')+
  `<hr><button type="button" data-act="go" data-screen="profiles" ${view.screen==='profiles'?'aria-current="page"':''}>${ic('user')}<span>Профили записи</span></button><button type="button" data-act="go" data-screen="settings" ${view.screen==='settings'?'aria-current="page"':''}>${ic('gear')}<span>Настройки</span></button>`;
 const total=state.clips.reduce((s,c)=>s+(c.size||0),0),disk=state.storage||{};
 const used=disk.disk_total?Math.round((disk.disk_total-disk.disk_free)/disk.disk_total*100):0;
 $('#disk').innerHTML=disk.disk_total?`<div><span>Свободно на диске</span><span class="num">${bytes(disk.disk_free)}</span></div><div class="bar" aria-hidden="true"><span style="width:${used}%"></span></div><div><span>${state.clips.length} записей · ${bytes(total)}</span></div>`:`<div><span>${state.clips.length} записей · ${bytes(total)}</span></div>`;
 renderHeader();
}
function renderHeader(){
 const lib=view.screen==='library';
 const titles={profiles:'Профили записи',settings:'Настройки'};
 const left=$('#hdLeft');const want=lib?'search':'title:'+view.screen;
 if(left.dataset.mode!==want){
  left.dataset.mode=want;
  left.innerHTML=lib?`<label class="search"><span class="sr">Поиск записей</span>${ic('search')}<input id="search" type="search" placeholder="Поиск по названию и игре" autocomplete="off" value="${esc(libUI.query)}"></label>`:`<h1>${titles[view.screen]||''}</h1>`;
 }
 renderProfileChip();renderDock();
}
function selectedProfile(){
 const rows=Object.values(state.settings.capture_profiles||{});
 return rows.find(p=>keyOf(p.id||p.path)===keyOf(state.settings.selected_capture_profile))||rows.find(p=>p.id==='screen:default')||rows[0];
}
function renderProfileChip(){
 const auto=!!state.auto_record?.active&&['starting','recording','stopping'].includes(state.replay?.phase);
 const name=(auto?state.replay?.active_profile:selectedProfile()?.name)||tr('Не выбран');
 const html=`<button type="button" class="chip-profile" data-act="go" data-screen="profiles" title="${esc((auto?'Автозапись: ':'Профиль: ')+name)}"><span class="ini" aria-hidden="true" data-i18n-ignore>${esc(initials(name))}</span><span><small>${auto?'Автозапись':'Профиль'}</small><b data-i18n-ignore>${esc(name)}</b></span></button>`;
 const host=$('#chip');if(host.dataset.html!==html){host.dataset.html=html;host.innerHTML=html}
}
let polledReplay=null,polledAt=0;
function liveSeconds(r){if(r!==polledReplay){polledReplay=r;polledAt=performance.now()}return (r.recording_seconds||0)+(performance.now()-polledAt)/1000}
function quickValues(){const v=state.settings.quick_clips;return Array.isArray(v)&&v.length>=2?v.slice(0,2):[30,120]}
function dockState(){
 const r=state.replay||{},keys=state.settings.hotkeys||{};
 const busy=['starting','stopping'].includes(r.phase)||!!r.finishing;
 const live=r.phase==='recording',manual=!!(r.continuous||r.pending_recording),replay=!!r.replay_enabled&&live;
 const minutes=Math.round((r.settings?.seconds||300)/60);
 let mode='off',title='Запись выключена',sub='Повтор и запись не идут';
 if(r.phase==='starting'){mode='busy';title='Запуск…';sub='Подключаем захват'}
 else if(r.phase==='stopping'||r.finishing){mode='busy';title='Сохранение…';sub='Дождитесь завершения'}
 else if(live&&manual){mode='record';title='Запись '+clock(liveSeconds(r));sub=replay?'и повтор · '+minutes+' мин':(r.active_profile||'Идёт запись')}
 else if(live){mode='replay';title='Повтор · '+minutes+' мин';sub=keys.save?keys.save+' — сохранить':'Буфер '+clock(r.buffer_seconds)}
 else if(r.phase==='error'){mode='error';title='Ошибка записи';sub=r.error||''}
 if(r.saving&&mode!=='busy')sub='Сохраняю клип…';
 const fill=mode==='replay'?Math.min(100,Math.round((r.buffer_seconds||0)/(r.settings?.seconds||300)*100)):0;
 return {r,keys,busy,manual,replay,mode,title,sub,fill,canSave:live&&!busy&&(r.save_queue||0)<8};
}
function renderDock(){
 const s=dockState(),q=quickValues();
 document.body.classList.toggle('recording',s.mode==='record');
 const html=`<div class="dock" data-mode="${s.mode}" role="group" aria-label="Управление записью">`+
  `<button type="button" class="dk-status" data-act="go" data-screen="profiles" title="${esc(s.title+' · '+s.sub)}"><i class="dot" aria-hidden="true"></i><span class="dk-text"><b>${esc(s.title)}</b><small>${esc(s.sub)}</small></span>${s.mode==='replay'?`<span class="dk-fill" aria-hidden="true"><span style="width:${s.fill}%"></span></span>`:''}</button>`+
  `<span class="dk-sep" aria-hidden="true"></span>`+
  `<button type="button" class="dk-toggle ${s.replay?'on':''}" data-act="${s.replay?'replay-stop':'replay-start'}" aria-pressed="${s.replay}" title="${s.replay?'Выключить повтор':'Включить повтор'}" ${s.busy?'disabled':''}>${ic('clock')}<span>Повтор</span></button>`+
  `<button type="button" class="dk-toggle dk-rec ${s.manual?'on':''}" data-act="${s.manual?'record-stop':'record-start'}" aria-pressed="${s.manual}" title="${s.manual?'Остановить и сохранить запись':'Начать запись'}${s.keys.record?' · '+esc(s.keys.record):''}" ${s.busy?'disabled':''}>${s.manual?ic('stop'):'<i class="rec-dot" aria-hidden="true"></i>'}<span>${s.manual?'Стоп':'Запись'}</span></button>`+
  `<span class="dk-sep" aria-hidden="true"></span>`+
  `<button type="button" class="dk-save" data-act="save" title="Сохранить повтор${s.keys.save?' · '+esc(s.keys.save):''}" ${s.canSave?'':'disabled'}>${ic('save')}<span>Сохранить</span>${s.keys.save?`<kbd>${esc(s.keys.save)}</kbd>`:''}</button>`+
  q.map((sec,i)=>`<button type="button" class="dk-quick" data-act="quick" data-index="${i}" title="Быстрый клип: последние ${secondsText(sec)}${s.keys['clip_'+(i+1)]?' · '+esc(s.keys['clip_'+(i+1)]):''}" aria-label="Сохранить последние ${secondsText(sec)}" ${s.canSave?'':'disabled'}>${secondsText(sec)}</button>`).join('')+`</div>`;
 const host=$('#dock');if(host.dataset.html!==html){host.dataset.html=html;host.innerHTML=html}
}
function render(){
 applyLook();renderShell();
 const main=$('#view');
 if(view.screen==='library')main.innerHTML=libraryHTML(),afterLibrary();
 else if(view.screen==='profiles')profiles.render();
 else if(view.screen==='settings')settingsUI.render();
}

// ---------- Library
const libUI={kind:'all',chip:'all',query:'',sel:null,limit:120,sig:'',detailSig:''};
function libraryRows(){
 const q=libUI.query.trim().toLocaleLowerCase();
 return state.clips.filter(c=>(libUI.kind==='all'||kindOf(c)===libUI.kind)&&(libUI.chip!=='marks'||marksOf(c).length)&&(libUI.chip!=='fav'||c.favorite)&&(!q||(nameOf(c)+' '+c.name+' '+gameOf(c)).toLocaleLowerCase().includes(q)));
}
function stepsHTML(){
 if(state.settings.onboarding?.status==='completed')return '';
 const r=state.replay||{},hasReplay=state.clips.some(c=>kindOf(c)==='replay');
 const steps=[['Включить повтор',!!r.replay_enabled||hasReplay,'replay-start'],['Проверить горячую клавишу',!!r.hotkey_ok,'open-keys'],['Сохранить первый повтор',hasReplay,'save']];
 const done=steps.filter(s=>s[1]).length;
 if(done===3){api('onboarding_config',{status:'completed'}).then(v=>state.settings.onboarding=v).catch(()=>{});return ''}
 return `<section class="card steps" aria-label="Первые шаги"><div class="t"><b>Первые шаги</b><span class="hint num">${done} из 3 готово</span></div>${steps.map(([label,ok,act])=>`<button type="button" class="step ${ok?'done':''}" data-act="${ok?'noop':act}"><i aria-hidden="true">${ok?'✓':''}</i>${label}</button>`).join('')}<span class="grow"></span><button type="button" class="btn icon ghost" data-act="steps-hide" aria-label="Скрыть первые шаги">${ic('x')}</button></section>`;
}
function cardHTML(c){
 const k=kindOf(c),m=marksOf(c).length,sel=libUI.sel===c.id;
 const meta=[gameOf(c),timeOf(c.mtime),bytes(c.size)].filter(Boolean).join(' · ');
 return `<button type="button" class="clip ${sel?'sel':''}" data-act="select" data-id="${esc(c.id)}" aria-pressed="${sel}" aria-label="${esc(nameOf(c)+', '+short(c.duration))}"><div class="thumb"><img src="${esc(thumbUrl(c))}" loading="lazy" alt=""><span class="badge kind ${k}${isGif(c)?' gif':''}">${kindText(c)}</span>${m?`<span class="badge marks">★ ${m}</span>`:''}${c.favorite?`<span class="badge fav" aria-label="В избранном">♥</span>`:''}<span class="badge dur">${short(c.duration)}</span></div><div class="meta"><b data-i18n-ignore>${esc(nameOf(c))}</b><small>${esc(meta)}</small></div></button>`;
}
function gridHTML(rows){
 const shown=rows.slice(0,libUI.limit);const groups=new Map();
 for(const c of shown){const g=groupOf(c.mtime);if(!groups.has(g))groups.set(g,[]);groups.get(g).push(c)}
 return [...groups].map(([label,items])=>`<section class="group"><h2 class="sec">${esc(label)}</h2><div class="grid">${items.map(cardHTML).join('')}</div></section>`).join('')+
  (rows.length>shown.length?`<button type="button" class="btn more" data-act="more">Показать ещё ${Math.min(120,rows.length-shown.length)}</button>`:'')+
  (!rows.length?`<div class="empty">${state.clips.length?'Ничего не найдено. Измените запрос или фильтр.':'Здесь появятся повторы и записи. Включите повтор кнопкой сверху или добавьте папку с видео в настройках.'}</div>`:'');
}
function libraryHTML(){
 const rows=libraryRows();
 if(libUI.sel&&!clipById(libUI.sel))libUI.sel=null;
 if(!libUI.sel&&rows.length)libUI.sel=rows[0].id;
 const titles={all:'Библиотека',replay:'Повторы',record:'Записи',clip:'Клипы'};
 const chips=[['all','Все'],['marks','С метками'],['fav','Избранное']];
 return `<div class="lib"><div class="lib-main">${stepsHTML()}<div class="lib-top"><h1>${titles[libUI.kind]}</h1><span class="num" id="libCount">${rows.length} записей</span><span class="grow"></span><div class="chips" role="group" aria-label="Фильтр">${chips.map(([id,l])=>`<button type="button" data-act="chip" data-chip="${id}" aria-pressed="${libUI.chip===id}">${l}</button>`).join('')}</div></div><div id="libGrid">${gridHTML(rows)}</div></div><aside class="detail" id="detail" aria-label="О записи"></aside></div>`;
}
function libSignature(){return state.clips.map(c=>c.id+c.favorite+c.size+c.duration+(c.marks||'')+(state.settings.clip_games?.[c.id]||'')).join('|')+libUI.kind+libUI.chip+libUI.query+libUI.limit}
function afterLibrary(){libUI.sig=libSignature();renderDetail(true)}
function refreshLibrary(){
 if(view.screen!=='library')return;
 const sig=libSignature();if(sig===libUI.sig)return renderDetail();
 libUI.sig=sig;const rows=libraryRows();
 if(libUI.sel&&!clipById(libUI.sel))libUI.sel=rows[0]?.id||null;
 if(!$('#libGrid'))return render();
 const steps=$('.steps');const html=stepsHTML();if(steps&&!html)steps.remove();
 $('#libGrid').innerHTML=gridHTML(rows);$('#libCount').textContent=rows.length+' записей';renderDetail();
}
const mediaInfo=new Map();
function loadInfo(id){
 if(mediaInfo.has(id))return mediaInfo.get(id);
 const p=api('clip_media_info',{id}).catch(()=>({fps:0,audio:[]}));mediaInfo.set(id,p);
 if(mediaInfo.size>80)mediaInfo.delete(mediaInfo.keys().next().value);return p;
}
function renderDetail(force=false){
 const box=$('#detail');if(!box)return;const c=libUI.sel&&clipById(libUI.sel);
 const sig=c?[c.id,c.favorite,c.marks,c.size,gameOf(c)].join('|'):'none';
 if(!force&&sig===libUI.detailSig)return;libUI.detailSig=sig;
 if(!c){box.innerHTML=`<h2 class="sec">О записи</h2><p class="hint">Выберите запись, чтобы увидеть сведения.</p>`;return}
 const k=kindOf(c),marks=marksOf(c);
 box.innerHTML=`<div class="row"><h2 class="sec">О записи</h2><button type="button" class="btn icon ghost" data-act="fav" data-id="${esc(c.id)}" aria-pressed="${!!c.favorite}" aria-label="${c.favorite?'Убрать из избранного':'В избранное'}" style="color:${c.favorite?'var(--accent)':'inherit'}">${ic('heart',c.favorite?'fill="currentColor"':'')}</button></div>
 <button type="button" class="big" data-act="watch" data-id="${esc(c.id)}" aria-label="Смотреть"><img src="${esc(thumbUrl(c))}" alt=""><span class="play" aria-hidden="true">${playIc}</span><span class="badge dur">${short(c.duration)}</span></button>
 <div><h3 data-i18n-ignore>${esc(nameOf(c))}</h3><div class="sub">${esc([gameOf(c),kindText(c)].filter(Boolean).join(' · '))}</div></div>
 <div class="acts"><button type="button" class="btn primary" data-act="watch" data-id="${esc(c.id)}">Смотреть</button>${isGif(c)?'':`<button type="button" class="btn" data-act="edit" data-id="${esc(c.id)}">Обрезать</button>`}<button type="button" class="btn" data-act="edit" data-id="${esc(c.id)}" data-export="1">Экспорт</button></div>
 <dl class="facts"><dt>Формат</dt><dd>${isGif(c)?'GIF-анимация':'Видео '+esc((c.name.match(/\.(\w+)$/)?.[1]||'').toUpperCase())}</dd><dt>Дата</dt><dd>${esc(timeOf(c.mtime))}</dd><dt>Длительность</dt><dd>${clock(c.duration)}</dd><dt>Размер</dt><dd>${bytes(c.size)}</dd><dt>${isGif(c)?'Кадр':'Видео'}</dt><dd id="dtVideo">${c.width?c.width+' × '+c.height:'—'}</dd><dt>Звук</dt><dd>${isGif(c)?'нет (GIF без звука)':c.audio?c.audio+' '+(c.audio===1?'дорожка':c.audio<5?'дорожки':'дорожек'):'нет'}</dd></dl>
 <div class="field"><span class="lbl">Метки</span><div class="marks">${marks.length?marks.map(m=>`<button type="button" class="mark" data-act="watch" data-id="${esc(c.id)}" data-at="${m}">★ ${short(m)}</button>`).join(''):'<span class="hint">Нет меток. Во время записи нажмите клавишу метки — она появится здесь.</span>'}</div></div>
 ${c.error?`<p class="hint" style="color:#FFB4B5">${esc(c.error)}</p>`:''}
 <span class="grow"></span>
 <div style="display:flex;gap:8px"><button type="button" class="btn" style="flex:1" data-act="reveal" data-id="${esc(c.id)}">${ic('folder')}Показать в папке</button><button type="button" class="btn danger" data-act="delete" data-id="${esc(c.id)}">Удалить</button></div>`;
 if(c.width&&!/\.gif$/i.test(c.name))loadInfo(c.id).then(info=>{const el=$('#dtVideo');if(el&&libUI.sel===c.id&&info.fps)el.textContent=c.width+' × '+c.height+' · '+Math.round(info.fps)+' fps'});
}
function selectClip(id){
 libUI.sel=id;for(const el of $$('.clip')){const on=el.dataset.id===id;el.classList.toggle('sel',on);el.setAttribute('aria-pressed',String(on))}
 renderDetail(true);
}

// ---------- Viewer (full window)
const viewer={
 c:null,v:null,raf:0,extras:new Map(),on:new Set([0]),speed:1,idleT:0,menu:false,sprite:null,scrubbing:false,keys:null,info:null,
 list(){const rows=libraryRows();return rows.length?rows:state.clips},
 open(id,at){
  const c=clipById(id);if(!c){go({screen:'library'},false);return}
  this.c=c;this.on=new Set([0]);this.extras=new Map();this.userMuted=false;this.speed=1;this.menu=false;this.sprite=null;this.info=null;this.frame=1/60;this.shown=null;
  const list=this.list(),i=list.findIndex(x=>x.id===id),marks=marksOf(c),cust=custom();
  const stage=$('#stage');stage.className='vw';
  const gif=this.gif=isGif(c);
  const hd=`<header class="st-hd"><button type="button" class="btn ghost" data-act="back">${ic('back')}Библиотека</button><div class="ttl"><b data-i18n-ignore>${esc(nameOf(c))}</b><small>${esc([gif?'GIF':'',gameOf(c),timeOf(c.mtime),i>=0?(i+1)+' из '+list.length:''].filter(Boolean).join(' · '))}</small></div><span class="grow"></span>
  <button type="button" class="btn icon ghost" data-act="vw-fav" aria-pressed="${!!c.favorite}" aria-label="В избранное" style="color:${c.favorite?'var(--accent)':'inherit'}">${ic('heart',c.favorite?'fill="currentColor"':'')}</button>
  ${gif?'':`<button type="button" class="btn" data-act="edit" data-id="${esc(c.id)}">${ic('scissors')}Обрезать</button>`}<button type="button" class="btn primary" data-act="edit" data-id="${esc(c.id)}" data-export="1">Экспорт</button></header>`;
  const nav=`<button type="button" class="side-nav l" data-act="vw-step" data-dir="-1" aria-label="Предыдущая запись">${ic('back')}</button><button type="button" class="side-nav r" data-act="vw-step" data-dir="1" aria-label="Следующая запись">${ic('next')}</button>`;
  if(gif){
   // GIF is an image, not a video: <video> cannot play it. Frames are decoded with
   // ImageDecoder and drawn on a canvas so the GIF can pause and step frame by frame.
   this.v=null;const src=`${base}media/${encodeURIComponent(c.id)}`;
   stage.innerHTML=hd+`<div class="vw-stage">${nav}<div class="vw-frame" id="vwFrame"><canvas class="vw-gif" id="vwGif"></canvas><button type="button" class="vw-hit" data-act="vw-gif-play" aria-label="Воспроизвести или пауза"></button></div></div>
   <div class="vw-ctl"><div class="ctl-row"><button type="button" class="btn icon" data-act="vw-gif-frame" data-d="-1" aria-label="Кадр назад">${ic('frameBack')}</button><button type="button" class="btn icon primary" data-act="vw-gif-play" id="vwPlay" aria-label="Пауза">${pauseIc}</button><button type="button" class="btn icon" data-act="vw-gif-frame" data-d="1" aria-label="Кадр вперёд">${ic('frameFwd')}</button><button type="button" class="btn ghost sm num" data-act="vw-gif-jump" data-d="-5">−5 с</button><button type="button" class="btn ghost sm num" data-act="vw-gif-jump" data-d="5">+5 с</button>
    <span class="num" style="padding:0 8px;color:var(--muted)" id="vwGifPos">Загрузка…</span><span class="fmt-badge">GIF</span><span class="hint"><span>без звука</span>${c.width?' · '+c.width+' × '+c.height:''}</span><span class="grow"></span><span class="hint keyhint">Пробел — пауза · ← → — кадр · Shift + ← → — 5 с · F или двойной клик — весь экран · Esc — назад</span><button type="button" class="btn icon" data-act="vw-full" aria-label="Во весь экран">${ic('full')}</button></div></div>`;
   this.keys=e=>this.key(e);document.addEventListener('keydown',this.keys);
   $('#vwFrame').addEventListener('dblclick',e=>{e.preventDefault();this.fullscreen()});
   this.fsch=()=>{this.wake();this.paintFull()};document.addEventListener('fullscreenchange',this.fsch);
   this.gifOpen(c,src);
   return;
  }
  stage.innerHTML=hd+`<div class="vw-stage">${nav}
   <div class="vw-frame" id="vwFrame"><video id="vwVideo" preload="auto" playsinline src="${base}media/${encodeURIComponent(c.id)}"></video><button type="button" class="vw-hit" data-act="vw-play" aria-label="Воспроизвести или пауза"><span class="bigplay" id="vwBig" aria-hidden="true">${playIc}</span></button><span class="vw-badge" id="vwMark" style="left:14px;background:var(--accent);color:var(--on-accent)" hidden>★ Метка</span><span class="vw-badge" id="vwSpeedBadge" style="right:14px;background:rgba(11,12,15,.8)" hidden></span></div></div>
  <div class="vw-ctl"><div class="scrub" id="vwScrub" role="slider" tabindex="0" aria-label="Позиция" aria-valuemin="0" aria-valuemax="${Math.round(c.duration)}"><div class="rail"><div class="buf" id="vwBuf"></div><div class="fill" id="vwFill"></div></div>${marks.map(m=>`<span class="pin" style="left:${(m/c.duration*100).toFixed(3)}%"></span>`).join('')}<span class="knob" id="vwKnob"></span><div class="preview" id="vwPrev" hidden><div class="pic" id="vwPic"></div><span id="vwPrevT"></span></div></div>
   <div class="ctl-row"><button type="button" class="btn icon" data-act="vw-frame" data-d="-1" aria-label="Кадр назад">${ic('frameBack')}</button><button type="button" class="btn icon primary" data-act="vw-play" id="vwPlay" aria-label="Воспроизвести">${playIc}</button><button type="button" class="btn icon" data-act="vw-frame" data-d="1" aria-label="Кадр вперёд">${ic('frameFwd')}</button><button type="button" class="btn ghost sm num" data-act="vw-seek" data-d="-5">−5 с</button><button type="button" class="btn ghost sm num" data-act="vw-seek" data-d="5">+5 с</button><span class="num" style="padding:0 8px;color:var(--muted)"><b id="vwTime" style="color:var(--text);font-weight:600">00:00</b> / ${short(c.duration)}</span>
    <div class="vol"><button type="button" class="btn icon ghost" data-act="vw-mute" id="vwMute" aria-label="Выключить звук">${ic('speaker')}</button><input type="range" id="vwVol" min="0" max="100" value="${Math.round((Number(localGet('ag.volume'))||0.8)*100)}" aria-label="Громкость"><span class="num hint" id="vwVolT" style="width:38px"></span></div>
    <span class="grow"></span><div class="seg" id="vwTracks" role="group" aria-label="Звуковые дорожки — можно включить несколько" hidden></div>
    <div class="menu-wrap"><button type="button" class="btn" data-act="vw-menu" aria-haspopup="true" aria-expanded="false" id="vwSpeed">Скорость 1×</button><div class="menu" id="vwMenu" role="menu" hidden>${[0.1,0.25,0.5,1,1.5,2,3,4,5].map(v=>`<button type="button" role="menuitemradio" data-act="vw-rate" data-v="${v}" aria-checked="${v===1}"><span>${String(v).replace('.',',')}×</span><span>${v===1?'✓':''}</span></button>`).join('')}</div></div>
    <button type="button" class="btn icon" data-act="vw-full" aria-label="Во весь экран">${ic('full')}</button></div>
   <div class="ctl-row"><span class="hint">Метки</span>${marks.length?marks.map(m=>`<button type="button" class="mark" data-act="vw-to" data-t="${m}">★ ${short(m)}</button>`).join(''):'<span class="hint">нет</span>'}<span class="grow"></span><span class="hint keyhint">Пробел — пауза · ← → — кадр · Shift + ← → — 5 с · ↑ ↓ — громкость · &lt; &gt; — скорость · F или двойной клик — весь экран · Esc — назад</span></div></div>`;
  const v=this.v=$('#vwVideo');v.volume=clamp(Number(localGet('ag.volume'))||0.8,0,1);this.syncVol();
  v.addEventListener('play',()=>{this.paint();this.loop();this.syncExtra();this.wake()});v.addEventListener('pause',()=>{this.paint();this.syncExtra();this.wake()});
  v.addEventListener('seeked',()=>{this.paint();this.syncExtra(true)});v.addEventListener('timeupdate',()=>{if(v.paused)this.paint()});
  v.addEventListener('loadedmetadata',()=>{if(at)v.currentTime=clamp(Number(at),0,v.duration||c.duration);this.paint()},{once:true});
  v.addEventListener('progress',()=>this.paintBuffer());v.addEventListener('ended',()=>this.paint());
  const sc=$('#vwScrub');
  sc.addEventListener('pointerdown',e=>{if(e.button)return;sc.setPointerCapture(e.pointerId);this.scrubbing=true;sc.classList.add('drag');this.seekTo(this.frac(e)*this.dur())});
  sc.addEventListener('pointermove',e=>{const f=this.frac(e);this.preview(f);if(this.scrubbing)this.seekTo(f*this.dur())});
  const end=e=>{if(this.scrubbing){this.scrubbing=false;sc.classList.remove('drag');try{sc.releasePointerCapture(e.pointerId)}catch{}}};
  sc.addEventListener('pointerup',end);sc.addEventListener('pointercancel',end);sc.addEventListener('pointerleave',()=>{if(!this.scrubbing)$('#vwPrev').hidden=true});
  sc.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();e.stopPropagation();this.arrow(e)}});
  $('#vwVol').addEventListener('input',e=>{v.volume=Number(e.target.value)/100;this.userMuted=false;localSet('ag.volume',v.volume);this.syncVol();this.syncExtra()});
  this.keys=e=>this.key(e);document.addEventListener('keydown',this.keys);
  $('#vwFrame').addEventListener('dblclick',e=>{e.preventDefault();this.fullscreen()});
  stage.addEventListener('pointermove',()=>this.wake());
  this.fsch=()=>{this.wake();this.paintFull()};document.addEventListener('fullscreenchange',this.fsch);
  if(!/\.gif$/i.test(c.name))loadInfo(c.id).then(info=>{if(this.c!==c)return;this.info=info;if(info?.fps>0)this.frame=1/info.fps;this.renderTracks()});
  v.play().catch(()=>{});
 },
 // ← → step one frame (like the trim editor); Shift jumps 5 s.
 arrow(e){const dir=e.key==='ArrowLeft'?-1:1;if(e.shiftKey)this.seekTo(this.v.currentTime+dir*5);else this.stepFrame(dir)},
 stepFrame(dir){const v=this.v;if(!v)return;if(!v.paused)v.pause();this.seekTo(v.currentTime+dir*this.frame)},
 // ---- GIF playback: decoded frames on a canvas, so pause and frame stepping work.
 async gifOpen(c,src){
  const g=this.g={c,dec:null,n:0,i:0,playing:true,timer:0,busy:false,closed:false};
  const pos=()=>$('#vwGifPos');
  try{
   if(!window.ImageDecoder)throw Error('no decoder');
   const r=await fetch(src);if(!r.ok)throw Error('load');
   const dec=new ImageDecoder({data:await r.arrayBuffer(),type:'image/gif'});
   await dec.tracks.ready;await dec.completed;
   if(g.closed){dec.close();return}
   g.dec=dec;g.n=dec.tracks.selectedTrack.frameCount||1;
   await this.gifDraw(0);if(g.playing)this.gifSchedule();
  }catch{
   // No decoder: fall back to a plain animated image (plays, but cannot be stepped).
   if(g.closed)return;const cv=$('#vwGif');if(!cv)return;
   const img=document.createElement('img');img.className='vw-gif';img.src=src;img.alt='';cv.replaceWith(img);
   const p=pos();if(p)p.textContent='Покадровый просмотр недоступен';
   for(const b of $$('[data-act=vw-gif-frame],[data-act=vw-gif-play],[data-act=vw-gif-jump]'))b.disabled=true;
  }
 },
 async gifDraw(i){
  const g=this.g;if(!g?.dec||g.closed)return 0;
  g.i=((i%g.n)+g.n)%g.n;
  const {image}=await g.dec.decode({frameIndex:g.i});
  const cv=$('#vwGif');let ms=100;
  if(cv&&!g.closed){
   if(cv.width!==image.displayWidth||cv.height!==image.displayHeight){cv.width=image.displayWidth;cv.height=image.displayHeight}
   cv.getContext('2d').drawImage(image,0,0);
  }
  if(image.duration)ms=image.duration/1000;image.close();
  const p=$('#vwGifPos');if(p)p.textContent='Кадр '+(g.i+1)+' / '+g.n;
  return ms<20?100:ms; // browsers treat near-zero GIF delays as 100 ms
 },
 gifSchedule(){
  const g=this.g;if(!g?.dec||g.closed)return;clearTimeout(g.timer);
  const run=async()=>{if(!g.playing||g.closed)return;const ms=await this.gifDraw(g.i);if(!g.playing||g.closed)return;g.timer=setTimeout(()=>{g.i++;run()},ms)};
  run();
 },
 gifPaintPlay(){const g=this.g,b=$('#vwPlay');if(!g||!b)return;b.innerHTML=g.playing?pauseIc:playIc;b.setAttribute('aria-label',g.playing?'Пауза':'Воспроизвести')},
 gifToggle(){const g=this.g;if(!g?.dec)return;g.playing=!g.playing;clearTimeout(g.timer);if(g.playing){g.i++;this.gifSchedule()}this.gifPaintPlay()},
 // Shift + ← → jumps 5 s like in video: convert seconds to frames by the average frame length.
 // Unlike single-frame steps it does not wrap around: a GIF is often shorter than 5 s,
 // so wrapping would land on the same frame. It stops at the first or last frame, like video.
 gifJump(sec){const g=this.g;if(!g?.dec)return;const per=(this.c?.duration>0?this.c.duration:g.n/10)/g.n;const d=Math.round(sec/(per||.1))||Math.sign(sec);this.gifStep(clamp(g.i+d,0,g.n-1)-g.i)},
 async gifStep(d){const g=this.g;if(!g?.dec||g.busy||!d)return;if(g.playing){g.playing=false;clearTimeout(g.timer);this.gifPaintPlay()}g.busy=true;try{await this.gifDraw(g.i+d)}finally{g.busy=false}},
 close(){
  if(this.g){this.g.closed=true;clearTimeout(this.g.timer);try{this.g.dec?.close()}catch{}this.g=null}
  cancelAnimationFrame(this.raf);document.removeEventListener('keydown',this.keys);document.removeEventListener('fullscreenchange',this.fsch);clearTimeout(this.idleT);clearTimeout(this.drift);$('#stage').classList.remove('idle');
  if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});
  if(this.v){this.v.pause();this.v.removeAttribute('src');this.v.load()}
  for(const a of this.extras.values()){a.pause();a.removeAttribute('src')}this.extras.clear();
  this.v=null;this.c=null;$('#stage').innerHTML='';
 },
 dur(){return this.v?.duration||this.c?.duration||0},
 frac(e){const r=$('#vwScrub').getBoundingClientRect();return clamp((e.clientX-r.left)/r.width,0,1)},
 seekTo(t){if(!this.v)return;this.v.currentTime=clamp(t,0,this.dur());this.paint()},
 preview(f){
  const box=$('#vwPrev'),c=this.c;if(!box||/\.gif$/i.test(c.name))return;box.hidden=false;box.style.left=(f*100)+'%';$('#vwPrevT').textContent=short(f*this.dur());
  if(!this.sprite){this.sprite=`${base}filmstrip/${encodeURIComponent(c.id)}?start=0&end=${c.duration}&frames=48`;$('#vwPic').style.backgroundImage=`url("${this.sprite}")`}
  $('#vwPic').style.backgroundPosition=`${-Math.min(47,Math.floor(f*48))*176}px 0`;
 },
 loop(){cancelAnimationFrame(this.raf);const tick=()=>{this.paint();if(this.v&&!this.v.paused)this.raf=requestAnimationFrame(tick)};this.raf=requestAnimationFrame(tick)},
 paint(){
  const v=this.v;if(!v)return;const d=this.dur()||1,t=v.currentTime,p=(t/d*100).toFixed(3)+'%';
  $('#vwFill').style.width=p;$('#vwKnob').style.left=p;$('#vwTime').textContent=short(t);$('#vwScrub').setAttribute('aria-valuenow',Math.round(t));
  // Rebuild the play button only when the state flips: replacing its icon every
  // animation frame swaps the node under the cursor between mousedown and mouseup,
  // and the browser then drops the click.
  const playing=!v.paused&&!v.ended;if(this.shown!==playing){this.shown=playing;const b=$('#vwPlay');b.innerHTML=playing?pauseIc:playIc;b.setAttribute('aria-label',playing?'Пауза':'Воспроизвести');$('#vwBig').hidden=playing}
  $('#vwMark').hidden=!marksOf(this.c).some(m=>Math.abs(m-t)<1);
 },
 paintBuffer(){const v=this.v;if(!v||!v.buffered.length)return;$('#vwBuf').style.width=(v.buffered.end(v.buffered.length-1)/(this.dur()||1)*100)+'%'},
 syncVol(){const v=this.v;const val=this.userMuted?0:Math.round(v.volume*100);$('#vwVolT').textContent=val+'%';$('#vwMute').setAttribute('aria-label',v.muted?'Включить звук':'Выключить звук');$('#vwMute').style.opacity=val?1:.5},
 renderTracks(){
  const box=$('#vwTracks');const audio=this.info?.audio||[];if(!box||audio.length<2)return;box.hidden=false;
  box.innerHTML=audio.map((a,i)=>`<button type="button" data-act="vw-track" data-i="${i}" aria-pressed="${this.on.has(i)}"${i===0?' title="Общий звук уже содержит все источники"':''}>${this.on.has(i)?'✓ ':''}${esc(a.title||'Дорожка '+(i+1))}</button>`).join('');
 },
 setTrack(i){
  const n=this.info?.audio?.length||0,on=toggleTrack(Array.from({length:n},(_,j)=>this.on.has(j)),i);
  this.on=new Set(on.flatMap((v,j)=>v?[j]:[]));
  this.syncExtra(true);this.renderTracks();
 },
 syncExtra(seek=false){
  const v=this.v;if(!v)return;
  v.muted=!!this.userMuted||!this.on.has(0);
  for(const [i,a] of this.extras)if(!this.on.has(i)){a.pause();a.removeAttribute('src');this.extras.delete(i)}
  const rate=v.playbackRate,lag=.15*Math.max(1,rate);
  for(const i of this.on){if(i===0)continue;let a=this.extras.get(i);
   if(!a){a=new Audio(`${base}audio-preview/${encodeURIComponent(this.c.id)}?track=${i}`);a.preload='auto';this.extras.set(i,a);seek=true}
   a.muted=!!this.userMuted;a.volume=v.volume;try{a.playbackRate=rate}catch{}
   if(seek||Math.abs(a.currentTime-v.currentTime)>lag){try{a.currentTime=v.currentTime}catch{}}
   if(v.paused)a.pause();else a.play().catch(()=>{});}
  clearTimeout(this.drift);if(!v.paused&&this.extras.size)this.drift=setTimeout(()=>this.syncExtra(),700);
 },
 key(e){
  if(e.target.closest('input,select,textarea'))return;const k=e.key;
  if(this.gif&&this.c){
   if(k===' '||k==='k'||k==='K'){e.preventDefault();this.gifToggle()}
   else if(k==='ArrowLeft'||k==='ArrowRight'){e.preventDefault();const d=k==='ArrowLeft'?-1:1;e.shiftKey?this.gifJump(d*5):this.gifStep(d)}
   else if(k==='f'||k==='F'||k==='а'||k==='А'){e.preventDefault();this.fullscreen()}
   else if(k==='Escape'&&!document.fullscreenElement){e.preventDefault();historyDirection(-1)}
   return;
  }
  const v=this.v;if(!v)return;
  if(k===' '||k==='k'||k==='K'){e.preventDefault();v.paused?v.play():v.pause()}
  else if(k==='ArrowLeft'||k==='ArrowRight'){e.preventDefault();this.arrow(e)}
  else if(k==='ArrowUp'||k==='ArrowDown'){e.preventDefault();const el=$('#vwVol');el.value=clamp(Number(el.value)+(k==='ArrowUp'?5:-5),0,100);el.dispatchEvent(new Event('input'))}
  else if(k==='f'||k==='F'||k==='а'||k==='А'){e.preventDefault();this.fullscreen()}
  else if(k==='<'||k==='>'||k===','||k==='.'||k==='б'||k==='ю'||k==='Б'||k==='Ю'){e.preventDefault();const L=[0.1,0.25,0.5,1,1.5,2,3,4,5],i=L.indexOf(this.speed),up=k==='>'||k==='.'||k==='ю'||k==='Ю';this.rate(L[clamp((i<0?3:i)+(up?1:-1),0,L.length-1)])}
  else if(k==='Escape'&&!document.fullscreenElement){e.preventDefault();historyDirection(-1)}
 },
 fullscreen(){if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});else $('#stage').requestFullscreen().catch(()=>{})},
 paintFull(){const b=$('[data-act=vw-full]');if(b)b.setAttribute('aria-label',document.fullscreenElement?'Выйти из полноэкранного режима':'Во весь экран')},
 wake(){const st=$('#stage');st.classList.remove('idle');clearTimeout(this.idleT);
  this.idleT=setTimeout(()=>{const v=this.v;if(v&&!v.paused&&!this.menu&&!this.scrubbing&&document.fullscreenElement&&!$('.vw-ctl:hover'))st.classList.add('idle')},2500)},
 step(dir){const list=this.list(),i=list.findIndex(x=>x.id===this.c.id);const next=list[(i+dir+list.length)%list.length];if(next&&next.id!==this.c.id){libUI.sel=next.id;leave();view={screen:'viewer',id:next.id};enter()}},
 rate(v){this.speed=v;this.v.playbackRate=v;this.syncExtra(true);$('#vwSpeed').textContent='Скорость '+String(v).replace('.',',')+'×';
  for(const b of $$('#vwMenu [data-v]')){const on=Number(b.dataset.v)===v;b.setAttribute('aria-checked',on);b.lastElementChild.textContent=on?'✓':''}
  const badge=$('#vwSpeedBadge');badge.hidden=v===1;badge.textContent=String(v).replace('.',',')+'×';this.toggleMenu(false)},
 toggleMenu(on=!this.menu){this.menu=on;$('#vwMenu').hidden=!on;$('#vwSpeed').setAttribute('aria-expanded',on)},
};
function localGet(k){try{return localStorage.getItem(k)}catch{return null}}
function localSet(k,v){try{localStorage.setItem(k,String(v))}catch{}}

// ---------- Editor: trim with the mouse, mix tracks, export
const isGifPreset=id=>id==='gif';
// Track 0 is the general mix that already contains every source. Turning it on turns
// the separate tracks off and vice versa; separate tracks can still be combined.
function toggleTrack(on,i){
 on=[...on];if(on.length<2){on[i]=!on[i];return on}
 if(i===0){const v=!on[0];return on.map((_,j)=>j===0?v:!v)}
 on[i]=!on[i];if(on[i])on[0]=false;else if(!on.slice(1).some(Boolean))on[0]=true;
 return on;
}
// Every preset has its own quality choice: a short label for the switch and a hint
// that says what the choice gives. est(len,rate) is a rough size in bytes.
const CRF_LEVELS=cap=>[
 {id:'standard',short:'Стандарт',hint:'Хорошее качество, файл меньше',args:{quality:'standard'},est:(l,r)=>l*Math.min(r*.8,cap*.6)},
 {id:'high',short:'Высокое',hint:'Без заметных потерь — подходит почти всегда',args:{quality:'high'},est:(l,r)=>l*Math.min(r,cap)},
 // No re-encoding: the recorded video is copied as is, so it can never beat or bloat the source.
 {id:'copy',short:'Исходник',hint:'Без перекодирования: качество и битрейт как в записи, экспорт за секунды · таймер не накладывается',args:{quality:'copy'},est:(l,r)=>l*r},
];
// Same rule as discord_plan() in app.py: 10 MB is a fixed budget, so the frame size
// follows the clip length. A long clip in 1080p turns into blocks; a smaller frame stays clean.
// Bits per pixel a frame needs to stay clean in busy game scenes (crowds, grass, particles).
// 0.035 looked fine on paper but turned 720p60 fights into mush; 0.07 keeps them readable.
const DISCORD_BPP=.07;
function discordPlan(len,srcH,fps){
 len=Math.max(len,.1);const audio=len<=60?96:64;
 const kbps=Math.min(8000,Math.floor((9.4e6*8/len-audio*1000-50000)/1000));
 const opts=[1080,720,540,480,360].filter(h=>h<=(srcH||1080));if(!opts.length)opts.push(Math.floor((srcH||360)/2)*2);
 const height=opts.find(h=>kbps*1000/((h*16/9)*h*fps)>=DISCORD_BPP)||opts[opts.length-1];
 return {kbps,height};
}
// Longest clip that still gets the given height.
function discordMaxLen(h,fps){const need=DISCORD_BPP*(h*16/9)*h*fps/1000;let len=9.4e6*8/1000/(need+96+50);if(len>60)len=9.4e6*8/1000/(need+64+50);return Math.floor(len)}
function discordHint(fps){return (len,c)=>{
 const pl=discordPlan(len,c?.height,fps);if(pl.kbps<200)return ['Отрезок слишком длинный для 10 МБ — укоротите его или выберите Nitro'];
 const h=pl.height,out=[];
 out.push(h>=1080?`Получится ${h}p · ${fps} fps — максимум для этого лимита.`:h>=720?`Получится ${h}p · ${fps} fps — чётко.`:h>=540?`Получится ${h}p · ${fps} fps — картинка мягче.`:`Получится ${h}p · ${fps} fps — картинка мелкая.`);
 if(h<720)out.push(`Для 720p укоротите до ~${discordMaxLen(720,fps)} с или выберите Nitro.`);
 else if(h<1080&&fps===30&&(c?.height||1080)>=1080)out.push(`Для 1080p укоротите до ~${discordMaxLen(1080,30)} с.`);
 // 60 fps splits the same 10 MB over twice as many frames: say so when it costs resolution.
 const at30=fps===60?discordPlan(len,c?.height,30).height:0;
 if(at30>h)out.push(`При 60 fps картинка размажется в динамике — в «Чётче · 30 fps» будет ${at30}p.`);
 return out;
}}
const PRESETS=[
 {id:'discord',label:'Discord · до 10 МБ',detail:'Влезает в лимит Discord без Nitro',args:{format:'original',quality:'discord'},q:'30',qualities:[
  {id:'30',short:'Чётче · 30 fps',hint:discordHint(30),args:{discord_height:'auto',discord_fps:30},est:l=>Math.min(9.2e6,l*8.1e6/8)},
  {id:'60',short:'Плавнее · 60 fps',hint:discordHint(60),args:{discord_height:'auto',discord_fps:60},est:l=>Math.min(9.2e6,l*8.1e6/8)}]},
 {id:'nitro',label:'Discord Nitro · до 500 МБ',detail:'Исходное разрешение и fps',args:{format:'original'},q:'high',qualities:CRF_LEVELS(4e6)},
 {id:'vertical',label:'TikTok / Shorts · 9:16',detail:'Вертикальное видео, обрезка по центру',args:{format:'vertical'},q:'1080-high',qualities:[
  {id:'720-std',short:'720p',hint:'720 × 1280 · лёгкий файл',args:{vertical_size:'720',quality:'standard'},est:(l,r)=>l*Math.min(r*.35,1e6)},
  {id:'1080-high',short:'1080p',hint:'1080 × 1920 · рекомендуем для TikTok и Shorts',args:{vertical_size:'1080',quality:'high'},est:(l,r)=>l*Math.min(r*.8,3e6)},
  {id:'1080-max',short:'1080p макс.',hint:'1080 × 1920 · почти без потерь, файл больше',args:{vertical_size:'1080',quality:'max'},est:(l,r)=>l*Math.min(r*1.2,5e6)}]},
 {id:'youtube',label:'YouTube',detail:'Исходное разрешение и fps',args:{format:'original'},q:'high',qualities:CRF_LEVELS(4.5e6).slice(1)},
 {id:'gif',label:'GIF · без звука',detail:'Анимация от 2 до 15 секунд',args:{format:'gif'},q:'high',qualities:[
  {id:'light',short:'Лёгкий',hint:'720 px · 15 fps · маленький файл',args:{gif_width:720,gif_quality:'standard'},est:l=>l*.55e6},
  {id:'good',short:'Хорошее',hint:'960 px · 30 fps',args:{gif_width:960,gif_quality:'high'},est:l=>l*1.5e6},
  {id:'high',short:'Высокое',hint:'1080 px · 30 fps · своя палитра на каждый кадр',args:{gif_width:1080,gif_quality:'high'},est:l=>l*2.2e6}]},
];
// The chosen quality of each preset is remembered between exports.
const exportQ=(()=>{try{return JSON.parse(localGet('ag.exportQ')||'{}')||{}}catch{return {}}})();
function hintOf(q,len,c){const v=typeof q.hint==='function'?q.hint(len,c):q.hint;return Array.isArray(v)?v:[v]}
// One span per sentence: the translator matches whole text nodes.
const hintHTML=(q,len,c)=>hintOf(q,len,c).map(x=>`<span>${esc(x)}</span>`).join(' ');
function presetQuality(p){return p.qualities.find(x=>x.id===exportQ[p.id])||p.qualities.find(x=>x.id===p.q)||p.qualities[0]}
const editor={
 c:null,v:null,info:null,inT:0,outT:0,marks:[],snap:false,drag:null,hover:null,raf:0,peaks:null,preset:'discord',tracks:[],timer:false,
 job:null,result:null,progress:0,ctx:null,nodes:null,keys:null,frame:1/60,pending:0,
 open(id){
  const c=clipById(id);if(!c){go({screen:'library'},false);return}
  const same=this.c?.id===id;
  this.c=c;this.marks=marksOf(c);this.drag=null;this.hover=null;this.peaks=null;this.result=null;
  // Reopening the editor shows an export that is still running instead of offering a second one.
  const running=(state.jobs||[]).find(j=>j.label==='Экспорт видео'&&j.status==='running'&&watchers.has(j.id));this.job=running?.id||null;this.progress=running?.progress||0;
  if(!same||!(this.outT>this.inT)){this.inT=0;this.outT=c.duration}
  this.timer=custom().timer_default===true;
  const gif=/\.gif$/i.test(c.name);this.preset=gif?'gif':this.fits('discord')?'discord':'nitro';
  this.tracks=[];this.info={fps:60,audio:[]};
  const stage=$('#stage');stage.className='ed';
  stage.innerHTML=`<header class="st-hd"><button type="button" class="btn ghost" data-act="back">${ic('back')}Назад</button><div class="ttl"><b data-i18n-ignore>${esc(nameOf(c))}</b><small id="edSub">${esc([gameOf(c),kindText(c),c.width?c.width+' × '+c.height:''].filter(Boolean).join(' · '))}</small></div><span class="grow"></span>
  <div class="keys">${[['Пробел','пауза'],['J K L','перемотка'],['← →','кадр'],['I','начало'],['O','конец'],['M','метка']].map(([k,l])=>`<span><kbd>${k}</kbd>${l}</span>`).join('')}</div></header>
  <div class="ed-body"><section class="ed-main" aria-label="Просмотр и обрезка">
   <div class="ed-frame" id="edFrame"><video id="edVideo" preload="auto" playsinline src="${base}media/${encodeURIComponent(c.id)}"></video>${gif?`<img class="ed-gif" src="${base}media/${encodeURIComponent(c.id)}" alt="">`:""}<span class="drag-note" id="edNote" hidden></span><span class="timer-ov" id="edTimer" hidden></span></div>
   <div class="ctl-row"><button type="button" class="btn icon" data-act="ed-frame" data-d="-1" aria-label="Кадр назад">${ic('frameBack')}</button><button type="button" class="btn icon primary" data-act="ed-play" id="edPlay" aria-label="Воспроизвести">${playIc}</button><button type="button" class="btn icon" data-act="ed-frame" data-d="1" aria-label="Кадр вперёд">${ic('frameFwd')}</button>
    <span class="num" style="padding:0 10px;color:var(--muted)"><b id="edTime" style="color:var(--text);font-weight:600">00:00:00.000</b> / ${precise(c.duration)}</span><span class="grow"></span>
    <button type="button" class="btn" data-act="ed-in">Начало здесь</button><button type="button" class="btn" data-act="ed-out">Конец здесь</button><button type="button" class="btn" data-act="ed-mark">★ Метка</button></div>
   <div class="card tl-card"><div class="tl-info"><span>Отрезок <b id="edRange"></b> · длительность <b id="edLen"></b></span><span>Тяните края отрезка, сам отрезок за кадры или шкалу под ними</span></div>
    <div class="tl" id="edTl"><div class="strip" id="edStrip"></div><canvas id="edWave" aria-hidden="true"></canvas><div class="dim" id="edDimL" style="left:0;border-radius:6px 0 0 6px"></div><div class="dim" id="edDimR" style="right:0;border-radius:0 6px 6px 0"></div><div class="sel" id="edSel"></div>
     <button type="button" class="handle in" id="edIn" aria-label="Начало отрезка">${grip()}</button><button type="button" class="handle out" id="edOut" aria-label="Конец отрезка">${grip()}</button>
     <div class="head" id="edHead"></div><div class="hover-line" id="edHover" hidden></div><span class="drag-time" id="edDragT" hidden></span><div id="edStars"></div></div></div>
  </section>
  <aside class="ed-side" aria-label="Экспорт">
   <div class="field"><label for="edName">Название файла</label><input class="input" id="edName" value="${esc(nameOf(c).replace(/[<>:"/\\|?*]/g,'').slice(0,120))}" maxlength="150"></div>
   <div class="field" role="radiogroup" aria-label="Куда экспортировать"><span class="lbl">Куда экспортировать</span><div id="edPresets" style="display:flex;flex-direction:column;gap:8px"></div></div>
   <div class="field" id="edTracksBox"><span class="lbl">Звуковые дорожки</span><div id="edTracks" style="display:flex;flex-direction:column;gap:8px"><span class="hint">Загрузка…</span></div></div>
   <label class="check"><input type="checkbox" id="edTimerOn" ${this.timer?'checked':''}> Таймер на видео (отсчёт от начала отрезка)</label>
   <span class="grow"></span><div id="edExport"></div>
  </aside></div>`;
  const v=this.v=$('#edVideo');
  v.addEventListener('loadedmetadata',()=>{this.seek(this.inT);this.layout()},{once:true});
  v.addEventListener('play',()=>{if(v.currentTime<this.inT-.05||v.currentTime>=this.outT-.02)v.currentTime=this.inT;this.loop();this.paintPlay()});
  v.addEventListener('pause',()=>{this.paintPlay();this.syncTracks()});v.addEventListener('seeked',()=>{this.paintHead();this.syncTracks(true)});
  const tl=$('#edTl');
  tl.addEventListener('pointerdown',e=>this.down(e));tl.addEventListener('pointermove',e=>this.move(e));
  tl.addEventListener('pointerup',e=>this.up(e));tl.addEventListener('pointercancel',e=>this.up(e));tl.addEventListener('pointerleave',()=>{if(!this.drag){this.hover=null;this.paintTl()}});
  for(const [sel,which] of [['#edIn','in'],['#edOut','out']])$(sel).addEventListener('keydown',e=>this.nudge(e,which));
  $('#edTimerOn').addEventListener('change',e=>{this.timer=e.target.checked;this.paintTimer();if(custom().timer_default!==this.timer)api('customize_config',{timer_default:this.timer}).then(r=>state.settings.customization=r).catch(()=>{})});
  this.keys=e=>this.key(e);document.addEventListener('keydown',this.keys);
  this.resize=()=>this.layout();window.addEventListener('resize',this.resize);
  this.renderPresets();this.renderExport();this.paintTl();this.paintTimer();
  if(!gif)loadInfo(c.id).then(info=>{if(this.c!==c)return;this.info=info||{fps:60,audio:[]};this.frame=1/(info?.fps||60);
   this.tracks=(info?.audio||[]).map((a,i)=>({index:a.index,title:a.title||'Дорожка '+(i+1),on:i===0,gain:100}));this.renderTracks();
   const sub=$('#edSub');if(sub&&info?.fps)sub.textContent=[gameOf(c),kindText(c),c.width?c.width+' × '+c.height:'',Math.round(info.fps)+' fps'].filter(Boolean).join(' · ');
  });else{this.renderTracks()}
  if(!gif&&c.audio)api('clip_waveform',{id:c.id,start:0,end:c.duration,track:0}).then(w=>{if(this.c===c){this.peaks=w.peaks||[];this.drawWave()}}).catch(()=>{});
  if(view.focusExport)setTimeout(()=>$('#edName')?.focus(),50);
 },
 close(){
  cancelAnimationFrame(this.raf);document.removeEventListener('keydown',this.keys);window.removeEventListener('resize',this.resize);
  if(this.v){this.v.pause();this.v.removeAttribute('src');this.v.load()}
  for(const n of this.nodes?.extra||[]){n.el.pause();n.el.removeAttribute('src')}
  if(this.ctx){this.ctx.close().catch(()=>{});this.ctx=null}this.nodes=null;this.v=null;$('#stage').innerHTML='';
 },
 D(){return this.c?.duration||0},
 fits(id){
  const len=this.outT-this.inT||this.c?.duration||0;
  if(isGifPreset(id))return len>=2&&len<=15;
  if(id==='discord')return len<=200;
  return true;
 },
 estimate(id){
  const len=this.outT-this.inT,c=this.c,rate=c.size&&c.duration?c.size/c.duration:2e6;
  const p=PRESETS.find(x=>x.id===id);const v=p?presetQuality(p).est(len,rate):0;
  return '≈ '+bytes(v);
 },
 renderPresets(){
  const box=$('#edPresets');if(!box)return;const gif=/\.gif$/i.test(this.c.name);
  if(!this.fits(this.preset)&&!gif)this.preset=this.fits('discord')?'discord':'nitro';
  box.innerHTML=PRESETS.map(p=>{const ok=gif?isGifPreset(p.id):this.fits(p.id);const why=isGifPreset(p.id)&&!ok&&!gif?'Выделите от 2 до 15 секунд':p.id==='discord'&&!ok?'Отрезок длиннее 3 минут — выберите Nitro':gif&&!isGifPreset(p.id)?'Для GIF-файла доступен только GIF':'';
   const on=this.preset===p.id&&ok,q=presetQuality(p);
   // Only the chosen preset shows its quality switch, so the list stays short.
   const quality=on&&p.qualities.length>1?`<div class="pq"><div class="seg pq-seg" role="radiogroup" aria-label="Качество: ${esc(p.label)}">${p.qualities.map(x=>`<button type="button" role="radio" aria-checked="${x.id===q.id}" data-act="ed-q" data-p="${p.id}" data-q="${x.id}">${esc(x.short)}</button>`).join('')}</div><small class="pq-hint">${hintHTML(q,this.outT-this.inT,this.c)}</small></div>`:'';
   return `<div class="preset-item ${on?'on':''} ${ok?'':'off'}"><button type="button" role="radio" class="preset" data-act="ed-preset" data-id="${p.id}" aria-checked="${on}" ${ok?'':'disabled'}><span class="r" aria-hidden="true"></span><span class="tx"><b>${p.label}</b><small>${esc(why||(on?p.detail:p.detail+(p.qualities.length>1?' · '+q.short:'')))}</small></span><span class="sz">${ok?this.estimate(p.id):''}</span></button>${quality}</div>`}).join('');
 },
 renderTracks(){
  const box=$('#edTracks');if(!box)return;
  if(!this.tracks.length){box.innerHTML=`<span class="hint">${/\.gif$/i.test(this.c.name)||isGifPreset(this.preset)?'GIF сохраняется без звука.':'В этом видео нет звуковых дорожек.'}</span>`;return}
  const multi=this.tracks.length>1;
  box.innerHTML=(multi?`<p class="hint">«Общий звук» уже содержит все источники. Чтобы менять громкость игры и чата по отдельности, выключите его и включите нужные дорожки.</p>`:'')+this.tracks.map((t,i)=>`<div class="track"><button type="button" class="switch" role="switch" aria-checked="${t.on}" data-act="ed-track" data-i="${i}" aria-label="${t.on?'Выключить':'Включить'} дорожку: ${esc(t.title)}"><span class="tr"><span></span></span></button><div style="display:flex;flex-direction:column;gap:4px;min-width:0"><span class="nm" style="color:${t.on?'var(--text)':'var(--muted)'}">${esc(t.title)}</span><input type="range" min="0" max="150" step="1" value="${t.gain}" data-gain="${i}" aria-label="Громкость: ${esc(t.title)}" ${t.on?'':'disabled'}></div><button type="button" class="pct" data-act="ed-gain-reset" data-i="${i}" title="Двойной клик — 100%" style="color:${t.gain>100?'var(--accent)':t.on?'var(--text)':'var(--muted)'}">${t.on?t.gain+'%':'—'}</button></div>`).join('');
 },
 renderExport(){
  const box=$('#edExport');if(!box)return;
  if(this.job){box.innerHTML=`<div class="progress" role="status"><div style="display:flex;justify-content:space-between;font-size:13px"><b>Экспорт…</b><span class="num hint" id="edPct">${this.progress}%</span></div><div class="bar"><span id="edBar" style="width:${this.progress}%"></span></div><button type="button" class="btn sm" data-act="ed-cancel" style="align-self:flex-start">Отменить</button></div>`;return}
  if(this.result){const r=this.result,c=r.id&&clipById(r.id);box.innerHTML=`<div class="result" role="status"><div style="display:flex;align-items:center;gap:10px"><i style="width:8px;height:8px;border-radius:50%;background:var(--ok)" aria-hidden="true"></i><b>Готово · <span data-i18n-ignore>${esc(r.name)}</span> · ${bytes(r.bytes||0)}</b></div><div class="result-acts"><button type="button" class="btn primary" data-act="ed-copy" ${c?'':'disabled'}>${ic('copy')}<span id="edCopyL">Копировать файл</span></button><button type="button" class="btn" data-act="reveal" data-id="${esc(r.id||'')}" ${c?'':'disabled'}>${ic('folder')}Показать в папке</button></div><button type="button" class="btn ghost sm" data-act="ed-again" style="align-self:flex-start">Экспортировать ещё раз</button></div>`;return}
  box.innerHTML=`<button type="button" class="btn primary" data-act="ed-export" style="height:48px;font-size:15px;width:100%">${ic('save')}Экспортировать · <span id="edExpSz">${this.estimate(this.preset)}</span></button>`;
 },
 // Changing quality updates the open card in place: rebuilding the whole list
 // made the card flash and dropped the hover state.
 updateQuality(pid){
  const p=PRESETS.find(x=>x.id===pid),card=$(`#edPresets .preset[data-id="${pid}"]`)?.closest('.preset-item');
  if(!p||!card||this.preset!==pid)return this.renderPresets(),this.renderExport();
  const q=presetQuality(p);
  for(const b of card.querySelectorAll('[data-act=ed-q]'))b.setAttribute('aria-checked',String(b.dataset.q===q.id));
  const hint=card.querySelector('.pq-hint');if(hint)hint.innerHTML=hintHTML(q,this.outT-this.inT,this.c);
  const sz=card.querySelector('.sz');if(sz)sz.textContent=this.estimate(pid);
  const exp=$('#edExpSz');if(exp)exp.textContent=this.estimate(pid);else this.renderExport();
 },
 layout(){this.drawWave();this.paintStrip();this.paintTl();this.paintTimer()},
 paintStrip(){
  const el=$('#edStrip');if(!el||/\.gif$/i.test(this.c.name))return;const w=el.clientWidth;if(!w)return;
  const n=clamp(Math.round(w/92),6,40);if(el.dataset.n==String(n))return;el.dataset.n=n;
  el.style.backgroundImage=`url("${base}filmstrip/${encodeURIComponent(this.c.id)}?start=0&end=${this.c.duration}&frames=${n}")`;el.style.backgroundSize='100% 100%';
 },
 drawWave(){
  const cv=$('#edWave');if(!cv)return;const w=cv.clientWidth,h=cv.clientHeight,dpr=window.devicePixelRatio||1;
  cv.width=Math.round(w*dpr);cv.height=Math.round(h*dpr);const g=cv.getContext('2d');g.scale(dpr,dpr);g.clearRect(0,0,w,h);
  const peaks=this.peaks;if(!peaks||!peaks.length){g.fillStyle='#262A31';g.fillRect(0,h/2-1,w,2);return}
  const bars=Math.max(20,Math.floor(w/4)),max=Math.max(.02,...peaks),D=this.D(),a=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();
  for(let i=0;i<bars;i++){
   const from=Math.floor(i/bars*peaks.length),to=Math.max(from+1,Math.floor((i+1)/bars*peaks.length));let v=0;for(let j=from;j<to;j++)v=Math.max(v,peaks[j]);
   const bh=Math.max(2,Math.min(1,v/max)*h),at=(i+.5)/bars*D;g.fillStyle=at>=this.inT&&at<=this.outT?a:'#363B44';g.globalAlpha=at>=this.inT&&at<=this.outT?.85:1;
   g.fillRect(i*(w/bars),(h-bh)/2,Math.max(1,w/bars-1.5),bh);
  }g.globalAlpha=1;
 },
 pct(v){return (v/(this.D()||1)*100).toFixed(4)+'%'},
 paintTl(){
  if(!$('#edTl'))return;const D=this.D(),len=this.outT-this.inT;
  $('#edDimL').style.width=this.pct(this.inT);$('#edDimR').style.width=this.pct(D-this.outT);
  const sel=$('#edSel');sel.style.left=this.pct(this.inT);sel.style.width=this.pct(len);sel.classList.toggle('drag',['in','out','range'].includes(this.drag?.mode));
  $('#edIn').style.left=this.pct(this.inT);$('#edOut').style.left=this.pct(this.outT);
  $('#edIn').setAttribute('aria-label','Начало отрезка '+precise(this.inT)+'. Стрелки — на кадр, Shift — на секунду');
  $('#edOut').setAttribute('aria-label','Конец отрезка '+precise(this.outT)+'. Стрелки — на кадр, Shift — на секунду');
  $('#edRange').textContent=precise(this.inT)+' – '+precise(this.outT);$('#edLen').textContent=precise(len);
  $('#edStars').innerHTML=this.marks.map(m=>`<span class="star" style="left:${this.pct(m)}">★</span>`).join('');
  const hv=$('#edHover');hv.hidden=!this.hover||!!this.drag;if(this.hover)hv.style.left=this.pct(this.hover.t);
  const dt=$('#edDragT'),note=$('#edNote');
  if(this.drag){const t=this.drag.mode==='in'?this.inT:this.drag.mode==='out'?this.outT:this.v?.currentTime??0;dt.hidden=false;dt.style.left=this.pct(t);dt.textContent=precise(t)+(this.drag.snapped?' · ★':'');
   note.hidden=false;note.textContent={in:'Начало отрезка',out:'Конец отрезка',range:'Сдвиг отрезка',head:'Перемотка'}[this.drag.mode]+' · '+precise(t)+(this.drag.snapped?' · притянуто к метке':'')}
  else{dt.hidden=true;note.hidden=true}
  $('#edTl').style.cursor=this.drag?.mode==='range'?'grabbing':{in:'ew-resize',out:'ew-resize',range:'grab',head:'text'}[this.drag?.mode||this.hover?.mode||'head'];
  this.paintHead();
 },
 paintHead(){const v=this.v;if(!v||!$('#edHead'))return;const t=v.currentTime;$('#edHead').style.left=this.pct(t);$('#edTime').textContent=precise(t);this.paintTimer()},
 paintPlay(){const p=this.v&&!this.v.paused;const b=$('#edPlay');if(b){b.innerHTML=p?pauseIc:playIc;b.setAttribute('aria-label',p?'Пауза':'Воспроизвести')}},
 paintTimer(){
  const el=$('#edTimer'),v=this.v;if(!el||!v)return;el.hidden=!this.timer;if(!this.timer)return;
  const c=custom(),t=Math.max(0,v.currentTime-this.inT),w=Math.floor(t);
  const fmt=c.timer_format||'milliseconds',fps=Math.round(this.info?.fps||60);
  el.textContent=fmt==='seconds'?pad(Math.floor(w/60))+':'+pad(w%60):fmt==='frames'?'Кадр '+Math.floor(t*fps+1e-4):pad(Math.floor(w/60))+':'+pad(w%60)+'.'+pad(Math.floor(t*1000+1e-4)%1000,3);
  const F=$('#edFrame'),fw=F.clientWidth,fh=F.clientHeight,vw=v.videoWidth||this.c.width||16,vh=v.videoHeight||this.c.height||9;
  const k=Math.min(fw/vw,fh/vh),rw=vw*k,rh=vh*k,rx=(fw-rw)/2,ry=(fh-rh)/2;
  const size=clamp(Number(c.timer_size)||100,10,400);
  el.style.fontSize=Math.max(14*k,rh*.032*size/100)+'px';el.style.padding=(6*k)+'px';el.style.lineHeight='1';el.style.borderRadius='0';
  el.style.color=c.timer_color||'#ffffff';el.style.background=`rgba(0,0,0,${clamp(Number(c.timer_background??65),0,100)/100})`;
  el.style.fontFamily=c.timer_font==='sans'?'Inter,sans-serif':'Consolas,monospace';el.style.transform='none';
  const tx=clamp(Number(c.timer_x??97.5),0,100)/100,ty=clamp(Number(c.timer_y??2.5),0,100)/100;
  el.style.left=(rx+(rw-el.offsetWidth)*tx)+'px';el.style.top=(ry+(rh-el.offsetHeight)*ty)+'px';
 },
 loop(){cancelAnimationFrame(this.raf);const tick=()=>{const v=this.v;if(!v)return;if(!this.drag&&v.currentTime>=this.outT){v.currentTime=this.inT}this.paintHead();if(!v.paused)this.raf=requestAnimationFrame(tick)};this.raf=requestAnimationFrame(tick)},
 seek(t){const v=this.v;if(!v)return;t=clamp(t,0,this.D());if(typeof v.fastSeek==='function'&&this.drag)v.fastSeek(t);else v.currentTime=t;this.paintHead()},
 timeAt(e){const r=this.drag?.rect||$('#edTl').getBoundingClientRect();return clamp((e.clientX-r.left)/r.width,0,1)*this.D()},
 modeAt(e){
  const r=$('#edTl').getBoundingClientRect(),x=e.clientX-r.left,w=r.width,D=this.D()||1,inX=this.inT/D*w,outX=this.outT/D*w;
  if(x>=inX-14&&x<=inX+4)return 'in';if(x>=outX-4&&x<=outX+14)return 'out';
  if(e.clientY-r.top<52&&x>inX&&x<outX)return 'range';return 'head';
 },
 snapTo(t,mode){
  if(!this.snap)return [t,false];const pts=[...this.marks];if(mode!=='head'&&this.v)pts.push(this.v.currentTime);
  let best=null;for(const p of pts)if(Math.abs(p-t)<=Math.max(.25,this.D()/400)&&(best===null||Math.abs(p-t)<Math.abs(best-t)))best=p;
  return best===null?[t,false]:[best,true];
 },
 down(e){
  if(e.button)return;const tl=$('#edTl');tl.setPointerCapture(e.pointerId);
  const mode=this.modeAt(e);this.drag={mode,rect:tl.getBoundingClientRect(),t0:0,in0:this.inT,out0:this.outT,snapped:false};this.drag.t0=this.timeAt(e);
  this.wasPlaying=this.v&&!this.v.paused;this.v?.pause();if(mode!=='range')this.apply(e);this.paintTl();
 },
 move(e){
  if(this.drag){this.apply(e);return}
  this.hover={mode:this.modeAt(e),t:this.timeAt(e)};this.paintTl();
 },
 up(e){
  if(!this.drag)return;try{$('#edTl').releasePointerCapture(e.pointerId)}catch{}
  const mode=this.drag.mode;this.drag=null;this.paintTl();this.drawWave();this.renderPresets();this.renderExport();
  if(mode==='head'&&this.wasPlaying)this.v.play().catch(()=>{});
 },
 apply(e){
  const g=this.drag,t=this.timeAt(e),min=Math.min(.5,this.D()/2),D=this.D();let snapped=false,v;
  if(g.mode==='in'){[v,snapped]=this.snapTo(t,'in');this.inT=clamp(v,0,this.outT-min);this.seek(this.inT)}
  else if(g.mode==='out'){[v,snapped]=this.snapTo(t,'out');this.outT=clamp(v,this.inT+min,D);this.seek(this.outT)}
  else if(g.mode==='range'){const len=g.out0-g.in0;this.inT=clamp(g.in0+(t-g.t0),0,D-len);this.outT=this.inT+len;this.seek(this.inT)}
  else{[v,snapped]=this.snapTo(t,'head');this.seek(v)}
  g.snapped=snapped;
  if(!this.pending)this.pending=requestAnimationFrame(()=>{this.pending=0;this.paintTl();if(g.mode!=='head')this.drawWave()});
 },
 nudge(e,which){
  const dir=e.key==='ArrowLeft'?-1:e.key==='ArrowRight'?1:0;if(!dir)return;e.preventDefault();e.stopPropagation();
  const step=e.shiftKey?1:this.frame,min=Math.min(.5,this.D()/2);
  if(which==='in'){this.inT=clamp(this.inT+dir*step,0,this.outT-min);this.seek(this.inT)}else{this.outT=clamp(this.outT+dir*step,this.inT+min,this.D());this.seek(this.outT)}
  this.paintTl();this.drawWave();this.renderPresets();this.renderExport();
 },
 setIn(){const t=this.v.currentTime;this.inT=clamp(t,0,this.outT-.5);this.after()},
 setOut(){const t=this.v.currentTime;this.outT=clamp(t,this.inT+.5,this.D());this.after()},
 after(){this.paintTl();this.drawWave();this.renderPresets();this.renderExport()},
 async addMark(){
  const t=Math.round(this.v.currentTime*100)/100;if(this.marks.some(m=>Math.abs(m-t)<.05))return;
  const marks=[...this.marks,t].sort((a,b)=>a-b);
  try{await saveClipMeta(this.c,{marks});this.marks=marks;this.paintTl();toast('Метка добавлена · '+precise(t))}catch(e){fail(e)}
 },
 step(d){const v=this.v;v.pause();this.seek(v.currentTime+d*this.frame)},
 key(e){
  if(e.target.closest('input:not([type=range]):not([type=checkbox]),select,textarea'))return;const v=this.v;if(!v)return;const k=e.key.toLowerCase();
  if(k===' '||k==='k'||k==='л'){e.preventDefault();v.paused?v.play():v.pause()}
  else if(k==='j'||k==='о'){e.preventDefault();this.seek(v.currentTime-5)}
  else if(k==='l'||k==='д'){e.preventDefault();this.seek(v.currentTime+5)}
  else if((k==='arrowleft'||k==='arrowright')&&!e.target.closest('.handle,input')){e.preventDefault();e.shiftKey?this.seek(v.currentTime+(k==='arrowleft'?-1:1)):this.step(k==='arrowleft'?-1:1)}
  else if(k==='i'||k==='ш'){e.preventDefault();this.setIn()}
  else if(k==='o'||k==='щ'){e.preventDefault();this.setOut()}
  else if(k==='m'||k==='ь'){e.preventDefault();this.addMark()}
  else if(k==='escape'){e.preventDefault();historyDirection(-1)}
 },
 // Listening matches the export: each enabled track at its own volume, up to 150%.
 mixing(){const t=this.tracks;return t.length>0&&!(t[0].on&&t[0].gain===100&&t.slice(1).every(x=>!x.on))},
 ensureMix(){
  if(!this.mixing()||this.ctx||!this.v)return;
  try{
   const ctx=this.ctx=new AudioContext();const src=ctx.createMediaElementSource(this.v),gain=ctx.createGain();src.connect(gain).connect(ctx.destination);
   this.nodes={main:gain,extra:[]};
  }catch(e){this.ctx=null}
 },
 syncTracks(seek=false){
  if(!this.v)return;this.ensureMix();if(!this.ctx)return;
  const v=this.v;this.nodes.main.gain.value=this.tracks[0]?.on?this.tracks[0].gain/100:0;
  for(let i=1;i<this.tracks.length;i++){
   const t=this.tracks[i];let n=this.nodes.extra.find(x=>x.i===i);
   if(t.on&&!n){const el=new Audio(`${base}audio-preview/${encodeURIComponent(this.c.id)}?track=${t.index}`);el.preload='auto';const s=this.ctx.createMediaElementSource(el),g=this.ctx.createGain();s.connect(g).connect(this.ctx.destination);n={i,el,g};this.nodes.extra.push(n)}
   if(!n)continue;n.g.gain.value=t.on?t.gain/100:0;n.el.playbackRate=v.playbackRate;
   if(seek||Math.abs(n.el.currentTime-v.currentTime)>.15){try{n.el.currentTime=v.currentTime}catch{}}
   if(v.paused||!t.on)n.el.pause();else n.el.play().catch(()=>{});
  }
  if(this.ctx.state==='suspended'&&!v.paused)this.ctx.resume();
  clearTimeout(this.drift);if(!v.paused)this.drift=setTimeout(()=>this.syncTracks(),700);
 },
 async exportNow(){
  // One click, one export: the button turns into progress before the request returns.
  if(this.job)return;this.job='starting';this.progress=0;this.result=null;this.renderExport();
  const c=this.c,p=PRESETS.find(x=>x.id===this.preset);const name=$('#edName').value.trim()||nameOf(c);
  const audio_tracks=isGifPreset(this.preset)?[]:this.tracks.filter(t=>t.on).map(t=>({index:t.index,gain:t.gain}));
  const args={id:c.id,start:Math.round(this.inT*1000)/1000,end:Math.round(this.outT*1000)/1000,name,timer:this.timer,show_inputs:false,...p.args,...presetQuality(p).args};
  if(args.quality==='copy')args.timer=false; // a copied stream cannot get an overlay
  if(!isGifPreset(this.preset)&&this.tracks.length)Object.assign(args,{audio_mode:'custom',audio_tracks});
  try{
   const job=await task('export',args,{
    progress:j=>{this.progress=j.progress||0;const b=$('#edBar');if(b){b.style.width=this.progress+'%';$('#edPct').textContent=this.progress+'%'}},
    done:async r=>{this.job=null;await pollState(true);const row=state.clips.find(x=>keyOf(x.path)===keyOf(r.path));this.result={...r,id:row?.id,name:r.path.split(/[\\/]/).pop()};this.renderExport();toast('Экспорт готов',false,this.result.name)},
    cancelled:()=>{this.job=null;this.renderExport();toast('Экспорт отменён')},
    error:j=>{this.job=null;this.renderExport();toast(j.message||'Экспорт не удался',true)},
   });
   if(this.job==='starting')this.job=job;
   this.renderExport();
  }catch(e){this.job=null;this.renderExport();fail(e)}
 },
};
function grip(){return '<svg width="6" height="22" viewBox="0 0 6 22" aria-hidden="true"><path d="M1.5 1v20M4.5 1v20" stroke="#0B0C0F" stroke-width="1.4" stroke-linecap="round"/></svg>'}

// ---------- Profiles
const PF_FIELDS=['seconds','fps','mbps','monitor','audio','audio_mode','capture_mode','quality_mode','cq','max_mbps','height','preset','encoder','audio_bitrate','audio_offset_ms','audio_follow_window','cursor','capture_backend','save_format','gif_seconds','chat_path','microphone_enabled','microphone_device','microphone_name','microphone_gain','microphone_voice_cleanup'];
const MINUTES=[1,3,5,10,15,20,30];
const RANGE_FMT={cq:v=>v+' · меньше — лучше',mbps:v=>v+' Мбит/с',max_mbps:v=>v+' Мбит/с',gif_seconds:v=>v+' с',microphone_gain:v=>v+'%'};
const busyCapture=()=>{const r=state.replay||{};return ['starting','recording','stopping'].includes(r.phase)||!!r.saving||!!r.finishing};
const profiles={
 sel:null,draft:null,base:'',devices:null,loading:false,
 rows(){const rows=Object.values(state.settings.capture_profiles||{});return rows.sort((a,b)=>(a.id==='screen:default'?-1:b.id==='screen:default'?1:a.name.localeCompare(b.name,'ru')))},
 find(id){return this.rows().find(p=>keyOf(p.id||p.path)===keyOf(id))},
 isActive(p){return keyOf(p.id||p.path)===keyOf(state.settings.selected_capture_profile||'screen:default')},
 autoOn(p){const s=state.auto_record?.settings||state.settings.auto_record;return !!p?.path&&!!s?.enabled&&(s.apps||[]).some(a=>a.enabled&&keyOf(a.path)===keyOf(p.path))},
 pick(id){
  const p=this.find(id)||this.rows()[0];if(!p)return;this.sel=p.id||p.path;
  const defaults=Object.fromEntries(PF_FIELDS.map(k=>[k,state.replay?.settings?.[k]]).filter(([,v])=>v!==undefined));
  this.draft={id:this.sel,name:p.name,path:p.path||'',hwnd:0,settings:{...defaults,...p.settings}};
  if(this.draft.id==='screen:default'){this.draft.settings.capture_mode='monitor';this.draft.path=''}
  this.base=JSON.stringify(this.draft);
 },
 dirty(){return !!this.draft&&JSON.stringify(this.draft)!==this.base},
 async loadDevices(force=false){
  if(this.loading||(this.devices&&!force))return;this.loading=true;
  try{this.devices=await api('replay_devices')}catch{this.devices={monitors:[],applications:[],audio_applications:[],microphones:[],process_audio_supported:false}}
  finally{this.loading=false}
  if(view.screen==='profiles')this.renderEdit();
 },
 render(){
  if(!this.draft||!this.find(this.draft.id)||(!this.dirty()&&this.draft.id!==this.sel))this.pick(this.sel||state.settings.selected_capture_profile||'screen:default');
  $('#view').innerHTML=`<div class="page"><nav class="pf-list" aria-label="Профили" id="pfList"></nav><section class="pf-edit" id="pfEdit" aria-label="Настройки профиля"></section></div>`;
  this.renderList();this.renderEdit();this.loadDevices();
 },
 renderList(){
  const box=$('#pfList');if(!box)return;
  box.innerHTML=this.rows().map(p=>{const on=keyOf(p.id||p.path)===keyOf(this.sel),d=on?this.draft:{name:p.name,settings:p.settings||{}};const s=d.settings;
   const sum=(s.capture_mode==='window'?'Окно':'Экран')+' · '+(s.fps||60)+' fps · '+Math.round((s.seconds||300)/60)+' мин';
   return `<button type="button" class="pf-item" data-act="pf-pick" data-id="${esc(p.id||p.path)}" aria-current="${on}"><span class="ini" aria-hidden="true">${esc(initials(d.name))}</span><span class="tx"><span style="display:flex;align-items:center;gap:6px;min-width:0"><b>${esc(d.name||'Без названия')}</b>${this.isActive(p)?'<span class="tag">Активен</span>':''}</span><small>${esc(sum)}</small>${this.autoOn(p)?'<small>⚡ Включается сам при запуске игры</small>':''}</span></button>`}).join('')+
   `<button type="button" class="btn" data-act="pf-new" style="border-style:dashed;height:44px" ${busyCapture()?'disabled':''}>${ic('plus')}Новый профиль</button>`;
 },
 seg(key,opts,{disabled=()=>false}={}){
  const cur=this.draft.settings[key];
  return `<div class="seg" role="radiogroup">${opts.map(([v,l])=>`<button type="button" role="radio" data-act="pf-set" data-k="${key}" data-v='${esc(JSON.stringify(v))}' aria-checked="${cur===v}" ${disabled(v)?'disabled':''}>${l}</button>`).join('')}</div>`;
 },
 sw(key,label,sub='',disabled=false){const on=!!this.draft.settings[key];return `<button type="button" class="switch" role="switch" aria-checked="${on}" data-act="pf-toggle" data-k="${key}" ${disabled?'disabled':''}><span class="tr"><span></span></span><span style="display:flex;flex-direction:column"><b style="font-weight:500">${label}</b>${sub?`<small class="hint">${sub}</small>`:''}</span></button>`},
 renderEdit(){
  const box=$('#pfEdit');if(!box||!this.draft)return;const d=this.draft,s=d.settings,dev=this.devices,isDefault=d.id==='screen:default';
  const p=this.find(d.id)||{},busy=busyCapture(),win=s.capture_mode==='window',procOk=!!dev?.process_audio_supported;
  const mons=dev?.monitors||[];
  const monTiles=[{id:'primary',label:'Основной монитор',detail:'Всегда главный экран',w:150,h:84},...mons.map((m,i)=>({id:m.id,label:'Монитор '+(i+1),detail:m.width+' × '+m.height+(m.primary?' · основной':''),w:Math.round(140*Math.min(1.25,m.width/2560)),h:Math.round(140*Math.min(1.25,m.width/2560)*m.height/m.width)}))];
  const apps=(dev?.applications||[]).filter(a=>!/afterplay/i.test(a.title)&&!/\\runtime\\python(w)?\.exe$/i.test(a.path));
  const known=d.path&&!apps.some(a=>keyOf(a.path)===keyOf(d.path));
  const mb=s.quality_mode==='cbr'?s.mbps:s.max_mbps,gb=(mb*1e6/8*(s.seconds||300))/1e9;
  const hints={system:'Записывается всё, что слышно в колонках или наушниках.',game:'Только звук выбранной игры: музыка и Discord в запись не попадут.',exclude:'Весь звук, кроме выбранной игры.',multitrack:'Общий звук, игра и чат — на отдельных дорожках. При монтаже громкость каждой меняется отдельно.',none:'Видео без звука.'};
  const procModes=['game','exclude','multitrack'];
  const audioDisabled=v=>procModes.includes(v)&&(!procOk||!win||!d.path||isDefault);
  const chats=[...new Map((dev?.audio_applications||[]).map(a=>[keyOf(a.path),a])).values()];
  const mics=dev?.microphones||[];
  box.innerHTML=`${busy?`<div class="note" style="border:1px solid rgba(var(--accent-rgb),.4)"><span>Идёт запись. Профиль можно посмотреть, а изменить — после остановки.</span></div>`:''}
  <div style="display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px">
   <div class="field" style="flex:1 1 260px;max-width:420px"><label for="pfName">Название профиля</label><input class="input" id="pfName" value="${esc(d.name)}" maxlength="100" style="font-weight:600;font-size:15px;height:42px"></div>
   <span class="grow"></span>
   ${this.isActive(p)?'<span class="tag" style="padding:6px 10px;font-size:12px">Активный профиль</span>':`<button type="button" class="btn" data-act="pf-activate" ${busy||this.dirty()?'disabled':''} title="${this.dirty()?'Сначала сохраните изменения':''}">Сделать активным</button>`}
   ${isDefault?'':`<button type="button" class="switch" role="switch" aria-checked="${this.autoOn(p)}" data-act="pf-auto" ${!p.path||this.dirty()?'disabled':''} style="height:42px;padding:0 14px;border:1px solid var(--line);border-radius:8px;background:var(--panel)"><span class="tr"><span></span></span>Включать при запуске игры</button>`}
   ${isDefault?'':`<button type="button" class="btn icon danger" data-act="pf-delete" aria-label="Удалить профиль" ${busy?'disabled':''}>${ic('trash')}</button>`}
  </div>
  <p class="hint" style="margin-top:-8px">${isDefault?'Профиль по умолчанию записывает весь экран. Он используется для ручной записи и когда не запущена игра со своим профилем.':this.autoOn(p)?'Когда игра запустится, AFTERPLAY сам включит повтор с этим профилем. Так можно настроить сразу несколько игр.':p.path?'Включите «Включать при запуске игры», чтобы повтор запускался сам.':'Выберите окно игры ниже и сохраните профиль — тогда можно будет включить автозапуск.'}</p>
  <div class="pf-grid">
   <section class="card box wide"><div class="box-head"><h3>Что записывать</h3>${this.seg('capture_mode',[['monitor','Весь экран'],['window','Окно приложения']],{disabled:v=>isDefault&&v==='window'})}</div>
    ${win?`<div class="apps" role="radiogroup" aria-label="Окно приложения">${known?`<button type="button" class="app" role="radio" aria-checked="true" data-act="noop"><span class="ini">${esc(initials(d.path.split(/[\\/]/).pop()))}</span><span><b>${esc(d.path.split(/[\\/]/).pop())}</b><small>сейчас не запущено</small></span></button>`:''}${apps.map(a=>`<button type="button" class="app" role="radio" aria-checked="${keyOf(a.path)===keyOf(d.path)}" data-act="pf-app" data-path="${esc(a.path)}" data-hwnd="${a.hwnd}" data-name="${esc(a.title||a.name)}"><span class="ini">${esc(initials(a.name.replace(/\.exe$/i,'')))}</span><span data-i18n-ignore><b>${esc(a.title||a.name)}</b><small>${esc(a.name)}</small></span></button>`).join('')}</div>
     <div style="display:flex;gap:8px;align-items:center"><button type="button" class="btn sm" data-act="pf-browse">${ic('folder')}Выбрать .exe</button><button type="button" class="btn sm" data-act="pf-devices">${ic('refresh')}Обновить список</button><span class="hint">${apps.length?'Запустите игру, если её нет в списке.':dev?'Открытых окон не найдено. Запустите игру и обновите список.':'Загрузка…'}</span></div>`
    :`<div class="mons" role="radiogroup" aria-label="Монитор">${monTiles.map((m,i)=>`<button type="button" class="mon" role="radio" aria-checked="${s.monitor===m.id}" data-act="pf-set" data-k="monitor" data-v='${esc(JSON.stringify(m.id))}'><span class="scr" style="width:${m.w}px;height:${m.h}px">${i===0?'★':i}</span><b>${esc(m.label)}</b><small>${esc(m.detail)}</small></button>`).join('')}</div>`}
   </section>
   <section class="card box"><h3>Качество видео</h3>
    <div class="field"><span class="lbl">Кадров в секунду</span>${this.seg('fps',[[24,'24'],[30,'30'],[60,'60'],[90,'90'],[120,'120']])}</div>
    <div class="field"><span class="lbl">Разрешение</span>${this.seg('height',[[0,'Исходное'],[2160,'2160p'],[1440,'1440p'],[1080,'1080p'],[720,'720p']])}</div>
    <div class="field"><span class="lbl">Режим качества</span>${this.seg('quality_mode',[['quality','Постоянное качество'],['vbr','Переменный битрейт'],['cbr','Постоянный битрейт']])}</div>
    ${s.quality_mode==='quality'?this.range('cq',14,32,1,'Качество (CQ)'):this.range('mbps',5,200,1,s.quality_mode==='cbr'?'Битрейт':'Средний битрейт')}
    ${s.quality_mode!=='cbr'?this.range('max_mbps',5,200,1,'Предел битрейта'):''}
    <div class="field"><span class="lbl">Нагрузка на систему</span>${this.seg('preset',[['performance','Минимум нагрузки'],['balanced','Баланс'],['quality','Лучшее качество']])}</div>
    <div class="field"><span class="lbl">Кодировщик</span>${this.seg('encoder',[['auto','Авто'],['h264_nvenc','NVIDIA NVENC'],['libx264','Процессор']])}</div>
    <div class="field"><span class="lbl">Способ захвата</span>${this.seg('capture_backend',[['auto','Авто · видеокарта'],['compatibility','Совместимый']])}</div>
    ${this.sw('cursor','Показывать курсор мыши')}
   </section>
   <section class="card box"><h3>Повтор</h3>
    <div class="kv"><label class="lbl" for="pfBuffer">Сколько хранить</label><span class="v" id="pfBufferV">${Math.round(s.seconds/60)} мин</span></div>
    <input type="range" id="pfBuffer" min="0" max="${MINUTES.length-1}" step="1" value="${Math.max(0,MINUTES.indexOf(Math.round(s.seconds/60)))}" data-pf-buffer>
    <div class="ticks" aria-hidden="true">${MINUTES.map(m=>`<span>${m}</span>`).join('')}</div>
    <div class="note"><span>Место на диске для буфера</span><b id="pfDisk">до ${gb.toFixed(1).replace('.',',')} ГБ</b></div>
    <div class="field"><span class="lbl">Кнопка «Сохранить» сохраняет</span>${this.seg('save_format',[['mp4','Видео MP4'],['gif','GIF без звука']])}</div>
    ${s.save_format==='gif'?this.range('gif_seconds',2,15,1,'Длина GIF'):''}
    <p class="hint">Быстрые клипы и клавиши — в разделе «Настройки».</p>
   </section>
   <section class="card box wide"><div class="box-head"><h3>Звук</h3>${this.seg('audio_mode',[['system','Весь звук'],['game','Только игра'],['exclude','Всё кроме игры'],['multitrack','Игра и чат отдельно'],['none','Без звука']],{disabled:audioDisabled})}</div>
    <p class="hint">${hints[s.audio_mode]||''}${!procOk&&dev?' Звук отдельных приложений требует Windows 11.':isDefault||!win?' Звук отдельной игры доступен в профиле окна игры.':''}</p>
    ${s.audio_mode==='multitrack'?`<div class="field" style="max-width:420px"><label for="pfChat">Приложение чата</label><select class="input" id="pfChat" data-pf-select="chat_path"><option value="">Discord · найти автоматически</option>${chats.map(a=>`<option value="${esc(a.path)}" ${keyOf(a.path)===keyOf(s.chat_path)?'selected':''} data-i18n-ignore>${esc(a.name)}</option>`).join('')}${s.chat_path&&!chats.some(a=>keyOf(a.path)===keyOf(s.chat_path))?`<option value="${esc(s.chat_path)}" selected>${esc(s.chat_path.split(/[\\/]/).pop())}</option>`:''}</select></div>`:''}
    ${s.audio_mode!=='none'?`<div class="field"><span class="lbl">Качество звука</span>${this.seg('audio_bitrate',[[128,'128 кбит/с'],[192,'192'],[256,'256'],[320,'320']])}</div>`:''}
    <div style="display:grid;grid-template-columns:auto minmax(0,260px) minmax(0,1fr) 50px;align-items:center;gap:14px;padding:12px;border-radius:10px;background:var(--side)">
     ${this.sw('microphone_enabled','Микрофон','Отдельная дорожка')}
     <select class="input" data-pf-select="microphone_device" aria-label="Микрофон" ${s.microphone_enabled?'':'disabled'}><option value="default">По умолчанию в Windows</option>${mics.map(m=>`<option value="${esc(m.id)}" data-name="${esc(m.name)}" ${String(s.microphone_device)===String(m.id)||(s.microphone_name&&s.microphone_name===m.name&&s.microphone_device!=='default')?'selected':''} data-i18n-ignore>${esc(m.name)}</option>`).join('')}</select>
     <input type="range" min="0" max="100" value="${s.microphone_gain}" data-pf-range="microphone_gain" aria-label="Громкость микрофона" ${s.microphone_enabled?'':'disabled'}>
     <span class="num" style="text-align:right;font-weight:600" data-out="microphone_gain">${s.microphone_enabled?s.microphone_gain+'%':'—'}</span>
    </div>
    ${this.sw('microphone_voice_cleanup','Шумоподавление голоса','Убирает фоновый шум микрофона',!s.microphone_enabled)}
    <div class="field" style="max-width:260px"><label for="pfOffset">Сдвиг звука относительно видео, мс</label><input class="input num" id="pfOffset" type="number" min="-2000" max="2000" step="10" value="${s.audio_offset_ms||0}" data-pf-number="audio_offset_ms"></div>
   </section>
  </div>
  <div class="savebar"><span id="pfStatus" class="hint" style="color:${this.dirty()?'var(--accent)':'var(--muted)'}">${this.dirty()?'Есть несохранённые изменения':'Все изменения сохранены'}</span><span class="grow"></span><button type="button" class="btn" data-act="pf-revert" ${this.dirty()?'':'disabled'}>Отменить</button><button type="button" class="btn primary" data-act="pf-save" ${this.dirty()&&!busy?'':'disabled'}>Сохранить профиль</button></div>`;
 },
 range(key,min,max,step,label){const v=this.draft.settings[key];return `<div class="field"><div class="kv"><span class="lbl">${label}</span><span class="num" style="font-weight:600" data-out="${key}">${esc(RANGE_FMT[key](v))}</span></div><input type="range" min="${min}" max="${max}" step="${step}" value="${v}" data-pf-range="${key}" aria-label="${label}"></div>`},
 changed(full=true){this.renderList();if(full){const y=window.scrollY;this.renderEdit();window.scrollTo(0,y)}else{const st=$('#pfStatus');if(st){st.textContent=this.dirty()?'Есть несохранённые изменения':'Все изменения сохранены';st.style.color=this.dirty()?'var(--accent)':'var(--muted)'}const sv=$('[data-act=pf-save]');if(sv)sv.disabled=!this.dirty()||busyCapture();const rv=$('[data-act=pf-revert]');if(rv)rv.disabled=!this.dirty()}},
 set(key,value){
  const s=this.draft.settings;s[key]=value;
  if(key==='capture_mode'&&value==='window'){s.audio_follow_window=true}
  if(key==='capture_mode'&&value==='monitor'&&['game','exclude','multitrack'].includes(s.audio_mode))s.audio_mode='system';
  if(key==='quality_mode'&&value==='vbr'&&s.max_mbps<s.mbps)s.max_mbps=s.mbps;
 },
 async save(){
  const d=this.draft,wasActive=state.settings.selected_capture_profile,isActive=keyOf(wasActive)===keyOf(d.id);
  const oldPath=this.find(d.id)?.path||'',app=oldPath?(state.auto_record?.settings?.apps||[]).find(a=>keyOf(a.path)===keyOf(oldPath)):null;
  const settings=Object.fromEntries(PF_FIELDS.filter(k=>d.settings[k]!==undefined).map(k=>[k,d.settings[k]]));
  if(d.hwnd)settings.window_hwnd=d.hwnd;
  if(settings.capture_mode==='window'&&!d.path)return toast('Выберите окно игры или файл .exe',true);
  try{
   const updated=await api('profile_configure',{id:d.id,name:d.name,path:d.path,settings});
   if(!isActive&&wasActive)await api('profile_apply',{path:wasActive}).catch(()=>{});
   if(app&&keyOf(oldPath)!==keyOf(updated.path))await setAutoApp(updated,!!app.enabled&&!!updated.path,oldPath);
   await pollState(true);this.sel=updated.id;this.pick(updated.id);
   render();toast('Профиль «'+updated.name+'» сохранён');
  }catch(e){fail(e)}
 },
};
async function setAutoApp(profile,on,oldPath){
 const cur=state.auto_record?.settings||state.settings.auto_record||{enabled:false,save_on_exit:false,apps:[]};
 let apps=(cur.apps||[]).map(a=>({...a})).filter(a=>!oldPath||keyOf(a.path)!==keyOf(oldPath));
 const i=apps.findIndex(a=>keyOf(a.path)===keyOf(profile.path));
 if(on&&i<0)apps.push({path:profile.path,name:profile.name,enabled:true});else if(i>=0)apps[i]={...apps[i],name:profile.name,enabled:on};
 state.auto_record=await api('auto_config',{...cur,apps,enabled:apps.some(a=>a.enabled)});state.settings.auto_record=state.auto_record.settings;
}

// ---------- Settings
const HK_ROWS=[['save','Сохранить повтор',true],['record','Начать или остановить запись',false],['mark','Поставить метку',false],['window','Показать или скрыть окно',true],['clip_1','Быстрый клип 1',false],['clip_2','Быстрый клип 2',false]];
const settingsUI={
 listening:null,cache:null,
 hotkeys(){return {save:'Ctrl+Alt+F10',window:'Ctrl+Alt+F8',...(state.settings.hotkeys||{})}},
 leave(){if(this.listening){this.listening=null;api('hotkeys_edit',{enabled:false}).catch(()=>{})}},
 render(){
  $('#view').innerHTML=`<div class="page"><nav class="st-nav" aria-label="Разделы настроек">${[['general','Общие'],['keys','Горячие клавиши'],['folders','Папки'],['look','Оформление'],['updates','Обновления'],['data','Данные']].map(([id,l])=>`<a href="#st-${id}" data-act="st-jump" data-id="${id}">${l}</a>`).join('')}</nav><div class="st-body" id="stBody"></div></div>`;
  this.paint();if(this.cache===null)api('cache_info').then(r=>{this.cache=r;this.paintData()}).catch(()=>{});
 },
 paint(){
  const box=$('#stBody');if(!box)return;const d=state.settings.desktop?.clips||{},auto=state.auto_record?.settings||{},c=custom(),hk=this.hotkeys(),q=quickValues(),r=state.replay||{};
  const sw=(act,on,label,sub,disabled=false)=>`<div class="st-row"><span class="t"><b>${label}</b>${sub?`<small>${sub}</small>`:''}</span><button type="button" class="switch" role="switch" aria-checked="${!!on}" aria-label="${esc(label)}" data-act="${act}" ${disabled?'disabled':''}><span class="tr"><span></span></span></button></div>`;
  const used=Object.entries(hk).filter(([,v])=>v);
  box.innerHTML=`<section class="card st-sec" id="st-general"><h2>Общие</h2>
   <div class="st-row"><span class="t"><b>Язык интерфейса</b><small>Переключение применяется сразу и сохраняется между запусками.</small></span><select class="input" id="interfaceLanguage" aria-label="Язык интерфейса" style="width:auto;min-width:160px">${[['ru','Русский'],['en','English'],['ko','한국어']].map(([v,l])=>`<option value="${v}" data-i18n-ignore ${(['en','ko'].includes(state.settings.language)?state.settings.language:'ru')===v?'selected':''}>${l}</option>`).join('')}</select></div>
   ${sw('st-autostart',d.autostart,'Запускать вместе с Windows','AFTERPLAY стартует свёрнутым в трей')}
   <div class="st-row"><span class="t"><b>Кнопка «Закрыть» в окне</b><small>Полный выход всегда есть в меню значка в трее</small></span><div class="seg" role="radiogroup" aria-label="Кнопка «Закрыть»">${[['tray','Свернуть в трей'],['close','Закрыть программу']].map(([v,l])=>`<button type="button" role="radio" data-act="st-close" data-v="${v}" aria-checked="${(d.close_action||'tray')===v}">${l}</button>`).join('')}</div></div>
   ${sw('st-exit-save',auto.save_on_exit,'Сохранять повтор при закрытии игры','Для профилей, которые включаются сами при запуске игры')}
   ${sw('st-sounds',c.sounds?.enabled,'Звуки событий','Короткий сигнал при сохранении и ошибке')}
   <div class="st-row"><span class="t"><b>Ярлык на рабочем столе</b><small>Создаёт ярлык AFTERPLAY</small></span><button type="button" class="btn" data-act="st-shortcut">Создать ярлык</button></div>
  </section>
  <section class="card st-sec" id="st-keys"><h2>Горячие клавиши</h2><p class="hint" style="margin:-2px 0 6px">${r.hotkey_ok===false&&r.hotkey_error?esc(r.hotkey_error):'Нажмите на сочетание и введите новое. Esc — отмена, Backspace — убрать необязательное.'}</p>
   ${HK_ROWS.map(([k,label,req],i)=>{const v=hk[k]||'',listen=this.listening===k,dup=v&&used.some(([o,ov])=>o!==k&&ov.toLowerCase()===v.toLowerCase());const quick=k.startsWith('clip_')?Number(k.slice(5))-1:-1;
    return `<div class="st-row"><span class="t"><b>${label}</b>${quick>=0?`<small>Сохраняет последние секунды записи</small>`:''}${dup?'<small style="color:#FFB4B5">Это сочетание занято другим действием</small>':''}</span>${quick>=0?`<label class="field" style="flex-direction:row;align-items:center;gap:8px"><input class="input num" type="number" min="5" max="1800" step="5" value="${q[quick]}" data-quick="${quick}" style="width:90px" aria-label="Длительность, секунд"><span class="hint">сек</span></label>`:''}<button type="button" class="keybtn ${listen?'listen':''} ${dup?'bad':''}" data-act="st-key" data-hk="${k}" aria-label="${esc(label)}: ${v?esc(v):'не задано'}. Нажмите, чтобы изменить">${listen?'Нажмите сочетание…':v?v.split('+').map(p=>`<kbd>${esc(p)}</kbd>`).join(''):'<span class="hint">Не задано</span>'}</button></div>`}).join('')}
  </section>
  <section class="card st-sec" id="st-folders"><h2>Папки</h2>
   <div class="st-row"><span class="t"><b>Новые повторы, записи и клипы</b><small style="overflow-wrap:anywhere" data-i18n-ignore>${esc(state.storage?.recordings_dir||'')}</small></span><button type="button" class="btn" data-act="st-recdir">Изменить</button><button type="button" class="btn" data-act="st-open" data-target="exports">Открыть</button></div>
   <div class="st-row" style="flex-direction:column;align-items:stretch"><span class="t"><b>Дополнительные папки с видео</b><small>Видео из них появляются в библиотеке. Файлы остаются на месте.</small></span>
    ${(state.settings.video_roots||[]).map(p=>`<div class="folder"><span title="${esc(p)}" data-i18n-ignore>${esc(p)}</span><button type="button" class="btn sm ghost" data-act="st-root-off" data-path="${esc(p)}">Отключить</button></div>`).join('')||'<span class="hint">Папки не добавлены.</span>'}
    <div style="display:flex;gap:8px"><button type="button" class="btn sm" data-act="st-root-add">${ic('plus')}Добавить папку</button><button type="button" class="btn sm" data-act="st-scan">${ic('refresh')}Обновить библиотеку</button></div></div>
  </section>
  <section class="card st-sec" id="st-look"><h2>Оформление</h2>
   <div class="st-row"><span class="t"><b>Акцентный цвет</b><small>${esc((ACCENTS.find(a=>a[0]===accent())||ACCENTS[0])[1])}</small></span><div class="swatches" role="radiogroup" aria-label="Акцентный цвет">${ACCENTS.map(([hex,name])=>`<button type="button" class="swatch" role="radio" style="--c:${hex}" aria-checked="${hex===accent()}" aria-label="${name}" data-act="st-accent" data-v="${hex}"></button>`).join('')}</div></div>
   <div class="st-row"><span class="t"><b>Размер карточек</b><small>В библиотеке</small></span><input type="range" min="180" max="420" step="10" value="${clamp(Number(c.card_size)||240,180,420)}" data-st-card style="max-width:260px" aria-label="Размер карточек"></div>
   ${sw('st-motion',c.animation!=='off','Анимации интерфейса','Плавные переходы и пульсация индикатора записи')}
   <div class="st-row"><span class="t"><b>Уведомления</b><small>Угол экрана для всплывающих уведомлений</small></span><div class="corners" role="radiogroup" aria-label="Угол уведомлений">${[['top-left','Слева сверху','top:8px;left:8px'],['top-right','Справа сверху','top:8px;right:8px'],['bottom-left','Слева снизу','bottom:8px;left:8px'],['bottom-right','Справа снизу','bottom:8px;right:8px']].map(([v,l,pos])=>`<button type="button" role="radio" aria-label="${l}" aria-checked="${(c.notice_position||'top-right')===v}" data-act="st-corner" data-v="${v}" style="${pos}"></button>`).join('')}</div><button type="button" class="btn sm" data-act="st-notice">Показать пример</button></div>
  </section>
  <section class="card st-sec" id="st-updates"><h2>Обновления</h2><div id="stUpdates"></div></section>
  <section class="card st-sec" id="st-data"><h2>Данные</h2><div id="stData"></div></section>`;
  this.paintUpdates();this.paintData();
 },
 paintUpdates(){
  const box=$('#stUpdates');if(!box)return;const u=state.updates||{},l=u.latest;
  box.innerHTML=`<div class="st-row"><span class="t"><b>AFTERPLAY ${esc(u.version||'')}</b><small style="color:${u.error?'#FFB4B5':l?.available?'var(--accent)':'var(--muted)'}">${esc(u.error||(l?l.available?'Доступна версия '+l.version:'Установлена последняя версия':'Проверка на GitHub по кнопке'))}</small></span>
   ${l?.available&&u.supported?`<button type="button" class="btn primary" data-act="st-update-install" ${u.busy?'disabled':''}>${u.prepared?'Перезапустить и обновить':'Скачать и установить'}</button>`:''}
   <button type="button" class="btn" data-act="st-update-check" ${u.busy?'disabled':''}>Проверить обновления</button></div>
   <div class="st-row"><span class="t"><b>Обновлять автоматически</b><small>Только когда запись не идёт</small></span><button type="button" class="switch" role="switch" aria-label="Обновлять автоматически" aria-checked="${!!state.settings.updates?.auto_enabled}" data-act="st-autoupdate"><span class="tr"><span></span></span></button></div>`;
 },
 paintData(){
  const box=$('#stData');if(!box)return;const c=this.cache;
  box.innerHTML=`<div class="st-row"><span class="t"><b>Кэш превью и звуковых волн</b><small>Создаётся заново при необходимости. Старше 30 дней удаляется сам.</small></span><span class="num hint">${c?bytes(c.bytes):'…'}</span><button type="button" class="btn" data-act="st-cache" ${c&&c.bytes?'':'disabled'}>Очистить</button></div>
   <div class="st-row"><span class="t"><b>Настройки и журналы</b><small>Папка data рядом с программой</small></span><button type="button" class="btn" data-act="st-open" data-target="data">${ic('folder')}Открыть папку</button></div>`;
 },
 combo(e){
  const map={Space:'Space',Insert:'Insert',Delete:'Delete',Home:'Home',End:'End',PageUp:'PageUp',PageDown:'PageDown',ArrowUp:'Up',ArrowDown:'Down',ArrowLeft:'Left',ArrowRight:'Right',Pause:'Pause'};
  let key='';const code=e.code||'';
  if(/^Key[A-Z]$/.test(code))key=code.slice(3);else if(/^Digit\d$/.test(code))key=code.slice(5);else if(/^Numpad\d$/.test(code))key=code.slice(6);else if(/^F\d{1,2}$/.test(code))key=code;else key=map[code]||'';
  if(!key)return null;const mods=[e.ctrlKey&&'Ctrl',e.altKey&&'Alt',e.shiftKey&&'Shift'].filter(Boolean);
  return {combo:[...mods,key].join('+'),ok:mods.length>0||/^F\d+$/.test(key),key};
 },
 async saveKeys(patch,quick){
  const hk={...this.hotkeys(),...patch};const values={};for(const [k] of HK_ROWS)if(hk[k])values[k]=hk[k];
  values.quick_clips=quick||quickValues();
  try{state.settings.hotkeys=await api('hotkeys_config',values);state.settings.quick_clips=values.quick_clips;toast('Горячие клавиши сохранены')}
  catch(e){fail(e)}finally{this.paint();renderDock()}
 },
};
document.addEventListener('keydown',e=>{
 const btn=e.target.closest?.('[data-hk]');if(!btn||settingsUI.listening!==btn.dataset.hk)return;
 e.preventDefault();e.stopPropagation();const k=btn.dataset.hk,row=HK_ROWS.find(x=>x[0]===k);
 if(e.key==='Escape'){settingsUI.leave();settingsUI.paint();return}
 if((e.key==='Backspace'||e.key==='Delete')&&!row[2]){settingsUI.leave();settingsUI.saveKeys({[k]:''});return}
 if(['Control','Alt','Shift','Meta'].includes(e.key))return;
 const r=settingsUI.combo(e);if(!r)return toast('Эту клавишу нельзя назначить',true);
 if(!r.ok)return toast('Добавьте Ctrl, Alt или Shift',true);if(r.key==='F12')return toast('F12 зарезервирована Windows',true);
 settingsUI.leave();settingsUI.saveKeys({[k]:r.combo});
},true);
document.addEventListener('focusout',e=>{if(e.target.closest?.('[data-hk]')&&settingsUI.listening){setTimeout(()=>{if(!document.activeElement?.closest?.('[data-hk]')&&settingsUI.listening){settingsUI.leave();settingsUI.paint()}},0)}});

// ---------- Actions
async function recordAction(name,el){
 const done=(msg)=>()=>{pollState(true);if(msg)toast(msg)};
 if(name==='replay-start')return task('replay_start',{},{done:done('Повтор включён')});
 if(name==='replay-stop')return task('replay_stop',{},{done:done('Повтор выключен')});
 if(name==='record-start')return task('recording_start',{},{done:done('Запись началась')});
 if(name==='record-stop')return task('recording_stop',{},{done:r=>{pollState(true);toast('Запись сохранена',false,r?.duration?short(r.duration):'')}});
 if(name==='save'||name==='quick'){
  const seconds=name==='quick'?quickValues()[Number(el.dataset.index)||0]:undefined;
  return task('replay_save',seconds?{seconds}:{},{done:r=>{pollState(true);toast(seconds?'Клип сохранён':'Повтор сохранён',false,r?.duration?short(r.duration):'')}});
 }
}
const ACT={
 noop(){},
 nav(el){libUI.kind=el.dataset.kind;libUI.limit=120;if(view.screen!=='library')go({screen:'library'});else{render()}},
 go(el){if(view.screen!==el.dataset.screen)go({screen:el.dataset.screen})},
 back(){if(backStack.length)historyDirection(-1);else go({screen:'library'},false)},
 select(el){selectClip(el.dataset.id)},
 watch(el){go({screen:'viewer',id:el.dataset.id,at:el.dataset.at})},
 edit(el){go({screen:'editor',id:el.dataset.id,focusExport:!!el.dataset.export})},
 async fav(el){const c=clipById(el.dataset.id);if(!c)return;await saveClipMeta(c,{favorite:!c.favorite});libUI.sig='';refreshLibrary();renderDetail(true)},
 reveal(el){if(el.dataset.id)return api('open',{target:'clip-folder',id:el.dataset.id})},
 async delete(el){const c=clipById(el.dataset.id);if(!c)return;
  const mode=await chooseBox('Удалить запись?',`<p><b data-i18n-ignore>«${esc(nameOf(c))}»</b></p><div class="dlg-notes"><p>В корзину: файл можно восстановить из корзины Windows.</p><p>Удалить навсегда: видео будет удалено с компьютера, минуя корзину. Это действие нельзя отменить в AFTERPLAY.</p></div>`,
   [{v:'permanent',label:'Удалить навсегда',cls:'danger solid'},{v:'recycle',label:'В корзину',cls:'primary',focus:true}]);
  if(!mode)return;
  const r=await api('clip_delete',{id:c.id,delete_mode:mode});if(libUI.sel===c.id)libUI.sel=null;await pollState(true);toast(r.missing?'Файла уже нет — запись убрана из библиотеки':mode==='permanent'?'Запись удалена навсегда':'Запись перемещена в корзину')},
 chip(el){libUI.chip=el.dataset.chip;libUI.limit=120;render()},
 more(){libUI.limit+=120;refreshLibrary()},
 async 'steps-hide'(){state.settings.onboarding=await api('onboarding_config',{status:'completed'});$('.steps')?.remove()},
 'open-keys'(){go({screen:'settings'});setTimeout(()=>$('#st-keys')?.scrollIntoView({behavior:'smooth'}),50)},
 // viewer
 'vw-play'(){const v=viewer.v;if(v){viewer.toggleMenu(false);v.paused||v.ended?v.play():v.pause()}},
 'vw-seek'(el){viewer.seekTo(viewer.v.currentTime+Number(el.dataset.d))},
 'vw-frame'(el){viewer.stepFrame(Number(el.dataset.d))},
 'vw-to'(el){viewer.seekTo(Number(el.dataset.t))},
 'vw-mute'(){viewer.userMuted=!viewer.userMuted;viewer.syncExtra();viewer.syncVol()},
 'vw-menu'(){viewer.toggleMenu()},'vw-rate'(el){viewer.rate(Number(el.dataset.v))},
 'vw-full'(){viewer.fullscreen()},'vw-track'(el){viewer.setTrack(Number(el.dataset.i))},
 'vw-step'(el){viewer.step(Number(el.dataset.dir))},
 'vw-gif-play'(){viewer.gifToggle()},'vw-gif-frame'(el){viewer.gifStep(Number(el.dataset.d))},'vw-gif-jump'(el){viewer.gifJump(Number(el.dataset.d))},
 async 'vw-fav'(el){const c=viewer.c;await saveClipMeta(c,{favorite:!c.favorite});el.setAttribute('aria-pressed',!!c.favorite);el.style.color=c.favorite?'var(--accent)':'inherit';el.innerHTML=ic('heart',c.favorite?'fill="currentColor"':'')},
 // editor
 'ed-play'(){const v=editor.v;v.paused?v.play():v.pause()},'ed-frame'(el){editor.step(Number(el.dataset.d))},

 'ed-in'(){editor.setIn()},'ed-out'(){editor.setOut()},'ed-mark'(){editor.addMark()},
 'ed-q'(el){exportQ[el.dataset.p]=el.dataset.q;localSet('ag.exportQ',JSON.stringify(exportQ));editor.updateQuality(el.dataset.p)},
 'ed-preset'(el){editor.preset=el.dataset.id;editor.renderPresets();editor.renderExport();editor.renderTracks()},
 'ed-track'(el){const on=toggleTrack(editor.tracks.map(t=>t.on),Number(el.dataset.i));editor.tracks.forEach((t,j)=>t.on=on[j]);editor.renderTracks();editor.syncTracks()},
 'ed-export'(){editor.exportNow()},
 async 'ed-cancel'(){if(editor.job&&editor.job!=='starting')await api('job_cancel',{id:editor.job}).catch(fail)},
 async 'ed-copy'(){const id=editor.result?.id;if(!id)return;await api('copy_file',{id});const l=$('#edCopyL');if(l)l.textContent='Скопировано ✓';toast('Файл скопирован','', 'Вставьте его в Discord или проводник')},
 'ed-again'(){editor.result=null;editor.renderExport()},
 // profiles
 'pf-pick'(el){if(profiles.dirty()&&keyOf(el.dataset.id)!==keyOf(profiles.sel)){confirmBox('Сбросить изменения?','Несохранённые изменения профиля будут потеряны.','Сбросить').then(ok=>{if(ok){profiles.pick(el.dataset.id);profiles.renderList();profiles.renderEdit()}});return}profiles.pick(el.dataset.id);profiles.renderList();profiles.renderEdit()},
 async 'pf-new'(){const p=await api('profile_new');await pollState(true);profiles.pick(p.id);profiles.draft.settings.capture_mode='window';profiles.renderList();profiles.renderEdit();$('#pfName')?.select()},
 'pf-set'(el){profiles.set(el.dataset.k,JSON.parse(el.dataset.v));profiles.changed()},
 'pf-toggle'(el){const k=el.dataset.k;profiles.set(k,!profiles.draft.settings[k]);profiles.changed()},
 'pf-app'(el){const d=profiles.draft;d.path=el.dataset.path;d.hwnd=Number(el.dataset.hwnd)||0;if(!d.name||d.name==='Новый профиль')d.name=el.dataset.name.slice(0,100);profiles.changed()},
 async 'pf-browse'(){const r=await api('browse',{purpose:'profile-app'});if(r.path){const d=profiles.draft;d.path=r.path;d.hwnd=0;if(!d.name||d.name==='Новый профиль')d.name=r.path.split(/[\\/]/).pop().replace(/\.exe$/i,'');profiles.changed()}},
 'pf-devices'(){profiles.loadDevices(true)},
 async 'pf-activate'(){await api('profile_apply',{path:profiles.draft.id});await pollState(true);profiles.renderList();profiles.renderEdit();toast('Профиль «'+profiles.draft.name+'» активен')},
 async 'pf-auto'(){const p=profiles.find(profiles.draft.id);if(!p?.path)return;const on=!profiles.autoOn(p);await setAutoApp(p,on);profiles.renderList();profiles.renderEdit();toast(on?'Профиль включится сам при запуске игры':'Автозапуск профиля выключен')},
 async 'pf-delete'(){const p=profiles.find(profiles.draft.id);if(!p||!await confirmBox('Удалить профиль?',`«${p.name}» будет удалён. Записи останутся.`))return;
  if(profiles.autoOn(p))await setAutoApp(p,false).catch(()=>{});await api('profile_remove',{path:p.id||p.path});await pollState(true);profiles.sel=null;profiles.draft=null;render();toast('Профиль удалён')},
 'pf-revert'(){profiles.pick(profiles.draft.id);profiles.changed()},
 'pf-save'(){profiles.save()},
 // settings
 'st-jump'(el,e){e.preventDefault();$('#st-'+el.dataset.id)?.scrollIntoView({behavior:'smooth',block:'start'})},
 async 'st-autostart'(){const on=!state.settings.desktop?.clips?.autostart;const r=await api('autostart_config',{enabled:on});state.settings.desktop={...state.settings.desktop,clips:{...state.settings.desktop?.clips,autostart:r.enabled}};settingsUI.paint()},
 async 'st-close'(el){await api('desktop_config',{close_action:el.dataset.v});state.settings.desktop={...state.settings.desktop,clips:{...state.settings.desktop?.clips,close_action:el.dataset.v}};settingsUI.paint()},
 async 'st-exit-save'(){const cur=state.auto_record?.settings||{enabled:false,save_on_exit:false,apps:[]};state.auto_record=await api('auto_config',{...cur,save_on_exit:!cur.save_on_exit});settingsUI.paint()},
 async 'st-sounds'(){const on=!custom().sounds?.enabled;state.settings.customization=await api('customize_config',{sounds:{enabled:on}});settingsUI.paint()},
 async 'st-shortcut'(){const r=await api('shortcut_desktop');toast('Ярлык создан',false,r.path||'')},
 'st-key'(el){const k=el.dataset.hk;if(settingsUI.listening===k){settingsUI.leave();settingsUI.paint();return}settingsUI.listening=k;api('hotkeys_edit',{enabled:true}).catch(()=>{});settingsUI.paint();$(`[data-hk="${k}"]`)?.focus()},
 async 'st-recdir'(){const r=await api('browse',{purpose:'recordings'});if(!r.path)return;state.storage=await api('storage_config',{recordings_dir:r.path});settingsUI.paint();toast('Папка для записей изменена')},
 'st-open'(el){return api('open',{target:el.dataset.target})},
 async 'st-root-off'(el){await api('settings',{remove_video_root:el.dataset.path});await pollState(true);settingsUI.paint()},
 async 'st-root-add'(){const r=await api('browse',{purpose:'video'});if(!r.path)return;await api('settings',{video_root:r.path});await pollState(true);settingsUI.paint();task('scan',{},{done:x=>{pollState(true);toast('Библиотека обновлена',false,(x?.count??0)+' видео')}})},
 'st-scan'(){return task('scan',{},{done:x=>{pollState(true);toast('Библиотека обновлена',false,(x?.count??0)+' видео')}})},
 async 'st-accent'(el){state.settings.customization=await api('customize_config',{afterglow_accent:el.dataset.v});applyLook();settingsUI.paint()},
 async 'st-motion'(){state.settings.customization=await api('customize_config',{animation:custom().animation==='off'?'calm':'off'});applyLook();settingsUI.paint()},
 async 'st-corner'(el){state.settings.customization=await api('customize_config',{notice_position:el.dataset.v});settingsUI.paint()},
 'st-notice'(){return api('customize_notice')},
 async 'st-autoupdate'(){const r=await api('updates_config',{auto_enabled:!state.settings.updates?.auto_enabled});state.settings.updates=r;settingsUI.paintUpdates()},
 'st-update-check'(){return task('update_check',{},{done:async()=>{await pollState(true);settingsUI.paintUpdates()},error:async j=>{await pollState(true);settingsUI.paintUpdates();toast(j.message,true)}})},
 async 'st-update-install'(){
  if(state.updates?.prepared){if(await confirmBox('Перезапустить AFTERPLAY?','Программа закроется, обновится и откроется снова.','Обновить',false))await api('update_install');return}
  task('update_prepare',{},{progress:()=>settingsUI.paintUpdates(),done:async()=>{await pollState(true);settingsUI.paintUpdates();if(await confirmBox('Обновление готово','Перезапустить AFTERPLAY сейчас?','Перезапустить',false))api('update_install').catch(fail)}});
 },
 async 'st-cache'(){const r=await api('cache_clear');settingsUI.cache={bytes:0};settingsUI.paintData();toast('Кэш очищен',false,'освобождено '+bytes(r.bytes||0))},
};
document.addEventListener('click',async e=>{
 const el=e.target.closest('[data-act]');if(!el||el.disabled)return;const fn=ACT[el.dataset.act]||(['replay-start','replay-stop','record-start','record-stop','save','quick'].includes(el.dataset.act)?(x=>recordAction(el.dataset.act,x)):null);
 if(!fn)return;
 if(el.dataset.act!=='vw-menu'&&viewer.menu&&!el.closest('#vwMenu'))viewer.toggleMenu(false);
 try{await fn(el,e)}catch(error){fail(error)}
});
document.addEventListener('dblclick',e=>{
 const card=e.target.closest('.clip[data-id]');if(card){go({screen:'viewer',id:card.dataset.id});return}
 const pct=e.target.closest('[data-act=ed-gain-reset]');if(pct){const t=editor.tracks[Number(pct.dataset.i)];if(t){t.gain=100;editor.renderTracks();editor.syncTracks()}}
});
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.matches?.('.clip[data-id]')){e.preventDefault();go({screen:'viewer',id:e.target.dataset.id})}});
let searchTimer=0;
document.addEventListener('input',e=>{
 const t=e.target;
 if(t.id==='search'){libUI.query=t.value;libUI.limit=120;clearTimeout(searchTimer);searchTimer=setTimeout(refreshLibrary,120);return}
 if(t.dataset.gain!==undefined){const tr=editor.tracks[Number(t.dataset.gain)];tr.gain=Number(t.value);const b=t.closest('.track').querySelector('.pct');b.textContent=tr.gain+'%';b.style.color=tr.gain>100?'var(--accent)':'var(--text)';editor.syncTracks();return}
 if(!profiles.draft)return;
 if(t.id==='pfName'){profiles.draft.name=t.value;profiles.changed(false);const item=$(`.pf-item[aria-current=true] b`);if(item)item.textContent=t.value||'Без названия';return}
 if(t.dataset.pfRange){const k=t.dataset.pfRange;profiles.set(k,Number(t.value));const o=$(`[data-out="${k}"]`);if(o)o.textContent=RANGE_FMT[k](Number(t.value));profiles.changed(false);return}
 if(t.dataset.pfBuffer!==undefined){const s=profiles.draft.settings;s.seconds=MINUTES[Number(t.value)]*60;$('#pfBufferV').textContent=MINUTES[Number(t.value)]+' мин';const mb=s.quality_mode==='cbr'?s.mbps:s.max_mbps;$('#pfDisk').textContent='до '+(mb*1e6/8*s.seconds/1e9).toFixed(1).replace('.',',')+' ГБ';profiles.changed(false);return}
});
document.addEventListener('change',async e=>{
 const t=e.target;
 try{
  if(t.dataset.pfRange||t.dataset.pfBuffer!==undefined){profiles.renderList();return}
  if(t.dataset.pfSelect){const k=t.dataset.pfSelect;profiles.set(k,t.value);if(k==='microphone_device')profiles.set('microphone_name',t.selectedOptions[0]?.dataset.name||'');profiles.changed();return}
  if(t.dataset.pfNumber){profiles.set(t.dataset.pfNumber,clamp(Math.round(Number(t.value)||0),-2000,2000));profiles.changed();return}
  if(t.dataset.quick!==undefined){const q=quickValues().slice();q[Number(t.dataset.quick)]=clamp(Math.round(Number(t.value)||30),5,1800);await settingsUI.saveKeys({},q);return}
  if(t.dataset.stCard!==undefined){state.settings.customization=await api('customize_config',{card_size:Number(t.value)});applyLook();return}
 }catch(error){fail(error)}
});

// ---------- Polling
let polling=false,pollSkips=0;
async function pollState(force=false){
 if(polling){if(!force)return;while(polling)await new Promise(r=>setTimeout(r,40));return pollState(true)}
 const hidden=document.hidden||window.customNativeHidden;
 if(hidden&&!force&&++pollSkips<5)return;pollSkips=0;polling=true;
 try{state=await api('state');onState()}catch{}finally{polling=false}
}
function onState(){
 applyLook();processJobs();renderShell();
 if(view.screen==='library')refreshLibrary();
 else if(view.screen==='profiles'){if(!profiles.dirty()&&!document.activeElement?.closest?.('#pfEdit'))profiles.renderList();profiles.changed(false)}
 else if(view.screen==='settings')settingsUI.paintUpdates();
 syncChrome();
}
window.pollState=pollState;window.customUpdatePause=()=>{};window.customNativeHidden=false;
setInterval(pollState,1800);
setInterval(()=>{const r=state.replay;if(r?.phase==='recording'&&!document.hidden&&!window.customNativeHidden){renderDock();syncChrome()}},1000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollState(true)});

// ---------- Start
(()=>{
 const tab=new URLSearchParams(location.search).get('tab');
 view={screen:tab==='replay'?'profiles':tab==='customize'?'settings':'library'};
 render();pollState(true).then(()=>{render();syncChrome(true)});
})();
// Missing thumbnails (not generated yet) show the card surface, not a broken image.
document.addEventListener('error',e=>{if(e.target?.tagName==='IMG')e.target.style.visibility='hidden'},true);
