'use strict';
// Keep each original select as the source of values and application events.
(()=>{
 const records=new Map();let serial=0,active=null,animation=null,generation=0;
 let query='',queryTime=0;
 const popup=document.createElement('div');popup.id='ap-dropdown-popup';popup.className='ap-dropdown-popup';popup.hidden=true;popup.setAttribute('role','listbox');
 const hasPopover=typeof popup.showPopover==='function';if(hasPopover)popup.setAttribute('popover','manual');else popup.classList.add('ap-dropdown-fallback');
 const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
 const disabled=option=>option.disabled||option.parentElement?.disabled;
 const visibleOptions=select=>[...select.options].filter(option=>!option.hidden&&!option.parentElement?.hidden);
 const labelFor=select=>{const sibling=(select.closest('.ap-select-control')||select).previousElementSibling;return select.getAttribute('aria-label')||select.labels?.[0]?.textContent?.trim()||(sibling?.matches('label')?sibling.textContent.trim():'')||select.closest('.field')?.querySelector('label')?.textContent.trim()||'Выбор значения'};
 function sync(record){
  const {select,trigger,wrapper,label}=record;if(!select.isConnected)return;
  if(wrapper.hidden!==select.hidden)wrapper.hidden=select.hidden;
  if(trigger.disabled!==select.disabled)trigger.disabled=select.disabled;
  const text=select.selectedOptions[0]?.label||'Выбери значение';if(label.textContent!==text)label.textContent=text;
  const accessible=labelFor(select)+': '+text;if(trigger.getAttribute('aria-label')!==accessible)trigger.setAttribute('aria-label',accessible);
  if(trigger.title!==text)trigger.title=text;
  if(active?.record===record&&(select.disabled||!wrapper.getClientRects().length))closeMenu({immediate:true});
 }
 function paintOptions(){
  if(!active)return;const {record}=active,select=record.select;let lastGroup=null;
  const fragment=document.createDocumentFragment();active.options=visibleOptions(select);
  for(const option of active.options){
   const group=option.parentElement?.tagName==='OPTGROUP'?option.parentElement:null;
   if(group&&group!==lastGroup){const heading=document.createElement('div');heading.className='ap-dropdown-group';heading.textContent=group.label;heading.setAttribute('role','presentation');fragment.append(heading)}lastGroup=group;
   const row=document.createElement('div');row.className='ap-dropdown-option';row.id=record.uid+'-option-'+option.index;row.dataset.index=String(option.index);row.setAttribute('role','option');row.setAttribute('aria-selected',String(option.selected));row.setAttribute('aria-disabled',String(!!disabled(option)));
   const text=document.createElement('span');text.textContent=option.label;const tick=document.createElement('span');tick.className='ap-dropdown-tick';tick.textContent='✓';tick.setAttribute('aria-hidden','true');row.append(text,tick);fragment.append(row);
  }
  if(!active.options.length){const empty=document.createElement('div');empty.className='ap-dropdown-empty';empty.textContent='Нет доступных вариантов';fragment.append(empty)}
  popup.replaceChildren(fragment);highlight(active.index,false);positionMenu();
 }
 function highlight(index,scroll=true){
  if(!active)return;const options=active.options,chosen=options.find(option=>option.index===index&&!disabled(option))||options.find(option=>!disabled(option));active.index=chosen?.index??-1;
  for(const row of popup.querySelectorAll('[data-index]'))row.dataset.highlight=String(Number(row.dataset.index)===active.index);
  const row=popup.querySelector('[data-index="'+active.index+'"]');
  if(row){active.record.trigger.setAttribute('aria-activedescendant',row.id);if(scroll)row.scrollIntoView({block:'nearest'})}else active.record.trigger.removeAttribute('aria-activedescendant');
 }
 function positionMenu(){
  if(!active)return;const rect=active.record.trigger.getBoundingClientRect();
  if(rect.bottom<=0||rect.top>=innerHeight){closeMenu({immediate:true});return}
  const width=Math.min(Math.max(rect.width,210),innerWidth-24),below=innerHeight-rect.bottom-10,above=rect.top-10;
  const up=below<Math.min(popup.scrollHeight,180)&&above>below;active.up=up;
  const room=Math.max(60,Math.min(320,(up?above:below)-12));
  popup.style.width=width+'px';popup.style.maxHeight=room+'px';popup.style.left=Math.max(12,Math.min(rect.left,innerWidth-width-12))+'px';
  popup.style.top=(up?Math.max(12,rect.top-popup.getBoundingClientRect().height-8):rect.bottom+8)+'px';
 }
 function closeMenu({immediate=false,focus=false}={}){
  if(!active&&!animation)return;const old=active,current=getComputedStyle(popup),painted={opacity:current.opacity,clipPath:current.clipPath};active=null;const ticket=++generation;animation?.cancel();animation=null;
  if(old){old.record.trigger.setAttribute('aria-expanded','false');old.record.trigger.removeAttribute('aria-activedescendant')}
  const finish=()=>{if(ticket!==generation)return;popup.hidden=true;if(hasPopover&&popup.matches(':popover-open'))popup.hidePopover();popup.remove();animation?.cancel();animation=null};
  if(immediate||reduced()||!old)finish();else{
   popup.inert=true;const target=old.up?'inset(100% 0 0 0 round 10px)':'inset(0 0 100% 0 round 10px)';
   animation=popup.animate([painted,{opacity:.2,clipPath:target}],{duration:160,easing:'cubic-bezier(.2,.7,.2,1)',fill:'both'});
   animation.finished.then(finish,()=>{});
  }
  if(focus&&old?.record.trigger.isConnected)old.record.trigger.focus({preventScroll:true});
 }
 function openMenu(record){
  sync(record);if(record.select.disabled||record.wrapper.hidden||!record.wrapper.getClientRects().length)return;
  const dialog=document.querySelector('dialog[open]');if(dialog&&!dialog.contains(record.select))return;
  closeMenu({immediate:true});const ticket=++generation;active={record,index:record.select.selectedIndex,options:[],up:false};query='';
  (dialog||document.body).append(popup);popup.hidden=false;popup.inert=false;popup.setAttribute('aria-label',labelFor(record.select));
  record.trigger.setAttribute('aria-expanded','true');if(hasPopover)popup.showPopover();paintOptions();highlight(active.index);
  const from=active.up?'inset(100% 0 0 0 round 10px)':'inset(0 0 100% 0 round 10px)';
  animation=popup.animate([{opacity:.2,clipPath:from},{opacity:1,clipPath:'inset(0 0 0 0 round 10px)'}],{duration:reduced()?0:210,easing:'cubic-bezier(.2,.7,.2,1)',fill:'both'});
  animation.finished.then(()=>{if(ticket===generation){animation.cancel();animation=null}},()=>{});
 }
 function choose(index){
  if(!active)return;const {record}=active,option=record.select.options[index];if(!option||disabled(option))return;
  const changed=record.select.selectedIndex!==index;record.select.selectedIndex=index;sync(record);closeMenu({focus:true});
  if(changed){record.select.dispatchEvent(new Event('input',{bubbles:true}));record.select.dispatchEvent(new Event('change',{bubbles:true}))}
 }
 function prepare(select){
  if(records.has(select)||select.multiple||select.size>1)return;
  const uid='ap-select-'+(++serial),wrapper=document.createElement('span'),trigger=document.createElement('button'),label=document.createElement('span');
  wrapper.className='ap-select-control';trigger.type='button';trigger.className='ap-dropdown-trigger';trigger.id=uid;trigger.dataset.selectId=select.id;trigger.setAttribute('role','combobox');trigger.setAttribute('aria-haspopup','listbox');trigger.setAttribute('aria-controls',popup.id);trigger.setAttribute('aria-expanded','false');
  label.className='ap-dropdown-label';const arrow=document.createElementNS('http://www.w3.org/2000/svg','svg');arrow.setAttribute('class','ap-dropdown-chevron');arrow.setAttribute('viewBox','0 0 24 24');arrow.setAttribute('aria-hidden','true');arrow.innerHTML='<path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="1.8"/>';
  trigger.append(label,arrow);const record={select,wrapper,trigger,label,uid};records.set(select,record);
  select.before(wrapper);wrapper.append(select,trigger);select.classList.add('ap-select-native');select.tabIndex=-1;select.setAttribute('aria-hidden','true');
  trigger.addEventListener('click',()=>{if(active?.record===record)closeMenu({focus:true});else openMenu(record)});
  select.addEventListener('focus',()=>trigger.focus({preventScroll:true}));
  select.addEventListener('change',()=>sync(record));select.addEventListener('input',()=>sync(record));sync(record);
 }
 function scan(root){if(root.nodeType!==Node.ELEMENT_NODE)return;if(root.matches('select'))prepare(root);root.querySelectorAll('select').forEach(prepare)}
 scan(document.body);
 const observer=new MutationObserver(changes=>{
  let optionsChanged=false;
  for(const change of changes){
   if(change.type==='childList')for(const node of change.addedNodes)scan(node);
   const select=change.target.matches?.('select')?change.target:change.target.closest?.('select');if(select&&records.has(select)){sync(records.get(select));if(active?.record.select===select)optionsChanged=true}
  }
  for(const [select,record] of records)if(!select.isConnected){if(active?.record===record)closeMenu({immediate:true});records.delete(select)}
  if(active&&!active.record.wrapper.getClientRects().length)closeMenu({immediate:true});if(optionsChanged&&active)paintOptions();
 });
 observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','hidden','selected','label','value']});
 setInterval(()=>{for(const record of records.values())sync(record)},250);
 popup.addEventListener('pointermove',event=>{const row=event.target.closest('[data-index]');if(row&&row.getAttribute('aria-disabled')!=='true')highlight(Number(row.dataset.index),false)});
 popup.addEventListener('pointerdown',event=>event.preventDefault());
 popup.addEventListener('click',event=>{const row=event.target.closest('[data-index]');if(row)choose(Number(row.dataset.index))});
 document.addEventListener('pointerdown',event=>{if(active&&!popup.contains(event.target)&&!active.record.trigger.contains(event.target))closeMenu()},{capture:true});
 document.addEventListener('focusin',event=>{if(active&&!popup.contains(event.target)&&event.target!==active.record.trigger)closeMenu()});
 document.addEventListener('scroll',event=>{if(active&&!popup.contains(event.target))positionMenu()},{capture:true,passive:true});window.addEventListener('resize',positionMenu);
 document.addEventListener('keydown',event=>{
  const record=[...records.values()].find(record=>record.trigger===event.target);if(!record&&!active)return;
  if(event.key==='Escape'&&active){event.preventDefault();event.stopImmediatePropagation();closeMenu({focus:true});return}
  if(event.key==='Tab'){if(active)closeMenu();return}
  if(!record||record.select.disabled||event.ctrlKey||event.metaKey)return;
  if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
   event.preventDefault();event.stopImmediatePropagation();if(!active){openMenu(record);return}
   const rows=active.options.filter(option=>!disabled(option)),at=rows.findIndex(option=>option.index===active.index);
   const next=event.key==='Home'?0:event.key==='End'?rows.length-1:(at+(event.key==='ArrowDown'?1:-1)+rows.length)%rows.length;if(rows[next])highlight(rows[next].index);return;
  }
  if(event.key==='Enter'||event.code==='Space'){event.preventDefault();event.stopImmediatePropagation();if(active)choose(active.index);else openMenu(record);return}
  if(event.key.length===1&&!event.altKey){
   event.preventDefault();const now=performance.now();query=(now-queryTime<700?query:'')+event.key.toLocaleLowerCase();queryTime=now;if(!active)openMenu(record);
   const option=active?.options.find(option=>!disabled(option)&&option.label.toLocaleLowerCase().startsWith(query));if(option)highlight(option.index);
  }
 },{capture:true});
 window.afterplayDropdowns={isOpen:id=>!!active&&active.record.select.id===id,close:()=>closeMenu(),sync:()=>{for(const record of records.values())sync(record)}};
})();
