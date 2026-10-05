from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from src.utils.logger import get_logger

logger = get_logger("app")

HEALTH_HOST = "0.0.0.0"
HEALTH_PORT = 8000


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return

        response = b"ok\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def do_HEAD(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "3")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def start_health_server() -> ThreadingHTTPServer:
    """Start the health endpoint without blocking Telegram polling."""
    server = ThreadingHTTPServer((HEALTH_HOST, HEALTH_PORT), _HealthHandler)
    Thread(target=server.serve_forever, name="health-server", daemon=True).start()
    logger.info("Health server listening on %s:%d.", HEALTH_HOST, HEALTH_PORT)
    return server
