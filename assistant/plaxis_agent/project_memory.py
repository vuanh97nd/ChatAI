"""Bounded project checkpoints; historical evidence must be read again before writes."""
import json
import sqlite3
from pathlib import Path
from typing import Any

_MAX_EVENTS = 3
_MAX_CHECKPOINT_CHARS = 8000


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    result = event.get('result', {})
    compact_result = {k: result[k] for k in ('ok', 'error', 'uncertain', 'metrics') if k in result}
    return {'tool': event.get('tool'), 'result': compact_result}


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
        compact_events = [_compact_event(e) for e in events[-_MAX_EVENTS:]]
        data = json.dumps({'events': compact_events, 'result': result}, ensure_ascii=False, default=str)
        if len(data) > _MAX_CHECKPOINT_CHARS:
            data = json.dumps({'note': 'Checkpoint too large; inspect live project again.'})
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT OR REPLACE INTO projects VALUES (?,?,?)', (project_id, version, data))
