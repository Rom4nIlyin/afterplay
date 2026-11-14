'use strict';
// Afterglow: the single AFTERPLAY theme. Graphite surfaces and one warm accent
// that only marks actions and live recording. Loaded after every other layer.
(()=>{
 const ACCENTS=[['#FF8A3D','Янтарь','Amber'],['#2DD4BF','Бирюза','Teal'],['#A78BFA','Фиалка','Violet'],['#A3E635','Лайм','Lime'],['#F472B6','Роза','Rose']];
 const TOKENS={cinema_background:'#0B0C0F',cinema_panel:'#131519',cinema_text:'#F2F3F5',cinema_muted:'#A3A9B4'};
 const QUICK_DEFAULTS=[30,120];
 const t=(ru,en)=>state.settings?.language==='en'?en:ru;
 const accentOf=value=>{const v=String(value||'').toLowerCase();return (ACCENTS.find(a=>a[0].toLowerCase()===v)||ACCENTS[0])[0]};
 const pad=n=>String(n).padStart(2,'0');
 const clock=s=>{s=Math.max(0,Math.floor(Number(s)||0));return (s>=3600?pad(Math.floor(s/3600))+':':'')+pad(Math.floor(s/60)%60)+':'+pad(s%60)};
 const duration=s=>s%60===0&&s>=60?(s/60)+' '+t('мин','min'):s+' '+t('с','s');

 // One look: the old palettes, sidebar artwork, scenes and the classic layout
 // are no longer offered. Stored choices stay in settings but are ignored.
 customDefaults.afterglow_accent=ACCENTS[0][0];
 const baseSettings=customSettings;
 customSettings=function(){
  const c=baseSettings();
  return {...c,...TOKENS,cinema_layout:true,cinema_palette:'custom',cinema_sidebar:'none',cinema_accent:accentOf(c.afterglow_accent),background:'none',theme:'obsidian'};
 };
 const baseApply=customApply;
 customApply=function(){baseApply();document.body.classList.add('afterglow');document.documentElement.dataset.theme='obsidian'};
 document.body.classList.add('afterglow');

 // ---- Recording dock: one place for replay, recording, save and quick clips.
 function quickValues(){const v=state.settings.quick_clips;return Array.isArray(v)&&v.length>=2?v.slice(0,2):QUICK_DEFAULTS}
 let polled=null,polledAt=0;
 function liveSeconds(r){
  // Count between the 1.8 s state polls without drifting from the app clock.
  if(r!==polled){polled=r;polledAt=performance.now()}
  return (r.recording_seconds||0)+(performance.now()-polledAt)/1000;
 }
 function dockState(){
  const r=state.replay||{},keys=state.settings.hotkeys||{};
  const busy=['starting','stopping'].includes(r.phase)||!!r.finishing;
  const live=r.phase==='recording';
  const manual=!!(r.continuous||r.pending_recording);
  const replay=!!r.replay_enabled&&live;
  const minutes=Math.round((r.settings?.seconds||300)/60);
  let mode='off',title=t('Запись выключена','Recording off'),sub=t('Повтор и запись не идут','Replay and recording are off');
  if(r.phase==='starting'){mode='busy';title=t('Запуск…','Starting…');sub=t('Подключаем захват','Connecting capture')}
  else if(r.phase==='stopping'||r.finishing){mode='busy';title=t('Сохранение…','Saving…');sub=t('Дождитесь завершения','Please wait')}
  else if(live&&manual){mode='record';title=t('Запись ','Recording ')+clock(liveSeconds(r));sub=replay?t('и повтор · ','and replay · ')+minutes+' '+t('мин','min'):(state.replay?.active_profile||t('Идёт запись','Recording'))}
  else if(live){mode='replay';title=t('Повтор · ','Replay · ')+minutes+' '+t('мин','min');sub=keys.save?keys.save+' — '+t('сохранить','save'):t('Буфер ','Buffer ')+clock(r.buffer_seconds)}
  else if(r.phase==='error'){mode='error';title=t('Ошибка записи','Recording error');sub=r.error||''}
  if(r.saving&&mode!=='busy')sub=t('Сохраняю клип…','Saving clip…');
  const fill=mode==='replay'?Math.min(100,Math.round((r.buffer_seconds||0)/((r.settings?.seconds||300))*100)):0;
  return {r,keys,busy,live,manual,replay,mode,title,sub,fill,canSave:live&&!busy&&(r.save_queue||0)<8};
 }
 const kbd=value=>value?`<kbd>${esc(value)}</kbd>`:'';
 const dockIcon={clock:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',save:'<path d="M12 4v11m-5-5 5 5 5-5M5 19h14"/>',stop:'<rect x="7" y="7" width="10" height="10" rx="2"/>'};
 const svg=name=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${dockIcon[name]}</svg>`;
 function dockMarkup(s){
  const quick=quickValues();
  const replayLabel=s.replay?t('Выключить повтор','Turn replay off'):t('Включить повтор','Turn replay on');
  const recordLabel=s.manual?t('Остановить и сохранить запись','Stop and save recording'):t('Начать запись','Start recording');
  return `<div class="ag-dock" data-mode="${s.mode}" role="group" aria-label="${t('Управление записью','Recording controls')}">`+
   `<button type="button" class="ag-dock-status" data-tab="replay" title="${esc(s.title+' · '+s.sub)}"><i class="ag-dot" aria-hidden="true"></i><span class="ag-dock-text"><b>${esc(s.title)}</b><small>${esc(s.sub)}</small></span>${s.mode==='replay'?`<span class="ag-fill" aria-hidden="true"><span style="width:${s.fill}%"></span></span>`:''}</button>`+
   `<span class="ag-dock-sep" aria-hidden="true"></span>`+
   `<button type="button" class="ag-dock-toggle ${s.replay?'is-on':''}" data-action="${s.replay?'replay-stop':'replay-start'}" aria-pressed="${s.replay}" title="${replayLabel}" ${s.busy?'disabled':''}>${svg('clock')}<span>${t('Повтор','Replay')}</span></button>`+
   `<button type="button" class="ag-dock-toggle ag-dock-rec ${s.manual?'is-on':''}" data-action="${s.manual?'replay-record-stop':'replay-record-start'}" aria-pressed="${s.manual}" title="${recordLabel}${s.keys.record?' · '+esc(s.keys.record):''}" ${s.busy?'disabled':''}>${s.manual?svg('stop'):'<i class="ag-rec-dot" aria-hidden="true"></i>'}<span>${s.manual?t('Стоп','Stop'):t('Запись','Record')}</span></button>`+
   `<span class="ag-dock-sep" aria-hidden="true"></span>`+
   `<button type="button" class="ag-dock-save" data-action="replay-save" title="${t('Сохранить повтор','Save replay')}${s.keys.save?' · '+esc(s.keys.save):''}" ${s.canSave?'':'disabled'}>${svg('save')}<span>${t('Сохранить','Save')}</span>${kbd(s.keys.save)}</button>`+
   quick.map((seconds,i)=>`<button type="button" class="ag-dock-quick" data-action="afterglow-quick" data-index="${i}" title="${t('Быстрый клип: последние ','Quick clip: last ')+duration(seconds)}${s.keys['clip_'+(i+1)]?' · '+esc(s.keys['clip_'+(i+1)]):''}" aria-label="${t('Сохранить последние ','Save last ')+duration(seconds)}" ${s.canSave?'':'disabled'}>${esc(duration(seconds))}</button>`).join('')+
   `</div>`;
 }
 let dockSignature='';
 function syncDock(){
  const host=$('#cinemaCapture');if(!host)return;
  const s=dockState(),markup=dockMarkup(s);
  document.body.classList.toggle('ag-recording',s.mode==='record');
  if(markup===dockSignature&&host.querySelector('.ag-dock'))return;
  dockSignature=markup;host.innerHTML=markup;host.classList.add('ag-dock-host');
 }

 // ---- Profiles: several game profiles can start automatically at once.
 const keyOf=value=>String(value||'').replaceAll('/','\\').toLowerCase();
 function autoApps(){return state.auto_record?.settings?.apps||state.settings.auto_record?.apps||[]}
 function autoFor(path){
  if(!path)return false;
  const enabled=state.auto_record?.settings?.enabled??state.settings.auto_record?.enabled;
  return !!enabled&&autoApps().some(a=>a.enabled&&keyOf(a.path)===keyOf(path));
 }
 async function setAuto(profile,on){
  const current=state.auto_record?.settings||state.settings.auto_record||{enabled:false,save_on_exit:false,apps:[]};
  let apps=(current.apps||[]).map(a=>({...a}));
  const index=apps.findIndex(a=>keyOf(a.path)===keyOf(profile.path));
  if(on&&index<0)apps.push({path:profile.path,name:profile.name,enabled:true});
  else if(index>=0)apps[index]={...apps[index],name:profile.name,enabled:on};
  const cfg={...current,apps,enabled:apps.some(a=>a.enabled)};
  state.auto_record=await api('auto_config',cfg);state.settings.auto_record=state.auto_record.settings;
 }
 function decorateProfiles(){
  const panel=$('.studio-profiles');if(!panel)return;
  const id=panel.dataset.profileId,rows=Object.values(state.settings.capture_profiles||{});
  const profile=rows.find(p=>keyOf(p.id||p.path)===keyOf(id));
  for(const option of $('#captureProfile')?.options||[]){
   const row=rows.find(p=>keyOf(p.id||p.path)===keyOf(option.value));
   if(row){const label=row.name+(autoFor(row.path)?t(' · авто',' · auto'):'');if(option.textContent!==label)option.textContent=label}
  }
  let box=$('#afterglowAuto');
  const isDefault=keyOf(id)==='screen:default';
  if(!box){box=document.createElement('div');box.id='afterglowAuto';box.className='ag-auto';panel.append(box)}
  const signature=[id,isDefault,profile?.path,autoFor(profile?.path),studioBusy()].join('|');
  if(box.dataset.signature===signature)return;box.dataset.signature=signature;
  if(isDefault){
   box.innerHTML=`<div class="ag-auto-note">${t('Профиль по умолчанию записывает весь экран. Он используется для ручной записи и когда не запущена игра со своим профилем.','The default profile records the entire screen. It is used for manual recording and when no game with its own profile is running.')}</div>`;
   return;
  }
  const on=autoFor(profile?.path),ready=!!profile?.path;
  box.innerHTML=`<label class="ag-switch"><input type="checkbox" id="afterglowAutoToggle" ${on?'checked':''} ${!ready||studioBusy()?'disabled':''}><span class="ag-switch-track" aria-hidden="true"><span></span></span><span><b>${t('Включать при запуске игры','Start with the game')}</b><small>${ready?t('Когда это приложение откроется, AFTERPLAY сам включит повтор с этим профилем. Так можно настроить несколько игр сразу.','When this app opens, AFTERPLAY turns on replay with this profile. Several games can be set up at once.'):t('Сначала укажите приложение .exe и сохраните профиль.','Choose the .exe and save the profile first.')}</small></span></label>`;
 }
 document.addEventListener('change',async e=>{
  if(e.target.id!=='afterglowAutoToggle')return;
  const control=e.target,id=$('.studio-profiles')?.dataset.profileId;
  const profile=Object.values(state.settings.capture_profiles||{}).find(p=>keyOf(p.id||p.path)===keyOf(id));
  if(!profile?.path){control.checked=false;return}
  control.disabled=true;
  try{await setAuto(profile,control.checked);toast(control.checked?t('Профиль включится сам при запуске игры','The profile will start with the game'):t('Автозапуск профиля выключен','Automatic start turned off'))}
  catch(error){control.checked=!control.checked;toast(error.message,true)}
  finally{control.disabled=false;$('#afterglowAuto')&&($('#afterglowAuto').dataset.signature='');decorateProfiles()}
 });

 // ---- Appearance: one theme, five accents.
 function accentPicker(){
  const panel=$('.cinema-design-panel');if(!panel||$('#afterglowAccent'))return;
  const current=accentOf(customSettings().afterglow_accent);
  const markup=`<section id="afterglowAccent" class="ag-accent"><div><span class="cinema-eyebrow">AFTERGLOW</span><h2>${t('Акцентный цвет','Accent color')}</h2><p>${t('Единая тема Afterglow. Цвет отмечает действия и идущую запись.','The single Afterglow theme. The accent marks actions and live recording.')}</p></div><div class="ag-swatches" role="radiogroup" aria-label="${t('Акцентный цвет','Accent color')}">${ACCENTS.map(([hex,ru,en])=>`<button type="button" role="radio" class="ag-swatch ${hex===current?'selected':''}" data-action="afterglow-accent" data-value="${hex}" aria-checked="${hex===current}" title="${t(ru,en)}" aria-label="${t(ru,en)}" style="--swatch:${hex}"></button>`).join('')}<span class="ag-swatch-name">${t(...(ACCENTS.find(a=>a[0]===current)||ACCENTS[0]).slice(1))}</span></div></section>`;
  panel.insertAdjacentHTML('afterbegin',markup);
 }
 function tidyCustomize(){
  if(tab!=='customize')return;
  // Scenes and wallpapers belonged to the retired themes.
  if(typeof customPane!=='undefined'&&customPane==='background')customPane='interface';
 }

 const baseAction=action;
 action=async function(name,element){
  if(name==='afterglow-accent'){
   const value=accentOf(element.dataset.value);
   const result=await api('customize_config',{afterglow_accent:value});state.settings.customization=result;
   if(typeof customDraft!=='undefined'&&customDraft)customDraft.afterglow_accent=value;
   customApply();render();return;
  }
  if(name==='afterglow-quick'){
   const seconds=quickValues()[Number(element.dataset.index)||0];
   await task('replay_save',{seconds},r=>{refresh(false);toast(t('Клип сохранён · ','Clip saved · ')+fmt(r.duration))});return;
  }
  return baseAction(name,element);
 };

 const baseRender=render;
 render=function(){
  tidyCustomize();baseRender();
  syncDock();accentPicker();decorateProfiles();
 };
 const baseUpdateReplay=window.updateReplay;
 window.updateReplay=function(){try{baseUpdateReplay?.()}finally{syncDock();decorateProfiles()}};
 const basePreferences=window.updatePreferences;
 window.updatePreferences=function(){basePreferences?.();syncDock()};
 // The recording timer in the dock ticks between state polls.
 setInterval(()=>{if(document.hidden||window.customNativeHidden)return;const r=state.replay;if(r?.phase==='recording'&&(r.continuous||r.pending_recording))syncDock()},1000);
 customApply();syncDock();
})();
