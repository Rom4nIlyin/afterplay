'use strict';
window.addEventListener('error',event=>{(window.customErrors??=[]).push(event.message)});
window.addEventListener('unhandledrejection',event=>{(window.customErrors??=[]).push(String(event.reason))});
// All assets stay on the loopback server; one moving thumbnail is alive at a time.
icons.palette='<path d="M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1.4-3.4 1.5 1.5 0 0 1 1.1-2.6H17a4 4 0 0 0 4-4c0-4.4-4-8-9-8Z"/><circle cx="7" cy="10" r=".8"/><circle cx="10" cy="6.5" r=".8"/><circle cx="15" cy="7" r=".8"/><circle cx="17.5" cy="11" r=".8"/>';
const customDefaults={theme:'obsidian',accent:'#9ccfc9',background:'scene',scene:'smoke',asset:'',background_color:'#090c10',dim:62,blur:0,saturation:85,fit:'cover',speed:1,pause_recording:true,pause_export:true,motion:true,glow:true,animation:'calm',panel_opacity:94,colors_custom:false,panel_color:'#14181f',text_color:'#edf1f5',muted_color:'#a8b0bf',scale:100,card_size:270,card_ratio:'16/9',radius:14,card_date:true,card_game:false,card_size_label:true,card_duration:true,card_tags:true,hover_enabled:true,hover_delay:450,hover_sound:false,hover_speed:1,hover_mode:'play',nav_compact:false,nav_order:['library','replay','favorites','tags','exports','settings'],nav_hidden:[],pinned_tags:[],notice_position:'top-right',notice_size:100,notice_opacity:96,notice_duration:4.5,notice_cover:true,timer_color:'#ffffff',timer_background:65,timer_size:100,timer_font:'mono',timer_format:'milliseconds',timer_x:97.5,timer_y:2.5,editor_width:340,timeline_height:150,editor_start:'view',editor_tab:'trim',sounds:{enabled:false,pack:'soft',mark:{enabled:true,volume:30,asset:''},saving:{enabled:true,volume:30,asset:''},success:{enabled:true,volume:30,asset:''},error:{enabled:true,volume:30,asset:''}}};
const customThemeData={obsidian:['Obsidian','Глубокий чёрный','#090b0f','#9ccfc9'],glass:['Frosted Glass','Стекло и мягкий свет','#1d2536','#c5bdff'],aurora:['Aurora','Северное сияние','#0a1721','#76dccb'],ember:['Ember','Графит и тёплая медь','#19110f','#e6ac79'],mist:['Mist','Светлый туман и стальной','#e9eef3','#4b6c89'],paper:['Paper','Тёплая светлая','#f0eade','#875d40']};
let customDraft=null,customPane='background',customDirty=false,customBackgroundKey='',customMedia=null,customPaused=false,customSaveBusy=false;
const customSettings=()=>customDraft&&tab==='customize'?customDraft:{...structuredClone(customDefaults),...state.settings.customization,theme:state.settings.customization?.theme||state.settings.appearance?.theme||'obsidian'};
function customPath(object,path,value){const keys=path.split('.');let target=object;for(const key of keys.slice(0,-1))target=target[key];if(arguments.length===3)target[keys.at(-1)]=value;return target[keys.at(-1)]}
function customField(label,key,type='range',low=0,high=100,step=1){
 const value=customPath(customSettings(),key);
 if(type==='check')return `<label class="check custom-check"><input type="checkbox" data-custom="${key}" ${value?'checked':''}>${label}</label>`;
 if(type==='color')return `<label class="custom-color">${label}<input type="color" data-custom="${key}" value="${value}"><span>${value}</span></label>`;
 return `<div class="custom-field"><label>${label}<output data-custom-output="${key}">${value}</output></label><input aria-label="${label}" type="${type}" data-custom="${key}" min="${low}" max="${high}" step="${step}" value="${value}"></div>`;
}
function customSelect(label,key,options){return `<div class="field"><label>${label}</label><select data-custom="${key}" aria-label="${label}">${Object.entries(options).map(([value,text])=>`<option value="${value}" ${String(customPath(customSettings(),key))===value?'selected':''}>${text}</option>`).join('')}</select></div>`}
function customPanel(){
 const c=customSettings();
 if(customPane==='background')return `<div class="custom-section-head"><div><h2>Фон с характером</h2><p>Свои обои, короткое видео или GIF. Фоновое видео всегда без звука.</p></div>${button('custom-import-bg','Выбрать файл','folder','secondary')}</div><div class="custom-options">${[['none','Без фона'],['color','Свой цвет'],['scene','Живые сцены'],['asset','Мой файл']].map(([id,name])=>`<button class="custom-option ${c.background===id?'selected':''}" data-action="custom-background" data-value="${id}">${name}</button>`).join('')}</div><div class="custom-scenes">${[['smoke','Тихий дым'],['aurora','Северное сияние'],['ember','Тлеющие искры'],['video','Aurora · видео']].map(([id,name])=>`<button class="scene-swatch scene-${id} ${c.scene===id&&c.background==='scene'?'selected':''}" data-action="custom-scene" data-value="${id}"><span>${name}</span></button>`).join('')}</div><p class="hint">${c.asset?'Свой фон загружен · '+(c.asset.endsWith('.mp4')||c.asset.endsWith('.webm')?'видео':'изображение'):'Поддерживаются PNG, JPG, GIF, MP4 и WebM до 300 МБ. GIF преобразуется в видео до 30 секунд для управления паузой.'}</p><div class="custom-grid">${customField('Цвет фона','background_color','color')}${customSelect('Заполнение','fit',{cover:'Заполнить с обрезкой',contain:'Вписать целиком',fill:'Растянуть'})}${customField('Затемнение · %','dim')}${customField('Размытие · px','blur','range',0,35)}${customField('Насыщенность · %','saturation','range',0,200)}${customField('Скорость движения','speed','range',.25,2,.05)}</div><div class="custom-checks">${customField('Живой фон включён','motion','check')}${customField('Пауза фона во время записи','pause_recording','check')}${customField('Пауза фона во время экспорта','pause_export','check')}</div><p class="hint">При сворачивании окна фон автоматически останавливается. Отключённая анимация оставляет неподвижный кадр.</p>`;
 if(customPane==='interface')return `<h2>Интерфейс под тебя</h2><div class="custom-grid">${customField('Акцентный цвет','accent','color')}${customField('Использовать свои цвета панелей и текста','colors_custom','check')}${customField('Цвет панелей','panel_color','color')}${customField('Основной текст','text_color','color')}${customField('Вторичный текст','muted_color','color')}${customField('Плотность панелей · %','panel_opacity','range',65,100)}${customField('Масштаб интерфейса · %','scale','range',80,130,5)}${customField('Скругление · px','radius','range',0,28)}${customSelect('Анимации','animation',{off:'Выключены',calm:'Спокойные',normal:'Обычные'})}${customField('Подсветка кнопок за курсором','glow','check')}${customField('Боковая панель только с иконками','nav_compact','check')}</div><h3>Разделы боковой панели</h3><div class="custom-nav-order">${c.nav_order.map((id,i)=>`<div><label class="check"><input type="checkbox" data-nav-visible="${id}" ${!c.nav_hidden.includes(id)?'checked':''} ${id==='settings'?'disabled':''}>${{library:'Библиотека',replay:'Повтор',favorites:'Избранное',tags:'Теги',exports:'Экспорт',settings:'Настройки'}[id]}</label><button data-action="custom-nav-move" data-id="${id}" data-direction="-1" ${i===0?'disabled':''} aria-label="Поднять раздел">↑</button><button data-action="custom-nav-move" data-id="${id}" data-direction="1" ${i===5?'disabled':''} aria-label="Опустить раздел">↓</button></div>`).join('')}</div><div class="field"><label>Закреплённые теги через запятую</label><input data-custom="pinned_tags" value="${esc(c.pinned_tags.join(', '))}" placeholder="дуэли, осады, лучшее"></div>`;
 if(customPane==='library')return `<h2>Карточки и живые превью</h2><div class="custom-grid">${customField('Размер карточек · px','card_size','range',180,460,10)}${customSelect('Пропорции обложек','card_ratio',{'16/9':'Широкие · 16:9','4/3':'Классические · 4:3','1/1':'Квадратные · 1:1'})}${customField('Дата записи','card_date','check')}${customField('Название игры из профиля','card_game','check')}${customField('Размер файла','card_size_label','check')}${customField('Длительность на обложке','card_duration','check')}${customField('Теги под записью','card_tags','check')}</div><div class="split-line"></div><div class="custom-grid">${customField('Превью при наведении','hover_enabled','check')}${customField('Превью со звуком','hover_sound','check')}${customField('Задержка перед запуском · мс','hover_delay','range',0,2000,50)}${customField('Скорость превью','hover_speed','range',.25,2,.05)}${customSelect('Как смотреть превью','hover_mode',{play:'Автоматическое воспроизведение',scrub:'Перемотка движением мыши'})}</div><p class="hint">Одновременно воспроизводится только одна карточка. Любой кадр открытой записи можно назначить обложкой.</p>`;
 if(customPane==='sound')return `<h2>Звуки AFTERPLAY</h2><p>Сигналы работают и в трее. Для каждого события можно выбрать собственный звук.</p>${customField('Включить звуковые сигналы','sounds.enabled','check')}${customSelect('Звуковой набор','sounds.pack',{soft:'Soft · мягкие',digital:'Digital · электронные',chime:'Chime · колокольчики'})}<div class="custom-sound-list">${[['mark','Момент отмечен'],['saving','Сохранение началось'],['success','Файл готов'],['error','Ошибка']].map(([event,label])=>`<section>${customField(label,'sounds.'+event+'.enabled','check')}${customField('Громкость · %','sounds.'+event+'.volume')}<div class="actions"><button class="button secondary" data-action="custom-sound" data-event="${event}">Послушать</button><button class="button quiet" data-action="custom-import-sound" data-event="${event}">${c.sounds[event].asset?'Заменить свой звук':'Свой звук'}</button>${c.sounds[event].asset?`<button class="button quiet" data-action="custom-sound-default" data-event="${event}">Из набора</button>`:''}</div></section>`).join('')}</div><p class="hint">Свой звук: WAV, MP3, OGG или M4A; используются первые 10 секунд. «Послушать» работает и при отключённых сигналах.</p>`;
 if(customPane==='notice')return `<div class="custom-section-head"><div><h2>Уведомления поверх игры</h2><p>Без перехвата фокуса и мыши.</p></div>${button('custom-notice','Проверить','play','secondary')}</div><div class="custom-grid">${customSelect('Расположение','notice_position',{'top-right':'Справа сверху','top-left':'Слева сверху','bottom-right':'Справа снизу','bottom-left':'Слева снизу'})}${customField('Размер · %','notice_size','range',75,140,5)}${customField('Непрозрачность · %','notice_opacity','range',35,100)}${customField('Длительность · сек','notice_duration','range',1,15,.5)}${customField('Показывать обложку','notice_cover','check')}</div><div class="custom-notice-demo"><span>01 / LOOP</span><div><b>Повтор сохранён</b><small>00:30 · видео готово</small></div></div>`;
 if(customPane==='timer')return `<h2>Таймер в кадре</h2><p>Перетащи таймер в предпросмотре. Оформление применяется и к экспорту MP4 / GIF.</p><div class="custom-timer-demo" id="customTimerDemo"><span id="customTimerSample">00:12.350</span><small>Перетащи таймер мышью</small></div><div class="custom-grid">${customField('Цвет цифр','timer_color','color')}${customField('Непрозрачность подложки · %','timer_background')}${customField('Размер · %','timer_size','range',50,200,5)}${customSelect('Шрифт','timer_font',{mono:'Моноширинный',sans:'Inter'})}${customSelect('Формат','timer_format',{milliseconds:'00:12.350 · миллисекунды',seconds:'00:12 · секунды',frames:'Кадр 741 · номер кадра'})}${customField('Положение по горизонтали · %','timer_x','range',0,100,.5)}${customField('Положение по вертикали · %','timer_y','range',0,100,.5)}</div>`;
 if(customPane==='workspace')return `<h2>Рабочее пространство</h2><p>Свой размер панелей и стартовый режим для просмотра записей.</p><div class="custom-grid">${customField('Ширина панели инструментов · px','editor_width','range',270,550,10)}${customField('Высота дорожки · px','timeline_height','range',90,300,10)}${customSelect('При открытии записи','editor_start',{view:'Обычный просмотр',edit:'Сразу монтаж'})}${customSelect('Первая вкладка монтажа','editor_tab',{trim:'Обрезка',sound:'Звук',export:'Экспорт',notes:'Заметки'})}</div><div class="actions">${[['view','Просмотр'],['analysis','Разбор боя'],['editing','Монтаж']].map(([id,label])=>`<button class="button secondary" data-action="custom-workspace" data-value="${id}">${label}</button>`).join('')}</div>`;
 return `<h2>Твои оформления</h2><p>Сохрани сочетание темы, фона, звуков и расположения панелей. Файл оформления включает собственные фоны и звуки.</p><div class="field-line custom-preset-new"><input id="customPresetName" placeholder="Например, Мой AFTERPLAY" maxlength="60">${button('custom-preset-save','Сохранить набор','check','primary')}</div><div class="custom-preset-list">${Object.keys(state.settings.appearance_presets||{}).map((name,index)=>`<div class="custom-preset-item" role="group" aria-labelledby="customPresetLabel${index}"><button id="customPresetLabel${index}" class="button secondary" data-action="custom-preset-load" data-name="${esc(name)}">${esc(name)}</button><button class="button quiet custom-preset-delete" data-action="custom-preset-delete" data-name="${esc(name)}" aria-label="Удалить набор" aria-describedby="customPresetLabel${index}" title="Удалить набор">${icon('trash')}</button></div>`).join('')||'<p class="hint">Пока нет сохранённых наборов.</p>'}</div><div class="actions">${button('custom-preset-export','Экспортировать набор','download','secondary')}${button('custom-preset-import','Импортировать набор','folder','secondary')}</div>`;
}
function customPage(){
 if(!customDraft)customDraft=structuredClone(customSettings());
 return `<div class="page-head"><div><div class="eyebrow">MAKE IT YOURS</div><h1>Твой AFTERPLAY</h1><p>Оформление, которое хочется оставить открытым.</p></div><span class="pill">${Object.keys(customThemeData).length} тем</span></div><section class="custom-theme-grid">${Object.entries(customThemeData).map(([id,[name,label,bg,accent]])=>`<button class="custom-theme ${customSettings().theme===id?'selected':''}" data-action="custom-theme" data-value="${id}" style="--swatch-bg:${bg};--swatch-accent:${accent}"><div class="custom-theme-mini"><i></i><div><b></b><span></span><span></span></div></div><strong>${name}</strong><small>${label}</small></button>`).join('')}</section><nav class="custom-tabs" aria-label="Оформление">${[['background','Фон'],['interface','Интерфейс'],['library','Библиотека'],['sound','Звуки'],['notice','Уведомления'],['timer','Таймер'],['workspace','Монтаж'],['presets','Мои наборы']].map(([id,name])=>`<button data-action="custom-pane" data-value="${id}" class="${customPane===id?'active':''}">${name}</button>`).join('')}</nav><section class="custom-panel">${customPanel()}</section><div class="custom-save-bar"><span id="customSaveStatus" role="status">${customDirty?'Предпросмотр · изменения ещё не сохранены':'Изменения видны сразу · сохрани понравившийся результат'}</span><div class="actions">${button('custom-reset','Сбросить','refresh','quiet')}${button('custom-cancel','Отменить','close','secondary')}${button('custom-save','Сохранить оформление','check','primary')}</div></div>`;
}
function customApply(){
 const c=customSettings(),root=document.documentElement;
 root.dataset.theme=c.theme;for(const [token,key] of [['--panel','panel_color'],['--text','text_color'],['--muted','muted_color']]){if(c.colors_custom)root.style.setProperty(token,c[key]);else root.style.removeProperty(token)};root.dataset.customMotion=c.animation;root.dataset.customGlow=String(c.glow);root.dataset.navCompact=String(c.nav_compact);
 const rgb=c.accent.slice(1).match(/../g).map(x=>parseInt(x,16));
 document.body.style.setProperty('--accent',c.accent);document.body.style.setProperty('--accent-rgb',rgb.join(','));
 root.style.setProperty('--custom-panel-alpha',c.panel_opacity+'%');root.style.setProperty('--custom-radius',c.radius+'px');
 root.style.setProperty('--custom-card-size',c.card_size+'px');root.style.setProperty('--custom-card-ratio',c.card_ratio);
 root.style.setProperty('--custom-editor-width',c.editor_width+'px');root.style.setProperty('--custom-timeline-height',c.timeline_height+'px');
 root.style.setProperty('--custom-ui-scale',c.scale/100);root.style.setProperty('--custom-bg-color',c.background_color);
 root.style.setProperty('--custom-motion-duration',(24/c.speed)+'s');
 for(const key of ['card_date','card_game','card_size_label','card_duration','card_tags'])root.dataset[key.replace(/_([a-z])/g,(_,v)=>v.toUpperCase())]=String(c[key]);
 let bg=$('#customBackground');
 if(!bg){bg=document.createElement('div');bg.id='customBackground';bg.setAttribute('aria-hidden','true');document.body.prepend(bg)}
 let key=[c.background,c.scene,c.asset].join('|');
 if(key!==customBackgroundKey){
  if(customMedia){customMedia.pause();customMedia.removeAttribute('src');customMedia.load();customMedia=null}
  customBackgroundKey=key;bg.replaceChildren();bg.className='';
  if(c.background==='scene'&&c.scene!=='video'){
   bg.className='custom-scene scene-'+c.scene;for(let i=0;i<5;i++){const node=document.createElement('i');node.style.setProperty('--i',i);bg.append(node)}
  }else if(c.background==='asset'&&c.asset||c.background==='scene'&&c.scene==='video'){
   const src=c.background==='asset'?base+'custom-assets/'+c.asset:base+'backgrounds/aurora.mp4';
   if(/\.(mp4|webm)$/i.test(src)){
    customMedia=document.createElement('video');customMedia.muted=true;customMedia.defaultMuted=true;customMedia.loop=true;customMedia.playsInline=true;customMedia.preload='metadata';customMedia.src=src;bg.append(customMedia);
    customMedia.addEventListener('loadeddata',customUpdatePause);customMedia.addEventListener('error',()=>{bg.dataset.error='true';if(tab==='customize')toast('Не удалось воспроизвести фон. Выбери другой файл.',true)},{once:true});
   }else{const img=document.createElement('img');img.alt='';img.src=src;bg.append(img)}
  }
 }
 bg.style.filter=`blur(${c.blur}px) saturate(${c.saturation}%) brightness(${1-c.dim/100})`;
 bg.style.opacity=c.background==='none'||c.background==='color'?'0':'1';
 const media=bg.querySelector('video,img');if(media)media.style.objectFit=c.fit;
 if(customMedia)customMedia.playbackRate=c.speed;
 root.dataset.hasBackground=String(!['none','color'].includes(c.background));
 customUpdatePause();customTimerSample();
}
function customUpdatePause(){
 const c=customSettings(),recording=['starting','recording','stopping'].includes(state.replay?.phase),exporting=state.jobs?.some(j=>j.status==='running');
 customPaused=document.hidden||window.customNativeHidden||!c.motion||c.animation==='off'||c.pause_recording&&recording||c.pause_export&&exporting;
 $('#customBackground')?.classList.toggle('paused',customPaused);
 if(customMedia){if(customPaused)customMedia.pause();else if(customMedia.paused)customMedia.play().catch(()=>{})}
 if(document.hidden||window.customNativeHidden)customStopHover();
}
function customTimerSample(){
 const c=customSettings(),sample=$('#customTimerSample');
 if(sample){sample.style.left=c.timer_x+'%';sample.style.top=c.timer_y+'%';sample.style.transform=`translate(${-c.timer_x}%,${-c.timer_y}%)`;sample.style.color=c.timer_color;sample.style.background=`rgba(0,0,0,${c.timer_background/100})`;sample.style.fontSize=16*c.timer_size/100+'px';sample.style.fontFamily=c.timer_font==='mono'?'Consolas,monospace':"'AFTERPLAY Inter',sans-serif";sample.textContent=c.timer_format==='frames'?'Кадр 741':c.timer_format==='seconds'?'00:12':'00:12.350'}
 const notice=$('.custom-notice-demo');if(notice){notice.style.opacity=c.notice_opacity/100;notice.style.transform=`scale(${c.notice_size/100})`;notice.style.transformOrigin='left center'}
}
function customChanged(){
 customDirty=true;$('#customSaveStatus')?.replaceChildren(document.createTextNode('Предпросмотр · изменения ещё не сохранены'));
 customApply();customDecorateCards();
}
async function customSave(){
 if(customSaveBusy)return;customSaveBusy=true;
 try{const result=await api('customize_config',customDraft||customSettings());state.settings.customization=result;state.settings.appearance={...state.settings.appearance,theme:result.theme};customDraft=structuredClone(result);customDirty=false;toast('Оформление сохранено');customApply();if(tab==='customize')render()}
 finally{customSaveBusy=false}
}
const beforeCustomPage=clipsPage;
clipsPage=function(){return tab==='customize'?customPage():beforeCustomPage()};
const beforeCustomCard=clipCard;
clipCard=function(clip){const html=beforeCustomCard(clip),cover=state.settings.clip_covers?.[clip.id];return cover?html.replace(base+'thumb/'+clip.id,base+'thumb/'+clip.id+'?cover='+cover.version):html};
const beforeCustomNavigation=navigation;
navigation=function(){
 beforeCustomNavigation();const c=customSettings(),nav=$('#nav');
 const nodes=new Map([...nav.querySelectorAll('[data-tab]')].map(el=>[el.dataset.tab,el]));
 for(const id of c.nav_order){const node=nodes.get(id);if(node){node.hidden=c.nav_hidden.includes(id);node.title=node.textContent.trim();node.classList.add('custom-nav-item');const text=[...node.childNodes].find(n=>n.nodeType===Node.TEXT_NODE);if(text){const span=document.createElement('span');span.className='custom-nav-text';span.textContent=text.textContent;text.replaceWith(span)}nav.append(node)}}
 const custom=document.createElement('button');custom.className='nav-button custom-nav-item '+(tab==='customize'?'active':'');custom.dataset.tab='customize';custom.title='Оформление';custom.innerHTML=icon('palette')+'<span class="custom-nav-text">Оформление</span>';nav.append(custom);
 for(const tag of c.pinned_tags){const node=document.createElement('button');node.className='nav-button custom-nav-item custom-pinned';node.dataset.tag=tag;node.title=tag;node.innerHTML=icon('tag')+'<span class="custom-nav-text">'+esc(tag)+'</span>';nav.append(node)}
 if(tab==='customize')$('#breadcrumb').innerHTML='AFTERPLAY <span>/ Оформление</span>';
};
function customDecorateCards(){
 for(const card of document.querySelectorAll('.clip-card[data-clip]')){
  const clip=state.clips.find(x=>x.id===card.dataset.clip);if(!clip||card.querySelector('.custom-card-extra'))continue;
  const extra=document.createElement('div');extra.className='custom-card-extra';
  const game=state.settings.clip_games?.[clip.id];
  extra.innerHTML=`<span class="custom-card-date">${new Date(clip.mtime*1000).toLocaleDateString(window.i18nLocale?.()||'ru-RU')}</span>${game?`<span class="custom-card-game">${esc(game)}</span>`:''}`;
  card.querySelector('.clip-info')?.append(extra);
 }
}
const beforeCustomRender=render;
render=function(){customStopHover();beforeCustomRender();customApply();customDecorateCards();installMicControls()};
const beforeCustomPreferences=window.updatePreferences;
window.updatePreferences=function(){beforeCustomPreferences?.();customApply()};
const beforeCustomAction=action;
action=async function(name,el){
 if(!name.startsWith('custom-'))return beforeCustomAction(name,el);
 if(!customDraft)customDraft=structuredClone(customSettings());
 if(name==='custom-pane'){customPane=el.dataset.value;render();return}
 if(name==='custom-theme'){
  const id=el.dataset.value;customDraft.colors_custom=false;customDraft.theme=id;customDraft.accent=customThemeData[id][3];
  customDraft.background_color=customThemeData[id][2];
  if(id==='aurora'||id==='ember'){customDraft.background='scene';customDraft.scene=id}
  if(['paper','mist'].includes(id))customDraft.background='color';
  if(id==='glass'){customDraft.panel_opacity=78;customDraft.background='scene';customDraft.scene='aurora';customDraft.dim=35}
  else customDraft.panel_opacity=94;
  customChanged();render();return;
 }
 if(name==='custom-background'){customDraft.background=el.dataset.value;customChanged();render();return}
 if(name==='custom-scene'){customDraft.background='scene';customDraft.scene=el.dataset.value;customChanged();render();return}
 if(name==='custom-save'){await customSave();return}
 if(name==='custom-cancel'){customDraft=null;customDirty=false;render();return}
 if(name==='custom-reset'){customDraft=structuredClone(customDefaults);customChanged();render();return}
 if(name==='custom-import-bg'||name==='custom-import-sound'){
  const value=await api('customize_import_asset',{kind:name==='custom-import-bg'?'background':'sound',event:el.dataset.event});
  if(value.cancelled)return;
  if(name==='custom-import-bg'){customDraft.asset=value.asset;customDraft.background='asset'}else customDraft.sounds[el.dataset.event].asset=value.asset;
  customChanged();render();return;
 }
 if(name==='custom-sound-default'){customDraft.sounds[el.dataset.event].asset='';customChanged();render();return}
 if(name==='custom-sound'){await api('customize_sound',{event:el.dataset.event,settings:customDraft});return}
 if(name==='custom-notice'){await api('customize_notice',{settings:customDraft});return}
 if(name==='custom-nav-move'){const i=customDraft.nav_order.indexOf(el.dataset.id),j=i+Number(el.dataset.direction);if(j>=0&&j<6)[customDraft.nav_order[i],customDraft.nav_order[j]]=[customDraft.nav_order[j],customDraft.nav_order[i]];customChanged();render();return}
 if(name==='custom-workspace'){
  Object.assign(customDraft,{view:{editor_start:'view',editor_width:340,timeline_height:150},analysis:{editor_start:'edit',editor_tab:'trim',editor_width:310,timeline_height:240},editing:{editor_start:'edit',editor_tab:'export',editor_width:400,timeline_height:190}}[el.dataset.value]);customChanged();render();return;
 }
 if(name==='custom-preset-save'){const label=$('#customPresetName').value;await customSave();state.settings.appearance_presets=await api('customize_preset_save',{name:label});render();toast('Набор сохранён');return}
 if(name==='custom-preset-load'){customDraft=structuredClone(state.settings.appearance_presets[el.dataset.name]);customChanged();render();return}
 if(name==='custom-preset-delete'){
  const label=el.dataset.name;
  modal('Удалить набор?',`<p data-i18n-ignore>${esc(label)}</p><p class="hint">Текущее оформление останется без изменений.</p>`,button('custom-preset-delete-confirm','Удалить набор','trash','danger',`data-name="${esc(label)}"`)+button('close','Отмена','close','quiet'));return;
 }
 if(name==='custom-preset-delete-confirm'){
  el.disabled=true;
  try{state.settings.appearance_presets=await api('customize_preset_delete',{name:el.dataset.name});close();render();toast('Набор удалён')}
  catch(error){el.disabled=false;throw error}
  return;
 }
 if(name==='custom-preset-export'){await customSave();const value=await api('customize_preset_export');if(!value.cancelled)toast('Набор экспортирован');return}
 if(name==='custom-preset-import'){const value=await api('customize_preset_import');if(!value.cancelled){state.settings.customization=value;customDraft=structuredClone(value);customDirty=false;render();toast('Оформление импортировано')}return}
 if(name==='custom-cover'){
  const value=await api('customize_cover',{id:selected.id,time:window.studioFrameTime?.()??$('#player')?.currentTime??0});
  for(const img of document.querySelectorAll(`.clip-card[data-clip="${selected.id}"] .thumb img`))img.src=base+'thumb/'+selected.id+'?v='+value.version;
  toast('Этот кадр выбран обложкой');return;
 }
};
document.addEventListener('input',e=>{
 const key=e.target.dataset.custom;if(!key||!customDraft)return;
 let value=e.target.type==='checkbox'?e.target.checked:e.target.type==='range'?Number(e.target.value):e.target.value;
 if(key==='pinned_tags')value=value.split(',').map(x=>x.trim()).filter(Boolean).slice(0,15);
 customPath(customDraft,key,value);const out=document.querySelector(`[data-custom-output="${key}"]`);if(out)out.textContent=String(value);
 if(e.target.type==='color')e.target.nextElementSibling.textContent=value;customChanged();
});
document.addEventListener('change',e=>{
 if(e.target.matches('select[data-custom]'))e.target.dispatchEvent(new Event('input',{bubbles:true}));
 if(e.target.dataset.navVisible){const id=e.target.dataset.navVisible;customDraft.nav_hidden=e.target.checked?customDraft.nav_hidden.filter(x=>x!==id):[...new Set([...customDraft.nav_hidden,id])];customChanged();navigation()}
});
document.addEventListener('visibilitychange',customUpdatePause);
document.addEventListener('pointerdown',e=>{
 if(e.target.id!=='customTimerSample')return;
 const sample=e.target,area=$('#customTimerDemo');sample.setPointerCapture(e.pointerId);
 function move(event){const r=area.getBoundingClientRect();customDraft.timer_x=Math.max(0,Math.min(100,(event.clientX-r.left)/r.width*100));customDraft.timer_y=Math.max(0,Math.min(100,(event.clientY-r.top)/r.height*100));customChanged()}
 function stop(){sample.removeEventListener('pointermove',move);sample.removeEventListener('pointerup',stop);for(const key of ['timer_x','timer_y']){const input=document.querySelector(`[data-custom="${key}"]`);if(input)input.value=customDraft[key];const out=document.querySelector(`[data-custom-output="${key}"]`);if(out)out.textContent=customDraft[key].toFixed(1)}}
 sample.addEventListener('pointermove',move);sample.addEventListener('pointerup',stop,{once:true});sample.addEventListener('pointercancel',stop,{once:true});
});
let customHoverCard=null,customHoverVideo=null,customHoverTimer=null,customHoverX=.1;
function customStopHover(){
 clearTimeout(customHoverTimer);customHoverTimer=null;customHoverCard?.classList.remove('custom-previewing');customHoverCard=null;
 if(customHoverVideo){customHoverVideo.pause();customHoverVideo.removeAttribute('src');customHoverVideo.load();customHoverVideo.remove();customHoverVideo=null}
}
document.addEventListener('pointerover',e=>{
 const card=e.target.closest('.clip-card[data-clip]'),cfg=customSettings();
 if(!card||card===customHoverCard||!cfg.hover_enabled||$('#dialog').open||e.target.closest('button'))return;
 customStopHover();customHoverCard=card;
 const clip=state.clips.find(x=>x.id===card.dataset.clip);if(!clip||/\.gif$/i.test(clip.path))return;
 customHoverTimer=setTimeout(()=>{
  if(customHoverCard!==card||document.hidden)return;
  const video=document.createElement('video');customHoverVideo=video;video.className='custom-hover-video';video.muted=!cfg.hover_sound;video.volume=.25;video.playsInline=true;video.loop=true;video.preload='metadata';video.playbackRate=cfg.hover_speed;video.src=base+'media/'+clip.id;
  card.querySelector('.thumb').append(video);
  video.addEventListener('loadedmetadata',()=>{if(customHoverVideo!==video)return;video.currentTime=Math.min(Math.max(0,video.duration-.1),cfg.hover_mode==='scrub'?customHoverX*video.duration:Math.min(3,video.duration*.1));if(cfg.hover_mode==='play')video.play().catch(()=>{})});
  video.addEventListener('loadeddata',()=>card.classList.add('custom-previewing'));
  video.addEventListener('error',()=>{if(customHoverVideo===video)customStopHover()},{once:true});
 },cfg.hover_delay);
});
document.addEventListener('pointerout',e=>{if(customHoverCard&&!customHoverCard.contains(e.relatedTarget))customStopHover()});
document.addEventListener('pointermove',e=>{
 if(!customHoverCard||!customHoverCard.contains(e.target))return;const rect=customHoverCard.querySelector('.thumb').getBoundingClientRect();customHoverX=Math.max(0,Math.min(.999,(e.clientX-rect.left)/rect.width));
 if(customSettings().hover_mode==='scrub'&&customHoverVideo?.readyState>=1&&!customHoverVideo.seeking)customHoverVideo.currentTime=customHoverX*customHoverVideo.duration;
});
const beforeCustomOpen=openClip;
openClip=function(id){
 customStopHover();beforeCustomOpen(id);const c=customSettings();
 if($('#player')?.tagName==='VIDEO'){
  const button=document.createElement('button');button.className='button quiet';button.dataset.action='custom-cover';button.textContent='Этот кадр — обложка';
  document.querySelector('[data-review-panel="notes"]')?.append(button);
  if(c.editor_start==='edit')reviewSetMode(true,c.editor_tab);
 }
};
function installMicControls(){
 if(tab!=='replay'||!$('#replayAudioMode'))return;
 if($('#microphoneEnabled')){
  const select=$('#microphoneDevice'),rows=replayDevices?.microphones||[],signature=JSON.stringify(rows);
  if(select.dataset.devices!==signature){
   const previous=select.value,cfg=state.replay?.settings||{};
   select.innerHTML='<option value="default">Микрофон по умолчанию</option>'+rows.map(d=>`<option value="${esc(d.id)}" data-name="${esc(d.name)}">${esc(d.name)}</option>`).join('');
   const match=rows.find(d=>d.name===cfg.microphone_name);select.value=[...select.options].some(o=>o.value===previous)?previous:match?.id||'default';select.dataset.devices=signature;
  }
  if($('#microphoneAvailability'))$('#microphoneAvailability').textContent=rows.length?'Доступно микрофонов: '+rows.length:'Windows не видит микрофон. Подключи устройство и нажми «Обновить список».';
  return;
 }
 const cfg=state.replay?.settings||{},busy=studioBusy(),field=document.createElement('section');field.className='custom-mic-field';
 field.innerHTML=`<h3>Микрофон · отдельная дорожка</h3><label class="check"><input id="microphoneEnabled" type="checkbox" ${cfg.microphone_enabled?'checked':''} ${busy?'disabled':''}>Записывать мой голос</label><div class="custom-grid"><div class="field"><label>Устройство микрофона</label><select id="microphoneDevice" ${busy?'disabled':''}><option value="default">Микрофон по умолчанию</option>${(replayDevices?.microphones||[]).map(d=>`<option value="${esc(d.id)}" data-name="${esc(d.name)}" ${cfg.microphone_name===d.name?'selected':''}>${esc(d.name)}</option>`).join('')}</select></div><div class="field"><label>Громкость микрофона · %</label><input type="number" id="microphoneGain" min="0" max="100" value="${cfg.microphone_gain??100}" ${busy?'disabled':''}></div></div><p class="hint" id="microphoneAvailability"></p><p class="hint">Микрофон добавляется в общий звук и сохраняется отдельно. В монтаже его можно отключить или сделать тише. По умолчанию выключен.</p>`;
 $('#replayAudioMode').closest('.replay-config-group').append(field);
}
const beforeMicReplayValues=replayValues;
replayValues=function(){const cfg=beforeMicReplayValues();if($('#microphoneEnabled'))Object.assign(cfg,{microphone_enabled:$('#microphoneEnabled').checked,microphone_device:$('#microphoneDevice').value,microphone_name:$('#microphoneDevice').selectedOptions[0]?.dataset.name||'',microphone_gain:Number($('#microphoneGain').value)});return cfg};
const beforeMicUpdate=window.updateReplay;
window.updateReplay=function(){beforeMicUpdate?.();if(tab==='replay'){installMicControls();for(const id of ['microphoneEnabled','microphoneDevice','microphoneGain'])if($('#'+id))$('#'+id).disabled=studioBusy()}};
window.customDebug=()=>({theme:customSettings().theme,background:customSettings().background,paused:!!customPaused,video:!!customMedia,videoPaused:customMedia?.paused,videoReady:customMedia?.readyState,hover:!!customHoverVideo,hoverReady:customHoverVideo?.readyState,dirty:customDirty,errors:window.customErrors||[],actionError:window.customTestError||'',overflow:document.documentElement.scrollWidth>innerWidth});
