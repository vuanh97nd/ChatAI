"""Run on the Windows machine hosting PLAXIS; imports don't connect to PLAXIS."""
import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from fastapi import FastAPI
from .jobs import Jobs
from .router import router
from .runtime import NativeRuntime
from .utils import logger


def create_app(model: Any = None, runtime: Any = None, api_token: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal model, runtime
        default_folder = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local' / 'share'))) / 'ChatAI' / 'logs'
        folder = Path(os.environ.get('CHATAI_AGENT_LOG_DIR', str(default_folder)))
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / 'plaxis-agent.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            if model is None:
                from langchain_ollama import ChatOllama
                model = ChatOllama(model=os.environ.get('CHATAI_AGENT_MODEL', 'qwen2.5:7b'),
                    base_url=os.environ.get('CHATAI_OLLAMA_URL', 'http://127.0.0.1:11434'),
                    temperature=0, client_kwargs={'timeout': 180}, async_client_kwargs={'timeout': 180})
            if runtime is None:
                from assistant.plaxis_remote import PlaxisRemoteApp
                runtime = NativeRuntime(PlaxisRemoteApp(None))
            app.state.jobs = Jobs(model, runtime)
            yield
        finally:
            if hasattr(app.state, 'jobs'):
                await app.state.jobs.close()
            logger.removeHandler(handler)
            handler.close()

    app = FastAPI(title='Chat AI — PLAXIS Agent', version='3.0.0', lifespan=lifespan)
    app.state.api_token = api_token if api_token is not None else os.environ.get('CHATAI_AGENT_API_TOKEN', '')
    app.include_router(router)

    @app.get('/health')
    async def health() -> dict[str, Any]:
        return {'ok': True, 'plaxis_connection_verified': False,
                'note': 'Service sống; dùng inspect để kiểm tra PLAXIS.'}

    return app


app = create_app()
