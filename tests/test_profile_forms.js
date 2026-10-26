'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.join(__dirname,'..'),profiles=fs.readFileSync(path.join(root,'ui/profiles-ui.js'),'utf8'),replay=fs.readFileSync(path.join(root,'ui/replay-ui.js'),'utf8');
async function run(){
 const game='C:\\Games\\Gloria Victis\\gv.exe',calls=[];
 const fields={'.studio-profiles':{dataset:{profileId:game}},'#captureProfile':{value:game},'#profilePath':{value:game},'#profileName':{value:'Gloria Victis'},'#replayWindow':{selectedOptions:[{dataset:{path:game}}]},'#replayConfigStatus':{dataset:{}}};
 const context={window:{},tab:'replay',state:{settings:{selected_capture_profile:'screen:default'},replay:{phase:'off'}},$:id=>fields[id],api:async(action,args)=>{calls.push({action,args});return args},refresh(){},toast(){},task:async action=>{calls.push({action});throw Error('Selected app is not running')}};
 vm.createContext(context);vm.runInContext(profiles.slice(profiles.indexOf('window.saveSelectedProfile='),profiles.indexOf("document.addEventListener('input'")),context);
 await context.window.saveSelectedProfile({capture_mode:'window',window_hwnd:123});
 assert.equal(calls[0].action,'profile_configure');assert.equal(calls[0].args.id,game,'form identity wins over stale polling state');
 calls.length=0;fields['#captureProfile'].value='screen:default';
 await assert.rejects(context.window.saveSelectedProfile({}),/загрузки/);assert.equal(calls.length,0,'a half-loaded selection cannot be saved');
 fields['#captureProfile'].value=game;context.state.settings.selected_capture_profile=game;
 vm.runInContext(replay.slice(replay.indexOf('window.replayAction='),replay.indexOf('function replaceReplayOptions(')),context);
 for(let i=0;i<4;i++)await assert.rejects(context.window.replayAction('replay-record-start'),/not running/);
 assert.equal(calls.every(call=>call.action==='recording_start'),true,'starting never writes profile forms');
 calls.length=0;fields['#replayConfigStatus'].dataset.dirty='true';
 await assert.rejects(context.window.replayAction('replay-start'),/сохрани/);assert.equal(calls.length,0);
 console.log('Profile forms: stale selection, stable identity and failed-start preservation passed.');
}
run().catch(error=>{console.error(error);process.exitCode=1});
