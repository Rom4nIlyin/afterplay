'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),Seq=require('../ui/sequence-model.js');
const review=fs.readFileSync(require.resolve('../ui/review-ui.js'),'utf8'),sequence=fs.readFileSync(require.resolve('../ui/sequence-ui.js'),'utf8');
const c={};vm.createContext(c);vm.runInContext(review.slice(review.indexOf('function reviewTimelineHeight('),review.indexOf('function reviewInstallSplitter(')),c);
assert.equal(c.reviewTimelineHeight(300,700),300);assert.equal(c.reviewTimelineHeight(900,500),290);assert.equal(c.reviewTimelineHeight(50,700),110);
let seek=null,select=null,remember=0;
Object.assign(c,{$:()=>null,sequenceNavigation:{type:'clip',uid:'b',cursor:6,time:14,moved:true},sequenceDrag:{},sequenceNavFrame:null,sequenceMotionTimer:null,
 cancelAnimationFrame(){},clearTimeout(){},setTimeout(){},sequenceRender(){},sequencePaintCursor(){},sequenceRemember(){remember++},
 sequenceSeek:(...args)=>seek=args,sequenceSelect:(...args)=>select=args,montageDraft:Seq.normalize({segments:[{uid:'a',id:'a',start:0,end:10},{uid:'b',id:'b',start:0,end:10}]}),Seq});
vm.runInContext(sequence.slice(sequence.indexOf('function sequenceEndNavigation('),sequence.indexOf('function sequencePointerDown(')),c);
c.sequenceEndNavigation();assert.deepEqual(seek,[6,false,false],'moving a clip restores absolute playhead without recapturing stale trim');assert.equal(select,null);assert.equal(remember,1);
seek=null;c.sequenceNavigation={type:'clip',uid:'b',cursor:6,time:14,moved:false};c.sequenceEndNavigation();assert.equal(select[0],'b');assert.equal(select[1].time,14,'plain clicks still seek');
assert.ok(!sequence.includes("button('sequence-export'"),'the shared export action replaces extra montage buttons');
console.log('Editor layout: constrained heights, stable playhead after drag, click navigation and one export action passed');
