'use strict';
// Local studio additions: profiles, session bookmarks, exact frames and audio tracks.
const studioBusy=()=>['starting','recording','stopping'].includes(state.replay?.phase)||state.replay?.saving;
const studioProfiles=()=>Object.values(state.settings.capture_profiles||{}).sort((a,b)=>a.name.localeCompare(b.name));
let studioEditor=null,studioFrameQueue=Promise.resolve();
window.studioFrameDuration=()=>studioEditor?.metadata?.fps?1/studioEditor.metadata.fps:.05;
window.studioFrameTime=()=>studioEditor?.exactTime;
window.studioChatPath=function(){
 const select=$('#replayChat'),value=select?.value,cfg=state.replay?.settings||{};
 if(value==='auto')return '';
 if(value==='saved'||!select)return cfg.chat_path||'';
 return (replayDevices?.audio_applications||[]).find(a=>String(a.pid)===value)?.path||cfg.chat_path||'';
};
function installChatSelector(){
 if(tab!=='replay'||!$('#replayAudioMode'))return;
 if(!$('#replayChatField'))$('#replayAudioMode').closest('.field').insertAdjacentHTML('afterend',`<div class="field" id="replayChatField"><label for="replayChat">Приложение чата</label><select id="replayChat"></select><small>В MP4: общий звук, только игра, только чат. Микрофон не записывается. Discord определяется и при сворачивании в трей.</small></div>`);
 const select=$('#replayChat'),cfg=state.replay?.settings||{},rows=replayDevices?.audio_applications||[];
 const signature=JSON.stringify(rows.map(a=>[a.pid,a.path]));
 if(select.dataset.signature!==signature&&!select.matches(':focus')&&!window.afterplayDropdowns?.isOpen('replayChat')){
  const old=select.value,match=rows.find(a=>a.path.toLowerCase()===(cfg.chat_path||'').toLowerCase());
  select.innerHTML='<option value="auto">Автоматически найти Discord</option>'+(cfg.chat_path&&!match?`<option value="saved">${esc(cfg.chat_path.split('\\').pop())} · запусти приложение</option>`:'')+rows.map(a=>`<option value="${a.pid}">${esc(a.name)} · PID ${a.pid}</option>`).join('');
  const previous=[...select.options].some(o=>o.value===old)?old:null;
  select.value=previous||(match?String(match.pid):cfg.chat_path?'saved':'auto');select.dataset.signature=signature;
 }
 select.disabled=!!studioBusy();$('#replayChatField').hidden=$('#replayAudioMode').value!=='multitrack';
}
const beforeStudioReplayUpdate=window.updateReplay;
window.updateReplay=function(){
 beforeStudioReplayUpdate?.();
 if($('#liveMark'))$('#liveMark').disabled=state.replay?.phase!=='recording';
 if($('#liveMarkCount'))$('#liveMarkCount').textContent=`Метки: ${state.replay?.marker_count||0}`;
 window.updateProfileControls?.();
 installChatSelector();
};
const beforeStudioExtras=window.renderDesktopExtras;
window.renderDesktopExtras=function(){
 beforeStudioExtras?.();if(tab!=='settings')return;
 const card=$('#windowHotkey')?.closest('.settings-card');
 if(card&&!$('#markHotkey'))$('#windowHotkey').closest('.field').insertAdjacentHTML('afterend',`<div class="field"><label for="markHotkey">Отметить момент во время записи · необязательно</label><input class="hotkey-input" id="markHotkey" value="${esc(state.settings.hotkeys?.mark||'')}" placeholder="Не назначена" autocomplete="off" spellcheck="false"><small>Оставь пустым, чтобы использовать кнопку или меню трея. Существующие сочетания сохраняются.</small></div>`);
};
function closeStudioEditor(){
 const current=studioEditor;studioEditor=null;
 if(!current)return;current.mixer?.dispose();clearTimeout(current.waveTimer);current.abort.abort();current.observer?.disconnect();
 if(current.audio){current.audio.pause();current.audio.removeAttribute('src');current.audio.load()}
}
function drawWave(){
 const current=studioEditor,canvas=$('#audioWaveform');if(!current||!canvas||!trimState)return;
 const dpr=window.devicePixelRatio||1,width=canvas.clientWidth,height=72;
 canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
 const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.clearRect(0,0,width,height);
 const range=trimState.viewEnd-trimState.viewStart,px=t=>(t-trimState.viewStart)/range*width;
 ctx.fillStyle='rgba(183,152,80,.16)';ctx.fillRect(px(trimState.start),0,px(trimState.end)-px(trimState.start),height);
 const peaks=current.wave?.peaks||[],maximum=Math.max(.08,...peaks),scale=(height/2-4)/maximum;
 ctx.strokeStyle=getComputedStyle(canvas).color;ctx.beginPath();
 for(let i=0;i<peaks.length;i++){const x=i/peaks.length*width,y=Math.max(.6,Math.min(height/2-3,peaks[i]*scale));ctx.moveTo(x,height/2-y);ctx.lineTo(x,height/2+y)}ctx.stroke();
 const time=current.exactTime??current.player.currentTime;
 if(time>=trimState.viewStart&&time<=trimState.viewEnd){ctx.strokeStyle='#f3d287';ctx.beginPath();ctx.moveTo(px(time),0);ctx.lineTo(px(time),height);ctx.stroke()}
}
function scheduleWave(){
 const current=studioEditor;if(!current||!current.metadata||!trimState)return;
 const start=trimState.viewStart,end=trimState.viewEnd,track=Number($('#waveTrack')?.value||0),key=[start.toFixed(3),end.toFixed(3),track].join(':');
 if(current.waveKey===key)return;current.waveKey=key;current.wave=null;drawWave();clearTimeout(current.waveTimer);
 if($('#waveStatus'))$('#waveStatus').textContent='Строю звуковую волну…';
 current.waveTimer=setTimeout(async()=>{
  try{const value=await api('clip_waveform',{id:current.id,start,end,track});if(studioEditor!==current||current.waveKey!==key)return;current.wave=value;$('#waveStatus').textContent=value.peaks.length?(value.silent?'На участке тишина':'Нажми на волну, чтобы перейти к моменту'):'В записи нет звука';drawWave()}
  catch(error){if(studioEditor===current&&$('#waveStatus'))$('#waveStatus').textContent=error.message}
 },400);
}
async function stepFrame(direction){
 const current=studioEditor;if(!current)return;
 current.player.pause();current.audio.pause();
 const result=await api('clip_frame_step',{id:current.id,time:current.exactTime??current.player.currentTime,direction});
 if(studioEditor!==current)return;
 await new Promise(resolve=>{const done=()=>resolve();current.player.addEventListener('seeked',done,{once:true});current.player.currentTime=result.time;setTimeout(done,700)});
 if(studioEditor!==current)return;
 current.image.src=result.image;current.image.hidden=false;current.exactTime=result.time;
 document.dispatchEvent(new CustomEvent('afterplay-frame',{detail:{time:result.time}}));
 $('#framePosition').textContent=trimFormat(result.time);updateTrimVisuals();
}
const beforeStudioOpen=openClip;
openClip=function(id){
 closeStudioEditor();beforeStudioOpen(id);
 const player=$('#player');if(!player||player.tagName!=='VIDEO')return;
 const abort=new AbortController(),on=(object,event,callback)=>object.addEventListener(event,callback,{signal:abort.signal});
 const current=studioEditor={id,player,abort,audio:new Audio(),wave:null,waveKey:null,exactTime:null};
 const stage=$('.playback-stage')||player.parentElement;
 const image=document.createElement('img');image.id='preciseFrame';image.className='studio-precise-frame';image.alt='Точный кадр';image.hidden=true;stage.append(image);current.image=image;
 $('.playback-controls').insertAdjacentHTML('beforeend',`<div class="actions studio-frame-controls">${button('frame-prev','Предыдущий кадр','arrow','quiet')}${button('frame-next','Следующий кадр','arrow','quiet')}<output id="framePosition">00:00:00.000</output><small>← / → — покадрово</small></div>`);
 $('#trimTrack').insertAdjacentHTML('afterend',`<section class="studio-wave"><div class="studio-wave-head"><label for="waveTrack">Звуковая волна</label><select id="waveTrack" aria-label="Дорожка звуковой волны"><option value="0">Общий звук</option></select><small id="sourceFps"></small></div><canvas id="audioWaveform" height="72" aria-label="Звуковая волна; нажми для перехода к моменту"></canvas><small id="waveStatus" aria-live="polite">Читаю дорожки…</small></section>`);
 $('.export-details').insertAdjacentHTML('beforeend',`<div class="field"><label for="exportAudioMode">Звук в MP4</label><select id="exportAudioMode"><option value="all">Сохранить все дорожки</option><option value="mix">Только общий звук</option><option value="none">Без звука</option></select></div><div id="exportTrackGains" class="studio-gain-grid" hidden><label>Игра: <output id="gameGainLabel">100%</output><input id="exportGameGain" type="range" min="0" max="100" value="100"></label><label>Discord / чат: <output id="chatGainLabel">100%</output><input id="exportChatGain" type="range" min="0" max="100" value="100"></label><small>Громкость при экспорте. Исходная запись сохраняется.</small></div>`);
 $('.playback-controls').insertAdjacentHTML('beforeend',`<div class="studio-listen"><label for="previewAudioTrack">Прослушивание</label><select id="previewAudioTrack"><option value="original">Общий звук</option></select><small id="previewAudioStatus"></small></div>`);
 function clearExact(){current.exactTime=null;image.hidden=true}
 function alignAudio(){if(current.mixer){current.mixer.seek();return}if($('#previewAudioTrack')?.value==='original')return;current.audio.currentTime=player.currentTime;current.audio.playbackRate=player.playbackRate}
 on(player,'seeking',()=>{clearExact();alignAudio();drawWave()});
 on(player,'timeupdate',()=>{if(current.exactTime===null)$('#framePosition').textContent=trimFormat(player.currentTime);if(current.mixer||(!current.audio.paused&&Math.abs(current.audio.currentTime-player.currentTime)>.15))alignAudio();drawWave()});
 on(player,'play',()=>{clearExact();if(current.mixer){current.mixer.play();return}if($('#previewAudioTrack').value!=='original'){alignAudio();current.audio.play().catch(error=>$('#previewAudioStatus').textContent='Не удалось воспроизвести дорожку: '+error.message)}});
 on(player,'pause',()=>{current.audio.pause();current.mixer?.pause()});on(player,'ended',()=>{current.audio.pause();current.mixer?.pause()});on(player,'ratechange',()=>{current.audio.playbackRate=player.playbackRate;current.mixer?.rate()});
 on($('#waveTrack'),'change',scheduleWave);
 on($('#audioWaveform'),'pointerdown',e=>{const rect=e.currentTarget.getBoundingClientRect();player.currentTime=trimState.viewStart+Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width))*(trimState.viewEnd-trimState.viewStart);clearExact();drawWave()});
 on($('#previewAudioTrack'),'change',async e=>{
  if(current.mixer){current.mixer.select(e.target.value);return}
  current.audio.pause();const value=e.target.value;
  if(value==='original'){player.muted=false;$('#previewAudioStatus').textContent='';return}
  player.pause();player.muted=true;$('#previewAudioStatus').textContent='Готовлю дорожку…';
  current.audio.src=base+'audio-preview/'+id+'?track='+value;current.audio.preload='auto';
  current.audio.onloadedmetadata=()=>{if(studioEditor!==current)return;alignAudio();$('#previewAudioStatus').textContent='Готово · нажми воспроизведение'};
  current.audio.onerror=()=>{if(studioEditor===current)$('#previewAudioStatus').textContent='Не удалось подготовить звук; выбери общий звук и попробуй снова'};
  current.audio.load();
 });
 on($('#exportGameGain'),'input',e=>$('#gameGainLabel').textContent=e.target.value+'%');on($('#exportChatGain'),'input',e=>$('#chatGainLabel').textContent=e.target.value+'%');
 current.observer=new ResizeObserver(drawWave);current.observer.observe($('#audioWaveform'));
 api('clip_media_info',{id}).then(metadata=>{
  if(studioEditor!==current)return;current.metadata=metadata;
  $('#sourceFps').textContent=metadata.fps.toFixed(3).replace(/\.?0+$/,'')+' FPS';
  $('#waveTrack').innerHTML=metadata.audio.map(a=>`<option value="${a.index}">${esc(a.title)}</option>`).join('')||'<option value="0">Без звука</option>';
  $('#previewAudioTrack').innerHTML='<option value="original">Общий звук · из видео</option>'+metadata.audio.map(a=>`<option value="${a.index}">${esc(a.title)}</option>`).join('');
  if(metadata.audio.length>=3){$('#exportAudioMode').insertAdjacentHTML('beforeend','<option value="game">Только игра</option><option value="chat">Только Discord / чат</option>');$('#exportTrackGains').hidden=false}
  window.buildStudioMixer?.(current,metadata);scheduleWave();
 }).catch(error=>{if(studioEditor===current)$('#waveStatus').textContent=error.message});
};
const beforeStudioTrimVisuals=updateTrimVisuals;
updateTrimVisuals=function(){beforeStudioTrimVisuals();drawWave();scheduleWave()};
$('#dialog').addEventListener('close',closeStudioEditor);
document.addEventListener('keydown',e=>{
 if(!studioEditor||e.ctrlKey||e.altKey||e.metaKey||e.target.closest('input,textarea,select,summary,[contenteditable=true],[role=tab],[role=combobox],[role=listbox],[data-edge]'))return;
 if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();e.stopImmediatePropagation();studioFrameQueue=studioFrameQueue.catch(()=>{}).then(()=>stepFrame(e.key==='ArrowLeft'?-1:1)).catch(error=>toast(error.message,true))}
},{capture:true});
const beforeStudioAction=action;
action=async function(a,el){
 if(a==='live-mark'){const value=await api('replay_mark');toast('Момент отмечен: '+trimFormat(value.time));return}
 if(a==='hotkeys-save'){
  const values={save:$('#saveHotkey').value,auto:$('#autoHotkey').value,window:$('#windowHotkey').value,mark:$('#markHotkey')?.value||''};
  state.settings.hotkeys=await api('hotkeys_config',values);await refresh();toast('Горячие клавиши сохранены');return;
 }
 if(a==='frame-prev'||a==='frame-next'){studioFrameQueue=studioFrameQueue.catch(()=>{}).then(()=>stepFrame(a==='frame-prev'?-1:1));await studioFrameQueue;return}
 if((a==='set-in'||a==='set-out')&&studioEditor&&trimState){const time=studioEditor.exactTime??studioEditor.player.currentTime;if(a==='set-in')setTrim(Math.min(time,trimState.end-.001),trimState.end);else setTrim(trimState.start,Math.max(time,trimState.start+.001));return}
 return beforeStudioAction(a,el);
};
