'use strict';
// Delegation also covers buttons created by dialogs, profiles and the library.
(()=>{
 function prepareButton(button){
  if(button.matches('[role=slider],[data-edge],.trim-handle')){
   button.classList.remove('ap-cursor','ap-cursor-relative');return;
  }
  if(button.classList.contains('ap-cursor'))return;
  const relative=getComputedStyle(button).position==='static';
  button.classList.add('ap-cursor');if(relative)button.classList.add('ap-cursor-relative');
 }
 function prepare(root){
  if(root.nodeType!==Node.ELEMENT_NODE)return;
  if(root.matches('button'))prepareButton(root);
  root.querySelectorAll('button').forEach(prepareButton);
 }
 prepare(document.body);
 const observer=new MutationObserver(records=>{
  for(const record of records)for(const node of record.addedNodes)prepare(node);
 });
 observer.observe(document.body,{childList:true,subtree:true});
 let pending=null,frame=null;
 function paint(button,x,y){
  if(!button.isConnected||button.disabled||button.getAttribute('aria-disabled')==='true')return;
  const bounds=button.getBoundingClientRect();if(!bounds.width||!bounds.height)return;
  const unit=(value,start,length)=>Math.max(0,Math.min(100,(value-start)/length*100)).toFixed(2)+'%';
  button.style.setProperty('--cursor-x',unit(x,bounds.left,bounds.width));
  button.style.setProperty('--cursor-y',unit(y,bounds.top,bounds.height));
 }
 document.addEventListener('pointerover',event=>{
  const button=event.target.closest('button.ap-cursor');
  if(button&&!button.contains(event.relatedTarget))paint(button,event.clientX,event.clientY);
 },{passive:true});
 document.addEventListener('pointermove',event=>{
  const button=event.target.closest('button.ap-cursor');if(!button)return;
  pending={button,x:event.clientX,y:event.clientY};
  if(frame!==null)return;
  frame=requestAnimationFrame(()=>{frame=null;const latest=pending;pending=null;if(latest)paint(latest.button,latest.x,latest.y)});
 },{passive:true});
})();
