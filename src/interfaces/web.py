"""Interfaz web local para Ckrafter."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from dotenv import load_dotenv, set_key

from src.sessions.manager import create_session, list_sessions, load_session, save_session


ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).with_name("web_static")
ENV_FILE = ROOT_DIR / ".env"
HOST = "127.0.0.1"
PORT = 8766
MAX_BODY_BYTES = 16_384
MAX_REQUIREMENT_LENGTH = 5_000
MAX_FOCUS_LENGTH = 1_000
MAX_PROJECT_PATH_LENGTH = 2_048
SESSION_ID_PATTERN = re.compile(r"^\d{8}_\d{6}$")
OUTPUT_FILES = {
    "00_project_analysis.md": "Lectura inicial del proyecto",
    "01_plan_tecnico.md": "Plan del proyecto",
    "02_backend_code.md": "Construccion",
    "03_frontend_code.md": "Interfaz",
    "04_qa_report.md": "Pruebas",
    "05_security_report.md": "Seguridad",
    "06_devops_config.md": "Preparacion",
    "07_documentation.md": "Guia de uso",
    "00_lead_review.md": "Revision enfocada",
}
REVIEW_SOURCE_FILES = tuple(
    filename for filename in OUTPUT_FILES if filename != "00_lead_review.md"
)
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "openai/gpt-oss-120b",
        "needs_key": True,
    },
    "openai": {
        "base_url": "",
        "model": "gpt-4o-mini",
        "needs_key": True,
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
        "needs_key": False,
    },
}

LOGGER = logging.getLogger("ckrafter.web")
load_dotenv(ENV_FILE)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ckrafter")
_jobs: dict[str, dict] = {}
_active_sessions: set[str] = set()
_jobs_lock = threading.Lock()


def _safe_session_id(value: str) -> bool:
    return SESSION_ID_PATTERN.fullmatch(value) is not None


def _resolve_project_folder(value: object) -> Path:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_PROJECT_PATH_LENGTH:
        raise ValueError("Indica la ruta de la carpeta del proyecto.")
    try:
        folder = Path(value.strip().strip('"').strip("'")).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("No encontramos una carpeta accesible en esa ruta.") from exc
    if not folder.is_dir():
        raise ValueError("La ruta seleccionada no es una carpeta.")
    return folder


def _settings() -> dict:
    provider = os.getenv("OPENAI_PROVIDER", "groq").lower()
    if provider not in PROVIDERS:
        provider = "groq"
    api_key_configured = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "provider": provider,
        "configured": api_key_configured or not PROVIDERS[provider]["needs_key"],
        "api_key_configured": api_key_configured,
        "model": os.getenv("OPENAI_MODEL", PROVIDERS[provider]["model"]),
    }


def _session_summary(session: dict) -> dict:
    session_id = str(session.get("id", ""))
    output_dir = Path(str(session.get("output_dir", "")))
    files = []
    for filename, label in OUTPUT_FILES.items():
        path = output_dir / filename
        files.append({
            "name": filename,
            "label": label,
            "available": path.is_file(),
        })
    return {
        "id": session_id,
        "requirement": str(session.get("requirement", "")),
        "language": str(session.get("language", "espanol")),
        "created_at": str(session.get("created_at", "")),
        "updated_at": str(session.get("updated_at", "")),
        "steps": session.get("steps", {}),
        "error": bool(session.get("error")),
        "files": files,
        "is_external": bool(session.get("external_folder")),
        "analysis_ready": (output_dir / "00_project_analysis.md").is_file(),
        "conversation": [
            {
                "role": message["role"],
                "content": message["content"][-12_000:],
            }
            for message in session.get("conversation", [])[-40:]
            if isinstance(message, dict)
            and message.get("role") in {"user", "assistant"}
            and isinstance(message.get("content"), str)
        ],
    }


def _run_job(job_id: str, session_id: str, kind: str, focus: str = "") -> None:
    try:
        session = load_session(session_id)
        if kind == "analysis":
            from src.crews.dev_crew import analyze_external_project

            analyze_external_project(
                session["external_folder"],
                session["language"],
                session=session,
            )
        elif kind == "ask":
            from src.crews.dev_crew import ask_about_project

            answer = ask_about_project(session, focus)
            session.setdefault("conversation", []).extend([
                {"role": "user", "content": focus},
                {"role": "assistant", "content": answer},
            ])
            session["conversation"] = session["conversation"][-40:]
            save_session(session)
        elif kind == "review":
            from src.crews.dev_crew import run_lead

            run_lead(session, focus, quiet=True)
        else:
            from src.crews.dev_crew import run as run_pipeline

            def on_progress(step: str, status: str) -> None:
                with _jobs_lock:
                    job = _jobs[job_id]
                    job["step"] = step
                    job["step_status"] = status
                    job["updated_at"] = datetime.now().isoformat()

            run_pipeline(
                session["requirement"],
                session["language"],
                session,
                progress_callback=on_progress,
            )
        with _jobs_lock:
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["updated_at"] = datetime.now().isoformat()
    except Exception:
        LOGGER.exception("Background job %s failed", job_id)
        with _jobs_lock:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["message"] = (
                "No se pudo completar este paso. Puedes volver a intentarlo; "
                "el avance anterior se conserva."
            )
            _jobs[job_id]["updated_at"] = datetime.now().isoformat()
    finally:
        with _jobs_lock:
            _active_sessions.discard(session_id)


def _start_job(session: dict, kind: str, focus: str = "") -> dict:
    job_id = uuid.uuid4().hex
    session_id = str(session["id"])
    job = {
        "id": job_id,
        "session_id": session_id,
        "kind": kind,
        "status": "running",
        "step": "",
        "step_status": "",
        "message": "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    with _jobs_lock:
        if session_id in _active_sessions:
            raise ValueError("Este proyecto ya tiene un proceso en marcha.")
        _active_sessions.add(session_id)
        _jobs[job_id] = job
    try:
        _executor.submit(_run_job, job_id, session_id, kind, focus)
    except Exception:
        with _jobs_lock:
            _active_sessions.discard(session_id)
            _jobs.pop(job_id, None)
        raise
    return job.copy()


def _write_settings(provider: str, api_key: str) -> None:
    configuration = PROVIDERS[provider]
    ENV_FILE.touch(exist_ok=True)
    if api_key:
        set_key(str(ENV_FILE), "OPENAI_API_KEY", api_key)
    set_key(str(ENV_FILE), "OPENAI_PROVIDER", provider)
    set_key(str(ENV_FILE), "OPENAI_BASE_URL", configuration["base_url"])
    set_key(str(ENV_FILE), "OPENAI_MODEL", configuration["model"])
    set_key(str(ENV_FILE), "LOW_COST_MODE", "1")
    os.environ["OPENAI_PROVIDER"] = provider
    os.environ["OPENAI_BASE_URL"] = configuration["base_url"]
    os.environ["OPENAI_MODEL"] = configuration["model"]
    os.environ["LOW_COST_MODE"] = "1"
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key


class LocalWebServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class WebHandler(BaseHTTPRequestHandler):
    server_version = "Ckrafter"
    sys_version = ""

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _host_is_local(self) -> bool:
        host = self.headers.get("Host", "").split(":", 1)[0].strip("[]").lower()
        return host in {"127.0.0.1", "localhost"}

    def _origin_is_local(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        parsed = urlparse(origin)
        expected_host = self.headers.get("Host", "").lower()
        return parsed.scheme == "http" and parsed.netloc.lower() == expected_host

    def _read_json(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._error(400, "Solicitud no valida.")
            return None
        if length < 1 or length > MAX_BODY_BYTES:
            self._error(413, "La solicitud es demasiado grande o esta vacia.")
            return None
        body = self.rfile.read(length)
        if self.headers.get_content_type() != "application/json":
            self._error(415, "La solicitud debe usar formato JSON.")
            return None
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(400, "No se pudo leer la solicitud.")
            return None
        if not isinstance(payload, dict):
            self._error(400, "Formato de solicitud no valido.")
            return None
        return payload

    def do_GET(self) -> None:
        if not self._host_is_local():
            self._error(403, "Acceso no permitido.")
            return
        path = unquote(urlparse(self.path).path)
        if path == "/":
            self._serve_static("index.html", "text/html; charset=utf-8")
        elif path == "/styles.css":
            self._serve_static("styles.css", "text/css; charset=utf-8")
        elif path == "/app.js":
            self._serve_static("app.js", "text/javascript; charset=utf-8")
        elif path == "/api/bootstrap":
            with _jobs_lock:
                active_jobs = [
                    job.copy() for job in _jobs.values()
                    if job["status"] == "running"
                ]
            self._json(200, {
                "settings": _settings(),
                "active_jobs": active_jobs,
                "sessions": [
                    _session_summary(session)
                    for session in list_sessions()
                ],
            })
        elif path == "/api/sessions":
            self._json(200, {
                "sessions": [
                    _session_summary(session)
                    for session in list_sessions()
                ]
            })
        elif path.startswith("/api/sessions/"):
            self._get_session(path)
        elif path.startswith("/api/jobs/"):
            self._get_job(path.removeprefix("/api/jobs/"))
        else:
            self._error(404, "No encontramos esta pagina.")

    def _serve_static(self, filename: str, content_type: str) -> None:
        try:
            content = (STATIC_DIR / filename).read_bytes()
        except OSError:
            LOGGER.exception("Could not read web asset %s", filename)
            self._error(500, "No se pudo cargar la aplicacion.")
            return
        self._send(200, content, content_type)

    def _get_session(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) == 4 and parts[3] and parts[3] != "files":
            session_id = parts[3]
            if not _safe_session_id(session_id):
                self._error(400, "Identificador de proyecto no valido.")
                return
            try:
                session = load_session(session_id)
            except FileNotFoundError:
                self._error(404, "No encontramos este proyecto.")
                return
            self._json(200, {"session": _session_summary(session)})
            return
        if len(parts) == 6 and parts[3] and parts[4] == "files":
            session_id, filename = parts[3], parts[5]
            if not _safe_session_id(session_id) or filename not in OUTPUT_FILES:
                self._error(404, "No encontramos este documento.")
                return
            try:
                session = load_session(session_id)
                content = (Path(session["output_dir"]) / filename).read_text(encoding="utf-8")
            except FileNotFoundError:
                self._error(404, "Este documento aun no esta disponible.")
                return
            except (KeyError, OSError):
                LOGGER.exception("Could not read project document %s", filename)
                self._error(500, "No se pudo abrir este documento.")
                return
            if len(content) > 100_000:
                content = content[:100_000] + "\n\n[Vista previa recortada.]"
            self._json(200, {"name": filename, "label": OUTPUT_FILES[filename], "content": content})
            return
        self._error(404, "No encontramos este proyecto.")

    def _get_job(self, job_id: str) -> None:
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is None:
                self._error(404, "No encontramos este proceso.")
                return
            response = job.copy()
        try:
            session = load_session(response["session_id"])
            response["session"] = _session_summary(session)
        except FileNotFoundError:
            response["session"] = None
        self._json(200, {"job": response})

    def do_POST(self) -> None:
        path = unquote(urlparse(self.path).path)
        payload = self._read_json()
        if payload is None:
            return
        if not self._host_is_local() or not self._origin_is_local():
            self._error(403, "Acceso no permitido.")
            return
        if path == "/api/settings":
            self._save_settings(payload)
        elif path == "/api/projects":
            self._create_project(payload)
        elif path == "/api/external-projects":
            self._create_external_project(payload)
        elif path.startswith("/api/sessions/") and path.endswith("/continue"):
            self._continue_project(path, payload)
        elif path.startswith("/api/sessions/") and path.endswith("/ask"):
            self._ask_external_project(path, payload)
        elif path.startswith("/api/sessions/") and path.endswith("/review"):
            self._start_review(path, payload)
        else:
            self._error(404, "No encontramos esta accion.")

    def _save_settings(self, payload: dict) -> None:
        provider = payload.get("provider")
        api_key = payload.get("api_key", "")
        if provider not in PROVIDERS:
            self._error(400, "Elige un proveedor disponible.")
            return
        if not isinstance(api_key, str) or len(api_key) > 512:
            self._error(400, "La clave no tiene un formato valido.")
            return
        api_key = api_key.strip()
        configured_provider = os.getenv("OPENAI_PROVIDER", "groq").lower()
        key_is_for_selected_provider = (
            bool(os.getenv("OPENAI_API_KEY")) and configured_provider == provider
        )
        if (
            PROVIDERS[provider]["needs_key"]
            and not api_key
            and not key_is_for_selected_provider
        ):
            self._error(400, "Agrega la clave del proveedor para continuar.")
            return
        try:
            _write_settings(provider, api_key)
        except OSError:
            LOGGER.exception("Could not save local provider settings")
            self._error(500, "No se pudo guardar la configuracion local.")
            return
        self._json(200, {"settings": _settings()})

    def _create_project(self, payload: dict) -> None:
        requirement = payload.get("requirement")
        language = payload.get("language", "espanol")
        if not isinstance(requirement, str) or not 2 <= len(requirement.strip()) <= MAX_REQUIREMENT_LENGTH:
            self._error(400, f"Describe tu proyecto con entre 2 y {MAX_REQUIREMENT_LENGTH} caracteres.")
            return
        if language not in {"espanol", "english"}:
            self._error(400, "Elige un idioma disponible.")
            return
        if not _settings()["configured"]:
            self._error(409, "Configura tu proveedor antes de empezar.")
            return
        os.environ["OUTPUT_LANGUAGE"] = language
        session = create_session(requirement.strip(), language)
        save_session(session)
        self._launch(session, "pipeline")

    def _create_external_project(self, payload: dict) -> None:
        try:
            folder = _resolve_project_folder(payload.get("folder"))
        except ValueError as exc:
            self._error(400, str(exc))
            return
        language = payload.get("language", "espanol")
        if language not in {"espanol", "english"}:
            self._error(400, "Elige un idioma disponible.")
            return
        if not _settings()["configured"]:
            self._error(409, "Configura tu proveedor antes de analizar el proyecto.")
            return
        session = create_session(f"Proyecto existente: {folder.name}", language)
        session["external_folder"] = str(folder)
        session["conversation"] = []
        save_session(session)
        self._launch(session, "analysis")

    def _continue_project(self, path: str, payload: dict) -> None:
        del payload
        session_id = path.removeprefix("/api/sessions/").removesuffix("/continue")
        if not _safe_session_id(session_id):
            self._error(400, "Identificador de proyecto no valido.")
            return
        try:
            session = load_session(session_id)
        except FileNotFoundError:
            self._error(404, "No encontramos este proyecto.")
            return
        if session.get("external_folder"):
            self._error(409, "Este proyecto se trabaja desde la conversación contextual.")
            return
        self._launch(session, "pipeline")

    def _ask_external_project(self, path: str, payload: dict) -> None:
        session_id = path.removeprefix("/api/sessions/").removesuffix("/ask")
        question = payload.get("question")
        if not _safe_session_id(session_id):
            self._error(400, "Identificador de proyecto no valido.")
            return
        if not isinstance(question, str) or not 2 <= len(question.strip()) <= MAX_REQUIREMENT_LENGTH:
            self._error(400, "Escribe una instruccion de entre 2 y 5000 caracteres.")
            return
        if not _settings()["configured"]:
            self._error(409, "Configura tu proveedor antes de continuar.")
            return
        try:
            session = load_session(session_id)
        except FileNotFoundError:
            self._error(404, "No encontramos este proyecto.")
            return
        if not session.get("external_folder"):
            self._error(409, "La conversación contextual solo está disponible para proyectos existentes.")
            return
        if not Path(session["output_dir"], "00_project_analysis.md").is_file():
            self._error(409, "Espera a que termine la lectura inicial del proyecto.")
            return
        if not Path(session["external_folder"]).is_dir():
            self._error(409, "La carpeta original ya no está disponible.")
            return
        self._launch(session, "ask", question.strip())

    def _start_review(self, path: str, payload: dict) -> None:
        session_id = path.removeprefix("/api/sessions/").removesuffix("/review")
        focus = payload.get("focus", "")
        if not _safe_session_id(session_id):
            self._error(400, "Identificador de proyecto no valido.")
            return
        if not isinstance(focus, str) or len(focus) > MAX_FOCUS_LENGTH:
            self._error(400, "La indicacion de revision es demasiado larga.")
            return
        focus = focus.strip()
        if not focus:
            self._error(400, "Escribe qué quieres revisar antes de continuar.")
            return
        if not _settings()["configured"]:
            self._error(409, "Configura tu proveedor antes de pedir una revision.")
            return
        try:
            session = load_session(session_id)
        except FileNotFoundError:
            self._error(404, "No encontramos este proyecto.")
            return
        if session.get("external_folder"):
            self._error(409, "Usa la conversación contextual para trabajar con este proyecto.")
            return
        if not any(
            Path(session["output_dir"], filename).is_file()
            for filename in REVIEW_SOURCE_FILES
        ):
            self._error(409, "Primero completa alguna etapa del proyecto.")
            return
        self._launch(session, "review", focus)

    def _launch(self, session: dict, kind: str, focus: str = "") -> None:
        try:
            job = _start_job(session, kind, focus)
        except ValueError as exc:
            self._error(409, str(exc))
            return
        except RuntimeError:
            LOGGER.exception("Could not queue background job")
            self._error(503, "No se pudo iniciar el proceso. Intenta de nuevo.")
            return
        self._json(202, {"job": job, "session": _session_summary(session)})

    def log_message(self, format_string: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format_string % args)


def main() -> None:
    log_path = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "ckrafter-web.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    server = None
    for port in range(PORT, PORT + 10):
        try:
            server = LocalWebServer((HOST, port), WebHandler)
            break
        except OSError:
            try:
                with urlopen(f"http://{HOST}:{port}/api/bootstrap", timeout=1) as response:
                    if response.headers.get("Server", "").startswith("Ckrafter"):
                        webbrowser.open(f"http://{HOST}:{port}")
                        return
            except (OSError, HTTPException):
                pass
            continue
    if server is None:
        LOGGER.error("No available local port for Ckrafter")
        return
    address = f"http://{HOST}:{server.server_port}"
    try:
        try:
            webbrowser.open(address)
        except (OSError, webbrowser.Error):
            LOGGER.exception("Could not open the local app in a browser")
        LOGGER.info("Local interface started at %s", address)
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Local interface stopped")
    finally:
        server.server_close()
        _executor.shutdown(wait=False, cancel_futures=True)


if __name__ == "__main__":
    main()
