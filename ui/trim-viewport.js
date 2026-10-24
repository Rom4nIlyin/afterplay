'use strict';
// Seconds are the source of truth; zoom never changes the selected clip range.
globalThis.TrimViewport={
 clamp(duration,start,span){
  const minimum=Math.min(duration,.25);
  span=Math.max(minimum,Math.min(duration,span));
  return {viewStart:Math.max(0,Math.min(duration-span,start)),viewEnd:Math.max(0,Math.min(duration-span,start))+span};
 },
 zoom(s,factor,anchor=.5){
  anchor=Math.max(0,Math.min(1,anchor));
  const span=s.viewEnd-s.viewStart,time=s.viewStart+span*anchor,next=span/factor;
  return this.clamp(s.duration,time-next*anchor,next);
 },
 pan(s,delta){return this.clamp(s.duration,s.viewStart+delta,s.viewEnd-s.viewStart)},
 fit(s){const length=s.end-s.start,padding=Math.max(.15,length*.15);return this.clamp(s.duration,s.start-padding,length+2*padding)},
 time(s,fraction){return Math.max(0,Math.min(s.duration,s.viewStart+Math.max(0,Math.min(1,fraction))*(s.viewEnd-s.viewStart)))}
};
