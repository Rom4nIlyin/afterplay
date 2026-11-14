'use strict';
(function(root){
 let serial=0;
 const clone=v=>JSON.parse(JSON.stringify(v)),uid=()=>`part-${Date.now().toString(36)}-${++serial}`;
 const length=r=>r.end-r.start,round=v=>Math.round(v*1000000)/1000000;
 function normalize(project){
  const p={name:'Мой монтаж',resolution:'source',audio_mode:'mix',format:'original',free:false,...clone(project||{})};
  let cursor=0;const used=new Set();
  p.segments=(p.segments||[]).map(row=>{
   const r={...row,uid:row.uid||uid()};if(used.has(r.uid))r.uid=uid();used.add(r.uid);
   if(!Number.isFinite(r.start)||!Number.isFinite(r.end)||r.start<0||r.end<=r.start)throw Error('Проверь границы фрагмента');
   r.at=Number.isFinite(r.at)?Math.max(0,r.at):cursor;cursor=r.at+length(r);return r;
  }).sort((a,b)=>a.at-b.at);
  return p;
 }
 function pack(p){let at=0;for(const r of p.segments){r.at=round(at);at+=length(r)}return p}
 function resolve(p){p.segments.sort((a,b)=>a.at-b.at);let end=0;for(const r of p.segments){r.at=round(Math.max(end,r.at));end=r.at+length(r)}return p}
 function total(p){return p.segments.reduce((end,r)=>Math.max(end,r.at+length(r)),0)}
 function find(p,id){const r=p.segments.find(r=>r.uid===id);if(!r)throw Error('Фрагмент не найден');return r}
 function add(p,row,index=p.segments.length){if(p.segments.length>=50)throw Error('Не больше 50 фрагментов');const r={...clone(row),uid:uid()};r.at=total(p);p.segments.splice(index,0,r);if(!p.free)pack(p);else resolve(p);return r}
 function reorder(p,id,index){const r=find(p,id);p.segments.splice(p.segments.indexOf(r),1);p.segments.splice(Math.max(0,Math.min(index,p.segments.length)),0,r);return pack(p)}
 function move(p,id,at){find(p,id).at=Math.max(0,round(at));return resolve(p)}
 function trim(p,id,start,end){const r=find(p,id);if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start)throw Error('Проверь границы фрагмента');r.start=start;r.end=end;return p.free?resolve(p):pack(p)}
 function split(p,id,time){const r=find(p,id),offset=time-r.at;if(offset<.02||length(r)-offset<.02)throw Error('Поставь курсор внутри фрагмента');if(p.segments.length>=50)throw Error('Не больше 50 фрагментов');const source=round(r.start+offset),right={...clone(r),uid:uid(),start:source,at:round(time)};r.end=source;p.segments.splice(p.segments.indexOf(r)+1,0,right);return right}
 function duplicate(p,id){const r=find(p,id);return add(p,r,p.segments.indexOf(r)+1)}
 function remove(p,id){p.segments=p.segments.filter(r=>r.uid!==id);if(!p.free)pack(p);return p}
 function at(p,time){return p.segments.find(r=>time>=r.at-1e-6&&time<r.at+length(r)-1e-6)||null}
 const api={normalize,clone,uid,length,total,find,pack,resolve,add,reorder,move,trim,split,duplicate,remove,at};root.SequenceModel=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof window==='object'?window:globalThis);
