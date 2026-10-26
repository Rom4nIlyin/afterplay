'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.join(__dirname,'..');
const studio=fs.readFileSync(path.join(root,'ui/studio-ui.js'),'utf8');
const review=fs.readFileSync(path.join(root,'ui/review-ui.js'),'utf8');
async function run(){
 const listeners={},player={paused:true},button={click(){player.paused=!player.paused;this.clicks++},clicks:0};
 const fullscreen={clicks:0,click(){this.clicks++}};
 const keyboard={reviewState:{player},document:{addEventListener(name,callback,options){assert.equal(options.capture,true);listeners[name]=callback}},$:id=>id==='#reviewFullscreen'?fullscreen:button};
 vm.runInNewContext(review.slice(review.indexOf('function reviewHandlesSpace('),review.indexOf('window.reviewDebug=')),keyboard);
 function key(repeat=false,form=false){return {code:'Space',repeat,target:{closest:()=>form?{}:null},preventDefault(){this.defaultPrevented=true},stopImmediatePropagation(){this.stopped=true}}}
 const down=key();listeners.keydown(down);
 assert.equal(player.paused,false);assert.equal(down.defaultPrevented,true);assert.equal(down.stopped,true);
 listeners.keydown(key(true));assert.equal(button.clicks,1,'holding Space must not repeatedly toggle playback');
 const up=key();listeners.keyup(up);assert.equal(up.defaultPrevented,true);assert.equal(up.stopped,true);assert.equal(button.clicks,1);
 listeners.keydown(key());assert.equal(player.paused,true);assert.equal(button.clicks,2);
 listeners.keydown(key(false,true));assert.equal(button.clicks,2,'form controls keep their keyboard behavior');
 const f=key();f.code='KeyF';listeners.keydown(f);assert.equal(fullscreen.clicks,1);assert.equal(f.defaultPrevented,true);
 const held=key(true);held.code='KeyF';listeners.keydown(held);assert.equal(fullscreen.clicks,1,'held F toggles once');
 const typed=key(false,true);typed.code='KeyF';listeners.keydown(typed);assert.equal(fullscreen.clicks,1,'typing F in a field cannot change fullscreen');

 const events={},visibility=[];let time=1;
 const image={src:'old',get hidden(){return this.value||false},set hidden(value){this.value=value;visibility.push(value)}};
 const video={paused:true,seeking:false,pause(){this.paused=true},addEventListener(name,fn){(events[name]??=new Set()).add(fn)},removeEventListener(name,fn){events[name]?.delete(fn)},get currentTime(){return time},set currentTime(value){time=value;this.seeking=true;for(const fn of events.seeking||[])fn();setImmediate(()=>{this.seeking=false;for(const fn of [...events.seeked||[]])fn()})}};
 const current={id:'clip',player:video,audio:{pause(){}},image,exactTime:1};
 const context={studioEditor:current,current,player:video,image,api:async(_,args)=>({time:args.time+args.direction/30,image:'decoded-'+args.time}),
  Image:class{decode(){return Promise.resolve()}},document:{dispatchEvent(){}},CustomEvent:class{},$:()=>({}),updateTrimVisuals(){},
  trimFormat:String,setTimeout,clearTimeout,alignAudio(){},drawWave(){},on:(object,event,fn)=>object.addEventListener(event,fn)};
 vm.createContext(context);
 vm.runInContext(studio.match(/ function clearExact\(\)\{[^\n]+/)[0],context);
 vm.runInContext(studio.match(/ on\(player,'seeking',[^\n]+/)[0],context);
 vm.runInContext(studio.slice(studio.indexOf('async function stepFrame('),studio.indexOf('const beforeStudioOpen=')),context);
 for(let i=0;i<10;i++)await context.stepFrame(i<6?1:-1);
 assert.equal(visibility.length,10);assert.equal(visibility.every(value=>value===false),true,'precise image stays visible through every native seek');
 assert.ok(Math.abs(current.exactTime-(1+2/30))<1e-8);assert.equal(current.frameSeeking,false);
 let release;context.api=()=>new Promise(resolve=>{release=resolve});
 const pending=context.stepFrame(1);video.paused=false;image.hidden=true;
 release({time:5,image:'stale'});await pending;
 assert.equal(image.hidden,true,'an old frame request cannot cover resumed playback');
 console.log('Playback keyboard and frame presentation regressions passed.');
}
run().catch(error=>{console.error(error);process.exitCode=1});
