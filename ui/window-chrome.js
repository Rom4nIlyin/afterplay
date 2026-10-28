'use strict';
// The actual window bar lives above the WebView, so modal tools cannot cover it.
(()=>{
 const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
 const context=canvas.getContext('2d',{willReadFrequently:true});
 let applied='',pending=false,frame=0,disabled=false;
 function color(value,fallback){
  context.clearRect(0,0,1,1);context.fillStyle=fallback;
  if(value.trim())context.fillStyle=value.trim();context.fillRect(0,0,1,1);
  return '#'+[...context.getImageData(0,0,1,1).data].slice(0,3).map(n=>n.toString(16).padStart(2,'0')).join('');
 }
 async function sync(){
  if(disabled||pending||!state.replay)return;
  const style=getComputedStyle(document.body),read=(name,fallback)=>color(style.getPropertyValue(name),fallback);
  const colors={background:read('--bg','#101314'),panel:read('--panel','#151c1d'),text:read('--text','#edf4f0'),muted:read('--muted','#9cacaa'),accent:read('--accent','#8bf5c8')};
  const key=JSON.stringify([colors,state.replay.phase,state.replay.continuous,state.replay.replay_enabled,Math.floor(state.replay.elapsed||0),state.settings.language]);
  if(key===applied)return;pending=true;
  try{const result=await api('window_chrome_config',{colors});if(result.styled)applied=key;else if(!result.native){disabled=true;clearInterval(timer)}}
  catch(error){console.warn('Window bar:',error.message)}finally{pending=false}
 }
 function schedule(){cancelAnimationFrame(frame);frame=requestAnimationFrame(sync)}
 const previous=render;render=function(){previous();schedule()};
 const observer=new MutationObserver(schedule);observer.observe(document.body,{attributes:true,attributeFilter:['style','class']});observer.observe(document.documentElement,{attributes:true,attributeFilter:['style','class']});
 const timer=setInterval(sync,1000);schedule();
})();
