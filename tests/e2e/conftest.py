from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn

from csm_dashboard.storage.memory import MemoryStore
from csm_dashboard.storage.repo import CsmRepo
from csm_dashboard.web.app import create_app


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="session")
def live_server():
    repo = CsmRepo(MemoryStore())
    app = create_app(repo=repo)
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(80):
        if getattr(server, "started", False):
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("desk server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
