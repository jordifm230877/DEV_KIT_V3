"""A small web server for this computer only: it hands out a page and answers with data.

It knows nothing about tickets; whoever starts it says what the data is.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

_PARTS = Path(__file__).with_name("pages")
_KINDS = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
_DATA = "application/json"


class _Answers(BaseHTTPRequestHandler):
    data: Callable[[str], object]  # given by `serve`

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            return self._data(path.removeprefix("/api/"))
        parts = {part.name: part for part in _PARTS.iterdir()}
        part = parts.get(path.removeprefix("/") or "index.html")
        if part is None:
            return self._send(404, "text/plain", b"there is no such page")
        self._send(200, _KINDS[part.suffix], part.read_bytes())

    def _data(self, what: str) -> None:
        try:
            self._send(200, _DATA, json.dumps(type(self).data(what)).encode())
        except LookupError as error:
            self._send(404, _DATA, json.dumps({"error": str(error)}).encode())

    def _send(self, status: int, kind: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return  # every look of the page would otherwise fill the terminal


def serve(port: int, data: Callable[[str], object], started: Callable[[str], object]) -> None:
    """Answer browsers on this computer until interrupted. `/api/<what>` is answered with
    `data(what)`, which raises LookupError for what is not there; anything else is one of
    the page's own files. `started` is told the address; port 0 takes any free one."""
    answers = type("Answers", (_Answers,), {"data": staticmethod(data)})
    with ThreadingHTTPServer(("127.0.0.1", port), answers) as server:
        started(f"http://127.0.0.1:{server.server_port}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return
