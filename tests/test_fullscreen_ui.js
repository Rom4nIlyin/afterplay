'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../ui/review-ui.js'),'utf8');
let now=0,serial=0;const timers=new Map();
function advance(ms){now+=ms;for(const [id,timer] of [...timers])if(timer.at<=now){timers.delete(id);timer.callback()}}
const document=new EventTarget(),window=new EventTarget();
class Element extends EventTarget{
 constructor(){super();this.classes=new Set();this.classList={toggle:(name,on)=>on?this.classes.add(name):this.classes.delete(name)};this.inert=false}
 contains(element){return element===this}
 focus(){document.activeElement=this}
 querySelector(){return this.menuOpen?{}:null}
}
const stage=new Element(),controls=new Element(),seek=new Element(),player=new Element(),abort=new AbortController();
document.fullscreenElement=stage;document.activeElement=stage;
const context={document,window,setTimeout(callback,delay){const id=++serial;timers.set(id,{callback,at:now+delay});return id},clearTimeout:id=>timers.delete(id)};
vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function installFullscreenUI('),source.indexOf('// End fullscreen UI visibility.')),context);
const ui=context.installFullscreenUI({stage,controls,seek,player,signal:abort.signal,on:(element,event,callback)=>element.addEventListener(event,callback,{signal:abort.signal})});
const hidden=()=>stage.classes.has('review-controls-hidden');
ui.update();advance(1499);assert.equal(hidden(),false);advance(1);assert.equal(hidden(),true);assert.equal(controls.inert,true);assert.equal(seek.inert,true);
stage.dispatchEvent(new Event('pointermove'));assert.equal(hidden(),false);advance(1000);stage.dispatchEvent(new Event('pointermove'));advance(1499);assert.equal(hidden(),false);advance(1);assert.equal(hidden(),true);
stage.dispatchEvent(new Event('pointerenter'));document.activeElement=controls;advance(1500);assert.equal(document.activeElement,stage,'hidden buttons cannot keep keyboard focus');
stage.dispatchEvent(new Event('pointerleave'));assert.equal(hidden(),true);player.dispatchEvent(new Event('play'));assert.equal(hidden(),true,'media events cannot show controls while the cursor is outside');
stage.dispatchEvent(new Event('pointerenter'));assert.equal(hidden(),false);window.dispatchEvent(new Event('blur'));assert.equal(hidden(),true);
stage.dispatchEvent(new Event('pointerenter'));controls.menuOpen=true;advance(1500);assert.equal(hidden(),false,'an open speed menu stays usable');
controls.menuOpen=false;controls.dispatchEvent(new Event('toggle'));advance(1500);assert.equal(hidden(),true);
stage.dispatchEvent(new Event('pointerenter'));const pointer=new Event('pointerdown');Object.defineProperty(pointer,'target',{value:seek});stage.dispatchEvent(pointer);advance(2000);assert.equal(hidden(),false,'scrubbing is not interrupted');
window.dispatchEvent(new Event('pointerup'));advance(1500);assert.equal(hidden(),true);
document.fullscreenElement=null;ui.update();advance(5000);assert.equal(hidden(),false);assert.equal(controls.inert,false);assert.equal(seek.inert,false);
document.fullscreenElement=stage;ui.update();assert.equal(timers.size,1);abort.abort();assert.equal(timers.size,0);assert.equal(hidden(),false);
console.log('Fullscreen controls: 1.5 s timeout, activity, pointer exit, blur, menus, scrubbing and cleanup passed.');
