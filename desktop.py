"""Taskbar/tray identity and user-selected close behavior."""
import ctypes
import threading
import time
from pathlib import Path
from localization import translate,language

class Desktop:
    def __init__(self,suite,mode):
        from PIL import Image,ImageDraw
        import pystray
        self.suite=suite;self.mode=mode;self.exiting=False;self.alive=True
        self.title='AFTERPLAY'
        self.notifications=None
        self.last_notice=None
        self.image=Image.open(Path(__file__).parent/'ui'/'afterplay.ico').convert('RGBA').resize((64,64))
        self.recording_image=Image.open(Path(__file__).parent/'ui'/'afterplay-recording.ico').convert('RGBA').resize((64,64))
        items=[pystray.MenuItem(lambda item:translate(suite,'Открыть '+self.title),self.show,default=True)]
        if suite.replay:
            items.extend([pystray.MenuItem(lambda item:translate(suite,'Сохранить последние '+str(suite.replay.settings['seconds']//60)+' мин'),lambda *_:suite.replay.save_job(),
                                          enabled=lambda item:suite.replay.phase=='recording' and not suite.replay.saving and not suite.replay.finishing),
                          pystray.MenuItem(lambda item:translate(suite,'Отметить момент'),lambda *_:suite.replay.add_marker(),
                                          enabled=lambda item:suite.replay.phase=='recording'),
                          pystray.MenuItem(lambda item:translate(suite,'Отключить запись' if suite.replay.continuous else 'Включить запись'),lambda *_:suite.replay.recording_job(),
                                          enabled=lambda item:suite.replay.phase not in {'starting','stopping'} and not suite.replay.saving and not suite.replay.finishing),
                          pystray.MenuItem(lambda item:translate(suite,'Отключить повтор' if suite.replay.replay_enabled else 'Включить повтор'),
                                          lambda *_:suite.job('Переключение повтора',lambda job:suite.auto.manual('stop_replay' if suite.replay.replay_enabled else 'start_replay')),
                                          enabled=lambda item:suite.replay.phase not in {'starting','stopping'} and not suite.replay.saving and not suite.replay.finishing)])
        items.extend([pystray.Menu.SEPARATOR,pystray.MenuItem(lambda item:translate(suite,'Выйти полностью'),self.exit)])
        self.icon=pystray.Icon('AFTERPLAY-'+mode,self.image,self.title,menu=pystray.Menu(*items))
        self.icon.run_detached()
        if suite.replay:suite.replay.tray=self.icon
        suite.window.events.closing+=self.closing
        threading.Thread(target=self._status,daemon=True).start()

    def show(self,*_):
        self._window_action(False)

    def toggle(self):
        self._window_action(True)

    def _window_action(self, toggle):
        from System import Action
        from System.Windows.Forms import FormWindowState
        def apply():
            native=self.suite.window.native
            if self.exiting or native.IsDisposed:return
            if toggle and native.Visible and native.WindowState != FormWindowState.Minimized:
                native.Hide()
            else:
                native.Show()
                if native.WindowState == FormWindowState.Minimized:
                    native.WindowState=FormWindowState.Normal
                native.BringToFront()
                native.Activate()
        self.suite.window.native.BeginInvoke(Action(apply))

    def attach_navigation(self):
        from System import Action,Int32
        if not self.suite.window.events.loaded.wait(15):
            self.suite.log('navigation_attach_failed',error='Native window did not become ready')
            return
        def navigate(direction):
            threading.Thread(target=lambda:self.suite.window.evaluate_js('historyDirection('+str(int(direction))+')'),daemon=True).start()
        def attach():
            try:
                native=self.suite.window.native
                def visibility_changed(sender,event):
                    hidden=not native.Visible or str(native.WindowState)=='Minimized'
                    threading.Thread(target=lambda:self.suite.window.evaluate_js('window.customNativeHidden='+str(hidden).lower()+';window.customUpdatePause?.()'),daemon=True).start()
                self._visibility_callback=visibility_changed
                native.VisibleChanged+=self._visibility_callback
                native.Resize+=self._visibility_callback
            except Exception as error:self.suite.log('visibility_attach_failed',error=str(error))
            try:
                native=self.suite.window.native
                core=native.webview.CoreWebView2
                def fullscreen_changed(sender,event):
                    desired=bool(sender.ContainsFullScreenElement)
                    if desired!=bool(native.is_fullscreen):native.toggle_fullscreen()
                self._fullscreen_callback=fullscreen_changed
                core.ContainsFullScreenElementChanged+=self._fullscreen_callback
            except Exception as error:self.suite.log('fullscreen_attach_failed',error=str(error))
            try:
                import clr
                clr.AddReference(str(Path(__file__).parent/'ReplayNotification.dll'))
                from Afterplay import DesktopNavigation
                self._navigate_callback=Action[Int32](navigate)
                self._navigation_filter=DesktopNavigation.Attach(self.suite.window.native,self._navigate_callback)
            except Exception as error:self.suite.log('navigation_attach_failed',error=str(error))
        self.suite.window.native.BeginInvoke(Action(attach))

    def closing(self):
        settings=self.suite.cfg.get('desktop',{}).get(self.mode,{})
        if not self.exiting and settings.get('close_action','close')=='tray':
            self.suite.window.hide()
            return False
        return True

    def exit(self,*_):
        self.exiting=True
        self.suite.window.destroy()

    def notify(self,title,message,kind='success',feedback=True,appearance=None):
        # All WinForms windows, including notices, belong to the desktop UI thread.
        from System import Action
        title=translate(self.suite,title);message=translate(self.suite,message)
        import customization
        cfg=appearance or customization.current(self.suite)
        if feedback:customization.sound(self.suite,kind if kind in customization.EVENTS else 'success')
        def show_notice():
            try:
                if self.notifications is None:
                    import clr
                    clr.AddReference(str(Path(__file__).parent/'ReplayNotification.dll'))
                    from Afterplay import ReplayNotifications
                    self.notifications=ReplayNotifications
                cover=''
                if cfg['notice_cover'] and kind=='success':
                    clips=self.suite.clips()
                    if clips:
                        path=self.suite.data/'thumbs'/(clips[0]['id']+'.jpg')
                        if path.exists():cover=str(path)
                self.notifications.Configure(cfg['notice_position'],float(cfg['notice_size'])/100,
                                             float(cfg['notice_opacity'])/100,int(cfg['notice_duration']*1000),cover)
                self.notifications.Show(title,message,kind)
                self.last_notice={'title':title,'message':message,'kind':kind}
            except Exception as e:
                self.suite.log('notification_failed',error=str(e))
        if self.alive:
            self.suite.window.native.BeginInvoke(Action(show_notice))

    def _status(self):
        from PIL import ImageDraw
        last=None;last_modes=None
        last_hotkey=None
        last_language=None
        while self.alive:
            replay=self.suite.replay
            active=bool(replay and replay.phase in {'starting','recording','stopping'})
            hotkey=self.suite.cfg.get('hotkeys',{}).get('save','Ctrl+Alt+F10')
            current_language=language(self.suite)
            modes=(replay.continuous,replay.replay_enabled,replay.saving,replay.finishing) if replay else None
            if active!=last or modes!=last_modes or hotkey!=last_hotkey or current_language!=last_language:
                im=self.recording_image if active else self.image
                try:
                    self.icon.icon=im
                    self.icon.title=self.title+translate(self.suite,' — ИДЁТ ЗАПИСЬ · '+hotkey if active else '')
                    self.icon.update_menu()
                    self.suite.window.set_title(self.title)
                    from System import Action
                    from System.Drawing import Icon
                    name='afterplay-recording.ico' if active else 'afterplay.ico'
                    native_icon=Icon(str(Path(__file__).parent/'ui'/name))
                    def assign():
                        previous=getattr(self,'_native_icon',None)
                        self.suite.window.native.Icon=native_icon
                        self._native_icon=native_icon
                        self.current_icon_name=name
                        if previous:previous.Dispose()
                    self.suite.window.native.Invoke(Action(assign))
                except Exception as e:self.icon_error=str(e)
                last=active;last_modes=modes;last_hotkey=hotkey;last_language=current_language
            time.sleep(.3)

    def shutdown(self):
        self.alive=False
        if self.suite.replay:self.suite.replay.tray=None
        try:self.icon.stop()
        except Exception:pass
