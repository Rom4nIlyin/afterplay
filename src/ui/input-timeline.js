'use strict';
// Checkpoints make arbitrary seeks independent from the length of a session.
(function(root){
 class InputTimeline{
  constructor(events){
   this.events=events||[];this.checkpoints=[new Set()];const held=new Set();
   for(let i=0;i<this.events.length;i++){
    const [,code,down]=this.events[i];down?held.add(code):held.delete(code);
    if((i+1)%256===0)this.checkpoints.push(new Set(held));
   }
  }
  at(time){
   let lo=0,hi=this.events.length;
   while(lo<hi){const mid=(lo+hi)>>>1;if(this.events[mid][0]<=time)lo=mid+1;else hi=mid}
   const checkpoint=Math.floor(lo/256),held=new Set(this.checkpoints[checkpoint]);
   for(let i=checkpoint*256;i<lo;i++){const [,code,down]=this.events[i];down?held.add(code):held.delete(code)}
   return held;
  }
 }
 root.InputTimeline=InputTimeline;
 if(typeof module==='object'&&module.exports)module.exports=InputTimeline;
})(typeof window==='object'?window:globalThis);
