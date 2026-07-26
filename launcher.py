import threading
import time
import webbrowser
from wsgiref.simple_server import make_server

from webapp.server import create_app


def _serve(host: str, port: int, ready: threading.Event) -> None:
    app = create_app()
    with make_server(host, port, app) as httpd:
        ready.set()
        httpd.serve_forever()


def _pick_port(host: str, start: int = 8501, end: int = 8520) -> int:
    import socket

    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex((host, port)) != 0:
                return port
    raise RuntimeError("No free port in range 8501-8520.")


def main() -> None:
    host = "127.0.0.1"
    port = _pick_port(host)
    ready = threading.Event()
    t = threading.Thread(target=_serve, args=(host, port, ready), daemon=False)
    t.start()
    if ready.wait(timeout=5.0):
        time.sleep(0.2)
        webbrowser.open(f"http://{host}:{port}", new=2)
    t.join()


if __name__ == "__main__":
    main()
