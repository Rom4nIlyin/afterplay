'use strict';
// Text-node translation leaves DOM nodes, event handlers and input values intact.
(()=>{
 const dictionary=window.AFTERPLAY_EN||{},normalized=new Map(Object.entries(dictionary).map(([key,value])=>[key.replace(/\s+/g,' ').trim(),value]));
 const escape=value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
 const fragments=new RegExp('(?<![А-Яа-яЁё])(?:'+Object.keys(dictionary).sort((a,b)=>b.length-a.length).map(escape).join('|')+')(?![А-Яа-яЁё])','g');
 const textMemory=new WeakMap(),attributeMemory=new WeakMap();
 let language='ru',busy=false,pending=false;
 const protectedContent='script,style,textarea,[data-i18n-ignore],.clip-name,.clip-tags,.custom-card-game,.result-path,.review-file-name,.review-dialog .dialog-head h2,[data-action="custom-preset-load"],.custom-pinned,[data-tag],#exportList .row-main b,.auto-app b';
 function translated(value){
  if(language!=='en'||!/[А-Яа-яЁё]/.test(value))return value;
  const trimmed=value.trim(),exact=dictionary[trimmed]??normalized.get(trimmed.replace(/\s+/g,' '));
  if(exact!==undefined)return value.slice(0,value.length-value.trimStart().length)+exact+value.slice(value.trimEnd().length);
  return value.replace(fragments,key=>dictionary[key]);
 }
 function userContent(element){
  return element?.closest(protectedContent)||element?.matches('#captureProfile option')&&(element.value!=='screen:default'||!['По умолчанию · весь экран','Default · entire screen'].includes(element.textContent));
 }
 function node(node){
  const parent=node.parentElement;if(!parent||userContent(parent))return;
  const old=textMemory.get(node),source=old&&node.nodeValue===old.result?old.source:node.nodeValue;
  const result=translated(source);textMemory.set(node,{source,result});if(node.nodeValue!==result)node.nodeValue=result;
 }
 function attributes(element){
  if(userContent(element))return;
  const memory=attributeMemory.get(element)||{};
  for(const name of ['title','aria-label','placeholder','alt']){
   if(!element.hasAttribute(name))continue;
   const value=element.getAttribute(name),previous=memory[name],source=previous&&value===previous.result?previous.source:value;
   // Paths, app names and entered profile names remain exactly as supplied.
   if(name==='title'&&(/[A-Z]:[\\/]/i.test(source)||element.closest('.clip-info')))continue;
   const result=translated(source);memory[name]={source,result};if(value!==result)element.setAttribute(name,result);
  }
  attributeMemory.set(element,memory);
 }
 function walk(root=document.body){
  if(!root||busy)return;busy=true;
  try{
   if(root.nodeType===Node.TEXT_NODE){node(root);return}
   if(root.nodeType!==Node.ELEMENT_NODE||root.matches('script,style,[data-i18n-ignore]'))return;
   attributes(root);
   const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT|NodeFilter.SHOW_ELEMENT);
   while(walker.nextNode()){const item=walker.currentNode;if(item.nodeType===Node.TEXT_NODE)node(item);else attributes(item)}
  }finally{busy=false}
 }
 function apply(value){
  language=value==='en'?'en':'ru';document.documentElement.lang=language;
  try{localStorage.setItem('afterplay.language',language)}catch{}
  walk();
 }
 window.i18nLocale=()=>language==='en'?'en-US':'ru-RU';
 function untranslated(){
  const items=[],walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){
   const item=walker.currentNode,parent=item.parentElement,value=item.nodeValue.trim();
   if(value&&/[А-Яа-яЁё]/.test(value)&&!userContent(parent)&&parent?.getClientRects().length)items.push({text:value,tag:parent.tagName,id:parent.id});
  }
  for(const element of document.querySelectorAll('[title],[aria-label],[placeholder],[alt]')){
   if(userContent(element)||!element.getClientRects().length)continue;
   for(const name of ['title','aria-label','placeholder','alt']){const value=element.getAttribute(name);if(value&&/[А-Яа-яЁё]/.test(value)&&!/[A-Z]:[\\/]/i.test(value))items.push({text:value,tag:element.tagName,id:element.id,attribute:name})}
  }
  return items;
 }
 window.afterplayI18n={get language(){return language},text:translated,apply,translate:walk,untranslated};
 const beforeRender=render;
 render=function(){
  const value=state.settings.language||'ru';language=value==='en'?'en':'ru';document.documentElement.lang=language;
  beforeRender();walk();
 };
 const beforePreferences=window.updatePreferences;
 window.updatePreferences=function(){beforePreferences?.();if((state.settings.language||'ru')!==language)apply(state.settings.language);else walk()};
 const beforeSettings=window.renderDesktopExtras;
 window.renderDesktopExtras=function(){
  beforeSettings?.();
  if(tab!=='settings'||$('#interfaceLanguage'))return;
  const card=document.createElement('section');card.className='settings-card';card.id='languageSettings';
  card.innerHTML='<h2>Язык интерфейса</h2><div class="field"><label for="interfaceLanguage">Язык</label><select id="interfaceLanguage"><option value="ru" data-i18n-ignore>Русский</option><option value="en" data-i18n-ignore>English</option></select><small>Переключение применяется сразу и сохраняется между запусками.</small></div>';
  $('.settings-panel')?.prepend(card);$('#interfaceLanguage').value=language;
 };
 document.addEventListener('change',async event=>{
  if(event.target.id!=='interfaceLanguage')return;
  const control=event.target,previous=language;control.disabled=true;
  try{const result=await api('language_config',{language:control.value});state.settings.language=result.language;apply(result.language);render();toast(translated('Язык сохранён'))}
  catch(error){control.disabled=false;control.value=previous;toast(translated(error.message),true)}
 });
 const observer=new MutationObserver(records=>{
  const roots=new Set();
  for(const record of records){
   if(record.type==='characterData')roots.add(record.target);
   else if(record.type==='attributes')roots.add(record.target);
   else for(const child of record.addedNodes)roots.add(child);
  }
  for(const root of roots)walk(root);
 });
 observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['title','aria-label','placeholder','alt']});
 try{language=localStorage.getItem('afterplay.language')==='en'?'en':'ru'}catch{}
 apply(language);
})();
