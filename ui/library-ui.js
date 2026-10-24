'use strict';
icons.list='<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>';
const libraryView=()=>state.settings.appearance?.library_view||'gallery';
const dateLabel=c=>new Date(c.mtime*1000).toLocaleString('ru-RU',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
const originalClipCard=clipCard;
clipCard=function(c){
 if(libraryView()!=='list')return originalClipCard(c);
 return `<article class="clip-card list-row" data-clip="${c.id}" tabindex="0" aria-label="Открыть ${esc(c.name)}"><div class="thumb"><img src="${base}thumb/${c.id}" loading="lazy" alt=""><div class="play-badge">${icon('play')}</div><span class="duration">${fmt(c.duration).replace(/^00:/,'')}</span></div><div class="clip-info"><div class="clip-name" title="${esc(c.name)}">${c.favorite?'★ ':''}${esc(c.name)}</div><div class="clip-meta">${esc(c.tags||'Без тегов')}</div></div><div class="list-details"><b>${fmt(c.duration)}</b><small>${c.width} × ${c.height}</small></div><div class="list-details"><b>${size(c.size)}</b><small>${esc(dateLabel(c))}</small></div><button class="icon-button" title="Удалить видео в корзину" aria-label="Удалить ${esc(c.name)}" data-action="delete-video" data-id="${c.id}">${icon('trash')}</button></article>`;
};
const beforeViewPage=clipsPage;
clipsPage=function(){
 let html=beforeViewPage();
 if(!['library','favorites'].includes(tab))return html;
 const view=libraryView();
 const switcher=`<div class="view-switch" role="group" aria-label="Вид библиотеки"><button class="icon-button ${view==='gallery'?'selected':''}" data-action="view-gallery" title="Галерея" aria-label="Галерея" aria-pressed="${view==='gallery'}">${icon('grid')}</button><button class="icon-button ${view==='list'?'selected':''}" data-action="view-list" title="Список" aria-label="Список" aria-pressed="${view==='list'}">${icon('list')}</button></div>`;
 html=html.replace('<span class="pill gold">',switcher+'<span class="pill gold">');
 if(view==='list')html=html.replace('class="clip-grid"','class="clip-grid list-view"');
 return html;
};
const beforeLibraryAction=action;
action=async function(a,el){
 if(a==='view-gallery'||a==='view-list'){
  const view=a.slice(5);const result=await api('appearance_config',{library_view:view});
  state.settings.appearance=result;render();return;
 }
 if(a==='storage-browse'){
  const result=await api('browse',{purpose:'recordings'});if(result.path)$('#recordingsPath').value=result.path;return;
 }
 if(a==='storage-save'||a==='storage-reset'){
  const path=a==='storage-reset'?'':$('#recordingsPath').value;
  const saved=await api('storage_config',{recordings_dir:path});state.storage=saved;
  await refresh();toast('Папка для новых записей сохранена');return;
 }
 return beforeLibraryAction(a,el);
};
const beforeStorageSettings=window.renderDesktopExtras;
window.renderDesktopExtras=function(){
 beforeStorageSettings?.();
 if(tab!=='settings'||$('#recordingsPath'))return;
 $('.settings-panel')?.insertAdjacentHTML('afterbegin',`<section class="settings-card wide storage-card"><span class="eyebrow">ТВОИ ВИДЕО — В ТВОЕЙ ПАПКЕ</span><h2>Место сохранения записей</h2><div class="field"><label for="recordingsPath">Папка для MP4 и GIF</label><div class="field-line"><input id="recordingsPath" value="${esc(state.storage?.recordings_dir||'')}" placeholder="Например, D:\\Игровые записи">${button('storage-browse','Выбрать','folder')}</div><small>Папка используется для повторов, обрезанных клипов и временного буфера. Существующие файлы сохраняют свои пути и доступны в библиотеке.</small></div><div class="actions">${button('storage-save','Сохранить папку','check','primary')}${button('storage-reset','По умолчанию','refresh','quiet')}${button('open-exports','Открыть папку','folder','secondary')}</div><p class="hint">Изменение доступно после остановки записи и завершения экспорта. Буфер: ${esc(state.storage?.buffer_dir||'')}</p></section>`);
};
