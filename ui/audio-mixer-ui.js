'use strict';
// Each source has its own media element, kept on the video's clock.
window.buildStudioMixer=function(current,metadata){
 if(studioEditor!==current)return;
 const box=$('.studio-listen'),status=$('#previewAudioStatus'),legacy=$('#previewAudioTrack');
 const tracks=metadata.audio.map(track=>({...track,enabled:track.index===0,gain:1,audio:new Audio(),loaded:false}));
 let nativeOriginal=true;
 const mixed=tracks.length>=3&&/общий|mix/i.test(tracks[0].title)?0:null;
 box.classList.add('studio-mixer');box.querySelector('label').hidden=true;legacy.hidden=true;
 const controls=document.createElement('div');controls.className='studio-audio-tracks';
 controls.innerHTML='<h3>Звуковые дорожки</h3><p class="hint">Включай нужные дорожки для прослушивания. Общий звук уже содержит все записанные источники.</p>'+tracks.map(track=>`<div class="studio-audio-track"><label class="check"><input type="checkbox" data-audio-track="${track.index}" ${track.enabled?'checked':''}>${esc(track.title)}</label><input type="range" data-audio-gain="${track.index}" min="0" max="100" step="1" value="100" aria-label="Громкость: ${esc(track.title)}"><output data-audio-level="${track.index}">100%</output></div>`).join('')+(tracks.length?'':'<p class="hint">В этой записи нет звука.</p>');
 box.prepend(controls);
 $('#exportTrackGains').hidden=true;
 const option=document.createElement('option');option.value='custom';option.textContent='Выбранные дорожки · как в прослушивании';$('#exportAudioMode').append(option);
 const exportHint=document.createElement('small');exportHint.className='hint';exportHint.textContent='После изменения дорожек экспорт использует их выбранный состав и громкость. В исходном файле остаются все дорожки.';box.append(exportHint);
 const abort=new AbortController(),on=(el,event,fn)=>el.addEventListener(event,fn,{signal:abort.signal});
 function align(track){
  track.audio.playbackRate=current.player.playbackRate;
  if(track.audio.readyState>=1&&Math.abs(track.audio.currentTime-current.player.currentTime)>.08)track.audio.currentTime=current.player.currentTime;
  track.audio.volume=Math.min(1,current.player.volume*track.gain);
 }
 function load(track){
  if(track.loaded)return;
  track.loaded=true;track.audio.preload='auto';track.audio.src=base+'audio-preview/'+current.id+'?track='+track.index;track.audio.load();
 }
 function play(track){
  if(nativeOriginal||!track.enabled)return;load(track);align(track);
  if(track.audio.readyState>=2)track.audio.play().catch(error=>{if(studioEditor===current)status.textContent='Звук: '+error.message});
 }
 function statusText(){
  const selected=tracks.filter(track=>track.enabled);
  status.textContent=selected.length?'Включено: '+selected.map(track=>track.title).join(' + '):'Все дорожки выключены';
 }
 function refresh(exportChanged=false){
  if(exportChanged)nativeOriginal=false;
  current.audio.pause();current.player.muted=!nativeOriginal;
  for(const track of tracks){
   controls.querySelector(`[data-audio-track="${track.index}"]`).checked=track.enabled;
   controls.querySelector(`[data-audio-gain="${track.index}"]`).disabled=!track.enabled;
   if(track.enabled&&!nativeOriginal){load(track);align(track);if(!current.player.paused)play(track)}else track.audio.pause();
  }
  if(exportChanged)$('#exportAudioMode').value='custom';statusText();
 }
 for(const track of tracks){
  on(track.audio,'loadedmetadata',()=>align(track));
  on(track.audio,'canplay',()=>{if(track.enabled&&!current.player.paused)play(track)});
  on(track.audio,'error',()=>{if(studioEditor===current&&track.enabled)status.textContent='Не удалось загрузить дорожку «'+track.title+'»'});
 }
 on(controls,'change',e=>{
  if(!e.target.matches('[data-audio-track]'))return;
  const track=tracks.find(t=>t.index===Number(e.target.dataset.audioTrack));track.enabled=e.target.checked;
  if(track.enabled&&mixed!==null){for(const other of tracks)if(other!==track&&(track.index===mixed||other.index===mixed))other.enabled=false}
  refresh(true);
 });
 on(controls,'input',e=>{
  if(!e.target.matches('[data-audio-gain]'))return;
  const track=tracks.find(t=>t.index===Number(e.target.dataset.audioGain));track.gain=Number(e.target.value)/100;
  controls.querySelector(`[data-audio-level="${track.index}"]`).textContent=e.target.value+'%';refresh(true);
 });
 on(current.player,'volumechange',()=>tracks.forEach(align));
 current.mixer={tracks,seek:()=>tracks.filter(t=>t.enabled).forEach(align),play:()=>tracks.forEach(play),pause:()=>tracks.forEach(t=>t.audio.pause()),rate:()=>tracks.forEach(align),
  select(value){nativeOriginal=value==='original';for(const track of tracks)track.enabled=track.index===Number(value==='original'?0:value);refresh()},
  export:()=>tracks.filter(t=>t.enabled).map(t=>({index:t.index,gain:Math.round(t.gain*100)})),
  dispose(){abort.abort();for(const track of tracks){track.audio.pause();track.audio.removeAttribute('src');track.audio.load()}}
 };
 refresh();
};
