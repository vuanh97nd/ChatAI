"""Run on the Windows machine hosting PLAXIS; imports don't connect to PLAXIS."""
import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from fastapi import FastAPI
from .jobs import Jobs
from .project_memory import ProjectMemory
from .knowledge import configured_knowledge
from .router import router
from .runtime import NativeRuntime
from .utils import logger


def create_app(flash_model: Any = None, reasoning_model: Any = None,
               runtime: Any = None, api_token: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal flash_model, reasoning_model, runtime
        default_folder = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share'))) / 'ChatAI' / 'logs'
        folder = Path(os.environ.get('CHATAI_AGENT_LOG_DIR', str(default_folder)))
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / 'plaxis-agent.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            if flash_model is None or reasoning_model is None:
                from .model_config import build_model_pair
                flash_model, reasoning_model = build_model_pair()
            if runtime is None:
                from assistant.plaxis_remote import PlaxisRemoteApp
                runtime = NativeRuntime(PlaxisRemoteApp(None))
            memory = ProjectMemory(Path(os.environ.get('CHATAI_AGENT_STATE_DIR', str(folder / 'agent-state'))) / 'projects.sqlite3')
            app.state.jobs = Jobs(flash_model, reasoning_model, runtime,
                                  memory=memory, knowledge=configured_knowledge(memory.path.parent))
            yield
        finally:
            if hasattr(app.state, 'jobs'):
                await app.state.jobs.close()
            logger.removeHandler(handler)
            handler.close()

    app = FastAPI(title='Chat AI — PLAXIS Agent', version='4.0.0', lifespan=lifespan)
    app.state.api_token = api_token if api_token is not None else os.environ.get('CHATAI_AGENT_API_TOKEN', '')
    app.include_router(router)

    @app.get('/health')
    async def health() -> dict[str, Any]:
        return {'ok': True, 'plaxis_connection_verified': False,
                'note': 'Service sống; dùng inspect để kiểm tra PLAXIS.'}

    @app.get('/config')
    async def config_info() -> dict[str, Any]:
        """Show current model routing configuration (no secrets)."""
        from .model_config import flash_config, reasoning_config
        fc, rc = flash_config(), reasoning_config()
        using_openrouter = bool(os.environ.get('CHATAI_OPENROUTER_KEY'))
        return {
            'backend': 'openrouter' if using_openrouter else 'ollama',
            'flash_model': fc.model_id,
            'reasoning_model': rc.model_id,
            'flash_max_tokens': fc.max_tokens,
            'reasoning_max_tokens': rc.max_tokens,
            'routing': 'auto by default; override with model_tier in JobRequest',
        }

    return app


app = create_app()
