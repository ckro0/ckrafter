"""Servidor local y API de busqueda para Repair Finder."""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen


HOST = "127.0.0.1"
PORT = 8765
MAX_QUERY_LENGTH = 120
MAX_RESULTS = 100
API_BASE_URL = "https://www.ifixit.com/api/2.0/search/"
STATIC_DIR = Path(__file__).parent / "static"
LOGGER = logging.getLogger("repair_finder")


class SearchError(Exception):
    """Error comunicable cuando el proveedor de busqueda no esta disponible."""


def _ifixit_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.startswith("https://"):
        return None
    hostname = urlparse(value).hostname
    if hostname not in {"ifixit.com", "www.ifixit.com"}:
        return None
    return value


def normalize_result(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None

    link = _ifixit_url(item.get("url"))
    title = item.get("display_title") or item.get("title")
    if not link or not isinstance(title, str) or not title.strip():
        return None

    image_data = item.get("image")
    image_url = None
    if isinstance(image_data, dict):
        thumbnail = image_data.get("thumbnail")
        if isinstance(thumbnail, str) and thumbnail.startswith(
            "https://guide-images.cdn.ifixit.com/"
        ):
            image_url = thumbnail

    modified = item.get("modified_date")
    if not isinstance(modified, (int, float)):
        modified = None

    return {
        "title": title.strip(),
        "summary": str(item.get("summary") or item.get("text") or "").strip(),
        "url": link,
        "kind": str(item.get("dataType") or "resource").lower(),
        "language": str(item.get("langid") or ""),
        "difficulty": str(item.get("difficulty") or ""),
        "modified": modified,
        "image": image_url,
    }


def search_ifixit(query: str) -> list[dict]:
    encoded_query = quote(query, safe="")
    request = Request(
        f"{API_BASE_URL}{encoded_query}?limit={MAX_RESULTS}",
        headers={
            "Accept": "application/json",
            "User-Agent": "RepairFinder/1.0 (local repair-resource search)",
        },
    )

    try:
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
    except HTTPError as exc:
        LOGGER.warning("iFixit search returned HTTP %s", exc.code)
        raise SearchError(
            f"iFixit rechazo la busqueda (HTTP {exc.code}). Intenta de nuevo mas tarde."
        ) from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("iFixit search failed: %s", type(exc).__name__)
        raise SearchError(
            "No se pudo conectar con iFixit. Comprueba tu conexion e intenta de nuevo."
        ) from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise SearchError("iFixit devolvio una respuesta con formato inesperado.")

    results = []
    for item in payload["results"]:
        normalized = normalize_result(item)
        if normalized is not None:
            results.append(normalized)

    return results


class RepairFinderHandler(BaseHTTPRequestHandler):
    server_version = "RepairFinder/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/search":
            self._search(parse_qs(parsed.query))
            return

        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        }
        file_entry = static_files.get(parsed.path)
        if file_entry is None:
            self._send_json(404, {"error": "No encontrado."})
            return

        filename, content_type = file_entry
        try:
            content = (STATIC_DIR / filename).read_bytes()
        except OSError:
            LOGGER.exception("Could not read static file %s", filename)
            self._send_json(500, {"error": "No se pudo cargar la interfaz."})
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def _search(self, query_values: dict[str, list[str]]) -> None:
        query = query_values.get("q", [""])[0].strip()
        if len(query) < 2:
            self._send_json(400, {"error": "Escribe al menos 2 caracteres para buscar."})
            return
        if len(query) > MAX_QUERY_LENGTH:
            self._send_json(
                400,
                {"error": f"La busqueda no puede superar {MAX_QUERY_LENGTH} caracteres."},
            )
            return

        try:
            results = search_ifixit(query)
        except SearchError as exc:
            self._send_json(502, {"error": str(exc)})
            return

        self._send_json(200, {"query": query, "results": results})

    def _send_json(self, status: int, payload: dict) -> None:
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format_string % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    server = ThreadingHTTPServer((HOST, PORT), RepairFinderHandler)
    print(f"Repair Finder esta disponible en http://{HOST}:{PORT}")
    print("Presiona Ctrl+C para detenerlo.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando Repair Finder...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
