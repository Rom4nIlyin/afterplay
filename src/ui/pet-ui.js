'use strict';
// One local sprite atlas, one animation loop. No work continues while hidden.
(()=>{
 const SIZE=144,FOOT=SIZE*234/256,HALF=SIZE/2,PURR_GAIN=.3;
 const rows={idle:0,walk:1,sleep:2,groom:3,jump:4,startled:5,petted:6,stretch:7};
 const reduced=matchMedia('(prefers-reduced-motion: reduce)');
 const clamp=(value,low,high)=>Math.max(low,Math.min(high,value));
 const random=(low,high)=>low+Math.random()*(high-low);
 const cfg=()=>({enabled:false,sound:true,...state.settings.pet,...pendingChoice});
 let layer,cat,sprite,bubble,loaded=false,groomLoaded=false,failed=false,raf=0,lastDraw=0,frameKey='',dirty=true;
 let x=0,y=0,facing=1,surface=null,surfaces=[],motion=null,mood='idle',since=0,until=0,bubbleUntil=0;
 let pending=false,pendingChoice=null,audio=null,purr=null,purrBytes=null,purrBuffer=null,audioRequest=0,enabledBefore=false;

 function create(){
  if(layer)return;
  layer=document.createElement('div');layer.id='rysya-layer';layer.hidden=true;
  cat=document.createElement('button');cat.id='rysya-cat';cat.type='button';
  cat.title='Рыся · ЛКМ — испугать · ПКМ — погладить';
  cat.setAttribute('aria-label','Рыся. Левый клик — испугать, правый клик или Enter — погладить.');
  sprite=document.createElement('span');sprite.className='rysya-sprite';sprite.setAttribute('aria-hidden','true');cat.append(sprite);
  bubble=document.createElement('span');bubble.className='rysya-bubble';bubble.setAttribute('aria-hidden','true');layer.append(cat,bubble);document.body.append(layer);
  cat.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();react(event.detail===0?'petted':'startled')});
  cat.addEventListener('contextmenu',event=>{event.preventDefault();event.stopPropagation();react('petted')});
  cat.addEventListener('pointerdown',event=>{event.stopPropagation();if(event.button===2)event.preventDefault()});
  const image=new Image();image.onload=()=>{loaded=true;sync()};image.onerror=()=>{failed=true;sync();toast('Не удалось загрузить Рыську. Проверь целостность папки программы.',true)};image.src=base+'pets/rysya.png';
  const groom=new Image();groom.onload=()=>{groomLoaded=true;cat.dataset.groomReady='true';frameKey='';sync()};groom.src=base+'pets/rysya-groom.png';
  purrBytes=fetch(base+'pets/purr.wav').then(response=>{if(!response.ok)throw Error('Purr audio unavailable');return response.arrayBuffer()});
  purrBytes.catch(()=>{});
 }
 function blocked(){return document.hidden||!!window.customNativeHidden||!!document.fullscreenElement||!!$('#dialog')?.open||!!$('#onboarding')?.open}
 function scan(){
  const result=[],seen=new Set();
  const selectors='#nav .nav-button, #main .settings-card, #main .panel, #main .custom-panel, #main .clip-card, #main .toolbar, #main .replay-config-group, #main .studio-profiles, #main button';
  for(const element of document.querySelectorAll(selectors)){
   if(element.closest('[hidden],.hidden')||element.disabled||element.closest('#petSettings')||element.matches('.settings-panel,.clip-delete,[data-action="delete-video"]'))continue;
   const r=element.getBoundingClientRect(),style=getComputedStyle(element);
   if(style.visibility==='hidden'||style.display==='none'||r.width<62||r.height<18||r.top<FOOT+16||r.top>innerHeight-28||r.right<HALF||r.left>innerWidth-HALF)continue;
   const left=Math.max(HALF+5,r.left+Math.min(28,r.width/4)),right=Math.min(innerWidth-HALF-5,r.right-Math.min(28,r.width/4));
   if(right<left)continue;
   const probe=document.elementFromPoint(clamp((left+right)/2,1,innerWidth-1),r.top+Math.min(8,r.height/2));
   if(probe&&probe!==element&&!element.contains(probe)&&!probe.contains(element))continue;
   const key=[Math.round(left),Math.round(right),Math.round(r.top)].join(':');if(seen.has(key))continue;seen.add(key);
   result.push({element,left,right,y:r.top});
  }
  // The window edge remains available on sparse tabs and very small windows.
  result.push({element:null,left:HALF+8,right:Math.max(HALF+8,innerWidth-HALF-8),y:innerHeight-24});
  surfaces=result;dirty=false;
 }
 function label(text,seconds=1.8){bubble.textContent=text;bubbleUntil=performance.now()+seconds*1000}
 function setMood(next,seconds){
  mood=next;since=performance.now();until=since+seconds*1000;cat.dataset.mood=next;frameKey='';
  if(next!=='petted')stopPurr();
 }
 function landAt(target,position){surface=target;x=clamp(position??x,target.left,target.right);y=target.y;motion=null}
 function settle(){
  scan();const nearest=surfaces.reduce((best,s)=>Math.hypot(clamp(x,s.left,s.right)-x,s.y-y)<Math.hypot(clamp(x,best.left,best.right)-x,best.y-y)?s:best,surfaces[0]);
  landAt(nearest);setMood('idle',random(2,4));
 }
 function initial(){
  scan();const candidates=surfaces.filter(s=>s.element&&!s.element.closest('.sidebar'));
  const target=candidates.find(s=>s.element.matches('.settings-card,.panel,.clip-card'))||candidates[0]||surfaces.at(-1);
  landAt(target,target.right);setMood('idle',3);label('Рыся',2.6);
 }
 function jump(flee=false){
  let choices=surfaces.filter(s=>s.element!==surface?.element&&Math.abs(s.y-y)<330&&Math.abs(clamp(x,s.left,s.right)-x)<650).map(target=>{
   const edge=Math.abs(target.left-x)>Math.abs(target.right-x)?target.left:target.right;
   const tx=flee?clamp(clamp(edge,x-540,x+540),target.left,target.right):clamp(x+random(-250,250),target.left,target.right);
   return {target,tx};
  });
  if(flee){
   choices=choices.filter(({target,tx})=>Math.hypot(tx-x,target.y-y)>=100);
   if(!choices.length&&surface){const tx=Math.abs(surface.left-x)>Math.abs(surface.right-x)?surface.left:surface.right;choices=[{target:surface,tx}]}
  }
  if(!choices.length)return walk();
  const {target,tx}=choices[Math.floor(Math.random()*choices.length)];
  const duration=clamp(.75+Math.hypot(tx-x,target.y-y)/650,.75,1.5);
  facing=tx<x?-1:1;motion={kind:'jump',flee,target,fromX:x,fromY:y,toX:tx,toY:target.y,start:performance.now(),duration:duration*1000,height:clamp(65+Math.abs(target.y-y)*.38,65,150)};
  setMood('jump',duration);
 }
 function walk(){
  if(!surface)return settle();
  let tx=clamp(x+(Math.random()<.5?-1:1)*random(60,210),surface.left,surface.right);
  if(Math.abs(tx-x)<25)tx=Math.abs(surface.right-x)>Math.abs(surface.left-x)?surface.right:surface.left;
  if(Math.abs(tx-x)<20){setMood('groom',random(3,5));return}
  facing=tx<x?-1:1;const duration=Math.abs(tx-x)/random(36,54);
  motion={kind:'walk',target:surface,fromX:x,fromY:y,toX:tx,toY:y,start:performance.now(),duration:duration*1000};setMood('walk',duration);
 }
 function decide(){
  if(reduced.matches){setMood('idle',3600);return}
  if(mood==='startled'){jump(true);return}
  const choice=Math.random();
  if(mood==='sleep'){setMood('stretch',1.8);return}
  if(choice<.18)setMood('sleep',random(12,25));
  else if(choice<.39)setMood('groom',random(4,7));
  else if(choice<.62)walk();
  else if(choice<.88)jump();
  else setMood('idle',random(3,6));
 }
 function react(next){
  if(layer?.hidden)return;
  // A click during a leap first finds a real perch, so the cat cannot freeze in mid-air.
  if(motion?.kind==='jump')landAt(motion.target,motion.toX);else motion=null;
  setMood(next,next==='petted'?5.5:2.4);label(next==='petted'?'Мур-р-р ♡':'Мр-р?!');
  if(next==='petted'&&cfg().sound)startPurr();wake();
 }
 function draw(now){
  const elapsed=(now-since)/1000;
  let frame=0;
  if(mood==='idle')frame=[0,0,0,0,0,0,0,1,2,3,4,5][Math.floor(elapsed*3)%12];
  else if(mood==='jump')frame=clamp(Math.floor((now-motion.start)/motion.duration*6),0,5);
  else if(mood==='startled')frame=Math.min(4,Math.floor(elapsed*8));
  else if(mood==='stretch')frame=Math.min(5,Math.floor(elapsed*3.5));
  else frame=Math.floor(elapsed*({walk:8,sleep:2,groom:5,petted:4}[mood]||4))%6;
  const row=mood==='groom'?0:rows[mood],key=(mood==='groom'?'groom-'+groomLoaded:row)+':'+frame;
  if(key!==frameKey){sprite.style.backgroundPosition=`${frame*20}% ${row*100/7}%`;frameKey=key}
  cat.style.transform=`translate3d(${Math.round(x-HALF)}px,${Math.round(y-FOOT)}px,0) scaleX(${facing})`;
  bubble.style.left=clamp(x,56,innerWidth-56)+'px';bubble.style.top=Math.max(30,y-FOOT+12)+'px';bubble.classList.toggle('visible',now<bubbleUntil);
 }
 function tick(now){
  raf=0;if(blocked()||!cfg().enabled||!loaded){sync();return}
  // Keep sprite/UI work at 30fps even on 144/240Hz monitors.
  if(now-lastDraw<1000/30){wake();return}lastDraw=now;
  if(dirty){
   const previous=surface?.element;scan();
   if(motion){
    const target=surfaces.find(s=>s.element===motion.target.element);
    if(target&&Math.abs(target.y-motion.toY)<2&&motion.toX>=target.left&&motion.toX<=target.right)motion.target=target;
    else settle();
   }
   else if(previous){const current=surfaces.find(s=>s.element===previous);if(current)landAt(current);else settle()}
   else landAt(surfaces.at(-1));
  }
  if(motion){
   const progress=clamp((now-motion.start)/motion.duration,0,1);
   x=motion.fromX+(motion.toX-motion.fromX)*progress;y=motion.fromY+(motion.toY-motion.fromY)*progress;
   if(motion.kind==='jump')y-=4*motion.height*progress*(1-progress);
   if(progress>=1){landAt(motion.target,motion.toX);setMood('idle',random(1.5,3))}
  }else if(now>=until)decide();
  x=clamp(x,HALF+5,Math.max(HALF+5,innerWidth-HALF-5));y=clamp(y,FOOT+8,innerHeight-10);
  draw(now);
  if(!reduced.matches||mood==='petted'||mood==='startled'||mood==='stretch')wake();
 }
 function wake(){if(!raf&&layer&&!layer.hidden)raf=requestAnimationFrame(tick)}
 function stopPurr(){
  audioRequest++;
  if(purr){const old=purr,request=audioRequest;purr=null;try{old.gain.gain.setTargetAtTime(0,audio.currentTime,.025);old.source.stop(audio.currentTime+.1)}catch{};setTimeout(()=>{if(request===audioRequest&&!purr&&audio?.state==='running')audio.suspend().catch(()=>{})},120)}
  else if(audio&&audio.state==='running')audio.suspend().catch(()=>{});
 }
 async function startPurr(){
  stopPurr();
  const request=audioRequest;
  try{
   const Audio=window.AudioContext||window.webkitAudioContext;if(!Audio)return;
   audio??=new Audio();await audio.resume();
   purrBuffer??=await audio.decodeAudioData((await purrBytes).slice(0));
   if(request!==audioRequest||mood!=='petted'||!cfg().enabled||!cfg().sound||blocked())return;
   const source=audio.createBufferSource(),gain=audio.createGain();source.buffer=purrBuffer;gain.gain.value=PURR_GAIN;source.connect(gain);gain.connect(audio.destination);
   const current={source,gain};purr=current;
   source.onended=()=>{source.disconnect();gain.disconnect();if(purr===current){purr=null;audio.suspend().catch(()=>{})}};source.start();
  }catch(error){if(request===audioRequest)stopPurr();console.warn('Rysya purr unavailable',error)}
 }
 function updateButton(){
  const toggle=document.querySelector('[data-action="pet-toggle"]');if(toggle){const text=cfg().enabled?'Скрыть питомца':'Показать питомца';if(toggle.textContent!==text)toggle.textContent=text;toggle.setAttribute('aria-pressed',String(cfg().enabled));toggle.disabled=pending}
  const sound=$('#petSound');if(sound){sound.disabled=pending;sound.checked=cfg().sound}
 }
 function sync(){
  if(cfg().enabled)create();updateButton();if(!layer)return;
  const active=cfg().enabled&&loaded&&!failed&&!blocked();
  if(!cfg().sound&&purr)stopPurr();
  if(!active){layer.hidden=true;if(raf)cancelAnimationFrame(raf);raf=0;stopPurr();enabledBefore=false;return}
  layer.hidden=false;if(!enabledBefore){initial();enabledBefore=true}wake();
 }
 async function save(change){
  if(pending)return;pending=true;pendingChoice=change;sync();
  try{state.settings.pet=await api('pet_config',change);sync()}
  catch(error){toast(error.message,true);updateButton()}
  finally{pending=false;pendingChoice=null;sync()}
 }
 function settingsCard(){
  if(tab!=='settings'||$('#petSettings'))return;
  $('.settings-panel')?.insertAdjacentHTML('beforeend',`<section class="settings-card" id="petSettings"><div class="rysya-settings-head"><span class="rysya-portrait" aria-hidden="true"></span><div><h2>Рыся · твой питомец</h2><p class="hint">Чёрный кот с характером. Гуляет по открытой вкладке, прыгает на блоки и кнопки, умывается и спит.</p></div></div><div class="actions"><button class="primary" data-action="pet-toggle" aria-pressed="${cfg().enabled}">${cfg().enabled?'Скрыть питомца':'Показать питомца'}</button></div><label class="check"><input id="petSound" type="checkbox" ${cfg().sound?'checked':''}>Мурчать при поглаживании</label><p class="hint">Левый клик — испугать: Рыся выгнет спину и распушит хвост. Правый клик — погладить. С клавиатуры: Tab до Рыси, Enter — погладить.</p><p class="hint">Во время просмотра видео и обучения Рыся прячется. Вернётся, когда закроешь окно.</p></section>`);
  $('#languageSettings')?.after($('#petSettings'));
 }
 const beforeRender=window.renderDesktopExtras;window.renderDesktopExtras=function(){beforeRender?.();settingsCard();dirty=true;sync()};
 const beforeUpdate=window.updatePreferences;window.updatePreferences=function(){beforeUpdate?.();sync()};
 document.addEventListener('click',event=>{if(event.target.closest('[data-action="pet-toggle"]'))save({enabled:!cfg().enabled})});
 document.addEventListener('change',event=>{if(event.target.id==='petSound')save({sound:event.target.checked})});
 document.addEventListener('visibilitychange',sync);window.addEventListener('resize',()=>{dirty=true;sync()});
 document.addEventListener('scroll',()=>{dirty=true},true);document.addEventListener('fullscreenchange',sync);
 new MutationObserver(records=>{if(records.some(record=>[...record.addedNodes,...record.removedNodes].some(node=>node.nodeType===1)))dirty=true}).observe($('#main'),{childList:true,subtree:true});
 new MutationObserver(sync).observe($('#dialog'),{attributes:true,attributeFilter:['open']});
  reduced.addEventListener('change',()=>{motion=null;if(cat)setMood('idle',1);dirty=true;sync()});
 window.addEventListener('pagehide',()=>{stopPurr();if(raf)cancelAnimationFrame(raf);audio?.close().catch(()=>{})});
 setInterval(sync,800);
 // Read-only diagnostics also let the native smoke test inspect the live companion.
 window.afterplayPet={info:()=>({enabled:cfg().enabled,sound:cfg().sound,loaded,failed,visible:!!layer&&!layer.hidden,mood,x,y,facing,moving:motion?.kind||null,fleeing:!!motion?.flee,surface:surface?.element?.className||'window-edge',surfaces:surfaces.length,purring:!!purr,audioState:audio?.state||'closed',purrRecording:true,purrGain:PURR_GAIN,frames:48,groomCorrected:groomLoaded})};
 settingsCard();sync();
})();
