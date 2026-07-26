import os
import socket

from webapp.server import create_app


def find_free_port(start: int = 8501, end: int = 8600) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{end}")


def _install_dir() -> str:
    install_dir = os.environ.get("USPEX_INSTALL_DIR", "").strip()
    if install_dir:
        return install_dir
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return os.path.join(appdata, "USPEX Runner")
    return "."


def write_port_file(port: int) -> None:
    d = _install_dir()
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, ".port"), "w") as f:
        f.write(str(port))


def main() -> None:
    flask_port = os.environ.get("FLASK_PORT", "").strip()
    if flask_port:
        port = int(flask_port)
    else:
        port = find_free_port()
    write_port_file(port)
    app = create_app()
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
