import http.client
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from src.interfaces.web import (
    LocalWebServer,
    WebHandler,
    _safe_session_id,
    _session_summary,
    _settings,
)
from src.sessions import manager as session_manager


class SessionManagerTests(unittest.TestCase):
    def test_session_ids_are_unique_when_created_in_the_same_second(self):
        class FixedDateTime(session_manager.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 26, 11, 49, 0, tzinfo=tz)

        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.dict("os.environ", {
                    "SESSIONS_DIR": temporary,
                    "OUTPUT_DIR": temporary,
                }),
                patch("src.sessions.manager.datetime", FixedDateTime),
                patch("src.sessions.manager._last_session_id", ""),
            ):
                first = session_manager.create_session("Primero", "espanol")
                second = session_manager.create_session("Segundo", "espanol")

        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["output_dir"], second["output_dir"])

    def test_concurrent_session_creation_never_reuses_an_id(self):
        class FixedDateTime(session_manager.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 26, 11, 49, 0, tzinfo=tz)

        with tempfile.TemporaryDirectory() as temporary:
            with (
                patch.dict("os.environ", {
                    "SESSIONS_DIR": temporary,
                    "OUTPUT_DIR": temporary,
                }),
                patch("src.sessions.manager.datetime", FixedDateTime),
                patch("src.sessions.manager._last_session_id", ""),
            ):
                with ThreadPoolExecutor(max_workers=16) as executor:
                    sessions = list(executor.map(
                        lambda index: session_manager.create_session(
                            f"Proyecto {index}", "espanol"
                        ),
                        range(64),
                    ))

        session_ids = [session["id"] for session in sessions]
        self.assertEqual(len(session_ids), len(set(session_ids)))

    def test_session_creation_skips_an_existing_timestamp_file(self):
        class FixedDateTime(session_manager.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 26, 11, 49, 0, tzinfo=tz)

        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "20261026_114900.json").touch()
            with (
                patch.dict("os.environ", {
                    "SESSIONS_DIR": temporary,
                    "OUTPUT_DIR": temporary,
                }),
                patch("src.sessions.manager.datetime", FixedDateTime),
                patch("src.sessions.manager._last_session_id", ""),
            ):
                session = session_manager.create_session("Proyecto", "espanol")

        self.assertEqual(session["id"], "20261026_114901")


class WebAppHelpersTests(unittest.TestCase):
    def test_session_summary_only_exposes_available_documents(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / "01_plan_tecnico.md").write_text("Plan", encoding="utf-8")
            summary = _session_summary({
                "id": "20261026_112200",
                "requirement": "Una app de ejemplo",
                "language": "espanol",
                "output_dir": str(output),
                "steps": {"pm": "completed"},
                "error": "internal error details",
                "created_at": "2026-10-26T11:22:00",
            })

        self.assertTrue(summary["files"][0]["available"])
        self.assertFalse(summary["files"][1]["available"])
        self.assertTrue(summary["error"])
        self.assertNotIn("output_dir", summary)
        self.assertNotIn("internal error details", json.dumps(summary))

    def test_session_ids_only_accept_the_existing_timestamp_format(self):
        self.assertTrue(_safe_session_id("20261026_112200"))
        self.assertFalse(_safe_session_id("../20261026_112200"))
        self.assertFalse(_safe_session_id("session-1"))

    def test_settings_report_key_presence_without_returning_the_secret(self):
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "test-secret-that-must-not-leak",
            "OPENAI_PROVIDER": "groq",
            "OPENAI_MODEL": "openai/gpt-oss-120b",
        }):
            settings = _settings()

        self.assertTrue(settings["configured"])
        self.assertTrue(settings["api_key_configured"])
        self.assertNotIn("api_key", settings)
        self.assertNotIn("test-secret-that-must-not-leak", json.dumps(settings))


class WebAppHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalWebServer(("127.0.0.1", 0), WebHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )
        encoded = json.dumps(body).encode("utf-8") if body is not None else None
        request_headers = dict(headers or {})
        if encoded is not None:
            request_headers.setdefault("Content-Type", "application/json")
        connection.request(method, path, body=encoded, headers=request_headers)
        response = connection.getresponse()
        payload = response.read()
        result = (response.status, response.getheaders(), payload)
        connection.close()
        return result

    def test_serves_local_interface_with_security_headers(self):
        status, headers, body = self.request("GET", "/")

        self.assertEqual(status, 200)
        self.assertIn(b"Ckrafter", body)
        self.assertNotIn(b"Agente S", body)
        self.assertNotIn(b"AGENTE S", body)
        response_headers = dict(headers)
        self.assertTrue(response_headers["Server"].startswith("Ckrafter"))
        self.assertIn("default-src 'self'", response_headers["Content-Security-Policy"])
        self.assertEqual(response_headers["X-Frame-Options"], "DENY")

    def test_api_key_is_never_in_bootstrap_response(self):
        status, _, body = self.request("GET", "/api/bootstrap")

        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertIn("api_key_configured", payload["settings"])
        self.assertNotIn("api_key", payload["settings"])

    def test_rejects_cross_origin_settings_changes(self):
        status, _, body = self.request(
            "POST",
            "/api/settings",
            {"provider": "groq", "api_key": "not-a-real-key"},
            {"Origin": "http://attacker.example"},
        )

        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "Acceso no permitido.")

    def test_accepts_same_origin_settings_request(self):
        with (
            patch("src.interfaces.web._write_settings"),
            patch("src.interfaces.web._settings", return_value={
                "provider": "ollama",
                "configured": True,
                "api_key_configured": False,
                "model": "llama3.2",
            }),
        ):
            status, _, body = self.request(
                "POST",
                "/api/settings",
                {"provider": "ollama", "api_key": ""},
                {"Origin": f"http://127.0.0.1:{self.server.server_port}"},
            )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["settings"]["provider"], "ollama")

    def test_rejects_non_json_post_body(self):
        status, _, body = self.request(
            "POST",
            "/api/settings",
            {"provider": "ollama"},
            {"Content-Type": "text/plain"},
        )

        self.assertEqual(status, 415)
        self.assertEqual(
            json.loads(body)["error"],
            "La solicitud debe usar formato JSON.",
        )

    def test_rejects_oversized_post_body(self):
        status, _, body = self.request(
            "POST",
            "/api/settings",
            {"provider": "ollama", "extra": "x" * 16_384},
        )

        self.assertEqual(status, 413)
        self.assertEqual(
            json.loads(body)["error"],
            "La solicitud es demasiado grande o esta vacia.",
        )

    def test_changing_provider_requires_a_matching_api_key(self):
        with (
            patch.dict("os.environ", {
                "OPENAI_API_KEY": "saved-groq-key",
                "OPENAI_PROVIDER": "groq",
            }),
            patch("src.interfaces.web._write_settings") as write_settings,
        ):
            status, _, body = self.request(
                "POST",
                "/api/settings",
                {"provider": "openai", "api_key": ""},
            )

        self.assertEqual(status, 400)
        self.assertEqual(
            json.loads(body)["error"],
            "Agrega la clave del proveedor para continuar.",
        )
        write_settings.assert_not_called()

    def test_review_rejects_blank_focus(self):
        with patch.dict("os.environ", {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_PROVIDER": "groq",
        }):
            status, _, body = self.request(
                "POST",
                "/api/sessions/20261026_112200/review",
                {"focus": "   "},
            )

        self.assertEqual(status, 400)
        self.assertEqual(
            json.loads(body)["error"],
            "Escribe qué quieres revisar antes de continuar.",
        )

    def test_review_requires_an_original_project_deliverable(self):
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "00_lead_review.md").write_text("Revision previa", encoding="utf-8")
            session = {"output_dir": temporary}
            with (
                patch.dict("os.environ", {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_PROVIDER": "groq",
                }),
                patch("src.interfaces.web.load_session", return_value=session),
                patch.object(WebHandler, "_launch") as launch,
            ):
                status, _, body = self.request(
                    "POST",
                    "/api/sessions/20261026_112200/review",
                    {"focus": "Revisar la seguridad"},
                )

        self.assertEqual(status, 409)
        self.assertEqual(
            json.loads(body)["error"],
            "Primero completa alguna etapa del proyecto.",
        )
        launch.assert_not_called()

    def test_started_job_response_includes_safe_session_summary(self):
        session_id = "20261026_112200"
        with tempfile.TemporaryDirectory() as temporary:
            session = {
                "id": session_id,
                "requirement": "Una app de ejemplo",
                "language": "espanol",
                "output_dir": temporary,
                "steps": {"pm": "completed"},
            }
            with (
                patch("src.interfaces.web.load_session", return_value=session),
                patch("src.interfaces.web._start_job", return_value={
                    "id": "job-1",
                    "session_id": session_id,
                    "status": "running",
                }),
            ):
                status, _, body = self.request(
                    "POST",
                    f"/api/sessions/{session_id}/continue",
                    {},
                )

        payload = json.loads(body)
        self.assertEqual(status, 202)
        self.assertEqual(payload["session"]["id"], session_id)
        self.assertNotIn("output_dir", payload["session"])

    def test_rejects_non_local_hosts(self):
        status, _, _ = self.request("GET", "/", headers={"Host": "attacker.example"})

        self.assertEqual(status, 403)

    def test_document_routes_cannot_escape_the_output_allowlist(self):
        status, _, _ = self.request(
            "GET", "/api/sessions/20261026_112200/files/%2e%2e%5c.env"
        )

        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
