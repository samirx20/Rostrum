"""Pictures made with Qt (PySide6, no extra dependency): scaling a frame and the labelled contact sheet."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from rostrum_core.errors import RostrumError, codes

LABEL_H, GAP, MARGIN = 26, 8, 10
BACK, TEXT = "#16171b", "#e8e8ec"


def _qt():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")      # Windows and Mac draw text headless on their own platform
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter
    from PySide6.QtCore import QRect, Qt
    if QGuiApplication.instance() is None:
        global _app
        _app = QGuiApplication([])
    return QColor, QFont, QImage, QPainter, QRect, Qt


def load(path: Path):
    _, _, QImage, *_ = _qt()
    img = QImage(str(path))
    if img.isNull():
        raise RostrumError(codes.RENDER_FAILED, "look", str(path), "was drawn but cannot be read back as a picture")
    return img


def scaled_copy(src: Path, width: int, dest: Path) -> tuple[int, int]:
    """Write `src` at `width` (never enlarged) to `dest`; returns the size written."""
    _, _, _, _, _, Qt = _qt()
    img = load(src)
    if width < img.width():
        img = img.scaledToWidth(width, Qt.SmoothTransformation)
    img.save(str(dest), "PNG")
    return img.width(), img.height()


def contact_sheet(tiles: list[tuple[Path, str]], tile_w: int, cols: int, dest: Path) -> tuple[int, int]:
    """A grid of (png, label) tiles, each tile labelled underneath; written to `dest`."""
    QColor, QFont, QImage, QPainter, QRect, Qt = _qt()
    first = load(tiles[0][0])
    tile_h = round(tile_w * first.height() / first.width())
    cols = max(1, min(cols, len(tiles)))
    rows = -(-len(tiles) // cols)
    W = MARGIN * 2 + cols * tile_w + (cols - 1) * GAP
    H = MARGIN * 2 + rows * (tile_h + LABEL_H) + (rows - 1) * GAP
    sheet = QImage(W, H, QImage.Format_RGB32)
    sheet.fill(QColor(BACK))
    p = QPainter(sheet)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    font = QFont("Segoe UI")
    font.setPixelSize(max(12, LABEL_H - 10))
    p.setFont(font)
    p.setPen(QColor(TEXT))
    for i, (png, label) in enumerate(tiles):
        x, y = MARGIN + (i % cols) * (tile_w + GAP), MARGIN + (i // cols) * (tile_h + LABEL_H + GAP)
        p.drawImage(QRect(x, y, tile_w, tile_h), load(png))
        p.drawText(QRect(x, y + tile_h, tile_w, LABEL_H), Qt.AlignLeft | Qt.AlignVCenter, label)
    p.end()
    if not sheet.save(str(dest), "PNG"):
        raise RostrumError(codes.RENDER_FAILED, "look_sheet", str(dest), "the sheet could not be saved")
    return W, H
