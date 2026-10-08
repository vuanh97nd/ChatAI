"""Explicit, persistent grant for ChatAI's supported task tools."""
GRANTS=('windows_apps_enabled','windows_apps_all_installed','windows_apps_auto_execute',
        'automation_auto_install','online_tools_enabled','online_document_upload',
        'auto_python','ai_tools_auto_execute')


def grant_autonomy(cfg):
    result=dict(cfg)
    result.update({name:True for name in GRANTS})
    result['online_document_provider']='deepseek_flash'
    result['online_document_pages']=0
    result['online_document_revision']=2
    return result


def task_tools_authorized(cfg):
    return cfg.get('ai_tools_auto_execute') is True
