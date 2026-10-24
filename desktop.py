"""Taskbar/tray identity and user-selected close behavior."""
import ctypes
import threading
import time
from pathlib import Path

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
        items=[pystray.MenuItem('Открыть '+self.title,self.show,default=True)]
        if suite.replay:
            items.extend([pystray.MenuItem(lambda item:'Сохранить последние '+str(suite.replay.settings['seconds']//60)+' мин',lambda *_:suite.replay.save_job(),
                                          enabled=lambda item:suite.replay.phase=='recording'),
                          pystray.MenuItem('Остановить повтор',lambda *_:threading.Thread(target=suite.replay.stop,daemon=True).start(),
                                          enabled=lambda item:suite.replay.phase=='recording')])
        items.extend([pystray.Menu.SEPARATOR,pystray.MenuItem('Выйти полностью',self.exit)])
        self.icon=pystray.Icon('AFTERPLAY-'+mode,self.image,self.title,menu=pystray.Menu(*items))
        self.icon.run_detached()
        if suite.replay:suite.replay.tray=self.icon
        suite.window.events.closing+=self.closing
        threading.Thread(target=self._status,daemon=True).start()

    def show(self,*_):
        self.suite.window.show();self.suite.window.restore()

    def closing(self):
        settings=self.suite.cfg.get('desktop',{}).get(self.mode,{})
        if not self.exiting and settings.get('close_action','close')=='tray':
            self.suite.window.hide()
            return False
        return True

    def exit(self,*_):
        self.exiting=True
        self.suite.window.destroy()

    def notify(self,title,message,kind='success'):
        # All WinForms windows, including notices, belong to the desktop UI thread.
        from System import Action
        def show_notice():
            try:
                if self.notifications is None:
                    import clr
                    clr.AddReference(str(Path(__file__).parent/'ReplayNotification.dll'))
                    from Afterplay import ReplayNotifications
                    self.notifications=ReplayNotifications
                self.notifications.Show(title,message,kind)
                self.last_notice={'title':title,'message':message,'kind':kind}
            except Exception as e:
                self.suite.log('notification_failed',error=str(e))
        if self.alive:
            self.suite.window.native.BeginInvoke(Action(show_notice))

    def _status(self):
        from PIL import ImageDraw
        last=None
        last_hotkey=None
        while self.alive:
            replay=self.suite.replay
            active=bool(replay and replay.phase in {'starting','recording','stopping'})
            hotkey=self.suite.cfg.get('hotkeys',{}).get('save','Ctrl+Alt+F10')
            if active!=last or hotkey!=last_hotkey:
                im=self.recording_image if active else self.image
                try:
                    self.icon.icon=im
                    self.icon.title=self.title+(' — ИДЁТ ЗАПИСЬ · '+hotkey if active else '')
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
                last=active;last_hotkey=hotkey
            time.sleep(.3)

    def shutdown(self):
        self.alive=False
        if self.suite.replay:self.suite.replay.tray=None
        try:self.icon.stop()
        except Exception:pass
