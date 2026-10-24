'use strict';
let trimState=null;
const trimFormat=value=>{
 const ms=Math.max(0,Math.round((Number(value)||0)*1000));
 return `${String(Math.floor(ms/3600000)).padStart(2,'0')}:${String(Math.floor(ms/60000)%60).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;
};
function updateTrimVisuals(){
 const s=trimState;if(!s||!$('#trimTrack'))return;
 const start=100*s.start/s.duration,end=100*s.end/s.duration;
 $('#trimSelection').style.left=start+'%';$('#trimSelection').style.width=(end-start)+'%';
 $('#trimBefore').style.width=start+'%';$('#trimAfter').style.width=(100-end)+'%';
 for(const edge of ['start','end']){
  const handle=$('#trim'+(edge==='start'?'Start':'End'));
  handle.style.left=100*s[edge]/s.duration+'%';handle.setAttribute('aria-valuenow',s[edge].toFixed(3));
  handle.setAttribute('aria-valuetext',trimFormat(s[edge]));
 }
 $('#trimSummary').textContent=`Выбрано ${trimFormat(s.end-s.start)} из ${trimFormat(s.duration)}`;
 $('#trimStartLabel').textContent=trimFormat(s.start);$('#trimEndLabel').textContent=trimFormat(s.end);
 const time=$('#player')?.currentTime||0;$('#trimPlayhead').style.left=Math.min(100,100*time/s.duration)+'%';
 $('#trimMarks').innerHTML=marks.map(value=>`<span style="left:${100*value/s.duration}%" title="Отметка ${trimFormat(value)}"></span>`).join('');
}
function setTrim(start,end,{seek=false,fields=true}={}){
 const s=trimState;if(!s)return;
 const minimum=Math.min(.05,s.duration);
 s.start=Math.max(0,Math.min(Number(start)||0,s.duration-minimum));
 s.end=Math.min(s.duration,Math.max(Number(end)||0,s.start+minimum));
 if(fields){$('#clipIn').value=trimFormat(s.start);$('#clipOut').value=trimFormat(s.end)}
 if(seek&&$('#player'))$('#player').currentTime=s.start;
 updateTrimVisuals();
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
 const duration=Math.max(.001,Number(selected.duration)||.001);
 trimState={id,duration,start:0,end:duration,preview:false};
 const panel=`<section class="trim-panel" aria-label="Выделение отрезка"><div class="trim-heading"><b>Выдели нужный момент</b><small>В экспорт попадёт подсвеченный участок</small></div><div class="trim-track" id="trimTrack"><img class="trim-filmstrip" id="trimFilmstrip" src="${base}filmstrip/${id}" alt="Кадры видео для выбора отрезка" draggable="false"><div class="trim-shade before" id="trimBefore"></div><div class="trim-shade after" id="trimAfter"></div><div class="trim-selection" id="trimSelection" title="Перетащи выделение целиком"></div><div id="trimMarks" class="trim-marks"></div><div class="trim-playhead" id="trimPlayhead"></div><button class="trim-handle" id="trimStart" data-edge="start" role="slider" aria-label="Начало отрезка" aria-valuemin="0" aria-valuemax="${duration}" type="button"><span></span></button><button class="trim-handle" id="trimEnd" data-edge="end" role="slider" aria-label="Конец отрезка" aria-valuemin="0" aria-valuemax="${duration}" type="button"><span></span></button></div><div class="trim-labels"><span id="trimStartLabel"></span><b id="trimSummary"></b><span id="trimEndLabel"></span></div><div class="actions">${button('trim-preview','Посмотреть выделенное','play','secondary')}${button('trim-reset','Всё видео','refresh','quiet')}</div><p class="hint" id="trimHint">Перетащи границы. Стрелки на выбранной границе меняют время на 0,1 с; Shift — на 1 с.</p><p id="trimError" class="hint error-text" aria-live="polite"></p></section>`;
 $('.editor .time-inputs').insertAdjacentHTML('beforebegin',panel);
 $('#clipIn').setAttribute('aria-label','Начало отрезка, часы минуты секунды');
 $('#clipOut').setAttribute('aria-label','Конец отрезка, часы минуты секунды');
 setTrim(0,duration);
 const player=$('#player');
 player.addEventListener('loadedmetadata',()=>{
  if(!trimState||trimState.id!==id||!Number.isFinite(player.duration))return;
  const all=Math.abs(trimState.end-trimState.duration)<.05;
  trimState.duration=player.duration;
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
 const position=e=>{const rect=track.getBoundingClientRect();return Math.max(0,Math.min(trimState.duration,(e.clientX-rect.left)/rect.width*trimState.duration))};
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
