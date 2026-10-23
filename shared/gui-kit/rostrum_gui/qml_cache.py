"""Each app's own compiled-QML cache, kept small (H65).

Qt keeps compiled QML in <cache folder>/qmlcache, named after the application. Unnamed, every app (and every checkout)
shared "%LOCALAPPDATA%/python/cache/qmlcache", which only ever grew (78 MB, 4,612 files, S59). `name_app` gives the
app its own name, so its own folder; `trim` deletes the least recently written entries past CAP_MB. An entry deleted
by mistake costs only one recompile of that file at the next start."""
from __future__ import annotations

import threading
from pathlib import Path

ORG = "Rostrum"
CAP_MB = 40          # one app on one checkout needs ~10 MB; a few checkouts' versions fit
KEEP_MB = 25         # trimmed down to this, so a trim is rare


def name_app(app, name: str) -> Path:
    """Name the Qt app (before its first QML engine) and trim its cache in the background. Returns the folder."""
    from PySide6.QtCore import QStandardPaths
    app.setOrganizationName(ORG)
    app.setApplicationName(name)
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation)) / "qmlcache"
    threading.Thread(target=trim, args=(folder,), name="qmlcache-trim", daemon=True).start()
    return folder


def trim(folder: Path, cap_mb: float = CAP_MB, keep_mb: float = KEEP_MB) -> int:
    """Delete the oldest entries while the folder is over `cap_mb`, down to `keep_mb`. Returns how many went."""
    try:
        files = [(f.stat(), f) for f in folder.iterdir() if f.is_file()]
    except FileNotFoundError:
        return 0
    total = sum(st.st_size for st, _ in files)
    if total <= cap_mb * 2**20:
        return 0
    gone = 0
    for st, f in sorted(files, key=lambda x: x[0].st_mtime):
        if total <= keep_mb * 2**20:
            break
        try:
            f.unlink()
        except OSError:              # in use by another running app: it stays, the next trim tries again
            continue
        total -= st.st_size
        gone += 1
    return gone
