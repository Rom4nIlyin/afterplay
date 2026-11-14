'use strict';
(function(root){
 const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));
 function width(duration,zoom,viewport){return Math.max(viewport,(duration+Math.min(2,duration*.02))*zoom)}
 function fit(duration,viewport){return clamp(Math.max(1,viewport-20)/Math.max(.1,duration),.02,250)}
 function pan(left,delta,content,viewport){return clamp(left+delta,0,Math.max(0,content-viewport))}
 function zoom(duration,viewport,current,left,anchor,factor){
  const scale=clamp(current*factor,.02,250),time=(left+anchor)/current;
  return {zoom:scale,left:pan(time*scale-anchor,0,width(duration,scale,viewport),viewport)};
 }
 function time(x,left,scroll,scale,duration){return clamp((x-left+scroll)/scale,0,duration)}
 // Native scrollbar presses belong to the browser, never to the playhead.
 function contentHit(x,y,rect,clientWidth,clientHeight){return x>=rect.left&&x<rect.left+clientWidth&&y>=rect.top&&y<rect.top+clientHeight}
 function follow(left,viewport,time,scale,content){const x=time*scale,pad=Math.min(50,viewport*.1);return x<left+pad||x>left+viewport-pad?pan(x-viewport*.25,0,content,viewport):left}
 const api={width,fit,pan,zoom,time,contentHit,follow};root.SequenceViewport=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof window==='object'?window:globalThis);
