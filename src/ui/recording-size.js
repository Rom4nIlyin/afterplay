'use strict';
(function(root){
 // Measured at 1080p60 CQ/CRF 19 with the application's real encoder options:
 // 2 s testsrc2, and the same source with seeded temporal noise (strength 5).
 // These are calibration points, not bounds on arbitrary game footage.
 const reference={
  h264_nvenc:{performance:[31.947,44.024],balanced:[32.194,54.716],quality:[32.010,59.908]},
  libx264:{performance:[32.050,33.227],balanced:[14.075,15.697],quality:[15.481,18.358]}
 };
 function outputSize(cfg,source={}){
  const known=Number(source.width)>=2&&Number(source.height)>=2;
  const width=known?Number(source.width):1920,height=known?Number(source.height):1080;
  const scale=Number(cfg.height)>0?Math.min(1,Number(cfg.height)/height):1;
  return {width:Math.max(2,Math.floor(width*scale/2)*2),height:Math.max(2,Math.floor(height*scale/2)*2),assumed:!known||!!source.assumed};
 }
 function estimate(cfg,source){
  const dimensions=outputSize(cfg,source),fps=Number(cfg.fps??60);
  if(!Number.isFinite(fps)||fps<=0)return null;
  if(cfg.save_format==='gif'){
   const seconds=Number(cfg.gif_seconds??5);if(!Number.isFinite(seconds)||seconds<2||seconds>15)return null;
   const scale=Math.min(1,720/dimensions.width),width=Math.floor(dimensions.width*scale),height=Math.max(2,Math.floor(dimensions.height*scale/2)*2);
   const pixels=width*height*15*seconds;
   return {kind:'gif',seconds,width,height,fps:15,assumed:dimensions.assumed,audioTracks:0,lowBytes:pixels*.06,highBytes:pixels*.9};
  }
  const seconds=Number(cfg.seconds),mode=cfg.quality_mode||'quality';
  const target=Number(cfg.mbps),cap=Number(mode==='cbr'?cfg.mbps:cfg.max_mbps);
  if(!['quality','vbr','cbr'].includes(mode)||!Number.isFinite(seconds)||seconds<=0||
     !Number.isFinite(cap)||cap<5||cap>200)return null;
  if(mode!=='quality'&&(!Number.isFinite(target)||target<5||target>cap))return null;
  const audioMode=cfg.audio_mode||'system',mic=!!cfg.microphone_enabled;
  const sources=(audioMode==='none'?0:audioMode==='multitrack'?2:1)+(mic?1:0);
  // Multiple sources produce a mixed track plus one track for each source.
  const audioTracks=sources>1?sources+1:sources,audioKbps=Number(cfg.audio_bitrate??192);
  if(audioTracks&&(!Number.isFinite(audioKbps)||audioKbps<=0))return null;
  const audioMbps=audioTracks*audioKbps/1000,toBytes=mbps=>seconds*(mbps+audioMbps)*1000000/8;
  let lowMbps=target,highMbps=target,kind='estimate';
  if(mode==='quality'){
   const cq=Number(cfg.cq??19),preset=cfg.preset||'performance',encoder=cfg.resolved_encoder||cfg.encoder||'auto';
   if(!Number.isFinite(cq)||cq<14||cq>32||!['performance','balanced','quality'].includes(preset)||!['auto','h264_nvenc','libx264'].includes(encoder))return null;
   const candidates=encoder==='auto'?Object.values(reference).map(row=>row[preset]):[reference[encoder][preset]];
   const factor=Math.pow(dimensions.width*dimensions.height/(1920*1080),.85)*Math.pow(fps/60,.65)*Math.pow(2,(19-cq)/6);
   // Broad scene allowance; maxrate is a reference, not a hard file limit.
   lowMbps=Math.min(cap,Math.min(...candidates.flat())*factor*.35);
   highMbps=Math.min(cap,Math.max(...candidates.flat())*factor*1.6);kind='range';
  }
  const bytes=toBytes(kind==='range'?(lowMbps+highMbps)/2:target);
  return {seconds,...dimensions,fps,audioTracks,audioMbps,mbps:target,cap,kind,bytes,gigabytes:bytes/1e9,lowBytes:toBytes(lowMbps),highBytes:toBytes(highMbps),limitBytes:toBytes(cap)};
 }
 const api={estimate,outputSize};root.AfterplayRecordingSize=api;
 if(typeof module==='object'&&module.exports)module.exports=api;
})(typeof window==='object'?window:globalThis);
