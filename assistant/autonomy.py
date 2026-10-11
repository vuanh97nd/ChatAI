"""Explicit, persistent grant for ChatAI's supported task tools."""
GRANTS=('windows_apps_enabled','windows_apps_all_installed','windows_apps_auto_execute',
        'automation_auto_install','online_tools_enabled','online_document_upload',
        'auto_python','ai_tools_auto_execute')


def grant_autonomy(cfg):
    result=dict(cfg)
    result.update({name:True for name in GRANTS})
    result.setdefault('online_document_provider','deepseek_flash')
    result['online_document_pages']=0
    result['online_document_revision']=2
    return result


def windows_work_folders(extra=()):
    """Existing user work folders, including Windows/OneDrive redirections."""
    import os
    from pathlib import Path
    if os.name != 'nt':
        return []
    folders=[]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
            for name in ('Desktop','Personal','{374DE290-123F-4565-9164-39C4925E467B}'):
                try:
                    folders.append(os.path.expandvars(winreg.QueryValueEx(key,name)[0]))
                except OSError:
                    pass
    except OSError:
        pass
    folders.extend(os.path.join(str(Path.home()),name) for name in ('Desktop','Documents','Downloads'))
    folders.extend(extra)
    return list(dict.fromkeys(str(Path(folder).resolve()) for folder in folders
                             if Path(folder).is_dir()))


def task_tools_authorized(cfg):
    return cfg.get('ai_tools_auto_execute') is True


def main():
    """Explicit user command; does not silently change permissions on startup."""
    import argparse
    from .config import load_config,save_config
    parser=argparse.ArgumentParser(description='Cấp quyền công cụ công việc cho Chat AI.')
    parser.add_argument('--folder',action='append',default=[],help='Thư mục công việc được phép, có thể dùng nhiều lần.')
    args=parser.parse_args()
    cfg=grant_autonomy(load_config())
    cfg['task_user_folders_enabled']=True
    cfg['task_extra_folders']=list(dict.fromkeys(cfg.get('task_extra_folders',[])+args.folder))
    cfg['whitelist']=list(dict.fromkeys(cfg['whitelist']+args.folder))
    saved=save_config(cfg)
    print('Đã lưu quyền tự thực hiện công cụ công việc. Khởi động lại Chat AI.')
    for folder in saved['whitelist']:print(folder)


if __name__=='__main__':main()
