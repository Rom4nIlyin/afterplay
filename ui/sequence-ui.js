'use strict';
// The project uses the same source player, trim handles, sound mixer and input tools.
const Seq=SequenceModel;
const SeqView=SequenceViewport;
let sequenceId=null,sequenceEditor=null,sequenceLoading=false,sequenceOpening=false,sequencePlaying=false;
let sequenceCursor=0,sequenceZoom=42,sequenceHistory=[],sequenceHistoryAt=-1,sequenceSave=Promise.resolve(),sequenceSaveTimer=null;
let sequenceDrag=null,sequenceGapTimer=null,sequenceGeneration=0,sequenceEditingSelection=false;
let sequenceLeft=0,sequenceFitPending=true,sequenceNavigation=null,sequenceNavFrame=null,sequenceMotionTimer=null;
const sequenceActive=()=>!!(reviewState?.editing&&sequenceRow()&&selected?.id===sequenceRow().id);
const sequenceRow=()=>montageDraft?.segments?.find(r=>r.uid===sequenceId);
const sequenceDuration=()=>montageDraft?Seq.total(montageDraft):0;
const sequenceClip=id=>state.clips.find(c=>c.id===id);
window.afterplaySourceSwap={switches:0,heldFrames:0,releasedFrames:0,opacitySamples:0,minimumOpacity:1,closedDuringSwitch:false};
function sequenceFreezeFrame(){
 const held=$('.sequence-frame-hold');if(held)return held;
 const player=$('#player');if(!$('#dialog').open||player?.tagName!=='VIDEO'||player.readyState<2||!player.videoWidth)return null;
 try{
  const canvas=document.createElement('canvas');canvas.className='sequence-frame-hold';canvas.width=Math.min(1920,player.videoWidth);canvas.height=Math.max(1,Math.round(canvas.width*player.videoHeight/player.videoWidth));
  const exact=studioEditor?.image,source=exact&&!exact.hidden&&exact.complete?exact:player;
  const context=canvas.getContext('2d',{alpha:false});if($('.sequence-gap')){context.fillStyle='#000';context.fillRect(0,0,canvas.width,canvas.height)}else context.drawImage(source,0,0,canvas.width,canvas.height);return canvas;
 }catch{return null}
}
function sequenceHoldFrame(canvas){
 const player=$('#player'),stage=$('.playback-stage'),signal=sequenceEditor?.abort.signal;if(!canvas||!player||!stage||!signal)return;
 stage.append(canvas);window.afterplaySourceSwap.heldFrames++;
 let frame=null,disposed=false;
 const release=()=>{if(disposed||$('#player')!==player)return;disposed=true;canvas.remove();window.afterplaySourceSwap.releasedFrames++};
 const ready=()=>{
  if(disposed||player.readyState<2||player.seeking||$('#player')!==player)return;
  cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{frame=requestAnimationFrame(()=>{if(player.readyState>=2&&!player.seeking)release()})});
 };
 for(const event of ['loadeddata','seeked','canplay','playing'])player.addEventListener(event,ready,{signal});
 player.addEventListener('error',release,{once:true,signal});signal.addEventListener('abort',()=>{disposed=true;cancelAnimationFrame(frame)},{once:true});ready();
}
function sequenceProject(){
 if(!montageDraft)montageDraft=Seq.normalize({segments:[]});
 if(montageDraft.segments.some(r=>!r.uid||!Number.isFinite(r.at)))montageDraft=Seq.normalize(montageDraft);
 return montageDraft;
}
function sequencePersist(){
 clearTimeout(sequenceSaveTimer);sequenceSaveTimer=setTimeout(()=>{
  if(!montageDraft)return;const project=Seq.clone(montageDraft);
  sequenceSave=sequenceSave.catch(()=>{}).then(()=>api('montage_project_save',{project})).catch(error=>toast('Монтаж не сохранён: '+error.message,true));
 },300);
}
function sequenceRemember(){
 const value=JSON.stringify(sequenceProject());if(sequenceHistory[sequenceHistoryAt]===value)return;
 sequenceHistory.splice(sequenceHistoryAt+1);sequenceHistory.push(value);if(sequenceHistory.length>80)sequenceHistory.shift();sequenceHistoryAt=sequenceHistory.length-1;sequencePersist();
}
function sequenceMutate(fn){sequenceStop();sequenceCapture();sequenceRemember();fn(sequenceProject());sequenceRemember();sequenceRender();}
function sequenceCapture(){
 const row=sequenceRow();if(!row||sequenceLoading||sequenceOpening||selected?.id!==row.id||!trimState)return;
 Seq.trim(montageDraft,row.uid,trimState.start,trimState.end);
 row.audio={audio_mode:$('#exportAudioMode')?.value||'mix',audio_tracks:studioEditor?.mixer?.export()||[],game_gain:Number($('#exportGameGain')?.value??100),chat_gain:Number($('#exportChatGain')?.value??100)};
 row.timer=!!$('#exportTimer')?.checked;
 if($('#exportInputs')&&inputEditor){row.show_inputs=$('#exportInputs').checked;row.preview_inputs=$('#previewInputs').checked;row.input_overlay={...inputEditor.settings}}
}
function sequenceRestore(){
 const row=sequenceRow();if(!row||selected?.id!==row.id)return;
 sequenceLoading=true;
 try{
  setTrim(row.start,row.end);if($('#exportTimer'))$('#exportTimer').checked=!!row.timer;
  if(row.audio&&studioEditor?.mixer){
   if(row.audio.audio_mode==='custom')for(const track of row.audio.audio_tracks||[]){
    const gain=$(`[data-audio-gain="${track.index}"]`);if(gain){gain.value=track.gain;gain.dispatchEvent(new Event('input',{bubbles:true}))}
   }
   if(row.audio.audio_mode==='custom')for(const checkbox of document.querySelectorAll('[data-audio-track]')){
    const should=(row.audio.audio_tracks||[]).some(t=>t.index===Number(checkbox.dataset.audioTrack));if(checkbox.checked!==should){checkbox.checked=should;checkbox.dispatchEvent(new Event('change',{bubbles:true}))}
   }
   $('#exportAudioMode').value=row.audio.audio_mode||'mix';
  }
  if($('#exportInputs')){
   $('#exportInputs').checked=!!row.show_inputs;$('#exportInputsCopy').checked=!!row.show_inputs;$('#previewInputs').checked=!!row.preview_inputs;
   if(row.input_overlay){inputEditor.settings={...inputEditor.settings,...row.input_overlay};for(const [key,id] of [['layout','inputLayout'],['position','inputPosition'],['size','inputSize'],['opacity','inputOpacity']])$('#'+id).value=inputEditor.settings[key];$('#inputSizeValue').textContent=inputEditor.settings.size;$('#inputOpacityValue').textContent=inputEditor.settings.opacity;inputEditor.preview.configure(inputEditor.settings)}
   inputEditor.preview?.setVisible(!!row.preview_inputs);
  }
 }finally{sequenceLoading=false}
}
function sequenceStop(){const wasPlaying=sequencePlaying;sequencePlaying=false;if(wasPlaying)$('#player')?.pause();sequenceGeneration++;clearInterval(sequenceGapTimer);sequenceGapTimer=null;$('.sequence-gap')?.remove();sequencePaintCursor()}
function sequenceSelect(id,{play=false,time=null,keepPane=false,capture=true}={}){
 if(capture)sequenceCapture();const row=Seq.find(sequenceProject(),id),clip=sequenceClip(row.id);if(!clip)throw Error('Исходная запись недоступна');
 const pane=reviewState?.pane||'assembly',previous=sequenceId,reuse=sequenceEditor&&selected?.id===row.id;
 sequenceLeft=$('#sequenceScroll')?.scrollLeft??sequenceLeft;sequenceId=id;sequenceCursor=time??row.at;
 if(!reuse){sequenceOpening=true;try{openClip(row.id)}finally{sequenceOpening=false}}
 if(!reuse||previous!==id||!capture)sequenceRestore();
 reviewSetMode(true,keepPane?pane:'assembly');
 const player=$('#player'),generation=++sequenceGeneration;
 const begin=()=>{if(generation!==sequenceGeneration||sequenceId!==id)return;sequenceLoading=true;player.currentTime=Math.max(row.start,Math.min(row.end-.0001,row.start+sequenceCursor-row.at));sequenceLoading=false;if(play)player.play().catch(error=>{sequenceStop();toast(error.message,true)})};
 if(player.readyState>=1)begin();else player.addEventListener('loadedmetadata',begin,{once:true,signal:sequenceEditor.abort.signal});
 if(!reuse||previous!==id||!capture)sequenceRender();else sequencePaintCursor();
}
function sequenceSeek(time,play=false,capture=true){
 clearInterval(sequenceGapTimer);sequenceGapTimer=null;const previousGap=$('.sequence-gap');
 const project=sequenceProject();sequenceCursor=Math.max(0,Math.min(time,Seq.total(project)));const row=Seq.at(project,sequenceCursor)||(sequenceCursor>=Seq.total(project)?project.segments.at(-1):null);
 if(row){sequenceSelect(row.uid,{play,time:sequenceCursor,keepPane:true,capture});previousGap?.remove();return}
 previousGap?.remove();
 $('#player')?.pause();sequenceRender();
 const next=project.segments.find(r=>r.at>sequenceCursor);if(!next){sequenceStop();return}
 const stage=$('.playback-stage');const mask=document.createElement('div');mask.className='sequence-gap';mask.textContent='Пауза между фрагментами';stage.append(mask);
 if(!play)return;
 const base=sequenceCursor,clock=performance.now();clearInterval(sequenceGapTimer);
 sequenceGapTimer=setInterval(()=>{if(!sequencePlaying){sequenceStop();return}sequenceCursor=base+(performance.now()-clock)/1000;sequencePaintCursor();if(sequenceCursor>=next.at){clearInterval(sequenceGapTimer);sequenceGapTimer=null;sequenceSelect(next.uid,{play:true,keepPane:true});mask.remove()}},30);
}
function sequencePlay(){
 if(sequencePlaying){$('#player')?.pause();sequenceStop();return}
 sequenceCapture();if(!montageDraft?.segments.length)throw Error('Добавь фрагменты в монтаж');sequencePlaying=true;
 if(sequenceCursor>=sequenceDuration()-.02)sequenceCursor=0;sequenceSeek(sequenceCursor,true);
 if($('#sequencePlay'))$('#sequencePlay').textContent='❚❚ Пауза';
}
function sequencePaintCursor(){
 const cursor=$('#sequenceCursor');if(cursor)cursor.style.left=(sequenceCursor*sequenceZoom)+'px';
 if(cursor){cursor.setAttribute('aria-valuemax',sequenceDuration());cursor.setAttribute('aria-valuenow',sequenceCursor.toFixed(3));cursor.setAttribute('aria-valuetext',trimFormat(sequenceCursor))}
 if($('#sequenceClock'))$('#sequenceClock').textContent=trimFormat(sequenceCursor)+' / '+trimFormat(sequenceDuration());
 if(sequenceActive()){
  $('#reviewClock').textContent=elapsedLabel(sequenceCursor);$('#reviewTotal').textContent='/ '+elapsedLabel(sequenceDuration());
  const seek=$('#reviewSeek');seek.max=sequenceDuration();seek.value=sequenceCursor;
  seek.style.setProperty('--seek-fill',`${sequenceDuration()?sequenceCursor/sequenceDuration()*100:0}%`);
  $('#reviewPlay').innerHTML=reviewIcon(sequencePlaying?'pause':'play');$('#reviewPlay').title=sequencePlaying?'Пауза':'Воспроизвести монтаж';$('#reviewPlay').setAttribute('aria-label',$('#reviewPlay').title);
 }
 const scroll=$('#sequenceScroll');if(scroll?.clientWidth>0&&sequencePlaying&&!sequenceNavigation&&!sequenceDrag){scroll.scrollLeft=SeqView.follow(scroll.scrollLeft,scroll.clientWidth,sequenceCursor,sequenceZoom,scroll.scrollWidth);sequenceLeft=scroll.scrollLeft}
}
const beforeSequenceClock=reviewClock;
reviewClock=function(){beforeSequenceClock();sequencePaintCursor()};
function sequenceRenderBlocks(project){
 const parent=$('#sequenceBlocks'),nodes=new Map([...parent.querySelectorAll('[data-sequence-part]')].map(node=>[node.dataset.sequencePart,node]));
 const drag=sequenceNavigation?.type==='clip'&&sequenceNavigation.moved?sequenceNavigation:null;
 if(drag&&!drag.edge){clearTimeout(sequenceMotionTimer);$('#sequenceBoard').dataset.reordering='true'}
 for(const [i,row] of project.segments.entries()){
  let node=nodes.get(row.uid);nodes.delete(row.uid);
  if(!node){node=document.createElement('div');node.dataset.sequencePart=row.uid;node.tabIndex=0;node.setAttribute('role','button');node.innerHTML='<img draggable="false" alt=""><span class="sequence-block-label" data-i18n-ignore></span><small></small><span class="sequence-edge left" data-sequence-edge="start" title="Начало фрагмента"></span><span class="sequence-edge right" data-sequence-edge="end" title="Конец фрагмента"></span>'}
  const clip=sequenceClip(row.id),moving=drag?.uid===row.uid&&!drag.edge,trimming=drag?.uid===row.uid&&!!drag.edge;
  node.className=`sequence-block${row.uid===sequenceId?' active':''}${moving?' is-dragging':''}${trimming?' is-trimming':''}`;
  const left=moving?Math.max(0,drag.at*sequenceZoom+drag.x-drag.startX+sequenceLeft-drag.left):row.at*sequenceZoom;
  node.style.left=left+'px';node.style.width=Math.max(8,Seq.length(row)*sequenceZoom)+'px';
  node.setAttribute('aria-label',`Фрагмент ${i+1}: ${clip?.name||'Нет исходника'}`);node.title=`${clip?.name||''} · ${trimFormat(row.start)} — ${trimFormat(row.end)}`;
  const img=node.querySelector('img');if(img.dataset.clip!==row.id){img.dataset.clip=row.id;img.src=`${base}thumb/${row.id}`}
  node.querySelector('.sequence-block-label').textContent=`${i+1}. ${clip?.name||'Нет исходника'}`;node.querySelector('small').textContent=trimFormat(Seq.length(row));
  if(parent.children[i]!==node)parent.insertBefore(node,parent.children[i]||null);
 }
 for(const node of nodes.values())node.remove();
 const slot=$('#sequenceDropSlot'),row=drag&&!drag.edge?project.segments.find(row=>row.uid===drag.uid):null;
 if(slot){slot.hidden=!row;if(row){slot.style.left=row.at*sequenceZoom+'px';slot.style.width=Seq.length(row)*sequenceZoom+'px'}}
}
function sequenceRender(){
 const current=sequenceEditor;if(!current||!$('#sequencePanel'))return;
 const project=sequenceProject(),row=sequenceRow(),duration=Seq.total(project),scroll=$('#sequenceScroll');
 if(sequenceFitPending&&scroll.clientWidth>0&&duration>0){sequenceZoom=SeqView.fit(duration,scroll.clientWidth);sequenceLeft=0;sequenceFitPending=false}
 const width=SeqView.width(duration,sequenceZoom,scroll.clientWidth);
 $('#sequenceTitle').value=project.name;$('#sequenceResolution').value=project.resolution;$('#sequenceFormat').value=project.format||'original';$('#sequenceFree').checked=!!project.free;
 $('#sequenceSelected').textContent=row?`${project.segments.indexOf(row)+1}. ${sequenceClip(row.id)?.name||'Исходник недоступен'}`:'Выбери фрагмент на дорожке';
 $('#sequenceSourceStart').value=row?trimFormat(row.start):'';$('#sequenceSourceEnd').value=row?trimFormat(row.end):'';$('#sequenceAt').value=row?trimFormat(row.at):'';$('#sequenceAt').disabled=!project.free||!row;
 $('#sequenceUndo').disabled=sequenceHistoryAt<=0;$('#sequenceRedo').disabled=sequenceHistoryAt>=sequenceHistory.length-1;
 const step=[.5,1,2,5,10,30,60,120,300,600].find(n=>n*sequenceZoom>=65)||1800;
 const ruler=Array.from({length:Math.floor((duration+2)/step)+1},(_,i)=>`<span style="left:${i*step*sequenceZoom}px">${fmt(i*step).replace(/^00:/,'')}</span>`).join('');
 $('#sequenceRail').style.width=width+'px';$('#sequenceRuler').innerHTML=ruler;
 sequenceRenderBlocks(project);
 if(scroll.clientWidth>0){scroll.scrollLeft=sequenceLeft;sequenceLeft=scroll.scrollLeft}
 $('#sequenceEmpty').hidden=!!project.segments.length;sequencePaintCursor();
}
function sequenceAttach(){
 const player=$('#player');if(!reviewState||!player||player.tagName!=='VIDEO')return;
 sequenceEditor?.abort.abort();$('#dialog').dataset.sequence='true';const current=sequenceEditor={abort:new AbortController()};const on=(node,event,fn)=>node.addEventListener(event,fn,{signal:current.abort.signal});
 const nav=reviewState.aside.querySelector('.review-tabs');nav.insertAdjacentHTML('afterbegin','<button type="button" role="tab" data-review-pane="assembly" aria-controls="review-panel-assembly" aria-selected="false" tabindex="-1">Сборка</button>');
 const panel=reviewPanel('assembly','Сборка монтажа');panel.id='sequencePanel';panel.hidden=true;
 panel.innerHTML=`<h3>Монтаж из фрагментов</h3><div class="field"><label for="sequenceTitle">Название монтажа</label><input id="sequenceTitle"></div><div class="field"><label for="sequenceAddSource">Добавить запись</label><select id="sequenceAddSource">${state.clips.filter(c=>!c.name.toLowerCase().endsWith('.gif')).map(c=>`<option value="${c.id}" ${c.id===selected.id?'selected':''}>${esc(c.name)}</option>`).join('')}</select></div><div class="actions">${button('sequence-add-source','Добавить целиком','plus','secondary')}${button('sequence-add-range','Добавить выделение','plus','primary')}</div><p class="hint">Нарежь исходник на вкладке «Обрезка» и добавь несколько выделений. На дорожке перетаскивай фрагменты и их края.</p><h3 id="sequenceSelected"></h3><div class="time-inputs"><label>Начало в исходнике<input id="sequenceSourceStart"></label><label>Конец в исходнике<input id="sequenceSourceEnd"></label></div><div class="field"><label for="sequenceAt">Позиция в монтаже</label><input id="sequenceAt"><small>Для свободного времени включи переключатель выше.</small></div><div class="actions">${button('sequence-range-save','Применить границы','check','secondary')}${button('sequence-up','Раньше','arrow','quiet')}${button('sequence-down','Позже','arrow','quiet')}</div><div class="actions">${button('sequence-duplicate','Дублировать','plus','secondary')}${button('sequence-remove','Удалить фрагмент','trash','quiet')}</div><p class="hint">Звук, таймер и нажатия выбранного фрагмента настраиваются в соседних вкладках.</p><div class="field"><label for="sequenceFormat">Формат монтажа</label><select id="sequenceFormat"><option value="original">MP4 · исходные пропорции</option><option value="vertical">MP4 · вертикально 9:16</option><option value="gif">GIF · 2–15 секунд</option></select></div><div class="field"><label for="sequenceResolution">Размер</label><select id="sequenceResolution"><option value="source">Как у первой записи</option><option value="1080p">До 1080p</option><option value="720p">До 720p</option></select></div>`;
 reviewState.aside.append(panel);
 const placement=document.createElement('label');placement.className='check sequence-placement';placement.title='Размещать фрагменты по времени. При выключении они соединяются без пауз.';placement.innerHTML='<input id="sequenceFree" type="checkbox"> Свободное размещение';$('#sequenceAt').closest('.field').before(placement);
 const board=document.createElement('section');board.className='sequence-board';board.id='sequenceBoard';
 board.hidden=!reviewState.editing;
 board.innerHTML=`<div class="sequence-toolbar"><b>Монтаж</b><div class="sequence-tools"><button id="sequenceUndo" data-action="sequence-undo" title="Отменить изменение монтажа" aria-label="Отменить изменение монтажа">↶</button><button id="sequenceRedo" data-action="sequence-redo" title="Повторить изменение монтажа" aria-label="Повторить изменение монтажа">↷</button>${button('sequence-split','Разрезать','film','quiet','title="Разрезать · S"')}<span class="sequence-tool-divider"></span><button data-action="sequence-fit" title="Весь монтаж на экране" aria-label="Весь монтаж на экране">↔</button><button data-action="sequence-zoom-out" title="Уменьшить дорожку" aria-label="Уменьшить дорожку">−</button><button data-action="sequence-zoom-in" title="Увеличить дорожку" aria-label="Увеличить дорожку">+</button></div></div><div class="sequence-scroll" id="sequenceScroll" title="Клик — перейти к моменту · линейка — перемотка · колесо — прокрутка · Ctrl + колесо — масштаб · средняя кнопка — перемещение дорожки"><div class="sequence-rail" id="sequenceRail"><div id="sequenceRuler" class="sequence-ruler"></div><div id="sequenceBlocks" class="sequence-blocks"></div><div id="sequenceCursor" class="sequence-cursor" role="slider" tabindex="0" aria-label="Позиция в монтаже" aria-valuemin="0"><span class="sequence-cursor-grip"></span></div></div></div><p id="sequenceEmpty" class="hint">Выбери отрезок исходника и нажми «+ Выделение».</p>`;
 $('.review-viewer').append(board);
 $('#sequenceBlocks').insertAdjacentHTML('beforebegin','<div id="sequenceDropSlot" class="sequence-drop-slot" hidden></div>');
 const sourceAdd=document.createElement('button');sourceAdd.type='button';sourceAdd.className='quiet';sourceAdd.dataset.action='sequence-add-range';sourceAdd.textContent='+ В монтаж';$('.review-timeline .trim-heading')?.append(sourceAdd);
 on(player,'timeupdate',()=>{
  const row=sequenceRow();if(!row||selected?.id!==row.id)return;
  if(sequenceLoading||sequenceOpening||sequenceNavigation||$('.sequence-gap'))return;
  sequenceCursor=Math.max(row.at,Math.min(row.at+Seq.length(row),row.at+player.currentTime-row.start));sequencePaintCursor();
  if(sequencePlaying&&player.currentTime>=row.end-.025){const next=montageDraft.segments[montageDraft.segments.indexOf(row)+1];if(next)sequenceSeek(row.at+Seq.length(row)+.00001,true);else sequenceStop()}
 });
 on(player,'ended',()=>{if(sequencePlaying){const row=sequenceRow();if(row)sequenceSeek(row.at+Seq.length(row)+.00001,true)}});
 on(player,'pause',()=>{if(sequencePlaying&&!sequenceGapTimer&&!sequenceOpening&&!$('.sequence-gap'))sequenceStop()});
 on($('#sequenceScroll'),'pointerdown',sequencePointerDown);
 on($('#sequenceScroll'),'scroll',()=>{sequenceLeft=$('#sequenceScroll').scrollLeft});
 $('#sequenceScroll').addEventListener('wheel',sequenceWheel,{passive:false,signal:current.abort.signal});
 for(const id of ['sequenceTitle','sequenceResolution','sequenceFormat','sequenceFree'])on($('#'+id),'change',()=>{
  sequenceMutate(p=>{p.name=$('#sequenceTitle').value;p.resolution=$('#sequenceResolution').value;p.format=$('#sequenceFormat').value;p.free=$('#sequenceFree').checked;if(!p.free)Seq.pack(p)});
 });
 sequenceRender();sequenceLayout();
}
const beforeSequenceOpen=openClip;
openClip=function(id){
 const switching=!!($('#dialog').open&&reviewState),held=switching?sequenceFreezeFrame():null;
 if(switching){const token=++window.afterplaySourceSwap.switches;window.afterplaySwitchingSource=token;let count=0;
  const sample=()=>{if(window.afterplaySwitchingSource!==token)return;const info=window.afterplaySourceSwap,dialog=$('#dialog');info.opacitySamples++;info.minimumOpacity=Math.min(info.minimumOpacity,Number(getComputedStyle(dialog).opacity));info.closedDuringSwitch||=!dialog.open;Object.assign(dialog.dataset,{sourceSwitches:String(info.switches),sourceSwitchSamples:String(info.opacitySamples),sourceSwitchOpacity:String(info.minimumOpacity),sourceSwitchClosed:String(info.closedDuringSwitch)});if(++count<8)requestAnimationFrame(sample);else delete window.afterplaySwitchingSource};requestAnimationFrame(sample);
 }
 if(!sequenceOpening){sequenceEndNavigation(true);sequenceStop();sequenceCapture();sequenceId=null;sequenceCursor=0;sequenceFitPending=true;sequenceLeft=0}
 delete $('#dialog').dataset.sequence;delete $('#dialog').dataset.sequenceSource;
 beforeSequenceOpen(id);sequenceAttach();
 if(held)sequenceHoldFrame(held);
 if(!sequenceOpening&&montageDraft?.segments.length===0){const p=sequenceProject(),c=sequenceClip(id);sequenceId=Seq.add(p,{id,start:0,end:c.duration}).uid;sequenceRemember();sequenceRender()}
};
const beforeSequenceMixer=window.buildStudioMixer;
window.buildStudioMixer=function(...args){beforeSequenceMixer(...args);sequenceRestore()};
document.addEventListener('afterplay-input-ready',sequenceRestore);
document.addEventListener('afterplay-trim',()=>{
 if(sequenceLoading||sequenceOpening||!sequenceRow()||!sequenceEditor||selected?.id!==sequenceRow().id)return;
 sequenceCapture();sequenceRemember();sequenceRender();
});
document.addEventListener('change',e=>{if(sequenceEditor&&!sequenceLoading&&(e.target.matches('[data-audio-track],#exportAudioMode,#exportTimer,#exportInputs,#exportInputsCopy,#previewInputs,#inputLayout,#inputPosition,#inputSize,#inputOpacity'))){sequenceCapture();sequenceRemember()}});
document.addEventListener('input',e=>{if(sequenceEditor&&!sequenceLoading&&e.target.matches('[data-audio-gain]')){sequenceCapture();sequenceRemember()}});
function sequenceSetZoom(factor,anchor=null){
 const scroll=$('#sequenceScroll');if(!scroll)return;
 const x=anchor??Math.max(0,Math.min(scroll.clientWidth,sequenceCursor*sequenceZoom-scroll.scrollLeft));
 const view=SeqView.zoom(sequenceDuration(),scroll.clientWidth,sequenceZoom,scroll.scrollLeft,x,factor);
 sequenceZoom=view.zoom;sequenceLeft=view.left;sequenceFitPending=false;sequenceRender();
}
function sequenceWheel(event){
 const scroll=event.currentTarget;event.preventDefault();
 if(event.ctrlKey||event.metaKey)sequenceSetZoom(Math.exp(-Math.max(-240,Math.min(240,event.deltaY))*.003),event.clientX-scroll.getBoundingClientRect().left);
 else{const units=event.deltaMode===1?18:event.deltaMode===2?scroll.clientWidth:1;scroll.scrollLeft=SeqView.pan(scroll.scrollLeft,(event.deltaX||event.deltaY)*units,scroll.scrollWidth,scroll.clientWidth);sequenceLeft=scroll.scrollLeft}
}
function sequenceNavigationUpdate(){
 const nav=sequenceNavigation,scroll=$('#sequenceScroll');if(!nav||!scroll)return;
 if(nav.type==='seekbar'){
  const seek=$('#reviewSeek'),rect=seek.getBoundingClientRect(),time=SeqView.time(nav.x,rect.left+5,0,Math.max(1,rect.width-10)/Math.max(.001,sequenceDuration()),sequenceDuration());
  if(Math.abs(sequenceCursor-time)>.001)sequenceSeek(time);return;
 }
 if(nav.type==='pan'){scroll.scrollLeft=SeqView.pan(nav.left,nav.startX-nav.x,scroll.scrollWidth,scroll.clientWidth);sequenceLeft=scroll.scrollLeft;return}
 const time=SeqView.time(nav.x,scroll.getBoundingClientRect().left,scroll.scrollLeft,sequenceZoom,sequenceDuration());
 if(nav.type==='scrub'){if(Math.abs(sequenceCursor-time)>.001)sequenceSeek(time);return}
 const delta=(nav.x-nav.startX+scroll.scrollLeft-nav.left)/sequenceZoom;
 if(Math.abs(nav.x-nav.startX+scroll.scrollLeft-nav.left)<4&&!nav.moved)return;nav.moved=true;
 montageDraft=Seq.clone(nav.project);
 if(nav.edge){const clip=sequenceClip(nav.id);if(nav.edge==='start')Seq.trim(montageDraft,nav.uid,Math.max(0,Math.min(nav.end-.04,nav.start+delta)),nav.end);else Seq.trim(montageDraft,nav.uid,nav.start,Math.min(clip.duration,Math.max(nav.start+.04,nav.end+delta)))}
 else if(montageDraft.free)Seq.move(montageDraft,nav.uid,Math.max(0,nav.at+delta));
 else{const target=Math.max(0,nav.at+delta),others=montageDraft.segments.filter(r=>r.uid!==nav.uid),index=others.filter(r=>r.at+Seq.length(r)/2<target).length;Seq.reorder(montageDraft,nav.uid,index)}
 sequenceRender();
}
function sequenceNavigationTick(){
 const nav=sequenceNavigation,scroll=$('#sequenceScroll');if(!nav||!scroll)return;
 if(nav.type==='scrub'||nav.type==='clip'){
  const rect=scroll.getBoundingClientRect(),edge=24,delta=nav.x<rect.left+edge?-Math.min(24,(rect.left+edge-nav.x)*.3):nav.x>rect.left+scroll.clientWidth-edge?Math.min(24,(nav.x-rect.left-scroll.clientWidth+edge)*.3):0;
  const left=scroll.scrollLeft;if(delta)scroll.scrollLeft=SeqView.pan(left,delta,scroll.scrollWidth,scroll.clientWidth);
  if(scroll.scrollLeft!==left){sequenceLeft=scroll.scrollLeft;sequenceNavigationUpdate()}
 }
 sequenceNavFrame=requestAnimationFrame(sequenceNavigationTick);
}
function sequenceEndNavigation(cancel=false){
 const nav=sequenceNavigation;sequenceNavigation=null;sequenceDrag=null;cancelAnimationFrame(sequenceNavFrame);sequenceNavFrame=null;$('#sequenceScroll')?.classList.remove('panning');
 if(!nav)return;
 if(nav.type==='clip'){
  if(cancel){montageDraft=nav.project;clearTimeout(sequenceMotionTimer);const board=$('#sequenceBoard');if(board)delete board.dataset.reordering;sequenceRender();return}
  if(nav.moved)sequenceRemember();
  if(nav.moved)sequenceSeek(nav.cursor,false,false);
  else sequenceSelect(nav.uid,{time:nav.time,keepPane:true,capture:false});
  const board=$('#sequenceBoard');clearTimeout(sequenceMotionTimer);sequenceMotionTimer=setTimeout(()=>{if(board)delete board.dataset.reordering},220);
 }
 sequencePaintCursor();
}
function sequencePointerDown(event){
 const scroll=event.currentTarget,rect=scroll.getBoundingClientRect();
 if(![0,1].includes(event.button)||event.target.closest('button,input')||!SeqView.contentHit(event.clientX,event.clientY,rect,scroll.clientWidth,scroll.clientHeight))return;
 event.preventDefault();sequenceStop();
 const block=event.target.closest('[data-sequence-part]'),pan=event.button===1||event.altKey;
 sequenceNavigation={type:pan?'pan':block?'clip':'scrub',pointer:event.pointerId,x:event.clientX,y:event.clientY,startX:event.clientX,left:scroll.scrollLeft};
 if(pan)scroll.classList.add('panning');
 else if(block){
  sequenceCapture();sequenceRemember();const row=Seq.find(sequenceProject(),block.dataset.sequencePart);
  Object.assign(sequenceNavigation,{uid:row.uid,id:row.id,at:row.at,start:row.start,end:row.end,edge:event.target.dataset.sequenceEdge||null,project:Seq.clone(montageDraft),moved:false,cursor:sequenceCursor,time:SeqView.time(event.clientX,rect.left,scroll.scrollLeft,sequenceZoom,sequenceDuration())});sequenceDrag=sequenceNavigation;
 }else sequenceSeek(SeqView.time(event.clientX,rect.left,scroll.scrollLeft,sequenceZoom,sequenceDuration()));
 $('#sequenceCursor')?.focus({preventScroll:true});sequenceNavFrame=requestAnimationFrame(sequenceNavigationTick);
}
window.addEventListener('pointermove',event=>{if(sequenceNavigation&&event.pointerId===sequenceNavigation.pointer){sequenceNavigation.x=event.clientX;sequenceNavigation.y=event.clientY;sequenceNavigationUpdate()}});
window.addEventListener('pointerup',event=>{if(sequenceNavigation&&event.pointerId===sequenceNavigation.pointer)sequenceEndNavigation()});
window.addEventListener('pointercancel',()=>sequenceEndNavigation(true));
window.addEventListener('pointerdown',event=>{
 if(event.button!==0||!sequenceActive()||event.target.id!=='reviewSeek')return;
 event.preventDefault();sequenceStop();
 sequenceNavigation={type:'seekbar',pointer:event.pointerId,x:event.clientX,y:event.clientY};sequenceNavigationUpdate();
},true);
showMontage=function(){
 sequenceStop();montageDraft=Seq.normalize(montageDraft);const first=montageDraft.segments[0]?.uid;sequenceId=null;if(!first)throw Error('Добавь запись в монтаж');
 sequenceFitPending=true;sequenceLeft=0;
 sequenceHistory=[];sequenceHistoryAt=-1;sequenceRemember();sequenceSelect(first,{capture:false});
};
const beforeSequenceMode=reviewSetMode;
function sequenceLayout(){
 if(!sequenceEditor||!reviewState)return;const active=sequenceActive(),source=reviewState.editing&&!active;$('#dialog').dataset.sequenceSource=String(source);if(reviewState.timeline)reviewState.timeline.hidden=!source;$('#sequenceBoard')?.toggleAttribute('hidden',!active);sequenceRender();
}
reviewSetMode=function(editing,pane){
 if(!editing&&!sequenceOpening)sequenceStop();
 if(editing&&sequenceEditor&&!sequenceRow()){
  const project=sequenceProject();let row=project.segments.find(r=>r.id===selected.id);
  if(!row&&!project.segments.length){row=Seq.add(project,{id:selected.id,start:trimState.start,end:trimState.end});sequenceRemember()}
  if(!row&&pane==='assembly'&&project.segments.length)return sequenceSelect(project.segments[0].uid);
  if(row){sequenceId=row.uid;sequenceCursor=row.at;sequenceRestore()}
 }
 beforeSequenceMode(editing,pane);sequenceLayout();sequencePaintCursor();
 const exportButton=reviewState?.aside.querySelector('[data-action=export]');if(exportButton&&sequenceActive())exportButton.innerHTML=icon('download')+(reviewState.pane==='export'?'Сохранить монтаж':'К экспорту');
};
const beforeSequenceModal=modal;
modal=function(...args){if(sequenceEditor){if(!sequenceOpening){sequenceEndNavigation(true);sequenceCapture();sequenceStop()}sequenceEditor.abort.abort();sequenceEditor=null}return beforeSequenceModal(...args)};
const beforeSequenceClose=close;
close=function(){sequenceEndNavigation(true);sequenceCapture();sequencePersist();sequenceStop();return beforeSequenceClose()};
const beforeSequenceAction=action;
action=async function(name,el){
 if(sequenceActive()&&(name==='frame-prev'||name==='frame-next')){
  const step=window.studioFrameDuration?.()||1/30,row=sequenceRow(),time=studioEditor?.exactTime??$('#player').currentTime;
  sequenceStop();if(name==='frame-prev'&&time<=row.start+step*.5||name==='frame-next'&&time>=row.end-step*1.5){sequenceSeek(sequenceCursor+(name==='frame-prev'?-step:step));return}
 }
 if(name==='montage-create'){sequenceCapture();return beforeSequenceAction(name,el)}
 if(name==='montage-export'||name==='export'&&sequenceActive()&&reviewState.pane==='export')name='sequence-export';
 if(!name.startsWith('sequence-'))return beforeSequenceAction(name,el);
 const project=sequenceProject(),row=sequenceRow();
 if(name==='sequence-play'){sequencePlay();return}
 if(name==='sequence-export'){
  sequenceCapture();sequenceRemember();if(!project.segments.length)throw Error('Добавь фрагменты в монтаж');
  await task('montage_export',Seq.clone(project),result=>modal('Монтаж готов',`<p>${fmt(result.duration)} · ${result.width} × ${result.height} · ${result.segments} фрагментов</p><div class="result-path">${esc(result.path)}</div>`,button('close','Закрыть','check','quiet')+button('open-exports','Открыть папку','folder','primary')));toast('Начат экспорт монтажа');return;
 }
 if(name==='sequence-add-range'||name==='sequence-add-source'){
  const id=name==='sequence-add-range'?selected.id:$('#sequenceAddSource').value,c=sequenceClip(id);if(!c)throw Error('Выбери исходник');let added;
  const source=name==='sequence-add-range'?{start:trimState.start,end:trimState.end,timer:!!$('#exportTimer')?.checked,show_inputs:!!$('#exportInputs')?.checked,preview_inputs:!!$('#previewInputs')?.checked,input_overlay:inputEditor?.settings,audio:{audio_mode:$('#exportAudioMode')?.value||'mix',audio_tracks:studioEditor?.mixer?.export()||[]}}:{start:0,end:c.duration};
  sequenceMutate(p=>{added=Seq.add(p,{id,...source})});sequenceSelect(added.uid,{capture:false});return;
 }
 if(name==='sequence-fit'){sequenceFitPending=true;sequenceRender();return}
 if(name==='sequence-zoom-in'||name==='sequence-zoom-out'){sequenceSetZoom(name.endsWith('in')?1.4:1/1.4);return}
 if(name==='sequence-undo'||name==='sequence-redo'){
  sequenceStop();
  const at=sequenceHistoryAt+(name.endsWith('undo')?-1:1);if(at<0||at>=sequenceHistory.length)return;sequenceHistoryAt=at;montageDraft=JSON.parse(sequenceHistory[at]);sequencePersist();if(!montageDraft.segments.some(r=>r.uid===sequenceId))sequenceId=montageDraft.segments[0]?.uid;if(sequenceId)sequenceSelect(sequenceId,{capture:false});else sequenceRender();return;
 }
 if(!row)throw Error('Выбери фрагмент на дорожке');let focus=row.uid;
 sequenceStop();
 if(name==='sequence-split')sequenceMutate(p=>{focus=Seq.split(p,row.uid,row.at+($('#player').currentTime-row.start)).uid});
 if(name==='sequence-duplicate')sequenceMutate(p=>{focus=Seq.duplicate(p,row.uid).uid});
 if(name==='sequence-remove')sequenceMutate(p=>{const index=p.segments.indexOf(row);Seq.remove(p,row.uid);focus=p.segments[Math.min(index,p.segments.length-1)]?.uid});
 if(name==='sequence-up'||name==='sequence-down')sequenceMutate(p=>Seq.reorder(p,row.uid,p.segments.indexOf(row)+(name==='sequence-up'?-1:1)));
 if(name==='sequence-range-save'){
  const start=parse($('#sequenceSourceStart').value),end=parse($('#sequenceSourceEnd').value),at=parse($('#sequenceAt').value),c=sequenceClip(row.id);
  if(end>c.duration||start<0||!Number.isFinite(start)||!Number.isFinite(end)||end<=start||!Number.isFinite(at)||at<0)throw Error('Проверь границы и позицию фрагмента');
  sequenceMutate(p=>{Seq.trim(p,row.uid,start,end);if(p.free)Seq.move(p,row.uid,at)});
 }
 if(focus)sequenceSelect(focus,{capture:false});else{sequenceId=null;sequenceRender()}
};
window.addEventListener('click',event=>{
 if(sequenceActive()&&event.target.closest('#reviewPlay')){event.preventDefault();event.stopImmediatePropagation();try{sequencePlay()}catch(error){toast(error.message,true)}}
},true);
document.addEventListener('input',event=>{
 if(sequenceActive()&&event.target.id==='reviewSeek'){event.preventDefault();event.stopImmediatePropagation();sequenceSeek(Number(event.target.value),sequencePlaying)}
},true);
document.addEventListener('afterplay-frame',event=>{if(sequenceActive()&&!sequenceNavigation){const row=sequenceRow();sequenceCursor=Math.max(row.at,Math.min(row.at+Seq.length(row),row.at+event.detail.time-row.start));sequencePaintCursor()}});
window.addEventListener('keydown',e=>{
 if(!sequenceEditor||!sequenceActive()||e.target.closest('input,select,textarea,summary,[role=tab],[contenteditable=true],[role=combobox]'))return;
 const board=!!e.target.closest('#sequenceBoard');
 let command=e.code==='Space'?'sequence-play':board&&e.code==='KeyS'&&!e.ctrlKey?'sequence-split':board&&e.code==='KeyD'&&e.ctrlKey?'sequence-duplicate':board&&e.code==='Delete'?'sequence-remove':board&&e.code==='KeyZ'&&e.ctrlKey?(e.shiftKey?'sequence-redo':'sequence-undo'):null;
 if(['ArrowLeft','ArrowRight','Home','End'].includes(e.code)&&!e.ctrlKey&&!e.altKey){
  e.preventDefault();e.stopImmediatePropagation();sequenceStop();
  if(e.code==='Home'||e.code==='End')sequenceSeek(e.code==='Home'?0:sequenceDuration());
  else if(e.shiftKey)sequenceSeek(sequenceCursor+(e.code==='ArrowLeft'?-1:1));
  else window.action(e.code==='ArrowLeft'?'frame-prev':'frame-next',{dataset:{}}).catch(error=>toast(error.message,true));return;
 }
 if(command){e.preventDefault();e.stopImmediatePropagation();window.action(command,{dataset:{}}).catch(error=>toast(error.message,true))}
},true);
$('#dialog').addEventListener('close',()=>{sequenceEndNavigation(true);sequenceCapture();sequencePersist();sequenceStop();sequenceEditor?.abort.abort();sequenceEditor=null;delete $('#dialog').dataset.sequence;delete $('#dialog').dataset.sequenceSource});
api('montage_project').then(value=>{if(value.project&&!montageDraft){montageDraft=Seq.normalize(value.project);sequenceRemember();if(!$('#dialog').open)render()}}).catch(error=>toast(error.message,true));
