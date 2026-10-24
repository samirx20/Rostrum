"""A saved pose's small picture: the viewport's own picture at the moment it was saved, shrunk, kept in the shared cache
(`<cache>/3d/poses/<key>.png`, trimmed to the newest CAP) and never in the document. The key names the project, the
document and the pose, so a pose in another project never shows this one's picture. A pose saved by an agent has no
picture (nothing was on screen): its row simply shows none. Poses (poses_qt.py) saves and reads them.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QImage
from rostrum_core.cache import default_root, put_file

WIDTH, HEIGHT, CAP = 144, 81, 300           # pixels (shown at half: sharp on a busy screen); files kept


def folder() -> Path:
    return default_root() / "3d" / "poses"


def _path(doc, pose_id: str) -> Path:
    key = hashlib.sha256(f"{doc.folder}|{doc.data.get('id', '')}|{pose_id}".encode("utf-8")).hexdigest()[:24]
    return folder() / f"{key}.png"


def save(doc, pose_id: str, picture: QImage) -> None:
    """Keep `picture` (the viewport's, any size) as the pose's thumbnail; an empty picture keeps nothing."""
    if picture.isNull():
        return
    small = picture.scaled(WIDTH, HEIGHT, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
    small = small.copy((small.width() - WIDTH) // 2, (small.height() - HEIGHT) // 2, WIDTH, HEIGHT)
    out = _path(doc, pose_id)
    out.unlink(missing_ok=True)             # the same pose id saved again (undo, then save): the new picture
    put_file(out, lambda tmp: small.save(str(tmp), "PNG"), "pose picture")
    files = sorted(folder().glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[CAP:]:
        old.unlink(missing_ok=True)


def url(doc, pose_id: str) -> str:
    """The thumbnail's file URL for QML, "" when there is none."""
    p = _path(doc, pose_id)
    return QUrl.fromLocalFile(str(p)).toString() if p.is_file() else ""
