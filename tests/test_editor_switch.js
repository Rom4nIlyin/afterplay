'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require.resolve('../ui/backgrounds/studio-polish.js'),'utf8');
const wrapper=source.slice(source.indexOf(' const oldOpen=openClip;'),source.indexOf(' const oldMode=reviewSetMode;'));
const dialog={open:false};let entrances=0,cancelled=0,opens=0;
const context={$:()=>dialog,reviewState:null,searchTimer:null,clearTimeout(){},snapshot:()=>({start:0,end:3}),notes:()=>'',decorateEditor(){},
 cancelMotion:()=>cancelled++,animate:()=>entrances++};
context.openClip=id=>{opens++;dialog.open=true;context.reviewState={};context.trimState={id};context.selected={id}};
vm.createContext(context);vm.runInContext(wrapper,context);
context.openClip('a');assert.equal(entrances,1,'first opening retains entrance animation');
context.openClip('b');context.openClip('c');assert.equal(opens,3);assert.equal(entrances,1,'source changes must never fade the entire dialog out');assert.equal(cancelled,2,'rapid changes cancel an unfinished entrance');
dialog.open=false;context.reviewState=null;context.openClip('d');assert.equal(entrances,2,'opening again after closing still animates normally');
console.log('Editor switches: no repeated dialog fade, rapid-switch cancellation and normal first opening passed');
