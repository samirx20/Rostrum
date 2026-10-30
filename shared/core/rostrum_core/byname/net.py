"""One HTTPS GET for the by-name parts, checked against the computer's own certificates (truststore, MIT) where it is
installed, else certifi's, else Python's: the bundled Python alone can't verify GitHub's certificate on Windows.
No network, a timeout or a refusal raises OSError with one plain line."""
from __future__ import annotations

import socket
import ssl
import urllib.error
import urllib.request
from functools import lru_cache

TIMEOUT_S = 30


@lru_cache(maxsize=1)
def _context() -> ssl.SSLContext:
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        pass
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Rostrum"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S, context=_context()) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise OSError(f"{url} answered {e.code} ({e.reason})") from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
        raise OSError(f"could not reach {urllib.request.urlparse(url).netloc}: {getattr(e, 'reason', e)}") from None
