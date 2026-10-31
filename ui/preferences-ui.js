'use strict';
icons.github='<path d="M9 19c-4.3 1.3-4.3-2.2-6-2.7M15 22v-3.9a3.4 3.4 0 0 0-1-2.6c3.3-.4 6.8-1.6 6.8-7.4A5.8 5.8 0 0 0 19.2 4a5.4 5.4 0 0 0-.1-4s-1.3-.4-4.3 1.6a14.8 14.8 0 0 0-7.8 0C4-.4 2.7 0 2.7 0A5.4 5.4 0 0 0 2.6 4 5.8 5.8 0 0 0 1 8.1c0 5.8 3.5 7 6.8 7.4A3.4 3.4 0 0 0 6.8 18v4" transform="translate(2 2) scale(.86)"/>';
if($('#githubBtn'))$('#githubBtn').innerHTML=icon('github');
icons.copy='<rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>';
document.addEventListener('click',event=>{if(event.target.id==='githubProfileUrl')event.target.select()});
document.addEventListener('focus',event=>{if(event.target.id==='githubProfileUrl')event.target.select()},true);
const themeNames={obsidian:'Obsidian',glass:'Frosted Glass',aurora:'Aurora',ember:'Ember',mist:'Mist',paper:'Paper'};
let pendingTheme=null,themeQueue=Promise.resolve();
function applyTheme(theme){document.documentElement.dataset.theme=themeNames[theme]?theme:'obsidian'}
const renderDesktopSettings=window.renderDesktopExtras;
window.renderDesktopExtras=function(){
 applyTheme(pendingTheme||state.settings.appearance?.theme||'obsidian');
 renderDesktopSettings?.();
 if($('#appVersion'))$('#appVersion').textContent=state.updates?.version||'1.3.1';
 if(tab!=='settings')return;
 $('.settings-panel').insertAdjacentHTML('beforeend',`<div class="split-line"></div><div class="panel-title">ЗНАКОМСТВО С AFTERPLAY</div><p class="hint">Короткий тур по библиотеке, записи и настройкам.</p><div class="actions">${button('onboarding-open','Пройти обучение','play','secondary')}</div>`);
 const panel=$('.settings-panel'),u=state.updates||{},latest=u.latest,recording=['starting','recording','stopping'].includes(state.replay?.phase)||state.replay?.saving;
 const cinema=typeof customSettings==='function'&&customSettings().cinema_layout!==false;
 panel.insertAdjacentHTML('beforeend',`<div class="split-line"></div><div class="panel-title">ЗАХВАТ</div><div class="field"><label class="check"><input id="captureBorder" type="checkbox" ${state.replay?.settings?.capture_border?'checked':''} ${recording?'disabled':''}> Показывать жёлтую рамку во время записи</label><small>По умолчанию выключена. Настройка общая для всех профилей. Применяется при следующем запуске записи. Для изменения останови запись и дождись экспорта.</small></div>
 ${cinema?'':`<div class="split-line"></div><div class="panel-title">ТЕМА ИНТЕРФЕЙСА</div><div class="field"><label for="interfaceTheme">Оформление</label><select id="interfaceTheme">${Object.entries(themeNames).map(([value,name])=>`<option value="${value}" ${(pendingTheme||state.settings.appearance?.theme||'obsidian')===value?'selected':''}>${name}</option>`).join('')}</select><small>Тема применяется сразу и сохраняется между запусками.</small></div>`}
 <div class="split-line"></div><div class="panel-title">ЗАПУСК И ЯРЛЫКИ</div><div class="field"><label class="check"><input id="launchAtLogin" type="checkbox" ${state.settings.desktop?.[mode]?.autostart?'checked':''}> Запускать автоматически при включении компьютера</label><small>При входе в Windows AFTERPLAY запускается в трее. Автозапись работает, если включена ниже и приложение добавлено в список.</small></div><div class="actions">${button('shortcut-desktop','Добавить ярлык на рабочий стол','plus','secondary')}${button('shortcut-taskbar','Добавить на панель задач','plus','secondary')}</div><p class="hint">Для панели задач откроется Проводник с ярлыком. Нажми по нему правой кнопкой и выбери «Закрепить на панели задач»; при необходимости — «Показать дополнительные параметры».</p>
 <div class="split-line"></div><div class="panel-title">ОБНОВЛЕНИЕ AFTERPLAY</div><label class="check"><input id="autoUpdateEnabled" type="checkbox" ${state.settings.updates?.auto_enabled?'checked':''}> Включить автообновление</label><p class="hint">По умолчанию выключено. При включении новая версия загружается и устанавливается, когда запись и экспорт остановлены. Кнопка ручной проверки работает всегда.</p><p id="updateVersion">Установлена версия ${esc(u.version||'1.3.1')}${latest?` · на GitHub ${esc(latest.version)}`:''}</p><p class="hint" id="updateHint">${u.busy?'Загрузка обновления…':latest?(latest.available?'Доступна новая версия.':'Новых версий нет.'):'Проверка стабильной версии в GitHub Releases.'}</p><div class="actions" style="margin-top:16px">${button('update-check','Проверить обновления','refresh','secondary',u.busy?'disabled':'')}<div class="github-profile-link">${button('update-github','GitHub','github','secondary')}<div class="github-profile-copy"><input id="githubProfileUrl" type="url" value="https://github.com/Rom4nIlyin/afterplay" readonly spellcheck="false" aria-label="Ссылка на репозиторий AFTERPLAY" title="Выделить ссылку для копирования">${button('update-github-copy','', 'copy','quiet','title="Скопировать ссылку" aria-label="Скопировать ссылку"')}</div></div>${latest?.available?button('update-start','Скачать и установить обновление','download','primary',u.busy||recording||!u.supported?'disabled':''):''}</div><p class="hint">Обновление сохраняет записи и настройки. Файлы программы копируются в backups перед заменой. Перед установкой останови запись и дождись экспорта.</p>${u.last_result?`<div class="notice">${esc(u.last_result.message)}</div>`:''}`);
};
window.updatePreferences=function(){
 applyTheme(pendingTheme||state.settings.appearance?.theme||'obsidian');
 if($('#appVersion'))$('#appVersion').textContent=state.updates?.version||'1.3.1';
 if($('#captureBorder'))$('#captureBorder').disabled=['starting','recording','stopping'].includes(state.replay?.phase)||!!state.replay?.saving;
};
document.addEventListener('change',e=>{
 if(e.target.id==='autoUpdateEnabled'){
  const control=e.target,value=control.checked;control.disabled=true;
  api('updates_config',{auto_enabled:value}).then(result=>{state.settings.updates=result;toast(value?'Автообновление включено':'Автообновление выключено')}).catch(error=>{control.checked=!value;toast(error.message,true)}).finally(()=>control.disabled=false);return;
 }
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
  try{const saved=await api('appearance_config',{theme:choice});state.settings.appearance=saved;if(pendingTheme===choice)pendingTheme=null;await refresh()}
  catch(error){if(pendingTheme===choice)pendingTheme=null;applyTheme(state.settings.appearance?.theme||'obsidian');toast(error.message,true)}
 });
});
window.updateAction=async function(action){
 if(action==='update-github-copy'){
  const field=$('#githubProfileUrl');if(!field)return;
  try{await navigator.clipboard.writeText(field.value)}
  catch(error){field.focus();field.select();if(!document.execCommand('copy'))throw Error('Не удалось скопировать. Выдели поле и нажми Ctrl+C.')}
  toast('Ссылка скопирована');return;
 }
 if(action==='update-github'){await api('open',{target:'github'});return}
 if(action==='shortcut-desktop'){const r=await api('shortcut_desktop');toast('Ярлык создан на рабочем столе');return}
 if(action==='shortcut-taskbar'){
  const r=await api('shortcut_taskbar');
  modal('Закрепить на панели задач','<p>В Проводнике выделен ярлык AFTERPLAY. Нажми по нему правой кнопкой мыши и выбери <b>«Закрепить на панели задач»</b>.</p><p style="margin-top:14px">Если пункта нет, открой «Показать дополнительные параметры». Также можно закрепить значок уже открытого AFTERPLAY через меню панели задач.</p>',button('close','Понятно','check','primary'));return;
 }
 if(action==='update-check'){
  await task('update_check',{},u=>{
   state.updates=u;if(tab==='settings'&&!$('#dialog').open)render();
   toast(u.latest?.available?'Доступна версия '+u.latest.version+'. Нажми «Скачать и установить обновление».':'Новых версий нет · установлена '+u.version);
  });return;
 }
 if(action==='update-start'){
  if($('#dialog').open)close();
  await task('update_prepare',{},async()=>{
   modal('Обновление загружено','<p>AFTERPLAY закрывается для замены файлов. После установки окно откроется снова.</p>');
   try{await api('update_install')}catch(error){close();toast(error.message,true)}
  });return;
 }
};
