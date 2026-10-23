'use strict';
const themeNames={standard:'Стандартная',dark:'Тёмная',light:'Светлая'};
let pendingTheme=null,themeQueue=Promise.resolve();
function applyTheme(theme){document.documentElement.dataset.theme=themeNames[theme]?theme:'standard'}
const renderDesktopSettings=window.renderDesktopExtras;
window.renderDesktopExtras=function(){
 applyTheme(pendingTheme||state.settings.appearance?.theme||'standard');
 renderDesktopSettings?.();
 if($('#appVersion'))$('#appVersion').textContent=state.updates?.version||'1.3.1';
 if(tab!=='settings')return;
 const panel=$('.settings-panel'),u=state.updates||{},latest=u.latest,recording=['starting','recording','stopping'].includes(state.replay?.phase)||state.replay?.saving;
 panel.insertAdjacentHTML('beforeend',`<div class="split-line"></div><div class="panel-title">ЗАХВАТ</div><div class="field"><label class="check"><input id="captureBorder" type="checkbox" ${state.replay?.settings?.capture_border?'checked':''} ${recording?'disabled':''}> Показывать жёлтую рамку во время записи</label><small>По умолчанию выключена. Применяется при следующем запуске записи. Для изменения останови запись и дождись экспорта.</small></div>
 <div class="split-line"></div><div class="panel-title">ТЕМА ИНТЕРФЕЙСА</div><div class="field"><label for="interfaceTheme">Оформление</label><select id="interfaceTheme">${Object.entries(themeNames).map(([value,name])=>`<option value="${value}" ${(pendingTheme||state.settings.appearance?.theme||'standard')===value?'selected':''}>${name}</option>`).join('')}</select><small>Тема применяется сразу и сохраняется между запусками.</small></div>
 <div class="split-line"></div><div class="panel-title">ЗАПУСК И ЯРЛЫКИ</div><div class="field"><label class="check"><input id="launchAtLogin" type="checkbox" ${state.settings.desktop?.[mode]?.autostart?'checked':''}> Запускать автоматически при включении компьютера</label><small>Программа запускается после входа текущего пользователя в Windows. Запись включается вручную.</small></div><div class="actions">${button('shortcut-desktop','Добавить ярлык на рабочий стол','plus','secondary')}${button('shortcut-taskbar','Добавить на панель задач','plus','secondary')}</div><p class="hint">Для панели задач откроется Проводник с ярлыком. Нажми по нему правой кнопкой и выбери «Закрепить на панели задач»; при необходимости — «Показать дополнительные параметры».</p>
 <div class="split-line"></div><div class="panel-title">ОБНОВЛЕНИЕ GAME CLIPS</div><p id="updateVersion">Установлена версия ${esc(u.version||'1.3.1')}${latest?` · на GitHub ${esc(latest.version)}`:''}</p><p class="hint" id="updateHint">${u.busy?'Загрузка обновления…':latest?(latest.available?'Доступна новая версия.':'Новых версий нет.'):'Проверка стабильной версии в GitHub Releases.'}</p><div class="actions" style="margin-top:16px">${button('update-check','Проверить обновления','refresh','secondary',u.busy?'disabled':'')}${latest?.available?button('update-start',`Обновить до ${latest.version} и перезапустить`,'download','primary',u.busy||recording||!u.supported?'disabled':''):''}</div><p class="hint">Обновление сохраняет записи и настройки. Файлы программы копируются в backups перед заменой. Перед установкой останови запись и дождись экспорта.</p>${u.last_result?`<div class="notice">${esc(u.last_result.message)}</div>`:''}`);
};
window.updatePreferences=function(){
 applyTheme(pendingTheme||state.settings.appearance?.theme||'standard');
 if($('#appVersion'))$('#appVersion').textContent=state.updates?.version||'1.3.1';
 if($('#captureBorder'))$('#captureBorder').disabled=['starting','recording','stopping'].includes(state.replay?.phase)||!!state.replay?.saving;
};
document.addEventListener('change',e=>{
 if(e.target.id==='captureBorder'){
  const control=e.target,value=control.checked;control.disabled=true;
  api('replay_config',{capture_border:value}).then(result=>{state.replay=result;toast(value?'Жёлтая рамка включена':'Жёлтая рамка выключена')}).catch(error=>{control.checked=!value;toast(error.message,true)}).finally(()=>control.disabled=['starting','recording','stopping'].includes(state.replay?.phase)||!!state.replay?.saving);return;
 }
 if(e.target.id==='launchAtLogin'){
  const control=e.target,value=control.checked;control.disabled=true;
  api('autostart_config',{enabled:value}).then(result=>{state.settings.desktop??={};state.settings.desktop[mode]??={};state.settings.desktop[mode].autostart=result.enabled;toast(result.enabled?'Автозапуск включён':'Автозапуск выключен')}).catch(error=>{control.checked=!value;toast(error.message,true)}).finally(()=>control.disabled=false);return;
 }
 if(e.target.id!=='interfaceTheme')return;
 const choice=e.target.value;pendingTheme=choice;applyTheme(choice);
 themeQueue=themeQueue.catch(()=>{}).then(async()=>{
  try{const saved=await api('appearance_config',{theme:choice});state.settings.appearance=saved;if(pendingTheme===choice)pendingTheme=null}
  catch(error){if(pendingTheme===choice)pendingTheme=null;applyTheme(state.settings.appearance?.theme||'standard');toast(error.message,true)}
 });
});
window.updateAction=async function(action){
 if(action==='shortcut-desktop'){const r=await api('shortcut_desktop');toast('Ярлык создан на рабочем столе');return}
 if(action==='shortcut-taskbar'){
  const r=await api('shortcut_taskbar');
  modal('Закрепить на панели задач','<p>В Проводнике выделен ярлык Game Clips. Нажми по нему правой кнопкой мыши и выбери <b>«Закрепить на панели задач»</b>.</p><p style="margin-top:14px">Если пункта нет, открой «Показать дополнительные параметры». Также можно закрепить значок уже открытого Game Clips через меню панели задач.</p>',button('close','Понятно','check','primary'));return;
 }
 if(action==='update-check'){
  await task('update_check',{},u=>{
   if(u.latest?.available)modal('Доступна версия '+u.latest.version,`<p>Установлена ${esc(u.version)}. Размер загрузки: ${size(u.latest.bytes)}.</p><p style="margin-top:14px">Программа скачает релиз с GitHub, проверит файлы и перезапустится. Записи и настройки сохранятся.</p><pre class="release-notes">${esc(u.latest.notes.slice(0,2000))}</pre>`,button('close','Позже','close','quiet')+button('update-start','Обновить и перезапустить','download','primary'));
   else toast('Новых версий нет · установлена '+u.version);
  });return;
 }
 if(action==='update-start'){
  if($('#dialog').open)close();
  await task('update_prepare',{},async()=>{
   modal('Обновление загружено','<p>Game Clips закрывается для замены файлов. После установки окно откроется снова.</p>');
   try{await api('update_install')}catch(error){close();toast(error.message,true)}
  });return;
 }
};
