"""Bounded project checkpoints; historical evidence must be read again before writes."""
import json
import sqlite3
from pathlib import Path
from typing import Any


class ProjectMemory:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT, version TEXT, data TEXT, PRIMARY KEY(id,version))')

    def load(self, project_id: str, version: str) -> dict[str, Any]:
        with sqlite3.connect(self.path) as db:
            row = db.execute('SELECT data FROM projects WHERE id=? AND version=?', (project_id, version)).fetchone()
        return json.loads(row[0]) if row else {}

    def save(self, project_id: str, version: str, events: list, result: dict) -> None:
        # Store observations, not executable calls, permissions or chain-of-thought.
        data = json.dumps({'events': [{'tool': e.get('tool'), 'result': e.get('result')} for e in events[-12:]], 'result': result}, ensure_ascii=False, default=str)
        if len(data) > 64000:
            data = json.dumps({'note': 'Checkpoint too large; inspect live project again.'})
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT OR REPLACE INTO projects VALUES (?,?,?)', (project_id, version, data))
