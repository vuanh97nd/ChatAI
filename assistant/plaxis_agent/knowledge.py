"""Bridge the agent to the existing source/hash-checked RAG collection."""
import json
import os
from pathlib import Path


def configured_knowledge(storage: Path):
    roots = json.loads(os.environ.get('CHATAI_AGENT_DOCUMENT_ROOTS', '[]'))
    if not roots:
        return None
    if not isinstance(roots, list) or not all(isinstance(r, str) and Path(r).is_dir() for r in roots):
        raise ValueError('CHATAI_AGENT_DOCUMENT_ROOTS must list existing document directories.')
    from ollama import Client
    from assistant.files import FileTools
    from assistant.rag import RagTools
    files = FileTools(roots, storage / 'backups', lambda *args, **kwargs: None)
    return RagTools(files, Client(host=os.environ.get('CHATAI_OLLAMA_URL', 'http://127.0.0.1:11434'), timeout=180),
                    storage, lambda *args, **kwargs: None,
                    owner=os.environ.get('CHATAI_AGENT_CORPUS_OWNER', 'local'), storage_root=storage)
