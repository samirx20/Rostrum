"""A model download never leaves a half or wrong file under the real name: right hash installs; wrong hash, a cancel and a 404
leave nothing. Served from a local http.server thread."""
import hashlib
import http.server
import threading
from dataclasses import replace

import pytest
from rostrum_core import RostrumError

from rostrum_sound.cleanup import fetch, models

DATA = b"rostrum-model" * 200_000          # 2.6 MB: several chunks


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/m.onnx":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(DATA)))
        self.end_headers()
        self.wfile.write(DATA)

    def log_message(self, *_):
        pass


@pytest.fixture
def served(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_MODELS_DIR", str(tmp_path))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"
    yield lambda path="/m.onnx", **kw: replace(models.DFN3, id="fake", file="m.onnx", size=len(DATA), url=base + path,
                                                **{"sha256": hashlib.sha256(DATA).hexdigest(), **kw})
    srv.shutdown()


def _nothing_left(m):
    assert list(fetch.target(m).parent.glob("*")) == []


def test_right_hash_installs(served):
    m = served()
    assert fetch.missing(m)
    seen = []
    f = fetch.install(m, progress=lambda d, t: seen.append((d, t)))
    assert f.read_bytes() == DATA and not fetch.missing(m) and seen[-1] == (len(DATA), len(DATA))


def test_wrong_hash_is_refused(served):
    m = served(sha256="0" * 64)
    with pytest.raises(RostrumError, match="refused"):
        fetch.install(m)
    _nothing_left(m)


def test_cancel_leaves_nothing(served):
    m, stop = served(), threading.Event()
    with pytest.raises(RostrumError, match="cancelled"):
        fetch.install(m, progress=lambda d, t: stop.set(), cancel=stop)
    _nothing_left(m)


def test_404_says_not_available(served):
    m = served("/nope.onnx")
    with pytest.raises(RostrumError, match="not available for download yet"):
        fetch.install(m)
    _nothing_left(m)
