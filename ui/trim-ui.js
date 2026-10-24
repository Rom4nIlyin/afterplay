'use strict';
let trimState=null;
let trimImageTimer=null,trimImageRequest=0;
function changeTrimView(view){
 if(!trimState)return;Object.assign(trimState,view);updateTrimVisuals();
 clearTimeout(trimImageTimer);const id=trimState.id,request=++trimImageRequest;
 trimImageTimer=setTimeout(()=>{
  if(!trimState||trimState.id!==id)return;
  const start=trimState.viewStart,end=trimState.viewEnd,image=new Image();
  image.onload=()=>{
   if(request!==trimImageRequest||trimState?.id!==id||!$('#trimFilmstrip'))return;
   const strip=$('#trimFilmstrip');strip.src=image.src;strip.dataset.start=start;strip.dataset.end=end;updateTrimVisuals();
  };
  image.src=`${base}filmstrip/${id}?start=${start.toFixed(3)}&end=${end.toFixed(3)}`;
 },350);
}
const trimFormat=value=>{
 const ms=Math.max(0,Math.round((Number(value)||0)*1000));
 return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;
};
function updateTrimVisuals(){
 const s=trimState;if(!s||!$('#trimTrack'))return;
 const span=s.viewEnd-s.viewStart,percent=time=>100*(time-s.viewStart)/span;
 const start=Math.max(0,Math.min(100,percent(s.start))),end=Math.max(0,Math.min(100,percent(s.end)));
 $('#trimSelection').style.left=start+'%';$('#trimSelection').style.width=(end-start)+'%';
 $('#trimBefore').style.width=start+'%';$('#trimAfter').style.width=(100-end)+'%';
 for(const edge of ['start','end']){
  const handle=$('#trim'+(edge==='start'?'Start':'End'));
  handle.hidden=s[edge]<s.viewStart-.001||s[edge]>s.viewEnd+.001;
  handle.style.left=percent(s[edge])+'%';handle.setAttribute('aria-valuenow',s[edge].toFixed(3));
  handle.setAttribute('aria-valuetext',trimFormat(s[edge]));
 }
 $('#trimSummary').textContent=`Выбрано ${trimFormat(s.end-s.start)} из ${trimFormat(s.duration)}`;
 $('#trimStartLabel').textContent=trimFormat(s.start);$('#trimEndLabel').textContent=trimFormat(s.end);
 const time=$('#player')?.currentTime||0;$('#trimPlayhead').style.left=Math.max(0,Math.min(100,percent(time)))+'%';$('#trimPlayhead').hidden=time<s.viewStart||time>s.viewEnd;
 $('#trimMarks').innerHTML=marks.filter(value=>value>=s.viewStart&&value<=s.viewEnd).map(value=>`<span style="left:${percent(value)}%" title="Отметка ${trimFormat(value)}"></span>`).join('');
 $('#trimZoomLabel').textContent=(s.duration/span).toFixed(1)+'×';
 $('#trimViewStart').textContent=trimFormat(s.viewStart);$('#trimViewEnd').textContent=trimFormat(s.viewEnd);
 const pan=$('#trimPan');pan.max=Math.max(0,s.duration-span);pan.value=s.viewStart;pan.hidden=span>=s.duration-.001;
 const strip=$('#trimFilmstrip'),imageStart=Number(strip.dataset.start)||0,imageEnd=Number(strip.dataset.end)||s.duration;
 strip.style.width=100*(imageEnd-imageStart)/span+'%';strip.style.left=percent(imageStart)+'%';
}
function setTrim(start,end,{seek=false,fields=true}={}){
 const s=trimState;if(!s)return;
 const minimum=Math.min(.05,s.duration);
 s.start=Math.max(0,Math.min(Number(start)||0,s.duration-minimum));
 s.end=Math.min(s.duration,Math.max(Number(end)||0,s.start+minimum));
 if(fields){$('#clipIn').value=trimFormat(s.start);$('#clipOut').value=trimFormat(s.end)}
 if(seek&&$('#player'))$('#player').currentTime=s.start;
 updateTrimVisuals();
 document.dispatchEvent(new Event('afterplay-trim'));
}
function trimFromFields(){
 if(!trimState)return;
 const start=parse($('#clipIn').value),end=parse($('#clipOut').value);
 const valid=Number.isFinite(start)&&Number.isFinite(end)&&start>=0&&end>start&&end<=trimState.duration+.001;
 $('#trimError').textContent=valid?'':'Начало должно быть раньше конца и находиться внутри видео.';
 $('[data-action="export"]').disabled=!valid;
 $('[data-action="trim-preview"]').disabled=!valid;
 if(valid)setTrim(start,end,{fields:false});
 return valid;
}
const beforeTrimOpen=openClip;
openClip=function(id){
 beforeTrimOpen(id);if(!selected||!$('#player'))return;
 clearTimeout(trimImageTimer);trimImageRequest++;
 const duration=Math.max(.001,Number(selected.duration)||.001);
 trimState={id,duration,start:0,end:duration,viewStart:0,viewEnd:duration,preview:false};
 const panel=`<section class="trim-panel" aria-label="Выделение отрезка"><div class="trim-heading"><b>Выдели нужный момент</b><small>В экспорт попадёт подсвеченный участок</small></div><div class="trim-track" id="trimTrack"><img class="trim-filmstrip" id="trimFilmstrip" src="${base}filmstrip/${id}" alt="Кадры видео для выбора отрезка" draggable="false"><div class="trim-shade before" id="trimBefore"></div><div class="trim-shade after" id="trimAfter"></div><div class="trim-selection" id="trimSelection" title="Перетащи выделение целиком"></div><div id="trimMarks" class="trim-marks"></div><div class="trim-playhead" id="trimPlayhead"></div><button class="trim-handle" id="trimStart" data-edge="start" role="slider" aria-label="Начало отрезка" aria-valuemin="0" aria-valuemax="${duration}" type="button"><span></span></button><button class="trim-handle" id="trimEnd" data-edge="end" role="slider" aria-label="Конец отрезка" aria-valuemin="0" aria-valuemax="${duration}" type="button"><span></span></button></div><div class="trim-labels"><span id="trimStartLabel"></span><b id="trimSummary"></b><span id="trimEndLabel"></span></div><div class="actions">${button('trim-preview','Посмотреть выделенное','play','secondary')}${button('trim-reset','Всё видео','refresh','quiet')}</div><p class="hint" id="trimHint">Перетащи границы. Стрелки на выбранной границе меняют время на 0,1 с; Shift — на 1 с.</p><p id="trimError" class="hint error-text" aria-live="polite"></p></section>`;
 $('.editor .time-inputs').insertAdjacentHTML('beforebegin',panel);
 $('#trimTrack').insertAdjacentHTML('beforebegin',`<div class="trim-zoom-tools"><div class="actions">${button('trim-zoom-out','−','search','quiet')}${button('trim-zoom-in','+','search','quiet')}<span id="trimZoomLabel" aria-live="polite">1.0×</span>${button('trim-fit','К выделению','search','quiet')}${button('trim-zoom-reset','Вся дорожка','refresh','quiet')}</div><small>Колесо — масштаб · Shift + колесо — прокрутка</small></div>`);
 const strip=$('#trimFilmstrip'),stripBox=document.createElement('div');stripBox.className='trim-filmstrip-viewport';strip.before(stripBox);stripBox.append(strip);strip.dataset.start=0;strip.dataset.end=duration;
 $('#trimTrack').insertAdjacentHTML('afterend',`<div class="trim-view-labels"><span id="trimViewStart"></span><span id="trimViewEnd"></span></div><input id="trimPan" class="trim-pan" type="range" min="0" max="0" step="0.01" value="0" aria-label="Положение увеличенной дорожки" hidden>`);
 $('#trimPan').addEventListener('input',e=>changeTrimView(TrimViewport.clamp(trimState.duration,Number(e.target.value),trimState.viewEnd-trimState.viewStart)));
 $('#clipIn').setAttribute('aria-label','Начало отрезка, часы минуты секунды');
 $('#clipOut').setAttribute('aria-label','Конец отрезка, часы минуты секунды');
 setTrim(0,duration);
 const player=$('#player');
 player.addEventListener('loadedmetadata',()=>{
  if(!trimState||trimState.id!==id||!Number.isFinite(player.duration))return;
  const all=Math.abs(trimState.end-trimState.duration)<.05;
  trimState.duration=player.duration;
  Object.assign(trimState,all?{viewStart:0,viewEnd:player.duration}:TrimViewport.clamp(player.duration,trimState.viewStart,trimState.viewEnd-trimState.viewStart));
  setTrim(trimState.start,all?player.duration:trimState.end);
 });
 player.addEventListener('timeupdate',()=>{
  if(!trimState||trimState.id!==id)return;
  if(trimState.preview&&player.currentTime>=trimState.end){player.pause();player.currentTime=trimState.end;trimState.preview=false}
  updateTrimVisuals();
 });
 $('#trimFilmstrip').addEventListener('error',()=>{
  if($('#trimHint'))$('#trimHint').textContent='Кадры предпросмотра недоступны. Границы и числовой выбор отрезка продолжают работать.';
 });
 const track=$('#trimTrack');let drag=null;
 track.addEventListener('wheel',e=>{
  if(!trimState||drag)return;e.preventDefault();
  const rect=track.getBoundingClientRect();
  if(e.shiftKey||Math.abs(e.deltaX)>Math.abs(e.deltaY))changeTrimView(TrimViewport.pan(trimState,(e.deltaX||e.deltaY)/rect.width*(trimState.viewEnd-trimState.viewStart)));
  else changeTrimView(TrimViewport.zoom(trimState,Math.exp(-Math.max(-240,Math.min(240,e.deltaY))*.003),(e.clientX-rect.left)/rect.width));
 },{passive:false});
 const position=e=>{const rect=track.getBoundingClientRect();return TrimViewport.time(trimState,(e.clientX-rect.left)/rect.width)};
 track.addEventListener('pointerdown',e=>{
  if(!trimState||trimState.id!==id)return;
  const edge=e.target.closest('[data-edge]')?.dataset.edge;
  if(edge||e.target.id==='trimSelection'){
   e.preventDefault();drag={edge:edge||'move',at:position(e),start:trimState.start,end:trimState.end};track.setPointerCapture(e.pointerId);
  }else{player.currentTime=position(e);updateTrimVisuals()}
 });
 track.addEventListener('pointermove',e=>{
  if(!drag||!trimState)return;
  const at=position(e),s=trimState;
  if(drag.edge==='start')setTrim(Math.min(at,s.end-.05),s.end,{seek:true});
  else if(drag.edge==='end')setTrim(s.start,Math.max(at,s.start+.05));
  else{const delta=Math.max(-drag.start,Math.min(at-drag.at,s.duration-drag.end));setTrim(drag.start+delta,drag.end+delta)}
 });
 const release=()=>{drag=null};track.addEventListener('pointerup',release);track.addEventListener('pointercancel',release);track.addEventListener('lostpointercapture',release);
 track.addEventListener('keydown',e=>{
  const edge=e.target.dataset.edge;if(!edge||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
  e.preventDefault();const s=trimState,delta=(e.shiftKey?1:.1)*(e.key==='ArrowLeft'?-1:1);
  let value=e.key==='Home'?0:e.key==='End'?s.duration:s[edge]+delta;
  if(edge==='start')setTrim(Math.min(value,s.end-.05),s.end,{seek:true});else setTrim(s.start,Math.max(value,s.start+.05));
 });
};
const beforeTrimAction=action;
action=async function(a,el){
 if(a==='trim-zoom-in'||a==='trim-zoom-out'){changeTrimView(TrimViewport.zoom(trimState,a==='trim-zoom-in'?1.5:1/1.5));return}
 if(a==='trim-zoom-reset'){changeTrimView(TrimViewport.clamp(trimState.duration,0,trimState.duration));return}
 if(a==='trim-fit'){changeTrimView(TrimViewport.fit(trimState));return}
 if(a==='trim-reset'){if(trimState)setTrim(0,trimState.duration);return}
 if(a==='trim-preview'){
  if(!trimFromFields())return;trimState.preview=true;$('#player').currentTime=trimState.start;
  try{await $('#player').play()}catch(error){trimState.preview=false;toast('Не удалось воспроизвести видео: '+error.message,true)}return;
 }
 if(a==='export'&&trimState&&!trimFromFields())throw Error('Проверь выделенный отрезок');
 const result=await beforeTrimAction(a,el);
 if((a==='set-in'||a==='set-out')&&trimState)trimFromFields();
 if(a==='mark'&&trimState)updateTrimVisuals();
 return result;
};
document.addEventListener('input',e=>{if(['clipIn','clipOut'].includes(e.target.id))trimFromFields()});

const beforeCenteredOpen=openClip;
openClip=function(id){
 beforeCenteredOpen(id);if(!selected||!$('#player'))return;
 const editor=$('.editor'),left=editor.firstElementChild,right=editor.lastElementChild;
 const preview=document.createElement('div');preview.className='editor-preview';
 preview.append($('#player'));
 const actions=left.querySelector('.actions');if(actions)preview.append(actions);
 const below=document.createElement('div');below.className='editor-below';
 left.className='editor-card editor-export';right.className='editor-card editor-notes';
 const summary=document.createElement('div');summary.className='recording-summary';
 const gif=/\.gif$/i.test(selected.name);
 summary.innerHTML=`<span class="pill">${gif?'GIF':'ВИДЕО'}</span><span>${selected.width} × ${selected.height}</span><span>${fmt(selected.duration)}</span><span>${size(selected.size)}</span><span>${gif?'Без звука':'Аудиодорожек: '+selected.audio}</span>`;
 for(const element of [...right.children].slice(0,3))element.remove();
 right.insertAdjacentHTML('afterbegin','<div class="editor-card-head"><h3>Заметки</h3><small>Теги и избранное помогут найти момент</small></div>');
 const noteFields=document.createElement('div');noteFields.className='note-fields';
 noteFields.append($('#clipTags').closest('.field'),$('#clipNote').closest('.field'));
 right.querySelector('.editor-card-head').after(noteFields);
 const noteActions=right.querySelector('.actions');noteActions.classList.add('editor-card-actions');noteActions.removeAttribute('style');
 const notice=right.querySelector('.notice');if(notice){notice.className='hint editor-note-hint';notice.textContent='Заметки хранятся в библиотеке. Исходный файл сохраняется.'}
 const belowTitle=document.createElement('div');belowTitle.className='editor-card-head';belowTitle.innerHTML='<h3>Отрезок и экспорт</h3><small>Выдели момент и выбери формат</small>';left.prepend(belowTitle);
 const details=document.createElement('div');details.className='export-details';
 details.append($('#clipFormat').closest('.field'),$('#clipName').closest('.field'));left.querySelector('.time-inputs').after(details);
 const exportActions=document.createElement('div');exportActions.className='editor-card-actions export-actions';exportActions.append(left.querySelector('[data-action="export"]'));left.append(exportActions);
 below.append(left,right);editor.append(preview,summary,below);
 $('#dialog').classList.add('clip-dialog');$('#dialog').scrollTop=0;
 if(gif){
  const image=document.createElement('img');image.className='player';image.alt=selected.name;image.src=base+'media/'+selected.id;$('#player').replaceWith(image);
  left.remove();below.classList.add('gif-details');preview.querySelector('.actions').innerHTML=button('open-clip-folder','Открыть в папке','folder','quiet');trimState=null;
  right.querySelector('[data-action="delete-video"]').innerHTML=icon('trash')+'Удалить GIF';
 }else{
  $('#clipFormat').addEventListener('change',()=>{
   if($('#clipFormat').value==='gif'&&trimState){const start=trimState.start,end=Math.min(trimState.duration,start+Math.min(5,trimState.end-start));setTrim(start,end)}
   trimFromFields();
  });
 }
};
$('#dialog').addEventListener('close',()=>$('#dialog').classList.remove('clip-dialog'));
const beforeGifTrimValidation=trimFromFields;
trimFromFields=function(){
 const valid=beforeGifTrimValidation();if(!valid)return valid;
 const length=parse($('#clipOut').value)-parse($('#clipIn').value),gif=$('#clipFormat').value==='gif';
 const allowed=!gif||(length>=2&&length<=15);
 if(!allowed)$('#trimError').textContent='Для GIF выберите отрезок от 2 до 15 секунд.';
 $('[data-action="export"]').disabled=!allowed;
 return allowed;
};
