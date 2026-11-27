"""A small web server for this computer and its network: it hands out a page and answers with data.

It knows nothing about tickets; whoever starts it says what the data is.
"""

from __future__ import annotations

import hmac
import json
import socket
import socketserver
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

_PARTS = Path(__file__).with_name("pages")
_KINDS = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
_DATA = "application/json"


_ONE_AT_A_TIME = threading.Lock()
_NO_KEY = "this needs the key `dk web` showed when it started: open the address it gave with it"


class _Answers(BaseHTTPRequestHandler):
    data: Callable[[str], object]  # given by `serve`, as are the next two
    change: Callable[[object], str]
    key: str

    def do_POST(self) -> None:
        """Carry out what is asked, for whoever has the key; what cannot be done is said."""
        if urlsplit(self.path).path != "/api/order":
            return self._send(404, "text/plain", b"there is no such page")
        if not hmac.compare_digest(self.headers.get("X-Key", "").encode(), self.key.encode()):
            return self._say(403, {"error": _NO_KEY})
        try:
            asked = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            with _ONE_AT_A_TIME:
                self._say(200, {"said": type(self).change(asked)})
        except (LookupError, ValueError) as error:
            self._say(400, {"error": str(error)})

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            return self._data(unquote(path.removeprefix("/api/")))
        parts = {part.name: part for part in _PARTS.iterdir()}
        part = parts.get(path.removeprefix("/") or "index.html")
        if part is None:
            return self._send(404, "text/plain", b"there is no such page")
        self._send(200, _KINDS[part.suffix], part.read_bytes())

    def _data(self, what: str) -> None:
        try:
            self._say(200, type(self).data(what))
        except LookupError as error:
            self._say(404, {"error": str(error)})

    def _say(self, status: int, what: object) -> None:
        self._send(status, _DATA, json.dumps(what).encode())

    def _send(self, status: int, kind: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return  # every look of the page would otherwise fill the terminal


def _reached() -> str:
    """The address by which other computers of the network reach this one; its own, if none."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))  # sends nothing; the system says which it would use
        except OSError:
            return "127.0.0.1"
        return str(probe.getsockname()[0])


class _Server(ThreadingHTTPServer):
    def server_bind(self) -> None:
        """Start without asking the network for this computer's name, which nothing here
        uses: on one computer that took five seconds every time `dk web` started."""
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "", self.server_address[1]


def serve(
    port: int,
    data: Callable[[str], object],
    started: Callable[[str], object],
    change: Callable[[object], str],
    key: str,
) -> None:
    """Answer browsers on this computer and its network until interrupted. `/api/<what>` is
    answered with `data(what)`, which raises LookupError for what is not there; anything else
    is one of the page's own files. `started` is told the address; port 0 takes any free one.
    What is sent to `/api/order` with `key` is given to `change`, one at a time; it returns
    what to say, or raises LookupError for what cannot be done."""
    given = {"data": staticmethod(data), "change": staticmethod(change), "key": key}
    answers = type("Answers", (_Answers,), given)
    with _Server(("0.0.0.0", port), answers) as server:
        started(f"http://{_reached()}:{server.server_port}/")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return
