'use strict';
// Finishing layer: local commands, editing history and deliberate motion.
(()=>{
 customDefaults.cinema_motion='subtle';
 const en=()=>state.settings.language==='en',t=(ru,english)=>en()?english:ru;
 const on=()=>document.body.classList.contains('onyx-cinema');
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 let history=null,restoring=false,dragging=false,queued=false,lastTab=tab,searchTimer=null,guardBusy=false;
 const activeAnimations=new Set();
 function motion(){return reduced.matches?'off':customSettings().cinema_motion||'subtle'}
 function animate(element,frames){
  if(!element||!on()||motion()==='off'||document.hidden)return;
  const animation=element.animate(frames,{duration:motion()==='full'?230:150,easing:'cubic-bezier(.2,.8,.2,1)'});
  activeAnimations.add(animation);animation.finished.then(()=>activeAnimations.delete(animation),()=>activeAnimations.delete(animation));
 }
 function cancelMotion(){for(const animation of activeAnimations)animation.cancel();activeAnimations.clear()}
 document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelMotion()});reduced.addEventListener('change',cancelMotion);
 const oldApply=customApply;customApply=function(){oldApply();document.body.dataset.studioMotion=motion();if(motion()==='off')cancelMotion()};
 function snapshot(){return trimState?{start:trimState.start,end:trimState.end}:null}
 const same=(a,b)=>a&&b&&Math.abs(a.start-b.start)<.00001&&Math.abs(a.end-b.end)<.00001;
 function updateHistory(){
  for(const [name,disabled] of [['undo',!history||history.at===0],['redo',!history||history.at>=history.items.length-1]]){
   const button=document.querySelector(`[data-action="studio-${name}"]`);if(button)button.disabled=disabled;
  }
 }
 function commit(){
  queued=false;if(restoring||dragging||!history||history.id!==trimState?.id)return;
  const value=snapshot();if(same(value,history.items[history.at]))return;
  history.items.splice(history.at+1);history.items.push(value);if(history.items.length>80)history.items.shift();history.at=history.items.length-1;updateHistory();
 }
 function schedule(){if(queued)return;queued=true;queueMicrotask(commit)}
 const oldSetTrim=setTrim;setTrim=function(...args){oldSetTrim(...args);if(on()&&history&&!restoring)schedule()};
 document.addEventListener('pointerdown',event=>{if(event.target.closest('#trimTrack'))dragging=true},true);
 for(const name of ['pointerup','pointercancel','lostpointercapture'])document.addEventListener(name,()=>{if(dragging){dragging=false;schedule()}},true);
 function restore(direction){
  commit();if(!history)return;const next=history.at+direction;if(next<0||next>=history.items.length)return;
  history.at=next;const value=history.items[next];restoring=true;
  try{setTrim(value.start,value.end);$('#trimError').textContent='';reviewClock()}finally{restoring=false;updateHistory()}
 }
 let notesBaseline=null;
 const notes=()=>$('#clipTags')?JSON.stringify([$('#clipTags').value,$('#clipNote').value,$('#clipFavorite').checked]):null;
 const dirty=()=>!!reviewState&&notesBaseline!==null&&notes()!==notesBaseline;
 function updateDirty(){const badge=$('#studioDirty');if(badge){badge.hidden=!dirty();badge.textContent=t('Есть изменения','Unsaved changes')}}
 const oldSave=saveClip;saveClip=async function(){await oldSave();notesBaseline=notes();updateDirty()};
 function decorateEditor(){
  if(!reviewState||!on())return;
  $('#dialog').classList.add('studio-refined');
  const heading=$('#dialog .dialog-head');
  if(!$('#studioDirty')){const badge=document.createElement('span');badge.id='studioDirty';badge.hidden=true;heading.insertBefore(badge,heading.querySelector('.review-head-actions'))}
  if(!reviewState.gif&&!$('#studioHistory')){
   const strip=document.createElement('div');strip.id='studioHistory';strip.innerHTML=`<button data-action="studio-undo" title="${t('Отменить обрезку · Ctrl+Z','Undo trim · Ctrl+Z')}" aria-label="${t('Отменить обрезку','Undo trim')}">${icon('refresh')}</button><button data-action="studio-redo" title="${t('Вернуть обрезку · Ctrl+Shift+Z','Redo trim · Ctrl+Shift+Z')}" aria-label="${t('Вернуть обрезку','Redo trim')}">${icon('refresh')}</button><span>${t('I — начало · O — конец','I — in · O — out')}</span>`;
   $('.review-timeline .trim-heading')?.prepend(strip);
  }
  const tabs={trim:['Обрезка','Trim','film'],sound:['Звук','Audio','volume'],export:['Экспорт','Export','download'],notes:['Заметки','Notes','tag']};
  for(const button of document.querySelectorAll('[data-review-pane]')){const data=tabs[button.dataset.reviewPane];button.innerHTML=icon(data[2])+`<span>${t(data[0],data[1])}</span>`}
  updateHistory();updateDirty();
 }
 const oldOpen=openClip;openClip=function(id){
  clearTimeout(searchTimer);history=null;notesBaseline=null;oldOpen(id);if(!reviewState)return;
  if(trimState&&selected?.id===trimState.id)history={id:trimState.id,items:[snapshot()],at:0};notesBaseline=notes();decorateEditor();
  animate($('#dialog'),[{opacity:0,transform:'translateY(8px) scale(.99)'},{opacity:1,transform:'none'}]);
 };
 const oldMode=reviewSetMode;reviewSetMode=function(...args){
  const oldPane=reviewState?.pane,wasEditing=reviewState?.editing;oldMode(...args);decorateEditor();
  if(reviewState?.editing&&(oldPane!==reviewState.pane||!wasEditing))animate($(`[data-review-panel="${reviewState.pane}"]`),[{opacity:.2,transform:'translateX(6px)'},{opacity:1,transform:'none'}]);
 };
 $('#dialog').addEventListener('close',()=>{history=null;notesBaseline=null;$('#dialog').classList.remove('studio-refined')});
 document.addEventListener('input',event=>{if(event.target.matches('#clipTags,#clipNote,#clipFavorite'))updateDirty()});
 document.addEventListener('change',event=>{if(event.target.matches('#clipFavorite'))updateDirty()});
 async function requestClose(){
  if(guardBusy)return;guardBusy=true;
  try{
   let guard=$('#studioUnsaved');if(!guard){guard=document.createElement('dialog');guard.id='studioUnsaved';document.body.append(guard)}
   guard.innerHTML=`<h2>${t('Сохранить изменения?','Save your changes?')}</h2><p>${t('Теги, заметка и избранное ещё не сохранены.','Tags, the note and favorite status have not been saved.')}</p><div class="actions"><button class="quiet" data-choice="continue">${t('Продолжить монтаж','Keep editing')}</button><button class="secondary" data-choice="discard">${t('Не сохранять','Discard')}</button><button class="primary" data-choice="save">${t('Сохранить','Save')}</button></div><p class="studio-guard-error" role="alert"></p>`;
   const outcome=await new Promise(resolve=>{guard.onclick=e=>{const choice=e.target.closest('[data-choice]')?.dataset.choice;if(choice)resolve(choice)};guard.oncancel=e=>{e.preventDefault();resolve('continue')};guard.showModal()});
   if(outcome==='continue'){guard.close();return}
   if(outcome==='save'){
    try{await saveClip()}catch(error){guard.querySelector('.studio-guard-error').textContent=error.message;guard.close();toast(error.message,true);return}
   }
   guard.close();close();await refresh();
  }finally{guardBusy=false}
 }
 document.addEventListener('click',event=>{if(on()&&event.target.closest('#dialog [data-action="close"]')&&dirty()){event.preventDefault();event.stopImmediatePropagation();requestClose().catch(error=>toast(error.message,true))}},true);
 $('#dialog').addEventListener('cancel',event=>{if(on()&&dirty()){event.preventDefault();event.stopImmediatePropagation();requestClose().catch(error=>toast(error.message,true))}},true);
 let commandDialog=null,commandIndex=0,visibleCommands=[];
 function commands(){
  if(reviewState)return [
   {label:t('Обрезка','Trim'),run:()=>reviewSetMode(true,'trim')},{label:t('Звуковые дорожки','Audio tracks'),run:()=>reviewSetMode(true,'sound')},{label:t('Параметры экспорта','Export settings'),run:()=>reviewSetMode(true,'export')},{label:t('Теги и заметки','Tags and notes'),run:()=>reviewSetMode(true,'notes')},
   ...(!reviewState.gif?[{label:t('Отменить обрезку','Undo trim'),key:'Ctrl Z',run:()=>restore(-1)},{label:t('Вернуть обрезку','Redo trim'),key:'Ctrl Shift Z',run:()=>restore(1)}]:[])
  ].filter(c=>!reviewState.gif||!['Обрезка','Trim','Звуковые дорожки','Audio tracks'].includes(c.label));
  return [['library','Все записи','All recordings'],['replay','Запись и повтор','Recording and replay'],['favorites','Избранное','Favorites'],['tags','Теги','Tags'],['exports','Экспорт','Exports'],['customize','Оформление','Appearance'],['settings','Настройки','Settings']].map(([id,ru,english])=>({label:t(ru,english),run:()=>{tab=id;tagFilter='';render()}}));
 }
 function paintCommands(){
  const query=$('#studioCommandSearch').value.trim().toLocaleLowerCase();visibleCommands=commands().filter(c=>c.label.toLocaleLowerCase().includes(query));commandIndex=Math.min(commandIndex,Math.max(0,visibleCommands.length-1));
  $('#studioCommandList').innerHTML=visibleCommands.length?visibleCommands.map((c,i)=>`<button type="button" role="option" id="studioCommand-${i}" data-command="${i}" aria-selected="${i===commandIndex}"><span>${esc(c.label)}</span><kbd>${esc(c.key||'↵')}</kbd></button>`).join(''):`<p>${t('Команды не найдены','No commands found')}</p>`;
  const input=$('#studioCommandSearch');if(visibleCommands.length)input.setAttribute('aria-activedescendant','studioCommand-'+commandIndex);else input.removeAttribute('aria-activedescendant');
 }
 function runCommand(i){const c=visibleCommands[i];if(!c)return;commandDialog.close();try{Promise.resolve(c.run()).catch(e=>toast(e.message,true))}catch(error){toast(error.message,true)}}
 function showCommands(){
  if($('#studioUnsaved')?.open)return;
  if(!commandDialog){commandDialog=document.createElement('dialog');commandDialog.id='studioCommands';document.body.append(commandDialog);commandDialog.addEventListener('click',e=>{const row=e.target.closest('[data-command]');if(row)runCommand(Number(row.dataset.command))})}
  if(commandDialog.open){commandDialog.close();return}
  commandDialog.innerHTML=`<div class="studio-command-search">${icon('search')}<input id="studioCommandSearch" role="combobox" aria-autocomplete="list" aria-expanded="true" aria-controls="studioCommandList" aria-label="${t('Найти команду','Find a command')}" placeholder="${t('Что хочешь сделать?','What would you like to do?')}" autocomplete="off"><kbd>Esc</kbd></div><div id="studioCommandList" role="listbox"></div><footer>${t('↑ ↓ — выбрать · Enter — открыть','↑ ↓ — select · Enter — open')}<span>Ctrl K</span></footer>`;
  commandIndex=0;paintCommands();$('#studioCommandSearch').addEventListener('input',()=>{commandIndex=0;paintCommands()});
  $('#studioCommandSearch').addEventListener('keydown',event=>{if(['ArrowDown','ArrowUp','Enter'].includes(event.key)){event.preventDefault();event.stopPropagation();if(event.key==='Enter')runCommand(commandIndex);else{commandIndex=(commandIndex+(event.key==='ArrowDown'?1:-1)+Math.max(1,visibleCommands.length))%Math.max(1,visibleCommands.length);paintCommands()}}});
  commandDialog.showModal();$('#studioCommandSearch').focus();
 }
 function decorate(){
  if(!on()){$('#studioCommandButton')?.remove();return}
  if(!$('#studioCommandButton')){const button=document.createElement('button');button.id='studioCommandButton';button.className='icon-button';button.dataset.action='studio-commands';button.innerHTML=icon('search');button.title=t('Команды · Ctrl+K','Commands · Ctrl+K');button.setAttribute('aria-label',button.title);$('.header-right')?.prepend(button)}
  const design=$('.cinema-design-panel');
  if(design&&!$('#studioMotion')){const field=document.createElement('div');field.id='studioMotion';field.innerHTML=customSelect(t('Анимации','Motion'),'cinema_motion',{subtle:t('Плавные','Subtle'),full:t('Выразительные','Expressive'),off:t('Выключены','Off')});$('.cinema-color-grid')?.after(field)}
  // Avoid two competing save bars and legacy background controls in Cinema.
  if(tab==='customize'){
   document.body.dataset.studioAppearance='true';
   const background=$('.custom-tabs [data-value="background"]');if(background)background.textContent=t('Дополнительно','Advanced');
   if(customPane==='background'&&$('.custom-panel'))$('.custom-panel').classList.add('studio-classic-background');
  }else delete document.body.dataset.studioAppearance;
 }
 const oldRender=render;render=function(){const changed=lastTab!==tab;lastTab=tab;oldRender();decorate();if(changed)animate($('#main'),[{opacity:.1,transform:'translateY(6px)'},{opacity:1,transform:'none'}])};
 document.addEventListener('input',event=>{
  if(!on()||event.target.id!=='searchInput')return;event.stopImmediatePropagation();search=event.target.value;clearTimeout(searchTimer);
  if(event.isComposing)return;
  searchTimer=setTimeout(()=>{if(!$('#dialog').open){const input=$('#searchInput'),position=input?.selectionStart;render();if(input===document.activeElement&&input?.type!=='search')input.setSelectionRange(position,position)}},120);
 },true);
 document.addEventListener('compositionend',event=>{if(on()&&event.target.id==='searchInput')event.target.dispatchEvent(new Event('input',{bubbles:true}))});
 const oldAction=action;action=async function(name,el){
  if(name==='studio-commands'){showCommands();return}
  if(name==='studio-undo'){restore(-1);return}
  if(name==='studio-redo'){restore(1);return}
  if(name==='cinema-more'||name==='cinema-clear')clearTimeout(searchTimer);
  if(name==='custom-save'){await oldAction(name,el);decorate();return}
  return oldAction(name,el);
 };
 document.addEventListener('keydown',event=>{
  if(!on()||event.target.closest('.hotkey-input')||event.isComposing)return;
  if((event.ctrlKey||event.metaKey)&&event.code==='KeyK'){event.preventDefault();event.stopImmediatePropagation();showCommands();return}
  if(commandDialog?.open||$('#studioUnsaved')?.open||event.target.closest('input,textarea,select,[contenteditable=true],[role=combobox]'))return;
  if(reviewState&&trimState&&event.ctrlKey&&event.code==='KeyZ'){event.preventDefault();event.stopImmediatePropagation();restore(event.shiftKey?1:-1);return}
  if(reviewState&&trimState&&!event.ctrlKey&&!event.altKey&&['KeyI','KeyO'].includes(event.code)){
   event.preventDefault();event.stopImmediatePropagation();action(event.code==='KeyI'?'set-in':'set-out',event.target).catch(error=>toast(error.message,true));return;
  }
  const card=event.target.closest('#cinemaGrid .clip-card');if(card&&['ArrowRight','ArrowLeft','ArrowUp','ArrowDown'].includes(event.key)){
   const cards=[...document.querySelectorAll('#cinemaGrid .clip-card')],index=cards.indexOf(card),columns=getComputedStyle($('#cinemaGrid')).display==='flex'?1:getComputedStyle($('#cinemaGrid')).gridTemplateColumns.split(' ').length;
   const delta={ArrowRight:1,ArrowLeft:-1,ArrowDown:columns,ArrowUp:-columns}[event.key],next=cards[Math.max(0,Math.min(cards.length-1,index+delta))];event.preventDefault();event.stopImmediatePropagation();next?.focus();
  }
 },true);
 // Keep the all-page command button available even after the regular renderer runs.
 if(Object.keys(state.settings).length){decorate();customApply()}
 window.afterplayStudioPolish={history:()=>history?{id:history.id,length:history.items.length,at:history.at}:null,dirty,motion,commands:showCommands};
})();
