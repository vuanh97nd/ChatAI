import json
from .office import OfficeTools
from .files import FileTools
from .rag import RagTools
from .runner import Runner
from .python_search import PythonSearch
from .template_engine import TemplateEngine
from .tools import TOOLS, EXTRA_TOOLS, WRITES, DOCUMENT_READ_SCHEMA
from .web import WebTools
from .media import MediaTools
from .media_basic import BasicMediaTools




class Capabilities:
    def __init__(self, manager, excel, client, cfg, root, audit, owner="local", storage_root=None, allow_web=False, on_status=None):
        self.manager, self.excel = manager, excel
        self.allow_web = bool(allow_web)
        self.files = FileTools(cfg["roots"], root / "data" / "backups", audit)
        self.office = OfficeTools(self.files)
        self.web = WebTools()
        self.runner = Runner(self.files, audit)
        self.python_search = PythonSearch(self.runner,self.web,audit)
        self.rag = RagTools(self.files, client, root, audit, owner=owner, storage_root=storage_root,
                            vision_model=cfg.get('vision_model','gemma3:4b'))
        self.media = MediaTools(self.files, client, cfg, root, audit,on_status=on_status,
                                model_variant=manager.media_variant())
        self.media_basic=BasicMediaTools(self.files,audit)
        self.template = TemplateEngine(cfg["roots"], root / "data" / "backups", audit)
        # Chụp snapshot module cho lượt UI này; không tự import dependency khi chưa bật.
        self.active = {key for key in ("web", "files", "python", "rag", "media", "office", "media_basic", "template") if manager.ready(key)}
        if not self.allow_web:self.active.discard("web")
        from .windows_apps import WindowsApps, available
        self.windows = WindowsApps(cfg, audit, owner=owner, policy_path=root / 'config.json')
        if cfg.get('windows_apps_enabled') and available():self.active.add('windows')
        from .browser import BrowserTools, available as browser_available
        self.browser = BrowserTools(cfg,audit,policy_path=root/'config.json',on_status=on_status)
        if cfg.get('windows_apps_enabled') and browser_available():self.active.add('browser')
        from .pdf_source import PDFSource
        self.pdf_source=PDFSource(self.windows,self.files,audit)
        from .word_app import WordApp
        self.word_app=WordApp(self.windows,self.files)
        from .cad_app import CadApp
        self.cad_app=CadApp(self.windows,self.files,audit)
        from .cad3d_app import Cad3DApp
        self.cad3d_app=Cad3DApp(self.windows,self.files,audit)
        from .plaxis_app import PlaxisApp
        self.plaxis_app=PlaxisApp(self.files,audit)
        from .geoslope_app import GeoslopeApp
        self.geoslope_app=GeoslopeApp(self.files,audit)
        from .soilfirm_app import SoilFirmApp
        self.soilfirm_app=SoilFirmApp(self.files,audit)
        from .borehole_dxf import BoreholeDxfApp
        self.borehole_dxf=BoreholeDxfApp(self.files,self.windows,audit)
        from .road_pipeline_app import RoadPipelineApp
        self.road_pipeline=RoadPipelineApp(self.files,self.soilfirm_app,audit)
        if 'windows' in self.active:self.active.update({'pdf_source','word_app','cad_app','cad3d_app'})
        self.active.add('plaxis_app')
        self.active.add('geoslope_app')
        self.active.add('soilfirm_app')
        self.active.add('road_pipeline')
        if 'windows' in self.active:self.active.add('borehole_dxf')
        self.schemas = TOOLS + [DOCUMENT_READ_SCHEMA] + [schema for module, schema in EXTRA_TOOLS if module in self.active and (schema['function']['name']!='python_search' or 'web' in self.active)]
        from .online_automation import app_permissions
        self.schemas = [dict(spec,function=dict(spec['function'],description=spec['function']['description']+' '+app_permissions(cfg))) if spec['function']['name'] in {'windows_open','browser_search','browser_run'} else spec for spec in self.schemas]

    def prepare(self, name, args):
        if name=='road_analyze':return self.road_pipeline.prepare_analyze(name,args)
        if name=='road_verify':return self.road_pipeline.prepare_verify(name,args)
        if name=='soilfirm_create':return self.soilfirm_app.prepare_create(name,args)
        if name=='borehole_dxf':return self.borehole_dxf.prepare(name,args)
        if name=='geoslope_create':return self.geoslope_app.prepare(name,args)
        if name=='plaxis_generate_script':return self.plaxis_app.prepare(name,args)
        if name=='cad3d_create_open':return self.cad3d_app.prepare(name,args)
        if name=='cad_create_open':return self.cad_app.prepare(name,args)
        if name=='word_create_open':return self.word_app.prepare(name,args)
        if name in {'pdf_source_open','pdf_read'}:return self.pdf_source.prepare(name,args)
        if name.startswith('browser_'):return self.browser.prepare(name,args)
        if name.startswith("windows_"):return self.windows.prepare(name,args)
        if name=="python_search" and not self.allow_web:raise PermissionError("Bật nút Tìm kiếm mạng trước.")
        if name=="python_search":return self.python_search.prepare(args["code"])
        if name == "excel_edit_cell":
            return {"action": name, **self.excel.prepare_edit(**args)}
        if name == "excel_create_from_template":
            return self.excel.prepare_from_template(**args)
        if name == "template_fill":
            return self.template.prepare(name, args)
        if name in {"office_create", "word_replace"}:
            return self.office.prepare(name, args)
        if name.startswith("file_"):
            return self.files.prepare(name, args)
        if name in {"python_run", "run_command"}:
            return self.runner.prepare(name, args)
        if name == "rag_index":
            return self.rag.prepare(**args)
        if name in {"image_generate", "video_generate"}:
            return self.media.prepare(name, args)
        if name in {"image_resize","video_from_images"}:
            return self.media_basic.prepare(name,args)
        raise ValueError("Thao tác ghi không có trong registry.")

    def commit(self, plan):
        action = plan.get("action", "excel_edit_cell")
        module = next((m for m, t in EXTRA_TOOLS if t["function"]["name"] == action), None)
        if module is not None and module not in self.active:
            raise RuntimeError("Module đã bị tắt hoặc chưa sẵn sàng; thao tác không chạy.")
        if action=='road_analyze':return self.road_pipeline.commit_analyze(plan)
        if action=='road_verify':return self.road_pipeline.commit_verify(plan)
        if action=='soilfirm_create':return self.soilfirm_app.commit_create(plan)
        if action=='borehole_dxf':return self.borehole_dxf.commit(plan)
        if action=='plaxis_generate_script':return self.plaxis_app.commit(plan)
        if action=='cad3d_create_open':return self.cad3d_app.commit(plan)
        if action=='cad_create_open':return self.cad_app.commit(plan)
        if action=='word_create_open':return self.word_app.commit(plan)
        if action.startswith("windows_"):return self.windows.commit(plan)
        if action.startswith('browser_'):return self.browser.commit(plan)
        if action in {'pdf_source_open','pdf_read'}:return self.pdf_source.commit(plan)
        if action=="python_search":
            if not self.allow_web:raise PermissionError("Bật nút Tìm kiếm mạng trước.")
            if not {"web","python"}.issubset(self.active):raise RuntimeError("Bật module Web và Python trước.")
            return self.python_search.commit(plan)
        if action in {"image_resize","video_from_images"}:
            return self.media_basic.commit(plan)
        if action == "excel_edit_cell":
            return self.excel.commit_edit(plan)
        if action == "excel_create_from_template":
            return self.excel.commit_from_template(plan)
        if action == "template_fill":
            return self.template.commit(plan)
        if action in {"office_create", "word_replace"}:
            return self.office.commit(plan)
        if action.startswith("file_"):
            return self.files.commit(plan)
        if action in {"python_run", "run_command"}:
            return self.runner.commit(plan)
        if action in {"image_generate", "video_generate"}:
            return self.media.commit(plan)
        return self.rag.commit(plan)

    def read(self, name, args):
        if name=="document_read":
            from .documents import read_document_range,pdf_vision_ocr
            return read_document_range(self.files,**args,
                pdf_ocr=pdf_vision_ocr(self.manager.client,self.cfg.get('vision_model','gemma3:4b'),
                                       num_ctx=self.cfg.get('num_ctx',4096)))
        if name in {"web_search","web_read"} and not self.allow_web:
            raise PermissionError("Bật nút Tìm kiếm mạng trước.")
        if name == 'soilfirm_read':
            mode = args.get('mode', 'summary')
            if mode == 'full':
                return self.soilfirm_app.read_project(args['path'])
            return self.soilfirm_app.summary(args['path'])
        registry = {"excel_list_files": self.excel.excel_list_files,
                    "excel_list_sheets": self.excel.excel_list_sheets,
                    "excel_read": self.excel.excel_read,
                    "excel_summary": self.excel.excel_summary,
                    "file_list": self.files.file_list, "file_read": self.files.file_read,
                    "web_search": self.web.web_search, "web_read": self.web.web_read,
                    "rag_search": self.rag.rag_search, "office_read": self.office.office_read,
                    "template_scan": self.template.scan_template}
        return registry[name](**args)
