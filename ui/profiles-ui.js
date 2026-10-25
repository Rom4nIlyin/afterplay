'use strict';
const profileId=p=>p?.id||p?.path||'';
const selectedProfile=()=>{
 const rows=studioProfiles();
 if(state.auto?.active&&state.replay?.active_profile){const automatic=rows.find(p=>p.name===state.replay.active_profile);if(automatic)return automatic}
 return rows.find(p=>profileId(p).toLowerCase()===String(state.settings.selected_capture_profile||'screen:default').toLowerCase())||rows[0];
};
function profilePanel(){
 const current=selectedProfile(),busy=studioBusy(),rows=studioProfiles();
 return `<section class="studio-profiles"><div class="field"><label for="captureProfile">Профиль записи</label><div class="studio-profile-row"><select id="captureProfile" ${busy?'disabled':''}>${rows.map(p=>`<option value="${esc(profileId(p))}" ${profileId(p)===profileId(current)?'selected':''}>${esc(p.name)}</option>`).join('')}</select>${button('profile-new','Новый профиль','plus','quiet',busy?'disabled':'')}${button('profile-delete','Удалить','trash','quiet',busy||profileId(current)==='screen:default'?'disabled':'')}</div><small>Выбери профиль — его параметры появятся ниже. Профиль по умолчанию записывает весь экран и звук устройства.</small></div><div class="studio-profile-meta"><div class="field"><label for="profileName">Название профиля</label><input id="profileName" value="${esc(current?.name||'')}" ${busy?'disabled':''}></div><div class="field"><label for="profilePath" id="profilePathLabel">Приложение .exe · необязательно для экрана</label><div class="field-line"><input id="profilePath" value="${esc(current?.path||'')}" placeholder="Для записи экрана можно оставить пустым" ${busy?'disabled':''}>${button('profile-browse','Выбрать','folder','quiet',busy?'disabled':'')}</div></div></div></section>`;
}
const beforeProfilesReplayPage=window.replayPage;
window.replayPage=function(){
 let markup=beforeProfilesReplayPage();
 markup=markup.replace('<div class="panel-title">ЗАХВАТ И КАЧЕСТВО</div>',`<div class="replay-config-head"><div><span class="eyebrow">ЗАПИСЬ ПО ПРОФИЛЮ</span><h2>Параметры профиля</h2></div><span class="pill" id="replayConfigStatus" role="status">Сохранено</span></div>${profilePanel()}<p class="hint">Все изменения ниже относятся к выбранному профилю. Сохрани их зелёной кнопкой внизу страницы.</p>`);
 markup=markup.replace('<span class="replay-hotkey">',button('live-mark','Отметить момент','plus','quiet',`id="liveMark" ${state.replay?.phase==='recording'?'':'disabled'}`)+'<span id="liveMarkCount" class="hint"></span><span class="replay-hotkey">');
 setTimeout(()=>{installChatSelector();updateProfileControls()},0);return markup;
};
window.updateProfileControls=function(){
 const badge=$('#replayConfigStatus');if(badge&&!badge.dataset.dirty)badge.textContent=studioBusy()?'Запись идёт · профиль заблокирован':'Сохранено';
 const field=$('#profilePath');if(field){const win=$('#replayCaptureMode').value==='window';field.required=win;$('#profilePathLabel').textContent=win?'Приложение .exe · обязательно для записи окна':'Приложение .exe · необязательно для экрана'}
};
window.saveSelectedProfile=async function(settings){
 const current=selectedProfile();if(!current)throw Error('Выбери профиль');
 const path=$('#profilePath').value.trim(),windowChoice=$('#replayWindow')?.selectedOptions[0];
 if(settings.capture_mode==='window'&&windowChoice?.dataset.path?.toLowerCase()!==path.toLowerCase())settings.window_hwnd=0;
 const value=await api('profile_configure',{id:profileId(current),name:$('#profileName').value,path,settings});
 const badge=$('#replayConfigStatus');if(badge){delete badge.dataset.dirty;badge.textContent='Сохранено'}
 return value;
};
document.addEventListener('input',e=>{
 if(!e.target.closest('.replay-config')||e.target.id==='captureProfile'||studioBusy())return;
 const badge=$('#replayConfigStatus');if(badge){badge.dataset.dirty='true';badge.textContent='Есть несохранённые изменения'}
});
document.addEventListener('change',async e=>{
 try{
  if(e.target.id==='captureProfile'){await api('profile_apply',{path:e.target.value});await refresh();toast('Профиль выбран');return}
  if(e.target.id==='replayCaptureMode')updateProfileControls();
  if(e.target.id==='replayWindow'){
   const path=e.target.selectedOptions[0]?.dataset.path;if(path)$('#profilePath').value=path;
  }
 }catch(error){toast(error.message,true)}
});
const beforeInlineProfileAction=action;
action=async function(name,element){
 if(name==='profile-new'){await api('profile_new');await refresh();$('#profileName').focus();$('#profileName').select();toast('Новый профиль создан · настрой параметры ниже');return}
 if(name==='profile-edit'){document.querySelector('.replay-config')?.scrollIntoView({behavior:'smooth'});$('#profileName').focus();return}
 if(name==='profile-browse'){const value=await api('browse',{purpose:'profile-app'});if(value.path){$('#profilePath').value=value.path;$('#profilePath').dispatchEvent(new Event('input',{bubbles:true}))}return}
 if(name==='profile-delete'){
  const current=selectedProfile();modal('Удалить профиль?',`<p>${esc(current.name)}</p><p class="hint">Записи сохраняются.</p>`,button('profile-delete-confirm','Удалить профиль','trash','danger',`data-path="${esc(profileId(current))}"`)+button('close','Отмена','close','quiet'));return;
 }
 if(name==='profile-delete-confirm'){await api('profile_remove',{path:element.dataset.path});close();await refresh();return}
 return beforeInlineProfileAction(name,element);
};
