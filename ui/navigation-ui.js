'use strict';
// Real History API entries also let native WebView2 Back/Forward work naturally.
let restoringRoute=false;
const routeSnapshot=()=>({afterplay:true,tab,tag:tagFilter,clip:$('#dialog').open?selected?.id||null:null});
const routeKey=r=>JSON.stringify([r.tab,r.tag||'',r.clip||null]);
function rememberRoute(){
 if(restoringRoute)return;
 const route=routeSnapshot();
 if(routeKey(route)===routeKey(history.state||{}))return;
 history.pushState(route,'',location.pathname+location.search+'#'+route.tab+(route.clip?'/'+route.clip:''));
}
history.replaceState(routeSnapshot(),'',location.href);
const renderBeforeHistory=render;
render=function(){renderBeforeHistory();rememberRoute()};
const openBeforeHistory=openClip;
openClip=function(id){openBeforeHistory(id);rememberRoute()};
const closeBeforeHistory=close;
close=function(){closeBeforeHistory();rememberRoute()};
window.addEventListener('popstate',event=>{
 const route=event.state;if(!route?.afterplay)return;
 restoringRoute=true;
 try{
  if($('#dialog').open)closeBeforeHistory();
  tab=['library','replay','favorites','tags','exports','settings','customize'].includes(route.tab)?route.tab:'library';
  tagFilter=route.tag||'';render();
  if(route.clip&&state.clips.some(c=>c.id===route.clip))openClip(route.clip);
 }finally{restoringRoute=false}
});
function historyDirection(direction){direction<0?history.back():history.forward()}
// Some mice send DOM side-button events, others invoke native browser navigation.
document.addEventListener('pointerdown',e=>{if(e.button===3||e.button===4)e.preventDefault()},true);
document.addEventListener('pointerup',e=>{if(e.button===3||e.button===4){e.preventDefault();e.stopPropagation();historyDirection(e.button===3?-1:1)}},true);
document.addEventListener('auxclick',e=>{if(e.button===3||e.button===4)e.preventDefault()},true);
document.addEventListener('keydown',e=>{
 if(e.target.classList?.contains('hotkey-input'))return;
 if(e.key==='BrowserBack'||e.key==='BrowserForward'||(e.altKey&&['ArrowLeft','ArrowRight'].includes(e.key))){
  e.preventDefault();historyDirection(['BrowserBack','ArrowLeft'].includes(e.key)?-1:1);
 }
},true);
