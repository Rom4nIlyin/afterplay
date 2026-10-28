'use strict';
// A quiet viewer by default. Editing tools keep their existing nodes and handlers.
window.reviewLayoutEnabled=true;
let reviewState=null;
const reviewIcons={
 pause:'<path d="M8 5v14M16 5v14"/>',
 back:'<path d="M6 5v14m12-14-9 7 9 7z"/>',
 next:'<path d="M18 5v14M6 5l9 7-9 7z"/>',
 expand:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
 volume:'<path d="m11 5-6 4H2v6h3l6 4zM15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>',
 mute:'<path d="m11 5-6 4H2v6h3l6 4zM16 9l6 6m0-6-6 6"/>'
};
function reviewIcon(name){return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${reviewIcons[name]||icons[name]||icons.file}</svg>`}
// Fullscreen UI visibility.
function installFullscreenUI({stage,controls,seek,player,on,signal,delay=1500}){
 let timer=null,dragging=false,disposed=false,inside=true;
 const active=()=>document.fullscreenElement===stage;
 function cancel(){if(timer!==null){clearTimeout(timer);timer=null}}
 function setHidden(hidden){
  if(hidden&&(controls.contains(document.activeElement)||document.activeElement===seek))stage.focus({preventScroll:true});
  stage.classList.toggle('review-controls-hidden',hidden);
  controls.inert=hidden;seek.inert=hidden;
 }
 function hide(force=false){
  cancel();
  if(!active()||disposed){setHidden(false);return}
  if(!force&&(dragging||controls.querySelector('details[open]')))return;
  if(force)dragging=false;
  setHidden(true);
 }
 function show(){
  cancel();if(active()&&!inside){setHidden(true);return}setHidden(false);
  if(active()&&!disposed)timer=setTimeout(()=>hide(),delay);
 }
 function leave(){inside=false;hide(true)}
 function enter(){inside=true;show()}
 on(stage,'pointermove',enter);on(stage,'pointerenter',enter);
 on(stage,'pointerleave',leave);on(window,'blur',leave);
 on(document,'pointerout',event=>{if(event.relatedTarget===null)leave()});
 on(stage,'pointerdown',event=>{dragging=controls.contains(event.target)||event.target===seek;show()});
 on(window,'pointerup',()=>{if(dragging){dragging=false;show()}});
 controls.addEventListener('toggle',show,{capture:true,signal});
 on(player,'play',show);on(player,'pause',show);on(player,'seeked',show);
 on(document,'afterplay-frame',show);
 signal.addEventListener('abort',()=>{disposed=true;cancel();setHidden(false)},{once:true});
 return {show,update(){inside=true;show()}};
}
// End fullscreen UI visibility.
function reviewDispose(){
 const current=reviewState;reviewState=null;
 if(current){current.abort.abort();current.observer?.disconnect()}
 const dialog=$('#dialog');dialog.classList.remove('review-dialog');delete dialog.dataset.editing;delete dialog.dataset.kind;
 dialog.style.removeProperty('width');dialog.style.removeProperty('height');delete dialog.dataset.vertical;
}
const beforeReviewModal=modal;
modal=function(title,body,actions=''){
 if(reviewState){reviewDispose();closeStudioEditor();disposePlayback();clearTimeout(trimImageTimer);trimImageRequest++}
 return beforeReviewModal(title,body,actions);
};
function reviewClock(){
 const current=reviewState;if(!current?.player)return;
 const player=current.player,time=studioEditor?.exactTime??player.currentTime;
 const label=studioEditor?.exactTime!=null?trimFormat(time):fmt(time).replace(/^00:/,'');
 $('#reviewClock').textContent=label;
 $('#reviewTotal').textContent='/ '+fmt(Number.isFinite(player.duration)?player.duration:selected?.duration||0).replace(/^00:/,'');
 const seek=$('#reviewSeek');seek.max=Number.isFinite(player.duration)?player.duration:selected?.duration||1;
 if(!current.seeking)seek.value=time;
 seek.style.setProperty('--seek-fill',`${Math.max(0,Math.min(100,time/Number(seek.max)*100))}%`);
 $('#reviewPlay').innerHTML=reviewIcon(player.paused?'play':'pause');
 $('#reviewPlay').title=player.paused?'Воспроизвести':'Пауза';$('#reviewPlay').setAttribute('aria-label',$('#reviewPlay').title);
 $('#reviewSpeedLabel').textContent=String(Number(player.playbackRate.toFixed(2))).replace('.',',')+'×';
 if($('#reviewSelection'))$('#reviewSelection').textContent=trimState?`Отрезок ${trimFormat(trimState.end-trimState.start)}`:'Вся запись';
}
function reviewSetMode(editing,pane=null){
 const current=reviewState;if(!current)return;
 if(pane)current.pane=pane;
 current.editing=!!editing;$('#dialog').dataset.editing=String(current.editing);
 if(current.editing){$('#dialog').style.removeProperty('width');$('#dialog').style.removeProperty('height')}
 current.aside.hidden=!current.editing;
 if(current.timeline)current.timeline.hidden=!current.editing;
 for(const tab of current.aside.querySelectorAll('[data-review-pane]')){
  const active=tab.dataset.reviewPane===current.pane;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1;
 }
 for(const panel of current.aside.querySelectorAll('[data-review-panel]'))panel.hidden=panel.dataset.reviewPanel!==current.pane;
 const edit=$('[data-action="review-edit"]');edit.innerHTML=icon(current.editing?'play':'settings')+(current.editing?'Просмотр':current.gif?'Заметки':'Монтаж');edit.setAttribute('aria-expanded',String(current.editing));
 const exportButton=current.aside.querySelector('[data-action="export"]');if(exportButton)exportButton.innerHTML=icon('download')+(current.pane==='export'?'Сохранить клип':'К экспорту');
 if(!current.editing&&current.aside.contains(document.activeElement))edit.focus({preventScroll:true});
 if(current.editing&&current.timeline){
  window.requestTrimFilmstrip?.();const strip=$('#trimFilmstrip');if(strip?.dataset.src){strip.src=strip.dataset.src;delete strip.dataset.src}
  requestAnimationFrame(()=>{if(reviewState!==current)return;updateTrimVisuals();scheduleWave()});
 }
 reviewClock();
 reviewFitViewer();
}
function reviewFitViewer(){
 const current=reviewState,dialog=$('#dialog');
 if(!current?.player||current.editing||!dialog.open)return;
 const player=current.player,ratio=(player.videoWidth||selected?.width||16)/(player.videoHeight||selected?.height||9);
 dialog.dataset.vertical=String(ratio<1);
 const viewer=dialog.querySelector('.review-viewer'),header=dialog.querySelector('.dialog-head');if(!viewer||!header)return;
 const style=getComputedStyle(viewer),px=x=>Number.parseFloat(x)||0;
 const paddingX=px(style.paddingLeft)+px(style.paddingRight),paddingY=px(style.paddingTop)+px(style.paddingBottom);
 const controls=dialog.querySelector('.review-transport')?.getBoundingClientRect().height||52;
 const chrome=header.getBoundingClientRect().height+paddingY+20+controls+px(style.rowGap)*2+2;
 const maxHeight=Math.floor(innerHeight*.94),maxWidth=Math.min(1560,innerWidth*.96);
 const videoWidth=Math.max(100,Math.min(maxWidth-paddingX-2,(maxHeight-chrome)*ratio));
 const width=Math.ceil(videoWidth+paddingX+2)+'px',height=Math.ceil(videoWidth/ratio+chrome)+'px';
 const changed=dialog.style.width!==width||dialog.style.height!==height;
 dialog.style.width=width;dialog.style.height=height;
 if(changed)requestAnimationFrame(reviewFitViewer);
}
window.addEventListener('resize',()=>requestAnimationFrame(reviewFitViewer));
function reviewPanel(name,label){
 const panel=document.createElement('section');panel.className='review-tool-panel';panel.dataset.reviewPanel=name;
 panel.id='review-panel-'+name;panel.setAttribute('role','tabpanel');panel.setAttribute('aria-label',label);
 return panel;
}
function reviewMove(parent,element){if(element)parent.append(element)}
const beforeReviewOpen=openClip;
openClip=function(id){
 beforeReviewOpen(id);
 const editor=$('.editor');if(!editor||!selected)return;
 const player=$('#player'),gif=!player||player.tagName!=='VIDEO';
 const abort=new AbortController(),on=(object,event,handler)=>object?.addEventListener(event,handler,{signal:abort.signal});
 const current=reviewState={id,abort,gif,player:gif?null:player,pane:gif?'notes':'trim',editing:false,seeking:false,previousVolume:1};
 if(!gif)on(player,'loadedmetadata',()=>requestAnimationFrame(reviewFitViewer));
 const dialog=$('#dialog');dialog.classList.add('review-dialog');dialog.dataset.kind=gif?'gif':'video';
 const preview=editor.querySelector('.editor-preview'),notes=editor.querySelector('.editor-notes');
 const oldBelow=editor.querySelector('.editor-below'),summary=editor.querySelector('.recording-summary');
 const workspace=document.createElement('div');workspace.className='review-workspace';
 const viewer=document.createElement('section');viewer.className='review-viewer';viewer.setAttribute('aria-label','Просмотр записи');
 const aside=document.createElement('aside');aside.className='review-sidebar';current.aside=aside;
 const names=gif?[['export','Экспорт'],['notes','Заметки']]:[['trim','Обрезка'],['sound','Звук'],['export','Экспорт'],['notes','Заметки']];
 const tabs=document.createElement('nav');tabs.className='review-tabs';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','Инструменты записи');
 tabs.innerHTML=names.map(([name,label])=>`<button type="button" role="tab" data-review-pane="${name}" aria-controls="review-panel-${name}" aria-selected="false">${label}</button>`).join('');
 aside.append(tabs);
 const panels={};for(const [name,label] of names){panels[name]=reviewPanel(name,label);aside.append(panels[name])}
 workspace.append(viewer,aside);editor.append(workspace);
 const heading=dialog.querySelector('.dialog-head'),closeButton=heading.querySelector('button');heading.querySelector('h2').title=selected.name;
 const headActions=document.createElement('div');headActions.className='review-head-actions';
 headActions.innerHTML=button('review-edit',gif?'Заметки':'Монтаж','settings','quiet','aria-expanded="false"')+(gif?'':button('review-export','Экспорт…','download','primary'));
 heading.insertBefore(headActions,closeButton);
 if(!gif){
  player.controls=false;
  const stage=$('.playback-stage');stage.tabIndex=-1;reviewMove(viewer,stage);
  const seek=document.createElement('input');seek.id='reviewSeek';seek.className='review-seek';seek.type='range';seek.min=0;seek.max=selected.duration||1;seek.step='.001';seek.value=0;seek.setAttribute('aria-label','Положение воспроизведения');viewer.append(seek);
  const controls=$('.playback-controls'),frameControls=controls.querySelector('.studio-frame-controls');controls.classList.add('review-transport');
  const speedRow=controls.querySelector('.speed-row'),presets=controls.querySelector('.speed-presets'),timer=controls.querySelector('.timer-actions'),help=controls.querySelector(':scope > small');
  const listen=controls.querySelector('.studio-listen');
  const speedMenu=document.createElement('details');speedMenu.className='review-speed-menu';
  speedMenu.innerHTML='<summary title="Скорость воспроизведения" aria-label="Скорость воспроизведения"><span id="reviewSpeedLabel">1×</span></summary><div class="review-speed-popover"></div>';
  speedMenu.lastElementChild.append(speedRow,presets);if(help)help.remove();
  controls.prepend(Object.assign(document.createElement('button'),{id:'reviewPlay',className:'review-play',type:'button',title:'Воспроизвести',innerHTML:icon('play')}));
  for(const [action,name,label] of [['frame-prev','back','Предыдущий кадр · ←'],['frame-next','next','Следующий кадр · →']]){
   const button=frameControls.querySelector(`[data-action="${action}"]`);button.innerHTML=reviewIcon(name);button.title=label;button.setAttribute('aria-label',label);button.classList.add('review-icon-button');controls.append(button);
  }
  const clock=document.createElement('div');clock.className='review-clock';clock.innerHTML='<span id="reviewClock">00:00</span><span id="reviewTotal"></span>';controls.append(clock);
  const spacer=document.createElement('span');spacer.className='review-transport-spacer';controls.append(spacer,speedMenu);
  const volume=document.createElement('div');volume.className='review-volume';volume.innerHTML=`<button type="button" id="reviewMute" class="review-icon-button" title="Выключить звук" aria-label="Выключить звук">${reviewIcon('volume')}</button><input id="reviewVolume" type="range" min="0" max="1" step=".01" value="${player.volume}" aria-label="Громкость просмотра">`;
  controls.append(volume);
  const fullscreen=document.createElement('button');fullscreen.type='button';fullscreen.id='reviewFullscreen';fullscreen.className='review-icon-button';fullscreen.title='Во весь экран';fullscreen.setAttribute('aria-label',fullscreen.title);fullscreen.innerHTML=reviewIcon('expand');controls.append(fullscreen);
  reviewMove(viewer,controls);
  const trim=$('.trim-panel');current.timeline=trim;trim.classList.add('review-timeline');
  const trimHead=trim.querySelector('.trim-heading');trimHead.querySelector('b').textContent='Дорожка';trimHead.querySelector('small')?.remove();reviewMove(trimHead,trim.querySelector('.trim-zoom-tools'));
  const wave=$('.studio-wave'),waveHead=wave.querySelector('.studio-wave-head'),waveStatus=$('#waveStatus');
  reviewMove(heading,$('#sourceFps'));reviewMove(panels.sound,listen);waveHead.querySelector('label').textContent='Волна';reviewMove(panels.sound,waveHead);reviewMove(panels.sound,waveStatus);
  const timeFields=editor.querySelector('.editor-export > .time-inputs');
  panels.trim.innerHTML='<h3>Нужный отрезок</h3><p class="review-panel-lead">Перетащи границы на дорожке или укажи время.</p>';
  reviewMove(panels.trim,timeFields);
  const here=document.createElement('div');here.className='review-here';
  for(const action of ['set-in','set-out'])reviewMove(here,preview.querySelector(`[data-action="${action}"]`));panels.trim.append(here);
  const exact=document.createElement('div');exact.className='review-exact-time';exact.innerHTML='<span>Точный кадр</span>';reviewMove(exact,$('#framePosition'));panels.trim.append(exact);
  const selectionActions=trim.querySelector(':scope > .actions');reviewMove(panels.trim,selectionActions);
  timer.classList.add('review-timer-toggle');panels.trim.append(timer);
  const bookmarks=document.createElement('section');bookmarks.className='review-bookmarks';bookmarks.innerHTML='<div class="review-bookmarks-head"><h3>Метки</h3></div>';
  reviewMove(bookmarks.firstElementChild,preview.querySelector('[data-action="mark"]'));reviewMove(bookmarks,$('#marks'));panels.trim.append(bookmarks);
  reviewMove(panels.trim,$('#trimError'));reviewMove(panels.trim,$('#trimHint'));
  const details=$('.export-details');reviewMove(panels.export,details);
  const audioField=$('#exportAudioMode').closest('.field');reviewMove(panels.sound,audioField);reviewMove(panels.sound,$('#exportTrackGains'));
  const nameField=$('#clipName').closest('.field');details.prepend(nameField);
  const formatHelp=$('#clipFormat').closest('.field').querySelector('small');if(formatHelp)formatHelp.textContent='MP4 для видео; GIF — короткая анимация без звука.';
  const timerHelp=details.querySelector('.export-timer-option small');if(timerHelp)timerHelp.textContent='Отсчёт от начала выбранного отрезка.';
  const footer=document.createElement('footer');footer.className='review-export-footer';
  const selection=trim.querySelector('.trim-labels');reviewMove(footer,selection);
  const selectionLabel=document.createElement('small');selectionLabel.id='reviewSelection';footer.append(selectionLabel);
  const exportButton=editor.querySelector('[data-action="export"]');exportButton.innerHTML=icon('download')+'Сохранить клип';footer.append(exportButton);aside.append(footer);
  frameControls.remove();
  reviewMove(viewer,trim);
  const setVolume=value=>{player.volume=value;if(studioEditor?.audio)studioEditor.audio.volume=value;$('#reviewMute').innerHTML=reviewIcon(value>0?'volume':'mute');$('#reviewMute').title=value>0?'Выключить звук':'Включить звук';$('#reviewMute').setAttribute('aria-label',$('#reviewMute').title)};
  on($('#reviewPlay'),'click',async()=>{if(player.paused){try{await player.play()}catch(error){toast(error.message,true)}}else player.pause()});
  on(player,'click',e=>{e.preventDefault();e.stopPropagation();if(document.fullscreenElement===stage)stage.focus({preventScroll:true});$('#reviewPlay').click()});
  on(player,'dblclick',()=>fullscreen.click());
  on(seek,'input',()=>{current.seeking=true;player.currentTime=Number(seek.value);reviewClock()});on(seek,'change',()=>{current.seeking=false;reviewClock()});
  on($('#reviewVolume'),'input',e=>setVolume(Number(e.target.value)));
  on($('#reviewMute'),'click',()=>{if(player.volume>0){current.previousVolume=player.volume;setVolume(0)}else setVolume(current.previousVolume||1);$('#reviewVolume').value=player.volume});
  on($('#previewAudioTrack'),'change',()=>setVolume(player.volume));
  const transportHome=controls.parentNode,transportNext=controls.nextSibling,seekHome=seek.parentNode,seekNext=seek.nextSibling;
  const fullscreenUI=installFullscreenUI({stage,controls,seek,player,on,signal:abort.signal});current.showControls=fullscreenUI.show;
  on(fullscreen,'click',()=>{
   const request=document.fullscreenElement?document.exitFullscreen():stage.requestFullscreen();
   request.catch(error=>toast(error.message,true));
  });
  on(document,'fullscreenchange',()=>{
   const active=document.fullscreenElement===stage;
   // The native video control layer also handles surface clicks. Keep our
   // transport in fullscreen so a click always has exactly one owner.
   player.controls=false;
   controls.classList.toggle('review-fullscreen-transport',active);
   seek.classList.toggle('review-fullscreen-seek',active);
   if(active){stage.append(controls,seek);stage.focus({preventScroll:true})}
   else{
    if(controls.parentNode===stage)transportHome.insertBefore(controls,transportNext?.parentNode===transportHome?transportNext:null);
    if(seek.parentNode===stage)seekHome.insertBefore(seek,seekNext?.parentNode===seekHome?seekNext:null);
   }
   fullscreen.title=active?'Выйти из полного экрана':'Во весь экран';fullscreen.setAttribute('aria-label',fullscreen.title);
   fullscreenUI.update();
  });
  for(const event of ['timeupdate','play','pause','ended','loadedmetadata','seeked','ratechange'])on(player,event,reviewClock);
  function positionSpeedMenu(){
   if(!speedMenu.open)return;
   const menu=speedMenu.getBoundingClientRect(),track=seek.getBoundingClientRect(),video=stage.getBoundingClientRect();
   const scale=menu.height/Math.max(1,speedMenu.offsetHeight),popover=speedMenu.lastElementChild;
   const topLimit=Math.max(12,video.top+12),bottomLimit=track.top-14;
   popover.style.bottom=Math.max(menu.height+10,menu.bottom-bottomLimit)/scale+'px';
   popover.style.maxHeight=Math.max(96,(bottomLimit-topLimit)/scale)+'px';
   popover.style.overflowY='auto';
  }
  on(speedMenu,'toggle',()=>{if(speedMenu.open){for(const other of controls.querySelectorAll('details'))if(other!==speedMenu)other.open=false;positionSpeedMenu()}});
  on(window,'resize',positionSpeedMenu);
  on(document,'fullscreenchange',()=>requestAnimationFrame(positionSpeedMenu));
  on(presets,'click',e=>{if(e.target.closest('[data-rate]'))speedMenu.open=false});
  on(document,'pointerdown',e=>{if(!speedMenu.contains(e.target))speedMenu.open=false});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&speedMenu.open&&!document.fullscreenElement){e.preventDefault();e.stopImmediatePropagation();speedMenu.open=false}},{capture:true,signal:abort.signal});
 }else{
  const image=preview.querySelector('img.player');const stage=document.createElement('div');stage.className='playback-stage review-gif-stage';stage.append(image);viewer.append(stage);
 }
 const info=document.createElement('section');info.className='review-file-info';info.setAttribute('aria-label','О записи');
 const fileName=document.createElement('div');fileName.className='review-file-name';fileName.textContent=selected.name;info.append(fileName);
 reviewMove(summary,$('#sourceFps'));reviewMove(info,summary);panels.notes.append(info);
 reviewMove(panels.notes,notes);notes.querySelector('.editor-card-head')?.remove();
 const external=document.createElement('div');external.className='review-external';
 reviewMove(external,preview.querySelector('[data-action="open-clip"]'));panels.notes.append(external);
 const exportTools=document.createElement('div');exportTools.className='review-export-tools';
 reviewMove(exportTools,preview.querySelector('[data-action="open-clip-folder"]'));
 reviewMove(exportTools,notes.querySelector('[data-action="delete-video"]'));panels.export.append(exportTools);
 oldBelow?.remove();preview?.remove();
 on(tabs,'click',e=>{const tab=e.target.closest('[data-review-pane]');if(tab)reviewSetMode(true,tab.dataset.reviewPane)});
 on(tabs,'keydown',e=>{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
  const buttons=[...tabs.querySelectorAll('button')],at=buttons.indexOf(document.activeElement);if(at<0)return;
  e.preventDefault();const index=e.key==='Home'?0:e.key==='End'?buttons.length-1:(at+(e.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
  buttons[index].focus();reviewSetMode(true,buttons[index].dataset.reviewPane);
 });
 reviewSetMode(false);requestAnimationFrame(reviewFitViewer);dialog.scrollTop=0;($('#reviewPlay')||$('[data-action="review-edit"]')).focus({preventScroll:true});
};
const beforeReviewWave=scheduleWave;
scheduleWave=function(){if(reviewState&&!reviewState.editing)return;return beforeReviewWave()};
const beforeReviewTrimVisuals=updateTrimVisuals;
updateTrimVisuals=function(){beforeReviewTrimVisuals();reviewClock()};
const beforeReviewAction=action;
action=async function(name,element){
 if(name==='review-edit'){reviewSetMode(!reviewState.editing);return}
 if(name==='review-export'){reviewSetMode(true,'export');return}
 if(name==='export'&&reviewState&&reviewState.pane!=='export'){reviewSetMode(true,'export');return}
 return beforeReviewAction(name,element);
};
$('#dialog').addEventListener('close',reviewDispose);
function reviewHandlesSpace(e){
 return reviewState?.player&&e.code==='Space'&&!e.ctrlKey&&!e.altKey&&!e.metaKey&&
  !e.target.closest('input,textarea,select,button,summary,[contenteditable=true]');
}
function reviewHandlesFullscreenKey(e){
 return reviewState?.player&&e.code==='KeyF'&&!e.ctrlKey&&!e.altKey&&!e.metaKey&&
  !e.target.closest('input,textarea,select,[contenteditable=true],[role=combobox],[role=listbox]');
}
// Own the entire key press before Chromium's native fullscreen controls see it.
// Keyup must also be consumed to avoid synthesizing a second button activation.
document.addEventListener('keydown',e=>{
 if(reviewHandlesFullscreenKey(e)){
  e.preventDefault();e.stopImmediatePropagation();if(!e.repeat)$('#reviewFullscreen').click();return;
 }
 if(!reviewHandlesSpace(e))return;
 e.preventDefault();e.stopImmediatePropagation();reviewState.showControls?.();if(!e.repeat)$('#reviewPlay').click();
},{capture:true});
document.addEventListener('keyup',e=>{
 if(reviewHandlesSpace(e)||reviewHandlesFullscreenKey(e)){e.preventDefault();e.stopImmediatePropagation()}
},{capture:true});
window.reviewDebug=()=>reviewState?{
 mode:reviewState.editing?'edit':'view',pane:reviewState.pane,gif:reviewState.gif,
 sidebarHidden:reviewState.aside.hidden,timelineHidden:reviewState.timeline?.hidden??true,
 dialogScroll:$('#dialog').scrollHeight-$('#dialog').clientHeight,
 horizontalOverflow:$('#dialog').scrollWidth>$('#dialog').clientWidth,
 sourceSwitch:{...window.afterplaySourceSwap,holdingFrame:!!document.querySelector('.sequence-frame-hold')},
 video:reviewState.player?{width:reviewState.player.clientWidth,height:reviewState.player.clientHeight,nativeControls:reviewState.player.controls}:null,
 missing:['clipTags','clipNote','clipFavorite',...(reviewState.gif?[]:['clipIn','clipOut','clipName','clipFormat','playbackSpeed','previewTimer','exportTimer','exportAudioMode','previewAudioTrack','framePosition','trimTrack','audioWaveform'])].filter(id=>!document.getElementById(id))
}:null;
