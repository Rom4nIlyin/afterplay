'use strict';
const saveBinding=()=>state.settings.hotkeys?.save||'Ctrl+Alt+F10';
const autoDefaults=()=>({enabled:false,save_on_exit:true,apps:[]});
function quickReplay(){
 const r=state.replay||{},cfg=r.settings||{},active=['starting','recording'].includes(r.phase),busy=['starting','stopping'].includes(r.phase);
 return `<section class="quick-replay"><div class="quick-state"><span class="status-lamp ${active?'on':''}"></span><div><b id="quickState">${active?'Повтор включён':'Повтор выключен'}</b><small id="quickDetail">${active?'Последние '+cfg.seconds/60+' мин · '+fmt(r.buffer_seconds||0):'Включи повтор или настрой автозапись'}</small></div></div><div class="quick-actions">${active?button('quick-save','Сохранить момент','download','primary',r.saving?'disabled':''):button('quick-start','Включить повтор','play','primary',busy?'disabled':'')}<kbd id="quickBinding">${esc(saveBinding())}</kbd>${active?button('quick-stop','Остановить','close','secondary',busy?'disabled':''):button('quick-auto','Автозапись','settings','secondary')}</div></section>`;
}
const previousClipsPage=clipsPage;
clipsPage=function(){
 let markup=previousClipsPage();
 if(['library','favorites'].includes(tab))markup=markup.replace('<div class="toolbar">',quickReplay()+'<div class="toolbar">');
 return markup;
};
const previousAction=action;
action=async function(a,el){
 if(a==='quick-auto'){tab='settings';render();$('#autoSection')?.scrollIntoView({behavior:'smooth',block:'start'});return}
 if(a==='quick-start'){await task('replay_start');return}
 if(a==='quick-save'){await task('replay_save');return}
 if(a==='quick-stop'){await task('replay_stop');return}
 if(a==='auto-add-file'){
  const result=await api('browse',{purpose:'auto-app'});if(result.path)await addAutoApp(result.path);return;
 }
 if(a==='auto-add-running'){
  const select=$('#autoRunning'),option=select.selectedOptions[0];
  if(!option?.value)throw Error('Сначала выбери запущенное приложение');
  await addAutoApp(option.value,option.dataset.name);return;
 }
 if(a==='auto-remove'){
  const cfg=structuredClone(state.auto_record?.settings||autoDefaults());cfg.apps=cfg.apps.filter(app=>app.id!==el.dataset.id);
  await saveAuto(cfg);return;
 }
 if(a==='hotkeys-save'){
  const values={save:$('#saveHotkey').value,auto:$('#autoHotkey').value};
  const result=await api('hotkeys_config',values);state.settings.hotkeys=result;
  await refresh();toast('Горячие клавиши сохранены');return;
 }
 if(a==='hotkeys-reset'){
  $('#saveHotkey').value='Ctrl+Alt+F10';$('#autoHotkey').value='Ctrl+Alt+F9';return;
 }
 return previousAction(a,el);
};
async function saveAuto(cfg){state.auto_record=await api('auto_config',cfg);state.settings.auto_record=state.auto_record.settings;await refresh();toast('Настройки автозаписи сохранены')}
async function addAutoApp(path,name){
 const cfg=structuredClone(state.auto_record?.settings||autoDefaults());
 cfg.apps.push({path,name:name||path.split(/[\\/]/).pop(),enabled:true});
 await saveAuto(cfg);
}
function autoSettings(){
 const cfg=state.auto_record?.settings||autoDefaults();
 return `<section id="autoSection" class="settings-card wide"><div class="section-top"><div><span class="eyebrow">ПРОГРАММА ПОМНИТ ЗА ТЕБЯ</span><h2>Автозапись игр и приложений</h2></div><span id="autoState" class="pill">${cfg.enabled?'Включена':'Выключена'}</span></div><label class="check switch-row"><input id="autoEnabled" type="checkbox" ${cfg.enabled?'checked':''}> Включать повтор при запуске приложений из списка</label><p class="hint">AFTERPLAY ждёт окно выбранного приложения и записывает только его. Сохраняется буфер последних ${(state.replay?.settings.seconds||300)/60} минут, а не весь сеанс. Нужный момент — по клавише <kbd>${esc(saveBinding())}</kbd>. Если игра уже открыта, запись начнётся после включения этой опции.</p><label class="check"><input id="autoSaveExit" type="checkbox" ${cfg.save_on_exit?'checked':''}> Сохранить последние минуты при закрытии игры или отключении автозаписи</label><div class="auto-add"><div class="field"><label for="autoRunning">Добавить из запущенных приложений</label><div class="field-line"><select id="autoRunning"><option value="">Загрузка списка окон…</option></select>${button('auto-add-running','Добавить','plus')}</div></div>${button('auto-add-file','Выбрать файл .exe','folder','secondary')}</div><div class="auto-list">${cfg.apps.length?cfg.apps.map(app=>`<div class="auto-app"><label class="check"><input data-auto-app="${esc(app.id)}" type="checkbox" ${app.enabled?'checked':''}><span><b>${esc(app.name)}</b><small title="${esc(app.path)}">${esc(app.path)}</small></span></label><button class="icon-button" data-action="auto-remove" data-id="${esc(app.id)}" aria-label="Убрать ${esc(app.name)} из списка" title="Убрать из списка">${icon('close')}</button></div>`).join(''):'<div class="auto-empty">Добавь игру или приложение — например, выбери его окно выше.<br>Само приложение и его файлы при удалении из списка не меняются.</div>'}</div><p class="hint">Распознавание идёт по полному пути .exe. При нескольких открытых приложениях приоритет у первого в списке. Качество и звук берутся из настроек повтора. После ручной остановки приложение пропускается до его следующего запуска.</p><p id="autoError" class="hint error-text">${esc(state.auto_record?.error||'')}</p></section>`;
}
function hotkeySettings(){
 return `<section class="settings-card"><span class="eyebrow">БЫСТРЫЕ ДЕЙСТВИЯ</span><h2>Горячие клавиши</h2><div class="field"><label for="saveHotkey">Сохранить последние минуты</label><input class="hotkey-input" id="saveHotkey" value="${esc(saveBinding())}" autocomplete="off" spellcheck="false" aria-describedby="hotkeyHelp"></div><div class="field"><label for="autoHotkey">Включить / выключить автозапись</label><input class="hotkey-input" id="autoHotkey" value="${esc(state.settings.hotkeys?.auto||'Ctrl+Alt+F9')}" autocomplete="off" spellcheck="false" aria-describedby="hotkeyHelp"></div><p id="hotkeyHelp" class="hint">Нажми на поле и введи своё сочетание. Подойдут Ctrl, Alt, Shift с буквой, цифрой или F-клавишей. Можно использовать отдельную F-клавишу, кроме F12. Клавиши работают и в трее.</p><div class="actions">${button('hotkeys-save','Сохранить','check','primary')}${button('hotkeys-reset','По умолчанию','refresh','quiet')}</div><p class="hint error-text">${esc(state.replay?.hotkey_error||'')}</p></section>`;
}
const previousDesktopExtras=window.renderDesktopExtras;
window.renderDesktopExtras=function(){
 previousDesktopExtras?.();
 if(tab!=='settings')return;
 const panel=$('.settings-panel');if(!panel||panel.dataset.afterplay)return;
 panel.dataset.afterplay='true';
 const elements=[...panel.children];panel.replaceChildren();
 let card=document.createElement('section');card.className='settings-card';panel.append(card);
 const heading=document.createElement('h2');heading.textContent='Библиотека и папки';card.append(heading);
 for(const element of elements){
  if(element.classList.contains('split-line')){
   card=document.createElement('section');card.className='settings-card';panel.append(card);
  }else card.append(element);
 }
 panel.insertAdjacentHTML('afterbegin',autoSettings()+hotkeySettings());
 api('replay_applications').then(result=>{
  const select=$('#autoRunning');if(!select)return;
  select.innerHTML='<option value="">Выбери окно игры или приложения</option>'+result.applications.filter(app=>!['afterplay.exe','pythonw.exe'].includes(app.name.toLowerCase())).map(app=>`<option value="${esc(app.path)}" data-name="${esc(app.title||app.name)}">${esc(app.name)} — ${esc(app.title)}</option>`).join('');
 }).catch(error=>{if($('#autoRunning'))$('#autoRunning').innerHTML='<option value="">'+esc(error.message)+'</option>'});
};
const previousPreferences=window.updatePreferences;
window.updatePreferences=function(){
 previousPreferences?.();
 const r=state.replay||{},active=['starting','recording'].includes(r.phase);
 if($('#quickState')){
  const changed=$('#quickState').dataset.phase!==r.phase;
  if(changed&&!$('#dialog').open){const bar=$('.quick-replay');if(bar)bar.outerHTML=quickReplay();if($('#quickState'))$('#quickState').dataset.phase=r.phase}
  if($('#quickDetail'))$('#quickDetail').textContent=active?'Последние '+r.settings.seconds/60+' мин · '+fmt(r.buffer_seconds||0):'Включи повтор или настрой автозапись';
  if($('[data-action="quick-save"]'))$('[data-action="quick-save"]').disabled=r.phase!=='recording'||r.saving;
 }
 if($('#autoState'))$('#autoState').textContent=state.auto_record?.active?'Записывается: '+state.auto_record.active:state.auto_record?.settings.enabled?'Ожидает приложение':'Выключена';
 if($('#autoEnabled')&&document.activeElement!==$('#autoEnabled'))$('#autoEnabled').checked=!!state.auto_record?.settings.enabled;
 if($('#autoError'))$('#autoError').textContent=state.auto_record?.error||'';
};
document.addEventListener('change',async e=>{
 if(!['autoEnabled','autoSaveExit'].includes(e.target.id)&&!e.target.dataset.autoApp)return;
 const control=e.target;control.disabled=true;
 try{
  const cfg=structuredClone(state.auto_record?.settings||autoDefaults());
  if(control.id==='autoEnabled')cfg.enabled=control.checked;
  else if(control.id==='autoSaveExit')cfg.save_on_exit=control.checked;
  else{const app=cfg.apps.find(a=>a.id===control.dataset.autoApp);if(app)app.enabled=control.checked}
  await saveAuto(cfg);
 }catch(error){control.checked=!control.checked;toast(error.message,true)}finally{control.disabled=false}
});
document.addEventListener('keydown',e=>{
 if(!e.target.classList.contains('hotkey-input')||e.key==='Tab')return;
 e.preventDefault();e.stopPropagation();
 if(['Control','Shift','Alt','Meta'].includes(e.key)||e.repeat)return;
 const special={Space:'Space',Insert:'Insert',Delete:'Delete',Home:'Home',End:'End',PageUp:'PageUp',PageDown:'PageDown',ArrowUp:'Up',ArrowDown:'Down',ArrowLeft:'Left',ArrowRight:'Right',Pause:'Pause'};
 let key=/^Key[A-Z]$/.test(e.code)?e.code.slice(3):/^Digit[0-9]$/.test(e.code)?e.code.slice(5):/^F\d+$/.test(e.code)?e.code:special[e.code]||(/^F\d+$/.test(e.key)?e.key:/^[a-z0-9]$/i.test(e.key)?e.key.toUpperCase():null);
 if(!key||e.metaKey){toast('Используй Ctrl, Alt, Shift и букву, цифру или F-клавишу',true);return}
 e.target.value=[e.ctrlKey?'Ctrl':'',e.altKey?'Alt':'',e.shiftKey?'Shift':'',key].filter(Boolean).join('+');
},true);
let hotkeyEditQueue=Promise.resolve();
function hotkeyEditing(enabled){
 hotkeyEditQueue=hotkeyEditQueue.catch(()=>{}).then(()=>api('hotkeys_edit',{enabled})).catch(error=>toast(error.message,true));
}
document.addEventListener('focusin',e=>{if(e.target.classList?.contains('hotkey-input'))hotkeyEditing(true)});
document.addEventListener('focusout',e=>{if(e.target.classList?.contains('hotkey-input'))setTimeout(()=>{if(!document.activeElement?.classList?.contains('hotkey-input'))hotkeyEditing(false)},0)});
window.addEventListener('blur',()=>hotkeyEditing(false));
window.addEventListener('focus',()=>{if(document.activeElement?.classList?.contains('hotkey-input'))hotkeyEditing(true)});
setInterval(()=>{if(document.hasFocus()&&document.activeElement?.classList?.contains('hotkey-input'))hotkeyEditing(true)},5000);
