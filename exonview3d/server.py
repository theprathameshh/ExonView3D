"""Local web server: JSON API plus the bundled Mol* viewer.

Uses only the standard library. By default it listens on the loopback
interface, so the viewer is reachable from this computer only.
"""

import json
import logging
import mimetypes
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import unquote, urlparse

from . import __version__
from .errors import ExonViewError

log = logging.getLogger("exonview3d.server")

ROUTE_GENE = re.compile(r"^/api/gene/([^/]+)/?$")
ROUTE_TRANSCRIPT = re.compile(r"^/api/gene/([^/]+)/transcript/([^/]+)/?$")
ROUTE_STRUCTURE = re.compile(
    r"^/api/gene/([^/]+)/transcript/([^/]+)/structure\.cif$"
)
ROUTE_ASSET = re.compile(r"^/assets/([A-Za-z0-9._-]+)$")

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


def _static_file(name):
    """Return the bytes of a bundled static file, or None."""

    try:
        return (
            resources.files("exonview3d")
            .joinpath("web", "static", name)
            .read_bytes()
        )
    except (FileNotFoundError, NotADirectoryError, OSError):
        return None


def make_handler(service):

    class Handler(BaseHTTPRequestHandler):

        server_version = f"ExonView3D/{__version__}"
        protocol_version = "HTTP/1.1"

        # -- helpers ---------------------------------------------------

        def log_message(self, fmt, *args):
            log.info("%s - %s", self.address_string(), fmt % args)

        def _send(self, status, body, content_type, extra=None):

            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-cache")

            for key, value in (extra or {}).items():
                self.send_header(key, value)

            self.end_headers()

            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, payload, status=200):
            body = json.dumps(payload).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _error(self, error):

            if isinstance(error, ExonViewError):
                self._json({"error": error.to_dict()}, error.http_status)
                return

            log.exception("Unhandled error")
            self._json(
                {
                    "error": {
                        "code": "internal_error",
                        "message": "An unexpected error occurred.",
                        "hint": "Run with --verbose for details.",
                    }
                },
                500,
            )

        # -- routing ---------------------------------------------------

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):

            path = urlparse(self.path).path

            try:
                self._route(path)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:  # noqa: BLE001 - reported as JSON
                self._error(error)

        def _route(self, path):

            if path in ("/", "/index.html"):

                body = _static_file("index.html")

                if body is None:
                    self._json(
                        {"error": {
                            "code": "missing_assets",
                            "message": "The bundled web interface is missing.",
                            "hint": "Reinstall ExonView3D.",
                        }},
                        500,
                    )
                    return

                self._send(200, body, "text/html; charset=utf-8")
                return

            match = ROUTE_ASSET.match(path)

            if match:

                name = match.group(1)
                body = _static_file(name)

                if body is None:
                    self._json(
                        {"error": {"code": "not_found",
                                   "message": "File not found."}},
                        404,
                    )
                    return

                content_type = (
                    mimetypes.guess_type(name)[0] or "application/octet-stream"
                )

                self._send(200, body, content_type)
                return

            if path == "/api/health":
                self._json({"status": "ok", "version": __version__})
                return

            match = ROUTE_STRUCTURE.match(path)

            if match:

                gene_id, transcript_id = map(unquote, match.groups())

                file_path = service.structure_file(gene_id, transcript_id)
                body = file_path.read_bytes()

                self._send(
                    200,
                    body,
                    "chemical/x-mmcif",
                    {"Content-Disposition":
                        f'inline; filename="{file_path.name}"'},
                )
                return

            match = ROUTE_TRANSCRIPT.match(path)

            if match:

                gene_id, transcript_id = map(unquote, match.groups())

                result = service.get_transcript(gene_id, transcript_id)

                if result["structure"]["status"] == "available":
                    result = {
                        **result,
                        "structure": {
                            **result["structure"],
                            "url": (
                                f"/api/gene/{result['gene']['gene_id']}"
                                f"/transcript/{transcript_id}/structure.cif"
                            ),
                        },
                    }

                self._json(result)
                return

            match = ROUTE_GENE.match(path)

            if match:
                self._json(service.search_gene(unquote(match.group(1))))
                return

            if path.startswith("/api/"):
                self._json(
                    {"error": {"code": "not_found",
                               "message": "Unknown API endpoint."}},
                    404,
                )
                return

            self._json(
                {"error": {"code": "not_found", "message": "Not found."}},
                404,
            )

        def _method_not_allowed(self):
            self._json(
                {"error": {"code": "method_not_allowed",
                           "message": "Only GET is supported."}},
                405,
            )

        do_POST = do_PUT = do_DELETE = do_PATCH = _method_not_allowed

    return Handler


class ViewerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(service, host="127.0.0.1", port=8765):
    """Create (but do not start) the viewer server."""

    return ViewerServer((host, port), make_handler(service))


def serve_in_thread(server):
    """Start a server in a daemon thread (used by tests)."""

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return thread
