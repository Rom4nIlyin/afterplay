'use strict';
// Targets are visible groups; the native selects are visually replaced dropdowns.
(()=>{
 let dialog,step=-1,offered=false,busy=false,origin=null,frame=0,layoutBusy=false;
 const english=()=>state.settings.language==='en';
 const t=(ru,en)=>english()?en:ru;
 const steps=[
  {tab:'library',target:'.page-head',place:['Библиотека','Library'],title:['Все записи в одном месте','All your recordings'],body:['Во вкладке «Библиотека» находятся видео из подключённых папок. Открой запись, чтобы посмотреть, обрезать или экспортировать фрагмент. Добавить папки можно в «Настройки → Библиотека и папки».','The Library tab shows videos from connected folders. Open a video to watch, trim or export a clip. Add folders in Settings → Library and folders.']},
  {tab:'replay',target:'.capture-mode-actions',place:['Запись и повтор → Управление записью','Recording and replay → Controls'],title:['Вся сессия или последние минуты','A session or the last few minutes'],body:['Открой вкладку «Запись и повтор». Здесь «Включить запись» записывает всю сессию до остановки, а «Включить повтор» хранит последние минуты. Эти режимы можно включать одновременно.','Open Recording and replay. Recording captures the full session until stopped; Replay keeps the last few minutes. Both modes can work together.']},
  {tab:'replay',target:'.studio-profiles > .field',place:['Запись и повтор → Параметры профиля','Recording and replay → Profile settings'],title:['Отдельный профиль для каждой игры','A profile for each game'],body:['Во вкладке «Запись и повтор», в блоке «Параметры профиля», находится список «Профиль записи». Выбери готовый профиль или нажми «Новый профиль». Ниже задаются окно игры, качество и звук. Изменения сохраняются кнопкой внизу страницы.','In Recording and replay, find Profile settings and the Recording profile list. Choose a saved profile or create a new one. Set the game window, quality and audio below, then save at the bottom of the page.']},
  {tab:'settings',target:'#autoSection .section-top, #autoSection .switch-row',place:['Настройки → Автозапись игр и приложений','Settings → Automatic recording'],title:['Автозапись при запуске игры','Record automatically when a game starts'],body:['Во вкладке «Настройки», в блоке «Автозапись игр и приложений», добавь .exe игры и включи переключатель. Повтор начнётся при появлении окна игры. Сохранение последних минут при выходе включается отдельно и по умолчанию выключено.','In Settings → Automatic recording, add the game executable and turn on the switch. Replay starts when its window appears. Saving the last minutes on exit is a separate option, off by default.']},
  {tab:'settings',target:'#saveHotkey',closest:'.field',place:['Настройки → Горячие клавиши','Settings → Keyboard shortcuts'],title:['Сохраняй нужный момент','Save the moment'],body:()=>t('Во вкладке «Настройки», в блоке «Горячие клавиши», можно изменить сочетания. Сохранение повтора сейчас: ','In Settings → Keyboard shortcuts, change the key combinations. Your current replay shortcut is ')+(state.settings.hotkeys?.save||'Ctrl+Alt+F10')+t('. Здесь же назначаются обычная запись, метка и показ окна. Сочетания работают и в трее.','. Recording, markers and the window have their own shortcuts here. They also work in the tray.')},
  {tab:'settings',target:'#startupSettings > .panel-title, #startupSettings > .field',place:['Настройки → Запуск и ярлыки','Settings → Startup and shortcuts'],title:['Запуск вместе с Windows','Start with Windows'],body:['Во вкладке «Настройки», в блоке «Запуск и ярлыки», включается автозапуск с Windows. Приложение запускается в трее. Действие крестика выбирается в настройках окна; при сворачивании в трей запись продолжается. Полный выход — в меню значка трея.','In Settings → Startup and shortcuts, choose whether AFTERPLAY starts with Windows in the tray. Choose the close-button action in window settings. Recording continues in the tray; quit fully from its icon menu.']},
  {tab:'customize',target:'.cinema-palette-card[data-value="onyx"], .cinema-palette-card[data-value="ocean"], .cinema-palette-card[data-value="ember"], .custom-theme[data-value="ember"], .custom-theme[data-value="mist"], .custom-theme[data-value="paper"]',place:['Оформление','Appearance'],title:['Сделай AFTERPLAY своим','Make AFTERPLAY your own'],body:()=>customSettings().cinema_layout!==false?t('В новом дизайне выбери одну из пяти палитр, настрой свои цвета и рисунок бокового меню. Здесь же меняются анимации, звуки и уведомления. Нажми «Сохранить оформление», чтобы оставить результат.','In the new design, choose one of five palettes, adjust colors and select sidebar artwork. Motion, sounds and notifications are also available here. Click Save appearance to keep the result.'):t('В классическом интерфейсе доступны темы Obsidian, Frosted Glass, Aurora, Ember, Mist и Paper, а также собственные фоны. Изменения видны в предпросмотре; нажми «Сохранить оформление».','The classic interface offers Obsidian, Frosted Glass, Aurora, Ember, Mist and Paper themes, plus custom backgrounds. Changes are previewed; click Save appearance to keep them.')}
 ];
 function ensure(){
  if(dialog)return;
  dialog=document.createElement('dialog');dialog.id='onboarding';dialog.setAttribute('aria-labelledby','tourTitle');
  dialog.innerHTML='<svg class="tour-shade" aria-hidden="true"><defs><mask id="tourMask" maskUnits="userSpaceOnUse"><rect class="tour-mask-base" fill="white"/><rect class="tour-mask-target" fill="black" rx="12"/><rect class="tour-mask-nav" fill="black" rx="10"/></mask></defs><rect class="tour-dim" fill="#000" fill-opacity=".66" mask="url(#tourMask)"/></svg><div class="tour-highlight" aria-hidden="true"></div><div class="tour-nav-highlight" aria-hidden="true"></div><section class="tour-card" data-i18n-ignore></section>';
  document.body.append(dialog);
  dialog.addEventListener('cancel',e=>{e.preventDefault();finish('skipped')});
  dialog.addEventListener('click',e=>{
   const control=e.target.closest('[data-tour]');if(!control||busy)return;
   if(control.dataset.tour==='skip')finish('skipped');
   if(control.dataset.tour==='back')showStep(step-1);
   if(control.dataset.tour==='next'){if(step===steps.length-1)finish('completed');else showStep(step+1)}
  });
  dialog.addEventListener('keydown',e=>{if(e.key!=='Escape')e.stopPropagation()});
 }
 function targets(){
  const current=steps[step];if(!current)return [];
  return [...document.querySelectorAll(current.target)].map(e=>current.closest?e.closest(current.closest):e).filter(e=>e&&e.getBoundingClientRect().width>4&&e.getBoundingClientRect().height>4);
 }
 function bounds(elements){
  if(!elements.length)return null;
  const rects=elements.map(e=>e.getBoundingClientRect());
  const left=Math.min(...rects.map(r=>r.left)),top=Math.min(...rects.map(r=>r.top));
  const right=Math.max(...rects.map(r=>r.right)),bottom=Math.max(...rects.map(r=>r.bottom));
  return {left,top,right,bottom,width:right-left,height:bottom-top};
 }
 function content(){
  const current=steps[step],card=dialog.querySelector('.tour-card'),lang=english()?1:0;
  const title=current?current.title[lang]:t('Добро пожаловать в AFTERPLAY','Welcome to AFTERPLAY');
  const body=current?(typeof current.body==='function'?current.body():current.body[lang]):t('Покажем, в каких вкладках находятся запись, профили, настройки и оформление. Семь коротких шагов — примерно минута.','See which tabs contain recording, profiles, settings and appearance. Seven short steps, about a minute.');
  card.innerHTML=`<div class="tour-topline"><span class="tour-eyebrow">${step<0?'AFTERPLAY':t('ШАГ ','STEP ')+(step+1)+' / '+steps.length}</span>${current?`<span class="tour-location">${esc(current.place[lang])}</span>`:''}</div><h2 id="tourTitle">${esc(title)}</h2><p>${esc(body)}</p><div class="tour-progress" aria-hidden="true">${steps.map((_,i)=>`<i class="${i<=step?'active':''}"></i>`).join('')}</div><div class="tour-actions"><button class="quiet" data-tour="skip">${t('Пропустить','Skip')}</button><span></span>${step>0?`<button class="secondary" data-tour="back">${t('Назад','Back')}</button>`:''}<button class="primary" data-tour="next">${step<0?t('Пройти обучение','Take the tour'):step===steps.length-1?t('Готово','Done'):t('Далее','Next')}</button></div><p class="tour-error" role="alert"></p>`;
  card.querySelector('[data-tour=next]').focus({preventScroll:true});
 }
 function drawHole(name,rect,padding){
  const ring=dialog.querySelector(name==='target'?'.tour-highlight':'.tour-nav-highlight'),mask=dialog.querySelector('.tour-mask-'+name);
  const r=rect?{left:Math.max(6,rect.left-padding),top:Math.max(6,rect.top-padding),right:Math.min(innerWidth-6,rect.right+padding),bottom:Math.min(innerHeight-6,rect.bottom+padding)}:null;
  ring.hidden=!r;
  for(const [key,value] of Object.entries(r?{x:r.left,y:r.top,width:Math.max(0,r.right-r.left),height:Math.max(0,r.bottom-r.top)}:{x:0,y:0,width:0,height:0}))mask.setAttribute(key,value);
  if(r)Object.assign(ring.style,{left:r.left+'px',top:r.top+'px',width:(r.right-r.left)+'px',height:(r.bottom-r.top)+'px'});
 }
 function position(){
  if(!dialog?.open||layoutBusy)return;
  layoutBusy=true;
  try{
   const card=dialog.querySelector('.tour-card'),w=innerWidth,h=innerHeight,sidebar=document.querySelector('.sidebar')?.getBoundingClientRect();
   const left=Math.min(sidebar?.right||0,w*.3)+24;
   card.style.width=Math.min(650,w-left-24)+'px';
   card.style.left=Math.max(16,left+(w-left-24-card.offsetWidth)/2)+'px';
   const ch=card.offsetHeight;
   const y=step<0?(h-ch)/2:h-ch-20;
   card.style.top=Math.max(16,y)+'px';
   // Reserve document space so the last settings section can scroll above the card.
   document.documentElement.style.setProperty('--tour-bottom-space',step<0?'0px':(ch+64)+'px');
   let target=bounds(targets());
   if(target&&step>=0){
    const top=20,bottom=Math.max(120,y-24),available=bottom-top;
    const desired=target.height<=available?top+(available-target.height)/2:top;
    if(Math.abs(target.top-desired)>2)scrollBy({top:target.top-desired,behavior:'instant'});
    target=bounds(targets());
   }
   const nav=steps[step]&&document.querySelector(`#nav [data-tab="${steps[step].tab}"]`);
   dialog.querySelector('.tour-shade').setAttribute('viewBox',`0 0 ${w} ${h}`);
   for(const e of dialog.querySelectorAll('.tour-mask-base,.tour-dim')){e.setAttribute('width',w);e.setAttribute('height',h)}
   drawHole('target',target,8);drawHole('nav',nav?.getBoundingClientRect(),4);
  }finally{layoutBusy=false}
 }
 function schedulePosition(){cancelAnimationFrame(frame);frame=requestAnimationFrame(position)}
 function showStep(index){
  step=index;
  if(index>=0){
   const old=restoringRoute;restoringRoute=true;
   try{tab=steps[index].tab;render()}finally{restoringRoute=old}
   // A hidden nav item may still be explained without changing its saved visibility.
   const nav=document.querySelector(`#nav [data-tab="${steps[index].tab}"]`);if(nav){nav.hidden=false;nav.scrollIntoView({block:'nearest',behavior:'instant'})}
  }
  content();position();schedulePosition();
 }
 function open(){
  if(dialog?.open||$('#dialog').open)return;
  ensure();offered=true;origin={tab,scroll:scrollY,focus:document.activeElement};
  step=-1;document.documentElement.dataset.tourActive='true';dialog.showModal();content();position();
 }
 async function finish(status){
  if(busy)return;busy=true;dialog.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{
   state.settings.onboarding=await api('onboarding_config',{status});
   dialog.close();step=-1;delete document.documentElement.dataset.tourActive;document.documentElement.style.removeProperty('--tour-bottom-space');
   const old=restoringRoute;restoringRoute=true;
   try{tab=origin.tab;render()}finally{restoringRoute=old}
   scrollTo({top:origin.scroll,behavior:'instant'});
   if(origin.focus?.isConnected)origin.focus.focus({preventScroll:true});else document.querySelector('[data-action=onboarding-open]')?.focus({preventScroll:true});
  }catch(error){dialog.querySelector('.tour-error').textContent=error.message}
  finally{busy=false;dialog.querySelectorAll('button').forEach(b=>b.disabled=false)}
 }
 const previous=render;
 render=function(){previous();if(dialog?.open)schedulePosition();else if(!offered&&!state.settings.onboarding?.status&&!$('#dialog').open)setTimeout(()=>{if(!offered&&!state.settings.onboarding?.status&&!$('#dialog').open)open()},200)};
 const oldAction=action;
 action=async function(name,el){if(name==='onboarding-open'){open();return}return oldAction(name,el)};
 window.addEventListener('resize',schedulePosition);
})();
