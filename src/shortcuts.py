"""User-requested Shell shortcuts; taskbar pinning stays under Windows control."""
from pathlib import Path
import os
import subprocess

APP_ID='AFTERPLAY.Desktop'

def executable(root):
    root=Path(root)
    return root/'AFTERPLAY.exe'

def create_shortcut(root,location='desktop',folder=None):
    root=Path(root).resolve();exe=executable(root)
    if not exe.is_file():raise ValueError('Ярлык доступен в готовой портативной сборке')
    import pythoncom
    import win32com.client
    from win32com.shell import shell,shellcon
    from win32com.propsys import propsys,pscon
    pythoncom.CoInitialize()
    try:
        if folder is None:
            csidl={'desktop':shellcon.CSIDL_DESKTOPDIRECTORY,'programs':shellcon.CSIDL_PROGRAMS,'startup':shellcon.CSIDL_STARTUP}[location]
            folder=Path(shell.SHGetFolderPath(0,csidl,0,0))
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        ws=win32com.client.Dispatch('WScript.Shell')
        path=folder/'AFTERPLAY.lnk';number=1
        while path.exists():
            old=ws.CreateShortcut(str(path))
            if str(old.TargetPath).casefold()==str(exe).casefold():break
            number+=1;path=folder/f'AFTERPLAY ({number}).lnk'
        link=ws.CreateShortcut(str(path));link.TargetPath=str(exe);link.WorkingDirectory=str(root)
        link.Arguments='--autostart' if location=='startup' else ''
        link.IconLocation=str(exe)+',0';link.Description='AFTERPLAY — видеотека и мгновенный повтор';link.Save()
        store=propsys.SHGetPropertyStoreFromParsingName(str(path),None,shellcon.GPS_READWRITE,propsys.IID_IPropertyStore)
        store.SetValue(pscon.PKEY_AppUserModel_ID,propsys.PROPVARIANTType(APP_ID));store.Commit()
        return path
    finally:pythoncom.CoUninitialize()

def taskbar_shortcut(root):
    link=create_shortcut(root,'programs')
    subprocess.Popen([str(Path(os.environ['WINDIR'])/'explorer.exe'),'/select,'+str(link)],
                     stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
    return {'path':str(link),'pinned':False,'requires_windows_menu':True}

def initialize_autostart(suite,root):
    settings=suite.cfg.setdefault('desktop',{}).setdefault(suite.app_mode,{})
    if 'autostart' in settings:return
    try:
        result=set_autostart(root,True)
        settings['autostart']=result['enabled']
        suite.save_cfg()
    except Exception as error:
        suite.log('autostart_setup_failed',error=str(error))


def set_autostart(root,enabled,folder=None):
    if not isinstance(enabled,bool):raise ValueError('Ожидался переключатель автозапуска')
    import pythoncom
    import win32com.client
    from win32com.shell import shell,shellcon
    pythoncom.CoInitialize()
    try:
        folder=Path(folder or shell.SHGetFolderPath(0,shellcon.CSIDL_STARTUP,0,0))
        ws=win32com.client.Dispatch('WScript.Shell')
        targets={str(Path(root).resolve()/name).casefold() for name in ('AFTERPLAY.exe',)}
        created=create_shortcut(root,'startup',folder) if enabled else None
        for link in folder.glob('*.lnk'):
            if created and link==created:continue
            if str(ws.CreateShortcut(str(link)).TargetPath).casefold() in targets:link.unlink()
        return {'enabled':enabled,**({'path':str(created)} if created else {})}
    finally:pythoncom.CoUninitialize()
