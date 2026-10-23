"""User-requested Shell shortcuts; taskbar pinning stays under Windows control."""
from pathlib import Path
import os
import subprocess

APP_ID='GVDesktop.clips'

def create_shortcut(root,location='desktop',folder=None):
    root=Path(root).resolve();exe=root/'Game Clips.exe'
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
        path=folder/'Game Clips.lnk';number=1
        while path.exists():
            old=ws.CreateShortcut(str(path))
            if str(old.TargetPath).casefold()==str(exe).casefold():break
            number+=1;path=folder/f'Game Clips ({number}).lnk'
        link=ws.CreateShortcut(str(path));link.TargetPath=str(exe);link.WorkingDirectory=str(root)
        link.IconLocation=str(exe)+',0';link.Description='Game Clips — видеотека и мгновенный повтор';link.Save()
        store=propsys.SHGetPropertyStoreFromParsingName(str(path),None,shellcon.GPS_READWRITE,propsys.IID_IPropertyStore)
        store.SetValue(pscon.PKEY_AppUserModel_ID,propsys.PROPVARIANTType(APP_ID));store.Commit()
        return path
    finally:pythoncom.CoUninitialize()

def taskbar_shortcut(root):
    link=create_shortcut(root,'programs')
    subprocess.Popen([str(Path(os.environ['WINDIR'])/'explorer.exe'),'/select,'+str(link)],
                     stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)
    return {'path':str(link),'pinned':False,'requires_windows_menu':True}

def set_autostart(root,enabled,folder=None):
    if not isinstance(enabled,bool):raise ValueError('Ожидался переключатель автозапуска')
    if enabled:return {'enabled':True,'path':str(create_shortcut(root,'startup',folder))}
    import pythoncom
    import win32com.client
    from win32com.shell import shell,shellcon
    pythoncom.CoInitialize()
    try:
        folder=Path(folder or shell.SHGetFolderPath(0,shellcon.CSIDL_STARTUP,0,0))
        ws=win32com.client.Dispatch('WScript.Shell');target=str(Path(root).resolve()/'Game Clips.exe')
        for link in folder.glob('Game Clips*.lnk'):
            if str(ws.CreateShortcut(str(link)).TargetPath).casefold()==target.casefold():link.unlink()
        return {'enabled':False}
    finally:pythoncom.CoUninitialize()
