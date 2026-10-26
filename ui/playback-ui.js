'use strict';
// Playback speed affects the viewer; elapsed time uses the selected source frames.
let disposePlayback=()=>{};
const beforePlaybackOpen=openClip;
const elapsedLabel=seconds=>{
 const ms=Math.max(0,Math.floor((Number(seconds)||0)*1000+.0001));
 return `${String(Math.floor(ms/60000)).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}.${String(ms%1000).padStart(3,'0')}`;
};
openClip=function(id){
 disposePlayback();beforePlaybackOpen(id);
 const player=$('#player');if(!player||player.tagName!=='VIDEO')return;
 let enabled=false,speed=1;
 try{enabled=localStorage.getItem('afterplay.timer')==='true';speed=Number(localStorage.getItem('afterplay.speed'))||1}catch{}
 speed=Math.min(4,Math.max(.1,speed));
 const stage=document.createElement('div');stage.className='playback-stage';
 player.before(stage);stage.append(player);
 const timer=document.createElement('output');timer.id='videoTimer';timer.className='video-timer';timer.hidden=!enabled;timer.textContent='00:00.000';stage.append(timer);
 // Native video fullscreen renders its own caption layer. A cue keeps the
 // timer in that layer without another top-layer popup intercepting Escape.
 const timerTrack=player.addTextTrack('captions','Таймер','ru');
 const timerCue=new VTTCue(0,86400,'00:00.000');
 timerCue.snapToLines=false;timerCue.line=2.5;timerCue.lineAlign='start';
 timerCue.position=97.5;timerCue.positionAlign='line-right';timerCue.align='end';timerCue.size=35;
 timerTrack.addCue(timerCue);timerTrack.mode='disabled';
 const controls=document.createElement('section');controls.className='playback-controls';controls.setAttribute('aria-label','Скорость и таймер');
 controls.innerHTML=`<div class="speed-row"><label for="playbackSpeedRange">Скорость просмотра</label><input id="playbackSpeedRange" type="range" min="0.1" max="4" step="0.01" value="${speed}" aria-label="Скорость воспроизведения"><div class="speed-number"><input id="playbackSpeed" type="text" inputmode="decimal" value="${String(speed).replace('.',',')}" aria-label="Точная скорость воспроизведения"><span>×</span></div></div><div class="actions speed-presets">${[.1,.25,.5,.75,1,1.5,2].map(n=>`<button type="button" class="button quiet" data-rate="${n}">${String(n).replace('.',',')}×</button>`).join('')}</div><div class="actions timer-actions"><label class="check"><input id="previewTimer" type="checkbox" ${enabled?'checked':''}> Таймер в углу видео · мин:сек.мс</label></div><small class="hint">Скорость просмотра: 0,1–4×. Таймер отсчитывает время от начала выделенного отрезка. Экспорт сохраняет исходную скорость.</small>`;
 stage.after(controls);
 const exportOption=document.createElement('div');exportOption.className='field export-timer-option';
 exportOption.innerHTML=`<label class="check"><input id="exportTimer" type="checkbox" ${enabled?'checked':''}> Добавить таймер в экспорт</label><small>Минуты, секунды и миллисекунды в правом верхнем углу MP4 или GIF. Отсчёт от начала отрезка.</small>`;
 $('.export-details').append(exportOption);
 const controller=new AbortController(),on=(el,event,fn)=>el.addEventListener(event,fn,{signal:controller.signal});
 let frame=null,disposed=false,wasFullscreen=false,lastFullscreenExit=-1000;
 function remember(key,value){try{localStorage.setItem(key,String(value))}catch{}}
 function updateTimer(time=window.studioFrameTime?.()??player.currentTime){
  const value=Math.max(0,time-(trimState?.start||0)),cfg=typeof customSettings==='function'?customSettings():{};
  const label=cfg.timer_format==='frames'?'Кадр '+Math.floor(value*(studioEditor?.metadata?.fps||60)+.0001):cfg.timer_format==='seconds'?elapsedLabel(value).split('.')[0]:elapsedLabel(value);
  timer.textContent=window.afterplayI18n?.text(label)||label;timerCue.text=timer.textContent;
 }
 function positionTimer(){
  const rect=player.getBoundingClientRect(),ratio=(player.videoWidth/player.videoHeight)||16/9;
  const width=Math.min(rect.width,rect.height*ratio),height=width/ratio;
  const cfg=typeof customSettings==='function'?customSettings():{},x=(cfg.timer_x??97.5)/100,y=(cfg.timer_y??2.5)/100;
  timer.style.fontSize=Math.max(10,height*.032*(cfg.timer_size??100)/100)+'px';
  timer.style.fontFamily=cfg.timer_font==='sans'?"'AFTERPLAY Inter',sans-serif":'Consolas,monospace';
  timer.style.color=cfg.timer_color||'#ffffff';timer.style.background=`rgba(0,0,0,${(cfg.timer_background??65)/100})`;
  timer.style.top=((rect.height-height)/2+(height-timer.offsetHeight)*y)+'px';
  timer.style.left=((rect.width-width)/2+(width-timer.offsetWidth)*x)+'px';timer.style.right='auto';
  timerCue.position=cfg.timer_x??97.5;timerCue.line=cfg.timer_y??2.5;
 }
 function setTimer(value){
  enabled=value;timer.hidden=!value;$('#previewTimer').checked=value;$('#exportTimer').checked=value;
  timerTrack.mode=value&&player.matches(':fullscreen')?'showing':'disabled';
  remember('afterplay.timer',value);updateTimer();positionTimer();
 }
 function setSpeed(value,{format=true,quiet=false}={}){
  const rate=Number(String(value).trim().replace(',','.'));
  if(!Number.isFinite(rate)||rate<.1||rate>4){if(!quiet)toast('Укажи скорость от 0,1 до 4×',true);return false}
  try{player.playbackRate=rate;speed=rate;remember('afterplay.speed',rate)}catch(error){toast(error.message,true);return false}
  $('#playbackSpeedRange').value=rate;if(format)$('#playbackSpeed').value=String(rate).replace('.',',');
  for(const button of controls.querySelectorAll('[data-rate]'))button.setAttribute('aria-pressed',Number(button.dataset.rate)===rate?'true':'false');
  return true;
 }
 function stopFrames(){if(frame!==null){if(player.cancelVideoFrameCallback)player.cancelVideoFrameCallback(frame);else cancelAnimationFrame(frame);frame=null}}
 function nextFrame(){
  if(disposed||player.paused||player.ended)return;
  if(player.requestVideoFrameCallback)frame=player.requestVideoFrameCallback((_,meta)=>{updateTimer(meta.mediaTime);nextFrame()});
  else frame=requestAnimationFrame(()=>{updateTimer();nextFrame()});
 }
 on($('#playbackSpeedRange'),'input',e=>setSpeed(e.target.value));
 on($('#playbackSpeed'),'input',e=>setSpeed(e.target.value,{format:false,quiet:true}));
 on($('#playbackSpeed'),'change',e=>{if(!setSpeed(e.target.value))e.target.value=String(speed).replace('.',',')});
 on($('#playbackSpeed'),'keydown',e=>{if(e.key==='Enter'){e.preventDefault();if(!setSpeed(e.target.value))e.target.value=String(speed).replace('.',',');e.target.blur()}});
 on(controls,'click',e=>{const button=e.target.closest('[data-rate]');if(button)setSpeed(button.dataset.rate)});
 on($('#previewTimer'),'change',e=>setTimer(e.target.checked));on($('#exportTimer'),'change',e=>setTimer(e.target.checked));
 on(player,'play',()=>{stopFrames();nextFrame()});
 on(player,'pause',()=>{stopFrames();updateTimer()});
 for(const event of ['seeked','timeupdate','loadedmetadata','ended'])on(player,event,()=>{updateTimer();positionTimer()});
 on(player,'ratechange',()=>{speed=player.playbackRate;$('#playbackSpeedRange').value=speed;if(document.activeElement!==$('#playbackSpeed'))$('#playbackSpeed').value=String(speed).replace('.',',')});
 on(document,'input',e=>{if(['clipIn','clipOut'].includes(e.target.id))updateTimer()});
 on(document,'afterplay-trim',()=>updateTimer());
 on(document,'afterplay-frame',e=>updateTimer(e.detail.time));
 // Escape can be delivered to the editor while native media fullscreen is
 // active. Exit fullscreen explicitly before the dialog's cancel default.
 document.addEventListener('keydown',e=>{
  if(e.key==='Escape'&&document.fullscreenElement){
   e.preventDefault();e.stopImmediatePropagation();
   document.exitFullscreen().catch(error=>toast(error.message,true));
  }
 },{capture:true,signal:controller.signal});
 on(document,'fullscreenchange',()=>{
  timerTrack.mode=enabled&&player.matches(':fullscreen')?'showing':'disabled';
  const active=document.fullscreenElement===stage||document.fullscreenElement===player;
  if(wasFullscreen&&!active)lastFullscreenExit=performance.now();
  wasFullscreen=active;positionTimer();
 });
 $('#dialog').addEventListener('cancel',e=>{
  if(wasFullscreen||performance.now()-lastFullscreenExit<500){
   e.preventDefault();e.stopImmediatePropagation();
   if(document.fullscreenElement)document.exitFullscreen().catch(error=>toast(error.message,true));
  }
 },{capture:true,signal:controller.signal});
 const observer=new ResizeObserver(positionTimer);observer.observe(stage);
 setSpeed(speed);setTimer(enabled);
 disposePlayback=()=>{disposed=true;stopFrames();timerTrack.mode='disabled';observer.disconnect();controller.abort();disposePlayback=()=>{}};
};
$('#dialog').addEventListener('close',()=>disposePlayback());
