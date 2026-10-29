'use strict';
// Local Onyx Cinema layout. Capture, editing and storage use the existing API.
(()=>{
 customDefaults.cinema_layout=true;
 const paletteKeys=['cinema_accent','cinema_background','cinema_panel','cinema_text','cinema_muted'];
 const palettes={
  cinema:{name:'Cinema',description:['Лавандовый · как на макете','Lavender · reference palette'],values:['#a58bff','#0d1018','#151a26','#f3f1fc','#b0b4c8']},
  onyx:{name:'Onyx',description:['Мята и чёрный графит','Mint and graphite'],values:['#80f7bd','#0c1114','#151c20','#f1f7f4','#acbab6']},
  ocean:{name:'Ocean',description:['Сапфир и ледяной синий','Sapphire and ice blue'],values:['#79c7ff','#0a111c','#121e2d','#edf6ff','#a8bdd1']},
  ember:{name:'Ember',description:['Янтарь и тёплый графит','Amber and warm graphite'],values:['#ffc17d','#15100f','#241c1b','#fff4e8','#c9b7aa']},
  rose:{name:'Rose',description:['Розовый кварц и тёмная слива','Rose quartz and dark plum'],values:['#f39bc5','#140e18','#221827','#fff0fa','#c6b0c6']}
 };
 Object.assign(customDefaults,Object.fromEntries(paletteKeys.map((key,i)=>[key,palettes.cinema.values[i]])),{cinema_palette:'cinema',cinema_sidebar:'banner'});
 const artwork=[['banner','Рыцарь со знаменем','Banner knight'],['ranger','Изумрудный лес','Emerald forest'],['citadel','Лунная цитадель','Moonlit citadel'],['ember','Пепельное знамя','Ember standard']];
 const mediaInfo=new Map(),favoritePending=new Set();
 const strokes={heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',scissors:'<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m8.1 8.1 12.4 12.4M14 10l6.5-6.5M8.1 15.9 11 13"/>',calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18M8 15h.01"/>',more:'<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>',frame:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m8 10 4 4-4 4M14 10h3"/>',image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m21 15-5-5L5 21"/>',record:'<circle cx="12" cy="12" r="9"/>',save:'<path d="M20 8a8 8 0 1 0 0 8M20 3v6h-6"/>',play:'<path d="m8 5 11 7-11 7Z" fill="currentColor" stroke="none"/>'};
 const cIcon=name=>strokes[name]?`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${strokes[name]}</svg>`:icon(name);
 let focusedId='',gameFilter='',order='newest',limit=36,shellSignature='',lastTab=tab;
 const t=(ru,en)=>state.settings.language==='en'?en:ru;
 const enabled=()=>customSettings().cinema_layout!==false;
 const clipsTab=()=>['library','favorites'].includes(tab);
 const gameOf=c=>state.settings.clip_games?.[c.id]||'';
 const nameOf=c=>{const full=c.name.replace(/\.(mp4|mkv|mov|avi|webm|gif)$/i,'').replace(/\.DVR$/i,'');return full.replace(/[-_ ]20\d{2}[-_]?\d{2}[-_]?\d{2}[-_ ]\d{2}[-_]?\d{2}[-_]?\d{2}(?:[-_][a-f\d]{4,16})?$/i,'')||full};
 const coverOf=c=>base+'thumb/'+encodeURIComponent(c.id)+(state.settings.clip_covers?.[c.id]?'?cover='+encodeURIComponent(state.settings.clip_covers[c.id].version):'');
 const tagsOf=c=>String(c.tags||'').split(',').map(s=>s.trim()).filter(Boolean);
 const dateOf=c=>{const date=new Date(c.mtime*1000),today=new Date(),yesterday=new Date();yesterday.setDate(today.getDate()-1);const day=date.toDateString()===today.toDateString()?t('Сегодня','Today'):date.toDateString()===yesterday.toDateString()?t('Вчера','Yesterday'):date.toLocaleDateString(window.i18nLocale?.()||'ru-RU',{day:'numeric',month:'short'});return day+', '+date.toLocaleTimeString(window.i18nLocale?.()||'ru-RU',{hour:'2-digit',minute:'2-digit'})};
 const ownButton=(a,label,ico='play',kind='secondary',extra='')=>`<button class="${kind}" data-action="${a}" ${extra}>${cIcon(ico)}${esc(label)}</button>`;
 function applyDesign(){
  const c=customSettings();if(!enabled())return;
  const values=c.cinema_palette==='custom'?paletteKeys.map((key,i)=>c[key]||palettes.cinema.values[i]):(palettes[c.cinema_palette]||palettes.cinema).values;
  const body=document.body;['accent','background','panel','text','muted'].forEach((key,i)=>body.style.setProperty('--cinema-'+key,values[i]));
  const rgb=values[0].slice(1).match(/../g).map(v=>parseInt(v,16)).join(',');
  body.style.setProperty('--accent',values[0],'important');body.style.setProperty('--accent-rgb',rgb,'important');
  const channels=rgb.split(',').map(v=>{const n=Number(v)/255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4});
  body.style.setProperty('--cinema-on-accent',channels[0]*.2126+channels[1]*.7152+channels[2]*.0722>.27?'#101322':'#ffffff');
 }
 const beforeDesignApply=customApply;customApply=function(){beforeDesignApply();applyDesign()};
 function filtered(){
  const query=search.trim().toLocaleLowerCase();
  const rows=state.clips.filter(c=>(tab!=='favorites'||c.favorite)&&(!tagFilter||tagsOf(c).includes(tagFilter))&&(!gameFilter||gameOf(c)===gameFilter)&&(!query||[c.name,c.tags,c.note,gameOf(c)].join(' ').toLocaleLowerCase().includes(query)));
  const sorts={newest:(a,b)=>b.mtime-a.mtime,oldest:(a,b)=>a.mtime-b.mtime,name:(a,b)=>a.name.localeCompare(b.name,window.i18nLocale?.()||'ru'),duration:(a,b)=>b.duration-a.duration};
  return rows.sort(sorts[order]||sorts.newest);
 }
 function focusClip(rows=filtered()){return rows.find(c=>c.id===focusedId)||rows[0]||null}
 function favoriteButton(c){return `<button type="button" class="cinema-favorite ${c.favorite?'is-favorite':''}" data-action="cinema-favorite" data-id="${esc(c.id)}" aria-pressed="${!!c.favorite}" title="${t(c.favorite?'Убрать из избранного':'В избранное',c.favorite?'Remove from favorites':'Add to favorites')}" aria-label="${t(c.favorite?'Убрать из избранного':'В избранное',c.favorite?'Remove from favorites':'Add to favorites')}">${cIcon('heart')}</button>`}
 function card(c,current){
  const view=libraryView()==='list';
  return `<article class="clip-card cinema-card ${view?'cinema-list-row':''} ${c.id===current?.id?'is-selected':''}" data-clip="${esc(c.id)}" tabindex="0" role="button" aria-label="${esc(t('Выбрать запись: ','Select recording: ')+nameOf(c))}" aria-pressed="${c.id===current?.id}"><div class="thumb"><img src="${esc(coverOf(c))}" loading="lazy" alt="${esc(nameOf(c))}">${favoriteButton(c)}<button class="cinema-card-play" data-action="cinema-watch" data-id="${esc(c.id)}" title="${t('Смотреть','Watch')}" aria-label="${esc(t('Смотреть: ','Watch: ')+nameOf(c))}">${cIcon('play')}</button><span class="duration">${esc(fmt(c.duration))}</span></div><div class="clip-info"><div class="cinema-card-heading"><div class="clip-name" title="${esc(c.name)}" data-i18n-ignore>${esc(nameOf(c))}</div><button class="cinema-more-button" data-action="cinema-notes" data-id="${esc(c.id)}" aria-label="${t('Теги и заметки','Tags and notes')}" title="${t('Теги и заметки','Tags and notes')}">${cIcon('more')}</button></div><div class="cinema-card-meta"><span data-i18n-ignore>${esc(gameOf(c)||t('Локальная запись','Local recording'))}</span><i>·</i><span>${esc(dateOf(c))}</span></div>${c.tags?`<div class="clip-tags">${tagsOf(c).slice(0,3).map(tag=>`<span data-i18n-ignore>${esc(tag)}</span>`).join('')}</div>`:''}</div>${view?`<div class="cinema-list-detail">${esc(fmt(c.duration))}<small>${c.width?esc(c.width+' × '+c.height):'—'}</small></div><div class="cinema-list-detail">${esc(size(c.size))}<small>${esc(dateOf(c))}</small></div>`:''}${libraryDeleteButton(c)}</article>`;
 }
 function hero(c){
  if(!c)return `<section class="cinema-hero cinema-no-selection page-head"><div class="cinema-hero-copy"><span class="cinema-eyebrow">AFTERPLAY · ONYX CINEMA</span><h1>${esc(t(state.clips.length?'Найдём нужный момент':'Твои лучшие моменты',state.clips.length?'Find your moment':'Your best moments'))}</h1><p>${esc(t(state.clips.length?'Измени поиск или фильтры, чтобы увидеть записи.':'Подключи папку с видео — здесь появится твоя библиотека.',state.clips.length?'Change search or filters to see recordings.':'Connect a video folder to build your library.'))}</p>${ownButton(state.clips.length?'cinema-clear':'video-settings',t(state.clips.length?'Сбросить фильтры':'Подключить папку',state.clips.length?'Clear filters':'Connect a folder'),'folder','primary')}</div></section>`;
  return `<section class="cinema-hero page-head" aria-label="${t('Выбранная запись','Selected recording')}"><img class="cinema-art" src="${esc(coverOf(c))}" alt=""><div class="cinema-hero-shade"></div><div class="cinema-hero-copy"><span class="cinema-eyebrow" data-i18n-ignore>${esc(gameOf(c)||t('ВЫБРАННАЯ ЗАПИСЬ','SELECTED RECORDING'))}</span><h1 title="${esc(c.name)}" data-i18n-ignore>${esc(nameOf(c))}</h1><div class="cinema-hero-meta"><span>${icon('clock')}${esc(fmt(c.duration).replace(/^00:/,''))}</span><span>${cIcon('calendar')}${esc(dateOf(c))}</span></div><div class="actions">${ownButton('cinema-watch',t('Смотреть','Watch'),'play','primary',`data-id="${esc(c.id)}"`)}${ownButton('cinema-trim',t(/\.gif$/i.test(c.name)?'Открыть':'Обрезать',/\.gif$/i.test(c.name)?'Open':'Trim'),'scissors','secondary',`data-id="${esc(c.id)}"`)}</div></div></section>`;
 }
 function details(c){
  if(!c)return `<aside class="cinema-inspector"><h2>${t('О записи','Recording details')}</h2><div class="cinema-detail-empty">${icon('film')}<p>${t('Выбери запись, чтобы увидеть сведения и быстрые действия.','Select a recording to see details and quick actions.')}</p></div></aside>`;
  const detail=(ico,label,value,extra='')=>`<div class="cinema-detail">${cIcon(ico)}<dt>${esc(label)}</dt><dd ${extra}>${esc(value)}</dd></div>`;
  const fps=mediaInfo.get(c.id)?.fps;
  return `<aside class="cinema-inspector" aria-label="${t('О записи','Recording details')}"><h2>${t('О записи','Recording details')}</h2><div class="cinema-detail-title"><h3 title="${esc(c.name)}" data-i18n-ignore>${esc(nameOf(c))}</h3><div class="cinema-title-tools">${favoriteButton(c)}<button class="cinema-more-button" data-action="cinema-notes" data-id="${esc(c.id)}" aria-label="${t('Теги и заметки','Tags and notes')}">${cIcon('more')}</button></div></div>${gameOf(c)?`<div class="cinema-detail-game" data-i18n-ignore>${esc(gameOf(c))}</div>`:''}<div class="clip-tags cinema-detail-tags">${tagsOf(c).map(tag=>`<button data-tag="${esc(tag)}">${esc(tag)}</button>`).join('')}</div><dl>${detail('calendar',t('Дата записи','Recorded'),dateOf(c))}${detail('clock',t('Длительность','Duration'),fmt(c.duration))}${detail('file',t('Размер файла','File size'),size(c.size))}${detail('image',t('Разрешение','Resolution'),c.width?c.width+' × '+c.height:t('Нет данных','Not available'))}${detail('frame',t('Частота кадров','Frame rate'),fps?Math.round(fps*100)/100+' FPS':'—',`id="cinemaFps" data-id="${esc(c.id)}"`)}<div class="cinema-detail cinema-location">${icon('folder')}<dt>${t('Расположение','Location')}</dt><dd title="${esc(c.path)}" data-i18n-ignore>${esc(c.path)}</dd></div></dl>${c.note?`<p class="cinema-note" data-i18n-ignore>${esc(c.note)}</p>`:''}${c.error?`<p class="hint error-text" data-i18n-ignore>${esc(c.error)}</p>`:''}<div class="cinema-inspector-actions">${ownButton('cinema-export',t('Экспорт','Export'),'download','cinema-export secondary',`data-id="${esc(c.id)}"`)}${ownButton('cinema-folder',t('Открыть папку','Open folder'),'folder','secondary',`data-id="${esc(c.id)}"`)}</div></aside>`;
 }
 function loadDetails(c){
  if(!c||mediaInfo.has(c.id))return;
  mediaInfo.set(c.id,{});
  api('clip_media_info',{id:c.id}).then(info=>{mediaInfo.set(c.id,info);const el=$('#cinemaFps');if(el?.dataset.id===c.id&&info.fps)el.textContent=Math.round(info.fps*100)/100+' FPS'}).catch(()=>mediaInfo.delete(c.id));
  if(mediaInfo.size>100)mediaInfo.delete(mediaInfo.keys().next().value);
 }
 function library(){
  const rows=filtered(),current=focusClip(rows);focusedId=current?.id||'';
  const games=[...new Set(state.clips.map(gameOf).filter(Boolean))].sort();
  return `<div class="cinema-layout"><div class="cinema-library"><div id="cinemaHero">${hero(current)}</div><div class="cinema-library-toolbar"><div class="cinema-library-heading"><h2>${esc(tab==='favorites'?t('Избранное','Favorites'):tagFilter?t('Тег: ','Tag: ')+tagFilter:search?t('Результаты поиска','Search results'):t('Последние записи','Recent recordings'))}</h2><span>${rows.length} ${t('записей','recordings')}</span></div><div class="cinema-filters"><div class="view-switch" role="group" aria-label="${t('Вид библиотеки','Library view')}"><button class="icon-button ${libraryView()==='gallery'?'selected':''}" data-action="view-gallery" aria-label="${t('Галерея','Gallery')}" title="${t('Галерея','Gallery')}" aria-pressed="${libraryView()==='gallery'}">${icon('grid')}</button><button class="icon-button ${libraryView()==='list'?'selected':''}" data-action="view-list" aria-label="${t('Список','List')}" title="${t('Список','List')}" aria-pressed="${libraryView()==='list'}">${icon('list')}</button></div><select id="cinemaGame" aria-label="${t('Фильтр по игре','Game filter')}"><option value="">${t('Все игры','All games')}</option>${games.map(game=>`<option value="${esc(game)}" ${gameFilter===game?'selected':''}>${esc(game)}</option>`).join('')}</select><select id="cinemaSort" aria-label="${t('Сортировка','Sort order')}">${[['newest',t('Сначала новые','Newest first')],['oldest',t('Сначала старые','Oldest first')],['name',t('По названию','By name')],['duration',t('По длительности','By duration')]].map(([id,label])=>`<option value="${id}" ${order===id?'selected':''}>${label}</option>`).join('')}</select>${tagFilter||search||gameFilter?ownButton('cinema-clear',t('Сбросить','Clear'),'close','quiet'):''}</div></div><div id="cinemaGrid" class="clip-grid cinema-grid ${libraryView()==='list'?'cinema-list':''}">${rows.slice(0,limit).map(c=>card(c,current)).join('')}</div>${!rows.length?`<div class="cinema-empty"><p>${t('Записей не найдено','No recordings found')}</p>${ownButton('cinema-clear',t('Сбросить фильтры','Clear filters'),'refresh','quiet')}</div>`:''}${rows.length>limit?`<div class="cinema-more">${ownButton('cinema-more',t('Показать ещё','Show more'),'plus','secondary')}<span>${Math.min(limit,rows.length)} / ${rows.length}</span></div>`:''}<div class="cinema-library-footer"><span>${esc(size(state.clips.reduce((sum,c)=>sum+c.size,0)))} · ${t('в исходных папках','in source folders')}</span>${ownButton('video-settings',t('Папки','Folders'),'folder','quiet')}${ownButton('scan',t('Обновить библиотеку','Refresh library'),'refresh','quiet')}</div></div><div id="cinemaInspector">${details(current)}</div></div>`;
 }
 function updateSelection(id){
  const rows=filtered(),c=rows.find(row=>row.id===id);if(!c)return;focusedId=id;
  releaseHero();$('#cinemaHero').innerHTML=hero(c);$('#cinemaInspector').innerHTML=details(c);sharpenHero(c);loadDetails(c);
  document.querySelectorAll('#cinemaGrid .clip-card').forEach(el=>{const match=el.dataset.clip===id;el.classList.toggle('is-selected',match);el.setAttribute('aria-pressed',String(match))});
 }
 function releaseHero(){const video=$('#cinemaHero video');if(video){video.pause();video.removeAttribute('src');video.load()}}
 function sharpenHero(c){
  if(!c||/\.gif$/i.test(c.name)||['starting','recording','stopping'].includes(state.replay?.phase)||state.jobs.some(j=>j.status==='running'))return;
  const stage=$('#cinemaHero .cinema-hero');if(!stage||stage.querySelector('video'))return;
  const video=document.createElement('video');video.className='cinema-art cinema-highres';video.muted=true;video.defaultMuted=true;video.playsInline=true;video.preload='metadata';
  video.addEventListener('loadedmetadata',()=>{const position=state.settings.clip_covers?.[c.id]?.time??Math.min(3,(c.duration||0)*.12);if(Number.isFinite(video.duration)&&video.duration>0)video.currentTime=Math.min(position,Math.max(0,video.duration-.05))},{once:true});
  video.addEventListener('seeked',()=>video.classList.add('is-ready'),{once:true});
  video.addEventListener('error',()=>video.remove(),{once:true});
  video.src=base+'media/'+encodeURIComponent(c.id);stage.prepend(video);
 }
 function controls(){
  const r=state.replay||{},busy=['starting','stopping'].includes(r.phase)||r.saving||r.finishing,manual=r.continuous||r.pending_recording;
  const saveKey=state.settings.hotkeys?.save,recordKey=state.settings.hotkeys?.record;
  return `<button class="cinema-save secondary" data-action="replay-save" ${r.phase!=='recording'||busy?'disabled':''}>${cIcon('save')}<span>${t('Сохранить повтор','Save replay')}</span>${saveKey?`<kbd>${esc(saveKey)}</kbd>`:''}</button><button class="secondary cinema-record ${manual?'is-recording':''}" data-action="${manual?'replay-record-stop':'replay-record-start'}" ${busy?'disabled':''}>${cIcon(manual?'close':'record')}<span>${t(manual?'Остановить запись':'Начать запись',manual?'Stop recording':'Start recording')}</span>${recordKey?`<kbd>${esc(recordKey)}</kbd>`:''}</button><button class="icon-button cinema-replay-toggle" data-action="${r.replay_enabled?'replay-stop':'replay-start'}" title="${t(r.replay_enabled?'Отключить повтор':'Включить повтор',r.replay_enabled?'Disable replay':'Enable replay')}" aria-label="${t(r.replay_enabled?'Отключить повтор':'Включить повтор',r.replay_enabled?'Disable replay':'Enable replay')}" aria-pressed="${!!r.replay_enabled}" ${busy?'disabled':''}>${icon('clock')}</button>`;
 }
 function status(){
  const r=state.replay||{},active=['recording','starting'].includes(r.phase),waiting=!active&&state.settings.auto_record?.enabled;
  const label=r.saving?t('Сохранение…','Saving…'):active?captureStatus(r):waiting?t('Ожидает игру','Waiting for a game'):t('Запись выключена','Recording is off');
  const el=$('#cinemaStatus');if(!el)return;
  el.classList.toggle('is-active',active);$('#cinemaStatusLabel').textContent=label;
  $('#cinemaStatusDetail').textContent=active?captureDetail(r):state.clips.length+' '+t('записей в библиотеке','recordings in library');
  $('#cinemaStorage').textContent=size(state.clips.reduce((sum,c)=>sum+c.size,0))+' · '+t('локально','local');
 }
 function profileBadge(){
  let badge=$('#cinemaProfile');
  if(!badge){badge=document.createElement('button');badge.id='cinemaProfile';badge.className='cinema-profile';badge.dataset.tab='replay';badge.innerHTML=icon('film')+'<span><small></small><b></b></span>';$('.header-right')?.prepend(badge)}
  const key=value=>String(value||'').replaceAll('/','\\').toLowerCase();
  const rows=Object.values(state.settings.capture_profiles||{}),selected=rows.find(p=>key(p.id||p.path)===key(state.settings.selected_capture_profile));
  const automatic=!!state.auto_record?.active&&['starting','recording','stopping'].includes(state.replay?.phase);
  const name=(automatic?state.replay?.active_profile:selected?.name)||state.replay?.active_profile||t('Не выбран','Not selected');
  const label=automatic?t('Автозапись','Automatic'):t('Профиль','Profile');
  badge.querySelector('small').textContent=label;badge.querySelector('b').textContent=name;badge.title=label+': '+name;badge.setAttribute('aria-label',label+': '+name);
 }
 function toggleCard(){
  const c=customSettings();
  const layout=`<div class="field cinema-layout-select"><label for="cinemaLayout">${t('Интерфейс','Interface')}</label><select id="cinemaLayout"><option value="true" ${enabled()?'selected':''}>Onyx Cinema</option><option value="false" ${!enabled()?'selected':''}>${t('Классический','Classic')}</option></select></div>`;
  if(tab!=='customize'||!enabled())return `<section class="cinema-layout-choice settings-card"><div><span class="cinema-eyebrow">ONYX × CINEMA</span><h2>${t('Дизайн приложения','Application design')}</h2><p>${t('Цветовые палитры и рисунки бокового меню находятся в разделе «Оформление».','Find color palettes and sidebar artwork in Appearance.')}</p></div>${layout}</section>`;
  const labels=[['Акцент','Accent'],['Фон','Background'],['Панели','Panels'],['Текст','Text'],['Вторичный текст','Secondary text']];
  return `<section class="cinema-design-panel settings-card"><div class="cinema-design-heading"><div><span class="cinema-eyebrow">ONYX × CINEMA</span><h2>${t('Оформление','Appearance')}</h2><p>${t('Цвета, иллюстрации и анимации интерфейса.','Colors, artwork and interface motion.')}</p></div>${layout}</div><div class="cinema-design-label"><h3>${t('Цветовая палитра','Color palette')}</h3><span id="cinemaPaletteLabel">${c.cinema_palette==='custom'?t('Свои цвета','Custom colors'):(palettes[c.cinema_palette]||palettes.cinema).name}</span></div><div class="cinema-palette-grid">${Object.entries(palettes).map(([id,p])=>`<button class="cinema-palette-card ${c.cinema_palette===id?'selected':''}" data-action="cinema-palette" data-value="${id}" aria-pressed="${c.cinema_palette===id}" style="--swatch-bg:${p.values[1]};--swatch-accent:${p.values[0]};--swatch-panel:${p.values[2]}"><span class="cinema-palette-preview"><i></i><b></b><em></em><em></em></span><strong>${p.name}</strong><small>${t(...p.description)}</small></button>`).join('')}</div><div class="cinema-color-grid">${paletteKeys.map((key,i)=>customField(t(...labels[i]),key,'color')).join('')}</div><div class="cinema-design-label"><h3>${t('Рисунок в боковом меню','Sidebar artwork')}</h3><button class="quiet ${c.cinema_sidebar==='none'?'selected':''}" data-action="cinema-art" data-value="none">${t('Без рисунка','No artwork')}</button></div><div class="cinema-art-grid">${artwork.map(([id,ru,en])=>`<button class="cinema-art-choice ${c.cinema_sidebar===id?'selected':''}" data-action="cinema-art" data-value="${id}" aria-pressed="${c.cinema_sidebar===id}"><img src="${base}backgrounds/onyx-art-${id}.png" alt=""><span>${t(ru,en)}</span>${c.cinema_sidebar===id?icon('check'):''}</button>`).join('')}</div><div class="cinema-design-save"><p>${t('Изменения видны сразу. Сохрани понравившийся результат.','Changes are previewed instantly. Save the result you like.')}</p>${ownButton('custom-save',t('Сохранить оформление','Save appearance'),'check','primary')}</div></section>`;
 }
 function sync(){
  const on=enabled();document.body.classList.toggle('onyx-cinema',on);document.body.dataset.cinemaLibrary=String(on&&clipsTab());
  if(on&&typeof customMedia!=='undefined'&&customMedia)customMedia.pause();
  if(!on){$('#cinemaTopbar')?.remove();$('#cinemaStatus')?.remove();$('#cinemaSidebarArt')?.remove();$('#cinemaProfile')?.remove();shellSignature='';return}
  applyDesign();
  let art=$('#cinemaSidebarArt');if(!art){art=document.createElement('div');art.id='cinemaSidebarArt';art.setAttribute('aria-hidden','true');art.innerHTML='<img alt="">';$('.sidebar').prepend(art)}
  const chosen=customSettings().cinema_sidebar||'banner';art.hidden=chosen==='none';document.body.dataset.cinemaArt=chosen;if(chosen!=='none'&&art.dataset.choice!==chosen){art.dataset.choice=chosen;art.querySelector('img').src=base+'backgrounds/onyx-art-'+chosen+'.png'}
  let bar=$('#cinemaTopbar');
  if(!bar){bar=document.createElement('div');bar.id='cinemaTopbar';bar.innerHTML=`<div class="cinema-search">${icon('search')}<input id="searchInput" type="search" autocomplete="off"></div><div class="cinema-section"></div><div id="cinemaCapture"></div>`;document.querySelector('.workspace>header').prepend(bar)}
  const input=bar.querySelector('input');input.placeholder=t('Поиск записей…','Search recordings…');input.setAttribute('aria-label',t('Поиск записей','Search recordings'));if(document.activeElement!==input)input.value=search;
  bar.querySelector('.cinema-search').hidden=!clipsTab();bar.querySelector('.cinema-section').hidden=clipsTab();bar.querySelector('.cinema-section').textContent=$('#breadcrumb')?.textContent?.replace(/^AFTERPLAY\s*\/?\s*/,'')||'';
  const r=state.replay||{},signature=JSON.stringify([r.phase,r.continuous,r.replay_enabled,r.saving,r.finishing,r.pending_recording,state.settings.hotkeys,state.settings.language]);
  if(signature!==shellSignature){$('#cinemaCapture').innerHTML=controls();shellSignature=signature}
  if(!$('#cinemaStatus'))$('.side-bottom')?.insertAdjacentHTML('afterbegin','<section id="cinemaStatus"><div class="cinema-status-line"><span class="cinema-status-dot"></span><b id="cinemaStatusLabel"></b></div><p id="cinemaStatusDetail"></p><small id="cinemaStorage"></small></section>');
  const replayToggle=$('#cinemaCapture .cinema-replay-toggle');if(replayToggle&&$('#cinemaStatus')){$('#cinemaStatus>.cinema-replay-toggle')?.remove();$('#cinemaStatus').append(replayToggle)}
  const nav=$('#nav [data-tab="library"] .custom-nav-text');if(nav)nav.textContent=t('Все записи','All recordings');
  const replayNav=$('#nav [data-tab="replay"] .custom-nav-text');if(replayNav)replayNav.textContent=t('Повторы','Replays');
  const favoriteNav=$('#nav [data-tab="favorites"] svg');if(favoriteNav)favoriteNav.innerHTML=strokes.heart;
  const settingsNav=$('#nav [data-tab="settings"] svg');if(settingsNav)settingsNav.innerHTML='<path d="M19.021 9.092L21.808 10.049L21.808 13.951L19.021 14.908L19.021 14.908L20.315 17.556L17.556 20.315L14.908 19.021L14.908 19.021L13.951 21.808L10.049 21.808L9.092 19.021L9.092 19.021L6.444 20.315L3.685 17.556L4.979 14.908L4.979 14.908L2.192 13.951L2.192 10.049L4.979 9.092L4.979 9.092L3.685 6.444L6.444 3.685L9.092 4.979L9.092 4.979L10.049 2.192L13.951 2.192L14.908 4.979L14.908 4.979L17.556 3.685L20.315 6.444L19.021 9.092Z"/><circle cx="12" cy="12" r="3.2"/>';
  status();profileBadge();
 }
 const oldPage=clipsPage;clipsPage=function(){return enabled()&&clipsTab()?library():oldPage()};
 const oldRender=render;render=function(){
  const pageChanged=lastTab!==tab;lastTab=tab;
  releaseHero();document.body.classList.toggle('onyx-cinema',enabled());oldRender();sync();if(enabled()&&clipsTab()){sharpenHero(focusClip());loadDetails(focusClip())}
  if(pageChanged&&!restoringRoute)scrollTo({top:0,behavior:'instant'});
  if(['customize','settings'].includes(tab)&&!$('#cinemaLayout')){
   if(tab==='customize')$('.custom-theme-grid')?.insertAdjacentHTML('beforebegin',toggleCard());else $('.settings-panel')?.insertAdjacentHTML('afterbegin',toggleCard());
  }
 };
 const oldPreferences=window.updatePreferences;window.updatePreferences=function(){oldPreferences?.();sync()};
 const oldAction=action;
 action=async function(name,el){
  if(!name.startsWith('cinema-'))return oldAction(name,el);
  if(name==='cinema-palette'||name==='cinema-art'){
   if(!customDraft)customDraft=structuredClone(customSettings());
   if(name==='cinema-art')customDraft.cinema_sidebar=el.dataset.value;
   else{const palette=palettes[el.dataset.value];if(!palette)return;customDraft.cinema_palette=el.dataset.value;paletteKeys.forEach((key,i)=>customDraft[key]=palette.values[i])}
   customChanged();render();return;
  }
  const id=el.dataset.id,c=state.clips.find(row=>row.id===id);
  if(name==='cinema-more'){const y=scrollY;limit+=36;render();scrollTo({top:y,behavior:'instant'});return}
  if(name==='cinema-clear'){search='';gameFilter='';tagFilter='';limit=36;render();return}
  if(!c)return;
  if(name==='cinema-folder'){await api('open',{target:'clip-folder',id});return}
  if(name==='cinema-favorite'){
   if(favoritePending.has(id))return;favoritePending.add(id);el.disabled=true;try{const latest=await api('state'),fresh=latest.clips.find(row=>row.id===id);if(!fresh)return;await api('clip_save',{id,tags:fresh.tags,note:fresh.note,favorite:!fresh.favorite,marks:JSON.parse(fresh.marks||'[]')});state=await api('state');render()}finally{favoritePending.delete(id);if(el.isConnected)el.disabled=false}return;
  }
  openClip(id);
  if(name==='cinema-trim'||name==='cinema-export'||name==='cinema-notes'){
   if(typeof reviewSetMode==='function')reviewSetMode(true);
   if(typeof reviewSelectPane==='function')reviewSelectPane(name==='cinema-export'?'export':name==='cinema-notes'?'notes':'trim');
   else{const pane=document.querySelector(`[data-review-pane="${name==='cinema-export'?'export':name==='cinema-notes'?'notes':'trim'}"]`);pane?.click()}
  }
 };
 document.addEventListener('click',event=>{
  if(!enabled()||event.target.closest('button,a,input,select,textarea'))return;
  const item=event.target.closest('#cinemaGrid .clip-card');if(!item)return;
  event.preventDefault();event.stopImmediatePropagation();updateSelection(item.dataset.clip);
 },true);
 document.addEventListener('dblclick',event=>{const item=event.target.closest('#cinemaGrid .clip-card');if(enabled()&&item&&!event.target.closest('button')){event.preventDefault();openClip(item.dataset.clip)}});
 document.addEventListener('keydown',event=>{
  if(!enabled()||!event.target.matches('#cinemaGrid .clip-card'))return;
  if(event.key===' '||event.key==='Enter'){event.preventDefault();event.stopImmediatePropagation();if(event.key==='Enter')openClip(event.target.dataset.clip);else updateSelection(event.target.dataset.clip)}
 },true);
 document.addEventListener('input',event=>{
  if(!paletteKeys.includes(event.target.dataset.custom))return;
  if(!customDraft)customDraft=structuredClone(customSettings());customDraft.cinema_palette='custom';
  const label=$('#cinemaPaletteLabel');if(label)label.textContent=t('Свои цвета','Custom colors');
  document.querySelectorAll('.cinema-palette-card').forEach(el=>{el.classList.remove('selected');el.setAttribute('aria-pressed','false')});
 },true);
 document.addEventListener('change',async event=>{
  const el=event.target;
  if(el.id==='cinemaGame'){gameFilter=el.value;limit=36;render()}
  if(el.id==='cinemaSort'){order=el.value;limit=36;render()}
  if(el.id==='cinemaLayout'){
   const previous=enabled();el.disabled=true;
   try{const result=await api('customize_config',{cinema_layout:el.value==='true'});state.settings.customization=result;if(customDraft)customDraft.cinema_layout=result.cinema_layout;render();if(!enabled())customUpdatePause()}
   catch(error){el.value=String(previous);el.disabled=false;toast(error.message,true)}
  }
 });
 document.addEventListener('error',event=>{if(event.target.matches?.('.cinema-art,#cinemaGrid .thumb img')){event.target.style.opacity='0';event.target.parentElement?.classList.add('cinema-missing-image')}},true);
 // The initial API request may have finished before the deferred add-on loads.
 if(state.clips.length||Object.keys(state.settings).length)render();
})();
