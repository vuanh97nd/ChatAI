"""Discover registered Windows desktop executables, without model-supplied commands."""
import os
from pathlib import Path


def installed_apps():
    if os.name!='nt':return []
    import winreg
    found={}
    def add(label,raw):
        if not isinstance(raw,str):return
        raw=os.path.expandvars(raw.strip())
        if raw.startswith('"'):
            parts=raw.split('"');raw=parts[1] if len(parts)>1 else ''
        else:raw=raw.rsplit(',',1)[0].strip()
        try:
            candidate=Path(raw)
            if not candidate.is_absolute():return
            path=candidate.resolve(strict=True)
        except (OSError,ValueError):return
        if not path.is_file() or path.suffix.lower()!='.exe' or str(path).startswith('\\\\'):return
        if path.name.lower() in {'uninstall.exe','unins000.exe','setup.exe','msiexec.exe','powershell.exe','pwsh.exe','cmd.exe','wscript.exe','cscript.exe','reg.exe','rundll32.exe'}:return
        found[str(path).casefold()]={'name':str(label)[:150],'path':str(path)}
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            for base,kind in ((r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths','paths'),
                              (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall','uninstall')):
                try:
                    with winreg.OpenKey(hive,base,0,winreg.KEY_READ|view) as key:
                        for index in range(min(winreg.QueryInfoKey(key)[0],2000)):
                            try:
                                name=winreg.EnumKey(key,index)
                                with winreg.OpenKey(key,name) as item:
                                    if kind=='paths':add(name,winreg.QueryValueEx(item,None)[0])
                                    else:add(winreg.QueryValueEx(item,'DisplayName')[0],winreg.QueryValueEx(item,'DisplayIcon')[0])
                            except OSError:continue
                except OSError:continue
    return sorted(found.values(),key=lambda row:row['name'].casefold())


def authorized_apps(cfg):
    rows=[{'name':Path(p).name,'path':p} for p in cfg.get('windows_apps_allowed',[])]
    if cfg.get('windows_apps_all_installed'):rows+=installed_apps()
    return list({row['path'].casefold():row for row in rows}.values())
