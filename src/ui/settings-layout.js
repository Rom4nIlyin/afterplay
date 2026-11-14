'use strict';
(()=>{
 let panel=null,resize=null,mutation=null,frame=0;
 function release(){resize?.disconnect();mutation?.disconnect();panel=null;resize=null;mutation=null}
 function schedule(){if(!frame)frame=requestAnimationFrame(arrange)}
 function arrange(){
  frame=0;const current=tab==='settings'?document.querySelector('.settings-panel'):null;
  if(!current){release();return}
  if(panel!==current){
   release();panel=current;
   resize=new ResizeObserver(schedule);
   mutation=new MutationObserver(()=>{for(const card of panel.children)resize.observe(card);schedule()});
   mutation.observe(panel,{childList:true});for(const card of panel.children)resize.observe(card);
  }
  const compact=matchMedia('(max-width:1050px)').matches;
  panel.classList.toggle('settings-masonry',!compact);
  const cards=[...panel.children].filter(el=>el.classList.contains('settings-card'));
  const spans=cards.map(card=>compact?'':`span ${Math.ceil((card.getBoundingClientRect().height+20)/4)}`);
  cards.forEach((card,index)=>{if(card.style.gridRowEnd!==spans[index])card.style.gridRowEnd=spans[index]});
 }
 const beforeRender=render;render=function(){beforeRender();schedule()};
 window.addEventListener('resize',schedule);
 document.fonts?.ready.then(schedule);
 window.afterplaySettingsLayout={refresh:schedule};schedule();
})();
