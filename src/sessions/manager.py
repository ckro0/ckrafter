"""
Gestion de sesiones: guarda el estado de cada ejecucion para poder reanudarla.

Las sesiones se almacenan como JSON en la carpeta ./sessions/
"""

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

_session_id_lock = threading.Lock()
_last_session_id = ""


def _sessions_dir() -> Path:
    base = Path(os.getenv("SESSIONS_DIR", "./sessions"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def create_session(requirement: str, language: str) -> dict:
    global _last_session_id
    with _session_id_lock:
        timestamp = datetime.now()
        session_id = timestamp.strftime("%Y%m%d_%H%M%S")
        sessions_dir = _sessions_dir()
        while (
            session_id <= _last_session_id
            or (sessions_dir / f"{session_id}.json").exists()
        ):
            timestamp += timedelta(seconds=1)
            session_id = timestamp.strftime("%Y%m%d_%H%M%S")
        _last_session_id = session_id

    base_output = Path(os.getenv("OUTPUT_DIR", "./output"))
    output_dir = str(base_output / session_id)
    return {
        "id": session_id,
        "requirement": requirement,
        "language": language,
        "provider": os.getenv("OPENAI_PROVIDER", "groq"),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
        "openai_base_url": os.getenv("OPENAI_BASE_URL", "") or "",
        "low_cost": os.getenv("LOW_COST_MODE", "0") == "1",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "output_dir": output_dir,
        "steps": {
            "pm":          "pending",
            "backend":     "pending",
            "frontend":    "pending",
            "qa":          "pending",
            "security":    "pending",
            "devops":      "pending",
            "tech_writer": "pending",
        },
        "error": None,
    }


def save_session(session: dict) -> None:
    session["updated_at"] = datetime.now().isoformat()
    path = _sessions_dir() / f"{session['id']}.json"
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


def load_session(session_id: str) -> dict:
    path = _sessions_dir() / f"{session_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions() -> list:
    d = _sessions_dir()
    sessions = []
    for f in sorted(d.glob("*.json"), reverse=True):
        try:
            sessions.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return sessions


def session_progress(session: dict) -> tuple:
    """Returns (completed_count, total_count)"""
    steps = session["steps"]
    total = len(steps)
    completed = sum(1 for s in steps.values() if s == "completed")
    return completed, total
