from http.client import HTTPConnection

from src.services.health_server import start_health_server


def test_health_server_returns_ok_for_root() -> None:
    server = start_health_server(host="127.0.0.1", port=0)
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request("GET", "/")
        response = connection.getresponse()

        assert response.status == 200
        assert response.read() == b"ok\n"
    finally:
        connection.close()
        server.shutdown()
        server.server_close()


def test_health_server_supports_head_requests() -> None:
    server = start_health_server(host="127.0.0.1", port=0)
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request("HEAD", "/")
        response = connection.getresponse()

        assert response.status == 200
        assert response.getheader("Content-Length") == "3"
        assert response.read() == b""
    finally:
        connection.close()
        server.shutdown()
        server.server_close()


def test_health_server_rejects_non_root_paths() -> None:
    server = start_health_server(host="127.0.0.1", port=0)
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        connection.request("GET", "/health")
        response = connection.getresponse()

        assert response.status == 404
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
