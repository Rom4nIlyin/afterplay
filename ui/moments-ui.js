'use strict';
const quickClipDefaults=[30,120,300];
const quickClipValues=()=>state.settings.quick_clips||quickClipDefaults;
const inputDefaults={layout:'full',position:'bottom-left',size:42,opacity:90};
const montageSelection=new Set();
let montageDraft=null,montageView=null,inputEditor=null;

// A video-only overlay: no native window and no changes to the source video.
function createInputPreview(stage,player,data,config,timeSource=()=>player.currentTime){
 const node=document.createElement('div');node.className='input-visual';node.dataset.i18nIgnore='';node.hidden=true;node.setAttribute('aria-hidden','true');stage.append(node);
 const timeline=new InputTimeline(data.events),abort=new AbortController();
 let settings={...inputDefaults,...config},visible=false,raf=0,disposed=false,signature='';
 let elements=[];
 function build(){
  const g=data.layouts[settings.layout];
  node.innerHTML=`<svg viewBox="0 0 ${g.width} ${g.height}" xmlns="http://www.w3.org/2000/svg">${g.keys.map(k=>`<g data-code="${k.code}"><rect x="${k.x}" y="${k.y}" width="${k.w}" height="${k.h}" rx="2.5"/><text x="${k.x+k.w/2}" y="${k.y+k.h/2}" dominant-baseline="central" text-anchor="middle">${esc(k.label)}</text></g>`).join('')}</svg>`;
  elements=[...node.querySelectorAll('[data-code]')];signature='';draw();
 }
 function fit(){
  const box=player.getBoundingClientRect(),home=stage.getBoundingClientRect();
  if(!box.width||!box.height)return;
  const ratio=(player.videoWidth||selected?.width||16)/(player.videoHeight||selected?.height||9);
  const width=Math.min(box.width,box.height*ratio),height=width/ratio;
  const left=box.left-home.left+(box.width-width)/2,top=box.top-home.top+(box.height-height)/2;
  const g=data.layouts[settings.layout],scale=Math.min(width*settings.size/100/g.width,height*.42/g.height);
  const w=g.width*scale,h=g.height*scale,margin=Math.max(8,Math.min(width,height)*.02);
  node.style.width=w+'px';node.style.height=h+'px';node.style.opacity=settings.opacity/100;
  node.style.left=(settings.position.endsWith('left')?left+margin:left+width-margin-w)+'px';
  node.style.top=(settings.position.startsWith('top')?top+margin:top+height-margin-h)+'px';
 }
 function draw(){
  if(disposed||!visible)return;
  fit();const held=timeline.at(timeSource()),next=[...held].sort().join(',');
  if(next===signature)return;signature=next;
  for(const element of elements)element.classList.toggle('pressed',held.has(element.dataset.code));
 }
 function tick(){draw();if(!disposed&&visible&&!player.paused)raf=requestAnimationFrame(tick)}
 function kick(){cancelAnimationFrame(raf);draw();if(visible&&!player.paused)raf=requestAnimationFrame(tick)}
 for(const event of ['play','pause','seeking','seeked','timeupdate','loadedmetadata','ratechange'])player.addEventListener(event,kick,{signal:abort.signal});
 document.addEventListener('afterplay-frame',draw,{signal:abort.signal});
 const observer=new ResizeObserver(draw);observer.observe(stage);
 build();
 return {node,draw,setVisible(value){visible=!!value;node.hidden=!visible;kick()},
  configure(value){const changed=settings.layout!==value.layout;settings={...settings,...value};if(changed)build();else draw()},
  dispose(){disposed=true;abort.abort();observer.disconnect();cancelAnimationFrame(raf);node.remove()}};
}

const beforeMomentsControls=captureControls;
captureControls=function(r){
 const enabled=!!r.input_recording?.enabled;
 return beforeMomentsControls(r)+button('inputs-toggle',enabled?'Нажатия: запись включена':'Записывать нажатия','settings',enabled?'secondary inputs-on':'quiet',`aria-pressed="${enabled}" ${['starting','stopping'].includes(r.phase)?'disabled':''}`);
};
const beforeMomentsExtras=window.renderDesktopExtras;
window.renderDesktopExtras=function(){
 beforeMomentsExtras?.();
 if(tab!=='settings'||$('#quickClipSettings'))return;
 const card=$('#saveHotkey')?.closest('.settings-card');if(!card)return;
 const values=quickClipValues(),keys=state.settings.hotkeys||{};
 card.querySelector('.actions').insertAdjacentHTML('beforebegin',`<section id="quickClipSettings"><h3>Клипы разной длины</h3><p class="hint">Каждая клавиша сохраняет последние N секунд в MP4. Доступная длина растёт по мере записи. Эти клипы могут перекрываться.</p>${values.map((seconds,i)=>`<div class="quick-clip-setting"><div class="field"><label for="quickClipKey${i}">Клавиша ${i+1} · необязательно</label><div class="hotkey-binding-row"><input class="hotkey-input" id="quickClipKey${i}" value="${esc(keys['clip_'+(i+1)]||'')}" placeholder="Не назначена" autocomplete="off" spellcheck="false"><button type="button" class="quiet clear-binding" data-action="clear-binding" data-target="quickClipKey${i}">Очистить</button></div></div><div class="field"><label for="quickClipSeconds${i}">Секунды</label><input id="quickClipSeconds${i}" type="number" min="5" max="1800" step="1" value="${seconds}"></div></div>`).join('')}<div class="field"><label for="inputsHotkey">Включить / выключить запись нажатий · необязательно</label><div class="hotkey-binding-row"><input class="hotkey-input" id="inputsHotkey" value="${esc(keys.inputs||'')}" placeholder="Не назначена" autocomplete="off" spellcheck="false"><button class="quiet clear-binding" data-action="clear-binding" data-target="inputsHotkey">Очистить</button></div></div></section>`);
 card.insertAdjacentHTML('afterend',`<section class="settings-card" id="inputRecordingSettings"><span class="eyebrow">КЛАВИАТУРА И МЫШЬ</span><h2>Запись нажатий</h2><label class="check"><input id="recordInputs" type="checkbox" ${state.replay?.input_recording?.enabled?'checked':''}> Записывать нажатия вместе с видео</label><p class="hint">Работает во время обычной записи и повтора. Можно переключать на ходу кнопкой на странице записи или назначенной клавишей.</p><p class="hint">При записи окна учитываются нажатия только в его приложении. При записи экрана — в активном приложении, кроме AFTERPLAY. Сохраняются клавиши, кнопки мыши и колесо.</p><div class="notice">Во время игры оверлей не отображается. Его вид и включение в ролик выбираются позже, во вкладке «Нажатия» монтажа.</div><p class="hint error-text" id="inputCaptureError">${esc(state.replay?.input_recording?.error||'')}</p></section>`);
};
const beforeMomentsPreferences=window.updatePreferences;
window.updatePreferences=function(){
 beforeMomentsPreferences?.();
 const cfg=state.replay?.input_recording||{};
 for(const button of document.querySelectorAll('[data-action="inputs-toggle"]')){
  button.setAttribute('aria-pressed',String(!!cfg.enabled));button.classList.toggle('inputs-on',!!cfg.enabled);
  button.innerHTML=icon('settings')+(cfg.enabled?'Нажатия: запись включена':'Записывать нажатия');
 }
 if($('#recordInputs')&&document.activeElement!==$('#recordInputs'))$('#recordInputs').checked=!!cfg.enabled;
 if($('#inputCaptureError'))$('#inputCaptureError').textContent=cfg.error||'';
};

function disposeInputEditor(){if(inputEditor){inputEditor.abort.abort();inputEditor.preview?.dispose();inputEditor=null}}
const beforeMomentsOpen=openClip;
openClip=function(id){
 disposeInputEditor();beforeMomentsOpen(id);
 const player=$('#player');if(!reviewState||!player||player.tagName!=='VIDEO')return;
 const current=inputEditor={id,abort:new AbortController(),preview:null,settings:{...inputDefaults}};
 const on=(node,event,fn)=>node?.addEventListener(event,fn,{signal:current.abort.signal});
 const nav=reviewState.aside.querySelector('.review-tabs');
 nav.insertAdjacentHTML('beforeend','<button type="button" role="tab" data-review-pane="inputs" aria-controls="review-panel-inputs" aria-selected="false" tabindex="-1">Нажатия</button>');
 const panel=reviewPanel('inputs','Нажатия');panel.hidden=true;panel.innerHTML='<p class="hint">Читаю дорожку нажатий…</p>';reviewState.aside.append(panel);
 api('clip_inputs',{id}).then(data=>{
  if(inputEditor!==current)return;
  if(!data.available){panel.innerHTML='<h3>Нажатия не записаны</h3><p class="hint">Включи «Записывать нажатия» перед нужным моментом или во время записи. Для старого видео восстановить нажатия нельзя.</p>';return}
  current.settings={...data.settings};
  panel.innerHTML=`<h3>Клавиатура и мышь</h3><label class="check"><input id="previewInputs" type="checkbox"> Показывать нажатия при просмотре</label><p class="hint">Слой синхронизирован с видео, перемоткой и точными кадрами.</p><div class="field"><label for="inputLayout">Вид клавиатуры</label><select id="inputLayout"><option value="full">Полная клавиатура + мышь</option><option value="compact">WASD, стрелки + мышь</option></select></div><div class="field"><label for="inputPosition">Расположение</label><select id="inputPosition"><option value="bottom-left">Снизу слева</option><option value="bottom-right">Снизу справа</option><option value="top-left">Сверху слева</option><option value="top-right">Сверху справа</option></select></div><div class="field"><label for="inputSize">Размер · <output id="inputSizeValue"></output>% ширины видео</label><input id="inputSize" type="range" min="20" max="70" value="${current.settings.size}"></div><div class="field"><label for="inputOpacity">Непрозрачность · <output id="inputOpacityValue"></output>%</label><input id="inputOpacity" type="range" min="20" max="100" value="${current.settings.opacity}"></div><label class="check"><input id="exportInputs" type="checkbox"> Добавить нажатия в готовый ролик</label><p class="hint">Исходная запись остаётся чистой. В экспортированном ролике включённый слой станет частью изображения.</p>`;
  $('#inputLayout').value=current.settings.layout;$('#inputPosition').value=current.settings.position;
  current.preview=createInputPreview($('.playback-stage'),player,data,current.settings,()=>studioEditor?.exactTime??player.currentTime);
  const update=()=>{current.settings={layout:$('#inputLayout').value,position:$('#inputPosition').value,size:Number($('#inputSize').value),opacity:Number($('#inputOpacity').value)};$('#inputSizeValue').textContent=current.settings.size;$('#inputOpacityValue').textContent=current.settings.opacity;current.preview.configure(current.settings)};
  update();
  on($('#previewInputs'),'change',e=>{current.preview.setVisible(e.target.checked)});
  on($('#exportInputs'),'change',syncInputExport);
  let saveQueue=Promise.resolve();
  for(const key of ['inputLayout','inputPosition','inputSize','inputOpacity']){
   on($('#'+key),'input',update);on($('#'+key),'change',()=>{update();const value={...current.settings};saveQueue=saveQueue.catch(()=>{}).then(()=>api('clip_inputs_config',{id,settings:value})).catch(error=>toast(error.message,true))});
  }
  const exportPanel=$('[data-review-panel="export"]');exportPanel.insertAdjacentHTML('beforeend','<label class="check input-export-copy"><input id="exportInputsCopy" type="checkbox"> Добавить нажатия клавиатуры и мыши</label>');
  on($('#exportInputsCopy'),'change',e=>{$('#exportInputs').checked=e.target.checked;syncInputExport()});
  document.dispatchEvent(new CustomEvent('afterplay-input-ready',{detail:{id}}));
 }).catch(error=>{if(inputEditor===current)panel.textContent=error.message});
 function syncInputExport(){if($('#exportInputsCopy'))$('#exportInputsCopy').checked=!!$('#exportInputs')?.checked}
};
$('#dialog').addEventListener('close',()=>{disposeInputEditor();disposeMontageView()});

// Library selection is kept independently from search and gallery/list layout.
const beforeMomentsCard=clipCard;
function montageCard(html,clip){
 const checked=montageSelection.has(clip.id);
 return html.replace(/<article\b[^>]*>/,tag=>tag.replace('<article ',`<article data-montage-selected="${checked}" `)+`<button type="button" class="montage-select ${checked?'selected':''}" data-action="montage-select" data-id="${clip.id}" aria-label="Выбрать для подборки: ${esc(clip.name)}" aria-pressed="${checked}">${icon(checked?'check':'plus')}</button>`);
}
clipCard=function(clip){
 return montageCard(beforeMomentsCard(clip),clip);
};
const beforeMomentsPage=clipsPage;
clipsPage=function(){
 const valid=new Set(state.clips.map(c=>c.id));for(const id of montageSelection)if(!valid.has(id))montageSelection.delete(id);
 let html=beforeMomentsPage();if(!['library','favorites'].includes(tab))return html;
 const count=montageSelection.size,cinema=html.includes('class="cinema-layout"');
 if(cinema)html=html.replace(/<article\b[^>]*class="[^"]*\bcinema-card\b[^"]*"[^>]*>/g,tag=>{
  const id=tag.match(/data-clip="([^"]+)"/)?.[1],clip=state.clips.find(c=>c.id===id);return clip?montageCard(tag,clip):tag;
 });
 const marker=cinema?'<div class="cinema-library-toolbar">':'<div class="toolbar">';
 const bar=`<section class="montage-selection-bar"><div><b>Подборка моментов</b><small>Нажми + на записях · выбрано: ${count}</small></div><div class="actions">${button('montage-create','Собрать подборку'+(count?' · '+count:''),'film','secondary',count?'':'disabled')}${count?button('montage-clear','Снять выбор','close','quiet'):''}${montageDraft?button('montage-resume','Продолжить подборку','play','quiet'):''}${cinema?button('inputs-toggle',state.replay?.input_recording?.enabled?'Нажатия: запись включена':'Записывать нажатия','settings','quiet'):''}</div></section>`;
 return html.replace(marker,bar+marker);
};

function readMontageForm(){
 if(!montageDraft||!$('#montageEditor'))return;
 montageDraft.name=$('#montageName').value;montageDraft.resolution=$('#montageResolution').value;montageDraft.audio_mode=$('#montageAudio').value;
 for(const [i,row] of montageDraft.segments.entries()){
  const el=$(`[data-montage-row="${i}"]`);if(!el)continue;
  row.start=parse(el.querySelector('[data-part-start]').value);row.end=parse(el.querySelector('[data-part-end]').value);
  row.show_inputs=!!el.querySelector('[data-part-inputs]')?.checked;
 }
}
function disposeMontageView(){
 if(montageView){montageView.preview?.dispose();montageView.abort.abort();montageView=null}
}
function showMontage(){
 disposeInputEditor();disposeMontageView();
 const draft=montageDraft;if(!draft)return;
 modal('Подборка моментов',`<div id="montageEditor" class="montage-editor"><section class="montage-view"><div class="montage-stage"><video id="montagePlayer" controls preload="metadata"></video></div><p id="montagePreviewLabel" class="hint">Выбери отрезок для просмотра.</p><div class="field"><label for="montageName">Название подборки</label><input id="montageName" value="${esc(draft.name)}"></div><div class="montage-output"><div class="field"><label for="montageResolution">Размер</label><select id="montageResolution"><option value="source">Как у первой записи</option><option value="1080p">До 1080p</option><option value="720p">До 720p</option></select></div><div class="field"><label for="montageAudio">Звук</label><select id="montageAudio"><option value="mix">Первая / общая дорожка</option><option value="none">Без звука</option></select></div></div><p class="hint">Разные пропорции сохраняются с полями. После ролика без звука следующий отрезок остаётся синхронным. Исходники сохраняются.</p><p id="montageTotal" class="notice"></p><div class="actions">${button('montage-export','Экспортировать подборку','download','primary')}${button('close','Продолжить позже','close','quiet')}</div></section><section class="montage-parts"><div class="montage-add"><label for="montageAdd">Добавить запись</label><div class="field-line"><select id="montageAdd">${state.clips.map(c=>`<option value="${c.id}">${esc(c.name)}</option>`).join('')}</select>${button('montage-add','Добавить','plus','secondary')}</div></div><div id="montageParts">${draft.segments.map((row,i)=>{
  const c=state.clips.find(c=>c.id===row.id);
  return `<article class="montage-part" data-montage-row="${i}"><div class="montage-part-head"><b>${i+1}.</b><span data-i18n-ignore title="${esc(c?.name||row.id)}">${esc(c?.name||row.id)}</span><div class="actions">${button('montage-up','↑','arrow','quiet',`data-index="${i}" ${i?'':'disabled'} aria-label="Переместить выше"`)}${button('montage-down','↓','arrow','quiet',`data-index="${i}" ${i<draft.segments.length-1?'':'disabled'} aria-label="Переместить ниже"`)}${button('montage-remove','Убрать','close','quiet',`data-index="${i}"`)}</div></div><div class="montage-trims"><label>Начало<input data-part-start value="${trimFormat(row.start)}" aria-label="Начало отрезка ${i+1}"></label><label>Конец<input data-part-end value="${trimFormat(row.end)}" aria-label="Конец отрезка ${i+1}"></label></div><div class="montage-part-footer">${button('montage-preview','Просмотреть','play','secondary',`data-index="${i}"`)}<label class="check"><input data-part-inputs type="checkbox" ${row.show_inputs?'checked':''} disabled> Показать нажатия</label><small data-input-status>Читаю дорожку…</small></div></article>`;
 }).join('')}</div></section></div>`);
 $('#dialog').classList.add('montage-dialog');$('#montageResolution').value=draft.resolution;$('#montageAudio').value=draft.audio_mode;
 const current=montageView={abort:new AbortController(),data:new Map(),preview:null,index:0};
 const on=(node,event,fn)=>node.addEventListener(event,fn,{signal:current.abort.signal});
 const player=$('#montagePlayer');
 on(player,'timeupdate',()=>{const row=draft.segments[current.index];if(row&&player.currentTime>=row.end){player.pause();player.currentTime=row.end}});
 on(player,'play',()=>{const row=draft.segments[current.index];if(row&&(player.currentTime<row.start||player.currentTime>=row.end-.01))player.currentTime=row.start});
 on($('#montageEditor'),'input',()=>{readMontageForm();montageTotal()});
 on($('#montageEditor'),'change',()=>{readMontageForm();const row=draft.segments[current.index];current.preview?.setVisible(!!row?.show_inputs)});
 for(const [i,row] of draft.segments.entries()){
  api('clip_inputs',{id:row.id}).then(data=>{
   if(montageView!==current)return;current.data.set(row.id,data);row.input_overlay={...data.settings};
   const el=$(`[data-montage-row="${i}"]`),checkbox=el.querySelector('[data-part-inputs]');checkbox.disabled=!data.available;
   el.querySelector('[data-input-status]').textContent=data.available?'Дорожка записана':'Без дорожки нажатий';
   if(i===current.index)previewMontage(i,false);
  }).catch(error=>{if(montageView===current)$(`[data-montage-row="${i}"] [data-input-status]`).textContent=error.message});
 }
 montageTotal();previewMontage(0,false);
}
function montageTotal(){
 if(!$('#montageTotal'))return;
 const duration=montageDraft.segments.reduce((sum,row)=>sum+Math.max(0,row.end-row.start),0);
 $('#montageTotal').textContent=`Отрезков: ${montageDraft.segments.length} · длительность: ${Number.isFinite(duration)?trimFormat(duration):'проверь границы'}`;
}
function previewMontage(index,play=true){
 const current=montageView;if(!current)return;readMontageForm();
 const row=montageDraft.segments[index],clip=state.clips.find(c=>c.id===row?.id);if(!clip)return;
 if(!Number.isFinite(row.start)||!Number.isFinite(row.end)||row.end<=row.start)throw Error('Проверь границы отрезка');
 current.index=index;current.preview?.dispose();current.preview=null;
 const player=$('#montagePlayer');player.pause();
 const src=base+'media/'+row.id;if(player.getAttribute('src')!==src){player.src=src;player.load()}
 const seek=()=>{if(montageView!==current||current.index!==index)return;player.currentTime=row.start;if(play)player.play().catch(error=>toast(error.message,true))};
 if(player.readyState>=1)seek();else player.addEventListener('loadedmetadata',seek,{once:true,signal:current.abort.signal});
 const data=current.data.get(row.id);if(data?.available){current.preview=createInputPreview($('.montage-stage'),player,data,row.input_overlay);current.preview.setVisible(row.show_inputs)}
 $('#montagePreviewLabel').textContent=`${index+1}. ${clip.name} · ${trimFormat(row.start)} — ${trimFormat(row.end)}`;
 for(const el of document.querySelectorAll('[data-montage-row]'))el.classList.toggle('previewing',Number(el.dataset.montageRow)===index);
}
const beforeMomentsClose=close;
close=function(){readMontageForm();disposeInputEditor();disposeMontageView();$('#dialog').classList.remove('montage-dialog');return beforeMomentsClose()};
const beforeMomentsAction=action;
action=async function(name,element){
 if(name==='inputs-toggle'){
  state.replay=await api('inputs_config',{enabled:!state.replay?.input_recording?.enabled});state.settings.input_recording={enabled:state.replay.input_recording.enabled};window.updatePreferences?.();return;
 }
 if(name==='clear-binding'){const field=$('#'+element.dataset.target);if(field)field.value='';return}
 if(name==='hotkeys-save'){
  const values={save:$('#saveHotkey').value,window:$('#windowHotkey').value,mark:$('#markHotkey')?.value||'',record:$('#recordHotkey')?.value||'',inputs:$('#inputsHotkey').value,quick_clips:[0,1,2].map(i=>Number($('#quickClipSeconds'+i).value))};
  for(let i=0;i<3;i++)values['clip_'+(i+1)]=$('#quickClipKey'+i).value;
  state.settings.hotkeys=await api('hotkeys_config',values);state.settings.quick_clips=values.quick_clips;await refresh();toast('Горячие клавиши сохранены');return;
 }
 if(name==='hotkeys-reset'){
  for(let i=0;i<3;i++){$('#quickClipKey'+i).value='';$('#quickClipSeconds'+i).value=quickClipDefaults[i]}
  $('#inputsHotkey').value='';return beforeMomentsAction(name,element);
 }
 if(name==='montage-select'){
  const id=element.dataset.id;if(montageSelection.has(id))montageSelection.delete(id);else{if(montageSelection.size>=50)throw Error('В подборке не больше 50 отрезков');montageSelection.add(id)}render();return;
 }
 if(name==='montage-clear'){montageSelection.clear();render();return}
 if(name==='montage-create'){
  montageDraft={name:'Подборка моментов',resolution:'source',audio_mode:'mix',segments:[...montageSelection].map(id=>({id,start:0,end:state.clips.find(c=>c.id===id).duration,show_inputs:false}))};showMontage();return;
 }
 if(name==='montage-resume'){showMontage();return}
 if(name==='montage-preview'){previewMontage(Number(element.dataset.index));return}
 if(['montage-up','montage-down','montage-remove','montage-add'].includes(name)){
  readMontageForm();const rows=montageDraft.segments,index=Number(element.dataset.index);
  if(name==='montage-add'){if(rows.length>=50)throw Error('В подборке не больше 50 отрезков');const clip=state.clips.find(c=>c.id===$('#montageAdd').value);if(clip)rows.push({id:clip.id,start:0,end:clip.duration,show_inputs:false})}
  else if(name==='montage-remove'){if(rows.length===1)throw Error('Оставь хотя бы один отрезок');rows.splice(index,1)}
  else{const other=index+(name==='montage-up'?-1:1);if(other>=0&&other<rows.length)[rows[index],rows[other]]=[rows[other],rows[index]]}
  showMontage();return;
 }
 if(name==='montage-export'){
  readMontageForm();if(montageDraft.segments.some(row=>!Number.isFinite(row.start)||!Number.isFinite(row.end)||row.start<0||row.end<=row.start))throw Error('Проверь начало и конец каждого отрезка');
  const args=structuredClone(montageDraft);await task('montage_export',args,result=>modal('Подборка готова',`<p>Отрезков: ${result.segments} · ${fmt(result.duration)} · ${result.width} × ${result.height}</p><div class="result-path">${esc(result.path)}</div>`,button('close','Закрыть','check','quiet')+button('open-exports','Открыть папку','folder','primary')));close();await refresh();return;
 }
 return beforeMomentsAction(name,element);
};
document.addEventListener('change',async event=>{
 if(event.target.id!=='recordInputs')return;
 const node=event.target;node.disabled=true;
 try{state.replay=await api('inputs_config',{enabled:node.checked});window.updatePreferences?.()}
 catch(error){node.checked=!node.checked;toast(error.message,true)}finally{node.disabled=false}
});
