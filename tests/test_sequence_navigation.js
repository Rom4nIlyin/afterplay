'use strict';
const assert=require('node:assert/strict'),V=require('../ui/sequence-viewport.js'),fs=require('node:fs'),vm=require('node:vm');
const rect={left:40,top:80},view=1000,zoom=42,duration=900;
assert.equal(V.contentHit(500,192,rect,1000,110),false,'horizontal scrollbar must not seek or replace the editor');
assert.equal(V.contentHit(1045,100,rect,1000,110),false,'vertical scrollbar must not seek');
assert.equal(V.contentHit(500,150,rect,1000,110),true);
assert.equal(V.time(250,40,8400,zoom,duration),205,'seek accounts for horizontal scrolling');
assert.equal(V.time(-100,40,0,zoom,duration),0);
assert.equal(V.time(99999,40,0,zoom,duration),duration);
const fitted=V.fit(duration,view);assert.ok(duration*fitted<=view&&duration*fitted>view-30,'long project fits the visible track');
const changed=V.zoom(duration,view,zoom,8400,500,.7);
assert.ok(Math.abs((8400+500)/zoom-(changed.left+500)/changed.zoom)<1e-9,'zoom stays anchored under the cursor');
assert.equal(V.pan(8400,1000,V.width(duration,zoom,view),view),9400);
assert.equal(V.pan(100,-200,2000,view),0);
assert.equal(V.pan(100,99999,2000,view),1000);
assert.equal(V.follow(8400,view,205,zoom,V.width(duration,zoom,view)),8400,'visible playhead does not move viewport');
assert.ok(V.follow(8400,view,260,zoom,V.width(duration,zoom,view))>8400,'playback follows cursor after visible range');
// Opening another source constructs the new timeline while its editor is hidden.
// A hidden element reports scrollLeft=0; rendering it must retain the saved view.
const nodes=new Map(),project={name:'long',segments:[{uid:'a',id:'one',start:0,end:300,at:0}]};
const scroll={clientWidth:0,_left:0,get scrollLeft(){return this._left},set scrollLeft(value){this._left=this.clientWidth?value:0}};
nodes.set('#sequenceScroll',scroll);
const context={$:id=>{if(!nodes.has(id))nodes.set(id,{style:{}});return nodes.get(id)},Seq:require('../ui/sequence-model.js'),SeqView:V,
 sequenceEditor:{},sequenceProject:()=>project,sequenceRow:()=>project.segments[0],sequenceClip:()=>({name:'source'}),sequencePaintCursor:()=>{},
 sequenceId:'a',sequenceZoom:42,sequenceLeft:922,sequenceFitPending:false,sequenceHistoryAt:0,sequenceHistory:[],base:'/',esc:String,trimFormat:String,fmt:String,sequenceRenderBlocks:()=>{}};
vm.createContext(context);const source=fs.readFileSync(require.resolve('../ui/sequence-ui.js'),'utf8');
vm.runInContext(source.slice(source.indexOf('function sequenceRender(){'),source.indexOf('function sequenceAttach(){')),context);
context.sequenceRender();assert.equal(context.sequenceLeft,922,'hidden replacement must keep horizontal viewport');
scroll.clientWidth=857;context.sequenceRender();assert.equal(scroll.scrollLeft,922,'viewport returns when new source becomes visible');
let stops=0;Object.assign(context,{sequenceOpening:true,sequenceEditor:null,sequenceStop:()=>stops++,beforeSequenceMode:()=>{},sequenceLayout:()=>{}});
vm.runInContext(source.slice(source.indexOf('reviewSetMode=function(editing,pane){'),source.indexOf('const beforeSequenceModal=modal;')),context);
context.reviewSetMode(false);assert.equal(stops,0,'temporary viewer creation during source transition must not stop the project');
context.sequenceOpening=false;context.reviewSetMode(false);assert.equal(stops,1,'explicitly leaving edit mode stops project playback');
console.log('Sequence navigation: native scrollbar, long projects, scrolled seeks, anchored zoom, cursor following and source-switch viewport passed');
