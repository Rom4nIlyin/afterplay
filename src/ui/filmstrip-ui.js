'use strict';
// Render tiles independently. Zoom changes sampling, never a thumbnail's shape.
let filmstripPreview=null;
function disposeFilmstrip(){
 clearTimeout(trimImageTimer);trimImageRequest++;
 filmstripPreview?.observer.disconnect();filmstripPreview=null;
}
function drawFilmstrip(){
 const current=filmstripPreview,s=trimState;if(!current||!s||current.id!==s.id)return;
 const box=current.box,width=box.clientWidth,height=box.clientHeight;if(!width||!height)return;
 const dpr=Math.min(2,window.devicePixelRatio||1),canvas=current.canvas;
 const drawKey=[width,height,dpr,s.viewStart,s.viewEnd,current.image?.src].join(':');if(current.drawKey===drawKey)return;current.drawKey=drawKey;
 const pixelWidth=Math.round(width*dpr),pixelHeight=Math.round(height*dpr);
 if(canvas.width!==pixelWidth)canvas.width=pixelWidth;if(canvas.height!==pixelHeight)canvas.height=pixelHeight;
 const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,width,height);
 ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
 if(!current.image)return;
 const count=current.frames,tileWidth=current.image.naturalWidth/count,tileHeight=current.image.naturalHeight;
 const columns=Math.max(1,Math.ceil(width/(height*16/9))),cell=width/columns,span=s.viewEnd-s.viewStart;
 let croppedWidth=tileWidth,croppedHeight=tileHeight;
 if(tileWidth/tileHeight>cell/height)croppedWidth=tileHeight*cell/height;else croppedHeight=tileWidth*height/cell;
 current.sampled=[];
 for(let i=0;i<columns;i++){
  const time=s.viewStart+span*(i+.5)/columns;if(time<current.start||time>current.end)continue;
  const index=Math.max(0,Math.min(count-1,Math.floor((time-current.start)/(current.end-current.start)*count)));
  ctx.drawImage(current.image,index*tileWidth+(tileWidth-croppedWidth)/2,(tileHeight-croppedHeight)/2,croppedWidth,croppedHeight,i*cell,0,cell,height);current.sampled.push(index);
 }
 current.canvas.dataset.columns=String(columns);current.canvas.dataset.scaleX=String(cell/croppedWidth);current.canvas.dataset.scaleY=String(height/croppedHeight);
}
function requestFilmstrip(){
 const current=filmstripPreview,s=trimState;if(!current||!s||current.id!==s.id)return;
 if(window.reviewLayoutEnabled&&$('#dialog').dataset.editing!=='true'){clearTimeout(trimImageTimer);current.requestKey=null;return}
 drawFilmstrip();const width=current.box.clientWidth,height=current.box.clientHeight;if(!width||!height)return;
 const frames=Math.min(64,Math.max(1,Math.ceil(width/(height*16/9))));
 const key=[s.viewStart.toFixed(3),s.viewEnd.toFixed(3),frames].join(':');
 if(current.requestKey===key)return;current.requestKey=key;clearTimeout(trimImageTimer);const ticket=++trimImageRequest;
 current.box.setAttribute('aria-busy','true');
 trimImageTimer=setTimeout(()=>{
  if(filmstripPreview!==current||trimImageRequest!==ticket)return;
  const start=s.viewStart,end=s.viewEnd,image=new Image();
  image.onload=()=>{
   if(filmstripPreview!==current||trimImageRequest!==ticket)return;
   current.image=image;current.start=start;current.end=end;current.frames=frames;
   const strip=$('#trimFilmstrip');strip.src=image.src;strip.dataset.start=start;strip.dataset.end=end;strip.dataset.frames=frames;
   current.box.setAttribute('aria-busy','false');drawFilmstrip();
  };
  image.onerror=()=>{if(filmstripPreview!==current||trimImageRequest!==ticket)return;current.box.setAttribute('aria-busy','false');current.requestKey=null;if($('#trimHint'))$('#trimHint').textContent='Кадры предпросмотра недоступны. Выделение отрезка продолжает работать.'};
  image.src=`${base}filmstrip/${current.id}?start=${start.toFixed(3)}&end=${end.toFixed(3)}&frames=${frames}`;
 },200);
}
function prepareFilmstrip(){
 disposeFilmstrip();const strip=$('#trimFilmstrip');if(!strip||!trimState)return;
 const box=strip.parentElement,canvas=document.createElement('canvas');canvas.id='trimFilmstripCanvas';canvas.className='trim-filmstrip-canvas';canvas.setAttribute('aria-hidden','true');box.append(canvas);
 box.setAttribute('aria-label','Кадры видео для выбора отрезка');strip.classList.add('trim-filmstrip-source');
 const observer=new ResizeObserver(requestFilmstrip);filmstripPreview={id:trimState.id,box,canvas,observer,image:null,start:0,end:0,frames:0,requestKey:null,sampled:[]};observer.observe(box);
 strip.removeAttribute('data-src');strip.removeAttribute('src');requestFilmstrip();
}
const beforeFilmstripOpen=openClip;
openClip=function(id){beforeFilmstripOpen(id);prepareFilmstrip()};
const beforeFilmstripVisuals=updateTrimVisuals;
updateTrimVisuals=function(){beforeFilmstripVisuals();drawFilmstrip()};
changeTrimView=function(view){if(!trimState)return;Object.assign(trimState,view);updateTrimVisuals();requestFilmstrip()};
window.requestTrimFilmstrip=requestFilmstrip;
$('#dialog').addEventListener('close',disposeFilmstrip);
