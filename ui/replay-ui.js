'use strict';
icons.trash='<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>';
let replayDevices=null,replayLoading=false;
const options=(rows,value)=>rows.map(([v,label])=>`<option value="${esc(String(v))}" ${String(v)===String(value)?'selected':''}>${esc(label)}</option>`).join('');
window.replayPage=function(){
 const r=state.replay||{},cfg=r.settings||{},minutes=(cfg.seconds||300)/60,mode=cfg.audio_mode||'system';
 if(!replayDevices&&!replayLoading){replayLoading=true;api('replay_devices').then(x=>{replayDevices=x;if(tab==='replay')render()}).catch(e=>toast(e.message,true)).finally(()=>replayLoading=false)}
 const screens=replayDevices?.monitors||[],audio=replayDevices?.audio||[],apps=replayDevices?.applications||[],active=['starting','recording','stopping'].includes(r.phase)||r.saving;
 return `<div class="page-head"><div><div class="eyebrow">KEEP YOUR BEST MOMENTS</div><h1>Мгновенный повтор</h1><p>Играешь — буфер обновляется. Нажимаешь клавиши — момент сохранён.</p></div><span class="pill gold">H.264 · GPU / CPU</span></div>
 <section class="replay-hero"><div class="replay-orb" id="replayOrb">${icon('clock')}</div><div class="replay-main"><div class="eyebrow" id="replayPhase">ПОВТОР ВЫКЛЮЧЕН</div><div class="replay-time"><span id="replayTime">00:00</span><small id="replayLimit">/ ${fmt(cfg.seconds||300).slice(3)}</small></div><p id="replayDescription">Включи буфер перед игрой, чтобы сохранить предшествующие события.</p><div class="replay-track"><span id="replayFill"></span></div></div></section>
 <div class="actions replay-actions">${active?button('replay-stop','Остановить повтор','close','danger'):button('replay-start','Включить повтор','play','primary')}${button('replay-save',`Сохранить последние ${minutes} мин`,'download','secondary',`id="replaySave" ${r.phase!=='recording'||r.saving?'disabled':''}`)}<span class="replay-hotkey"><span class="kbd">Ctrl</span> + <span class="kbd">Alt</span> + <span class="kbd">F10</span><span id="hotkeyStatus"></span></span></div>
 <div class="two-col"><section class="panel panel-pad"><div class="panel-title">ЗАХВАТ И КАЧЕСТВО</div>
 <div class="field"><label>Длительность буфера</label><select id="replaySeconds" ${active?'disabled':''}>${[1,3,5,10,15,20,30].map(n=>`<option value="${n*60}" ${minutes===n?'selected':''}>${n} мин</option>`).join('')}</select><small>Сохраняется выбранное время перед нажатием горячей клавиши. Длинный буфер требует больше места на диске.</small></div>
 <div class="field"><label>Что записывать</label><select id="replayCaptureMode" ${active?'disabled':''}>${options([['monitor','Весь выбранный экран'],['window','Только окно приложения']],cfg.capture_mode||'monitor')}</select></div>
 <div class="field" id="replayMonitorField" ${(cfg.capture_mode||'monitor')==='monitor'?'':'hidden'}><label>Экран</label><select id="replayMonitor" ${active?'disabled':''}><option value="primary" ${cfg.monitor==='primary'?'selected':''}>Основной экран</option>${screens.map(m=>`<option value="${esc(m.id)}" ${cfg.monitor===m.id?'selected':''}>${esc(m.id)} · ${m.width} × ${m.height}</option>`).join('')}</select></div>
 <div class="field" id="replayWindowField" ${cfg.capture_mode==='window'?'':'hidden'}><label>Окно для записи</label><select id="replayWindow" ${active?'disabled':''}><option value="0">${cfg.window_title?esc(cfg.window_title)+' · выбрано ранее':'Запусти приложение и выбери окно'}</option>${apps.map(a=>`<option value="${a.hwnd}" ${a.hwnd===cfg.window_hwnd?'selected':''}>${esc(a.name)} — ${esc(a.title)}</option>`).join('')}</select><small>Другие окна поверх приложения не попадают в запись. Не сворачивай выбранное окно. Для игры используй оконный режим без рамки. Защищённые окна могут не захватываться.</small></div>
 <div class="time-inputs"><div><label>Частота кадров</label><select id="replayFPS" ${active?'disabled':''}>${options([24,30,60,90,120].map(n=>[n,n+' FPS']),cfg.fps||60)}</select></div><div><label>Разрешение</label><select id="replayHeight" ${active?'disabled':''}>${options([[0,'Как у источника'],[720,'720p'],[1080,'1080p'],[1440,'1440p'],[2160,'2160p']],cfg.height||0)}</select></div></div>
 <div class="field"><small>Пропорции сохраняются; маленький источник не увеличивается. Высокий FPS повышает нагрузку.</small></div>
 <div class="field"><label>Режим качества</label><select id="replayQuality" ${active?'disabled':''}>${options([['quality','Постоянное качество · рекомендуется'],['vbr','Переменный битрейт (VBR)'],['cbr','Постоянный битрейт (CBR)']],cfg.quality_mode||'quality')}</select></div>
 <div class="field" id="replayCQField" ${(cfg.quality_mode||'quality')==='quality'?'':'hidden'}><label>Качество CQ / CRF · 14–32</label><input id="replayCQ" type="number" min="14" max="32" value="${cfg.cq??19}" ${active?'disabled':''}><small>Меньше число — больше деталей и размер файла. Для динамичной игры начни с 18–20.</small></div>
 <div class="time-inputs"><div id="replayBitrateField" ${(cfg.quality_mode||'quality')==='quality'?'hidden':''}><label>Битрейт, Мбит/с</label><input id="replayBitrate" type="number" min="5" max="200" value="${cfg.mbps||35}" ${active?'disabled':''}></div><div id="replayMaxField" ${cfg.quality_mode==='cbr'?'hidden':''}><label>Предел битрейта, Мбит/с</label><input id="replayMax" type="number" min="5" max="200" value="${cfg.max_mbps||80}" ${active?'disabled':''}></div></div>
 <div class="field"><small>Для 1440p60 в движении используй CQ 19 и предел 80 Мбит/с. Низкий предел может снижать качество сложных сцен.</small></div>
 <div class="time-inputs"><div><label>Кодировщик</label><select id="replayEncoder" ${active?'disabled':''}>${options([['auto','Авто · NVENC / CPU'],['h264_nvenc','NVIDIA NVENC'],['libx264','Процессор (CPU)']],cfg.encoder||'auto')}</select></div><div><label>Скорость кодирования</label><select id="replayPreset" ${active?'disabled':''}>${options([['performance','Быстрее'],['balanced','Баланс'],['quality','Больше сжатие']],cfg.preset||'balanced')}</select></div></div>
 <div class="field"><label class="check"><input id="replayCursor" type="checkbox" ${cfg.cursor!==false?'checked':''} ${active?'disabled':''}> Записывать курсор</label></div>
 <div class="field"><label>Какой звук записывать</label><select id="replayAudioMode" ${active?'disabled':''}><option value="system" ${mode==='system'?'selected':''}>Весь звук устройства</option><option value="game" ${mode==='game'?'selected':''} ${replayDevices?.process_audio_supported===false?'disabled':''}>Только выбранная игра / приложение</option><option value="exclude" ${mode==='exclude'?'selected':''} ${replayDevices?.process_audio_supported===false?'disabled':''}>Весь звук, кроме выбранного приложения</option><option value="none" ${mode==='none'?'selected':''}>Без звука</option></select><small>Микрофон не записывается. Выбор отдельного приложения доступен на Windows 11 и Windows build 20348+.</small></div>
 <div class="field" id="replayFollowField" ${cfg.capture_mode==='window'&&mode==='game'?'':'hidden'}><label class="check"><input id="replayFollow" type="checkbox" ${cfg.audio_follow_window!==false?'checked':''} ${active?'disabled':''}> Звук того же приложения, чьё окно записывается</label></div>
 <div class="field" id="replayApplicationField" ${['game','exclude'].includes(mode)&&!(cfg.capture_mode==='window'&&mode==='game'&&cfg.audio_follow_window!==false)?'':'hidden'}><label>Игра / приложение</label><select id="replayApplication" ${active?'disabled':''}><option value="0">${cfg.game_path?esc(cfg.game_path.split('\\').pop())+' · выбрано ранее':'Запусти игру и выбери её окно'}</option>${apps.map(a=>`<option value="${a.pid}" ${a.pid===cfg.game_pid?'selected':''}>${esc(a.name)} — ${esc(a.title)} (PID ${a.pid})</option>`).join('')}</select><small>Запусти игру перед выбором. Захватывается звук её процесса и дочерних процессов. При перезапуске игры включи буфер заново.</small></div>
 <div class="field" id="replayDeviceField" ${mode==='system'?'':'hidden'}><label>Устройство вывода</label><select id="replayAudio" ${active?'disabled':''}><option value="default" ${cfg.audio==='default'?'selected':''}>Текущее устройство вывода Windows</option>${audio.map(d=>`<option value="${d.id}" ${String(d.id)===cfg.audio?'selected':''}>${esc(d.name.replace(' [Loopback]',''))}</option>`).join('')}</select><small>Все приложения, которые воспроизводят звук через это устройство.</small></div>
 <div class="time-inputs"><div><label>Качество звука</label><select id="replayAudioBitrate" ${active?'disabled':''}>${options([128,192,256,320].map(n=>[n,n+' кбит/с']),cfg.audio_bitrate||192)}</select></div><div><label>Сдвиг звука, мс</label><input id="replayOffset" type="number" min="-2000" max="2000" step="10" value="${cfg.audio_offset_ms||0}" ${active?'disabled':''}></div></div><div class="field"><small>Обычно оставляй 0. Отрицательное значение сдвигает звук раньше, положительное — позже.</small></div>
 <div class="audio-level"><span id="audioIndicator"></span><div><b id="audioLabel">Ожидает запуска</b><small id="audioSource">${esc(r.audio_name||'')}</small></div><div class="audio-meter"><span id="audioMeter"></span></div></div>
 <div class="actions" style="margin-top:20px">${button('replay-settings','Сохранить настройки','check','quiet',active?'disabled':'')}${button('replay-devices','Обновить список','refresh','quiet',active?'disabled':'')}</div></section>
 <section><div class="panel panel-pad"><div class="panel-title">КАК СОХРАНИТЬ МОМЕНТ</div><p style="font-size:12px">1. Нажми «Включить повтор» перед игрой.<br><br>2. После нужного момента нажми <b>Ctrl + Alt + F10</b>.<br><br>3. Готовая запись появится в библиотеке и разделе «Экспорт».</p><div class="notice">Если с запуска прошло меньше ${minutes} мин, сохранится накопленная часть. Во время записи логотипы в трее и на панели задач становятся красными. Остановить запись можно здесь или через меню трея.</div></div><div class="panel panel-pad" style="margin-top:18px"><div class="panel-title">СОСТОЯНИЕ</div><p id="replayInfo" style="font-size:12px"></p><div id="replayLast" class="hint"></div><div class="actions" style="margin-top:18px">${button('open-exports','Открыть записи','folder')}</div></div></section></div>
 <div id="replayError" class="notice hidden"></div>`;
};
window.renderDesktopExtras=function(){
 if(tab!=='settings')return;
 const panel=$('.settings-panel');if(!panel||$('#closeAction'))return;
 const choice=state.settings.desktop?.[mode]?.close_action||'close';
 panel.insertAdjacentHTML('beforeend',`<div class="split-line"></div><div class="panel-title">ОКНО И ЗНАЧОК В ТРЕЕ</div><div class="field"><label>При нажатии на крестик</label><select id="closeAction"><option value="close" ${choice==='close'?'selected':''}>Полностью закрыть программу</option><option value="tray" ${choice==='tray'?'selected':''}>Свернуть программу в трей</option></select><small>${mode==='clips'?'При сворачивании в трей запись продолжается. При полном закрытии останавливается.':'Значок в трее позволяет снова открыть окно.'}</small></div><div class="actions">${button('desktop-save','Сохранить поведение','check','primary')}${button('desktop-exit','Выйти полностью','close','quiet')}</div>`);
};
window.updateReplay=function(){
 if(mode!=='clips'||!state.replay)return;
 const r=state.replay,limit=r.settings.seconds||300,active=['starting','recording'].includes(r.phase),seconds=Math.min(limit,r.buffer_seconds||0);
 $('#headerStatus').textContent=active?'● ИДЁТ ЗАПИСЬ · '+fmt(seconds):'Личная видеотека · повтор выключен';
 $('.local-dot').classList.toggle('recording-dot',active);
 if(tab!=='replay')return;
 const phase=$('#replayPhase');if(!phase)return;
 phase.textContent=({off:'ПОВТОР ВЫКЛЮЧЕН',starting:'ЗАПУСК ЗАПИСИ',recording:'● ИДЁТ ЗАПИСЬ',stopping:'ОСТАНОВКА',error:'ЗАПИСЬ ОСТАНОВЛЕНА'})[r.phase]||'ПОВТОР ВЫКЛЮЧЕН';
 $('#replayOrb').classList.toggle('active',active);
 $('#replayTime').textContent=fmt(seconds).slice(3);$('#replayFill').style.width=(seconds/limit*100)+'%';
 $('#replayDescription').textContent=active?(seconds<limit?'Буфер наполняется. Можно сохранить уже записанную часть.':`Буфер заполнен: доступны последние ${limit/60} мин.`):'Включи буфер перед игрой, чтобы сохранить предшествующие события.';
 $('#replaySave').disabled=r.phase!=='recording'||r.saving;
 $('#hotkeyStatus').textContent=r.hotkey_ok?' · действует и в свёрнутом окне':' · клавиши заняты или запущена браузерная проверка';
 $('#audioLabel').textContent=!active?'Ожидает запуска':r.settings.audio_mode==='none'?'Звук выключен':r.audio_recent?'Есть звуковой сигнал':'Сейчас тишина';
 $('#audioSource').textContent=r.audio_name||'';
 $('#audioIndicator').classList.toggle('signal',r.audio_recent&&active);
 $('#audioMeter').style.width=Math.min(100,Math.sqrt(r.audio_peak||0)*140)+'%';
 $('#replayInfo').textContent=active?`${r.engine} · ${r.encoder==='h264_nvenc'?'H.264 NVENC':'H.264 CPU'} · ${(r.output_size||[]).join(' × ')} · ${r.settings.fps} FPS · ${r.settings.quality_mode==='quality'?'CQ / CRF '+r.settings.cq:r.settings.mbps+' Мбит/с'}. Буфер: ${size(r.disk_bytes)}. Повторено кадров: ${r.duplicate_frames||0}; пропущено: ${r.dropped_frames||0}.`:'Запись экрана не выполняется. Запуск без консоли; сворачивание в трей настраивается в разделе «Настройки».';
 $('#replayLast').textContent=r.last_saved?`Последний повтор: ${fmt(r.last_saved.duration)} · ${size(r.last_saved.bytes)}`:'';
 $('#replayError').classList.toggle('hidden',!r.error);$('#replayError').textContent=r.error||'';
};
function updateCaptureFields(){
 if(!$('#replayCaptureMode'))return;
 const win=$('#replayCaptureMode').value==='window',audio=$('#replayAudioMode').value,q=$('#replayQuality').value;
 $('#replayMonitorField').hidden=win;$('#replayWindowField').hidden=!win;
 $('#replayFollowField').hidden=!(win&&audio==='game');
 $('#replayApplicationField').hidden=!['game','exclude'].includes(audio)||(win&&audio==='game'&&$('#replayFollow').checked);
 $('#replayDeviceField').hidden=audio!=='system';$('#replayCQField').hidden=q!=='quality';$('#replayBitrateField').hidden=q==='quality';$('#replayMaxField').hidden=q==='cbr';
}
document.addEventListener('change',e=>{if(['replayAudioMode','replayCaptureMode','replayFollow','replayQuality'].includes(e.target.id))updateCaptureFields()});
async function replaySettings(){
 const win=$('#replayCaptureMode').value==='window',follow=$('#replayFollow').checked;
 return api('replay_config',{seconds:Number($('#replaySeconds').value),capture_mode:$('#replayCaptureMode').value,window_hwnd:win?Number($('#replayWindow').value):0,audio_follow_window:follow,
 audio_mode:$('#replayAudioMode').value,game_pid:win&&follow&&$('#replayAudioMode').value==='game'?0:Number($('#replayApplication').value),monitor:$('#replayMonitor').value,audio:$('#replayAudio').value,
 fps:Number($('#replayFPS').value),height:Number($('#replayHeight').value),mbps:Number($('#replayBitrate').value),max_mbps:Number($('#replayMax').value),cq:Number($('#replayCQ').value),quality_mode:$('#replayQuality').value,
 encoder:$('#replayEncoder').value,preset:$('#replayPreset').value,audio_bitrate:Number($('#replayAudioBitrate').value),audio_offset_ms:Number($('#replayOffset').value),cursor:$('#replayCursor').checked})
}
window.replayAction=async function(a,el){
 if(a==='desktop-save'){await api('desktop_config',{close_action:$('#closeAction').value});await refresh();toast('Действие крестика сохранено');return}
 if(a==='desktop-exit'){await api('desktop_exit');return}
 if(a==='replay-devices'){const saved={};document.querySelectorAll('[id^="replay"] select,[id^="replay"] input').forEach(el=>saved[el.id]=el.type==='checkbox'?el.checked:el.value);replayDevices=await api('replay_devices');render();for(const [id,value] of Object.entries(saved)){const el=$('#'+id);if(!el)continue;if(el.type==='checkbox')el.checked=value;else if(el.tagName!=='SELECT'||[...el.options].some(o=>o.value===value))el.value=value}updateCaptureFields();return}
 if(a==='replay-settings'){await replaySettings();await refresh(false);toast('Настройки повтора сохранены');return}
 if(a==='replay-start'){await replaySettings();await task('replay_start',{},()=>{refresh(false);toast('Повтор включён · сохранить: Ctrl+Alt+F10')});return}
 if(a==='replay-stop'){await task('replay_stop',{},()=>{refresh(false);toast('Запись остановлена')});return}
 if(a==='replay-save'){await task('replay_save',{},r=>{refresh(false);modal('Повтор сохранён',`<p>${fmt(r.duration)} · ${r.width} × ${r.height} · аудиодорожек: ${r.audio}</p><div class="result-path" style="margin-top:15px">${esc(r.path)}</div>`,button('close','Готово','check','quiet')+button('open-exports','Открыть папку','folder','primary'))});return}
};
window.videoDeleteAction=async function(a,el){
 if(a==='delete-video'){
  const item=el.dataset.export?{name:el.dataset.export,path:'Папка экспорта Game Clips'}:state.clips.find(c=>c.id===el.dataset.id);
  if(!item)throw Error('Видео не найдено');
  if(selected&&selected.id===item.id&&$('#clipTags'))await saveClip();
  const player=$('#player');if(player){player.pause();player.removeAttribute('src');player.load()}
  modal('Переместить видео в корзину?',`<p><b>${esc(item.name)}</b></p><div class="result-path" style="margin-top:15px">${esc(item.path)}</div><p style="margin-top:16px;font-size:12px">Будет удалён сам видеофайл. Вернуть его можно из корзины Windows. Остальные записи останутся на месте.</p>`,button('close','Отмена','close','quiet')+button('delete-video-confirm','В корзину','trash','danger',el.dataset.export?`data-export="${esc(el.dataset.export)}"`:`data-id="${esc(item.id)}"`));return;
 }
 if(a==='delete-video-confirm'){
  const args=el.dataset.export?{export_name:el.dataset.export}:{id:el.dataset.id};
  el.disabled=true;
  try{await api('clip_delete',args);close();await refresh();toast('Видео перемещено в корзину Windows')}
  catch(e){el.disabled=false;throw e}
 }
};
