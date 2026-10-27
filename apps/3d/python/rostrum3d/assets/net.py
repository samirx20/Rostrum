"""The asset library's one way onto the network (the standard library's urllib, nothing else). Every request names
its source and is refused before it starts while that source is off, so an off source can't reach a site through
any path. Failures say plainly what failed: no network, a timeout, or what the site answered.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "Rostrum3D/0.1 (asset library)"
TIMEOUT_S = 20
CHUNK = 64 * 1024


class AssetError(Exception):
    """A plain sentence for the sheet's line and the agent's error. `off`: the source is switched off."""

    def __init__(self, line: str, off: bool = False):
        super().__init__(line)
        self.off = off


def _open(source_id: str, url: str):
    from .settings import require_on      # (late: settings imports AssetError from here)
    require_on(source_id)
    host = urllib.parse.urlsplit(url).netloc
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(request, timeout=TIMEOUT_S)
    except urllib.error.HTTPError as e:
        raise AssetError(f"{host} said {e.code} ({e.reason}) for {url}") from None
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise AssetError(f"{host} did not answer within {TIMEOUT_S} s") from None
        raise AssetError(f"could not reach {host} (no network?): {reason}") from None
    except (socket.timeout, TimeoutError):
        raise AssetError(f"{host} did not answer within {TIMEOUT_S} s") from None


def get_json(source_id: str, url: str):
    with _open(source_id, url) as r:
        body = r.read()
    try:
        return json.loads(body)
    except ValueError:
        raise AssetError(f"{urllib.parse.urlsplit(url).netloc} sent something that is not a list of models ({url})") from None


def get_bytes(source_id: str, url: str) -> bytes:
    with _open(source_id, url) as r:
        return r.read()


def download(source_id: str, url: str, dest: Path, progress=None) -> int:
    """Write `url` to `dest` (through `<dest>.partial`, so a cut download never looks whole); progress(bytes) as it
    comes. The bytes written."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".partial")
    done = 0
    try:
        with _open(source_id, url) as r, open(part, "wb") as out:
            while chunk := r.read(CHUNK):
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(len(chunk))
    except (OSError, socket.timeout) as e:
        part.unlink(missing_ok=True)
        raise AssetError(f"the download of {url} stopped after {done // 1024} KB: {e}") from None
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    part.replace(dest)
    return done
