"""The canvas pointer set on one picture (CURSORS.md): every shape, every badge, resize / rotate at 0, 20, 45 and 135°,
each at 1x, 1.5x and 2x true size plus a 3x close-up of the 2x drawing (hotspot pixel boxed in red), on a light and a
dark background.

    python shared/gui-kit/demo/cursor_sheet.py [out.png]     (offscreen; default waves/results/ix-pkgA/cursor-sheet.png)
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QPA_FONTDIR", "C:/Windows/Fonts")
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import checkout_paths  # noqa: E402

checkout_paths.use_this_checkout()

from PySide6.QtCore import QPoint, QRect, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen  # noqa: E402

from rostrum_gui.cursors import BADGES, KINDS, picture  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\ix-pkgA\cursor-sheet.png")
CELL_W, CELL_H, COLS, ZOOM = 190, 280, 8, 3
PEN_BADGES = ("copy", "remove", "close", "x", "caret", "slash")


def cells():
    out = [(k, 0, "", k) for k in KINDS if KINDS[k] is not None]
    out += [("pick", 0, b, f"pick+{b}") for b in BADGES if b not in ("centre",) and b not in PEN_BADGES[3:]]
    out += [("pen", 0, b, f"pen+{b}") for b in PEN_BADGES]
    out += [("text", 0, "wrap", "text+wrap"), ("resize", 0, "centre", "resize+centre (Alt)")]
    out += [(k, a, "", f"{k}@{a}°") for k in ("resize", "rotate") for a in (0, 20, 45, 135)]
    return out


def panel(p, top, bg, fg, items):
    rows = (len(items) + COLS - 1) // COLS
    p.fillRect(QRect(0, top, COLS * CELL_W, rows * CELL_H + 40), QColor(bg))
    p.setPen(QColor(fg))
    p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
    p.drawText(16, top + 26, f"Canvas pointers on {'light' if bg > '#8' else 'dark'} · true size 1x / 1.5x / 2x · "
                             f"close-up: 2x drawing at {ZOOM}x, red box = hotspot pixel")
    p.setFont(QFont("Segoe UI", 9))
    for i, (kind, angle, badge, label) in enumerate(items):
        x, y = (i % COLS) * CELL_W, top + 40 + (i // COLS) * CELL_H
        img, hot = picture(kind, angle, badge, 2.0)
        big = img.scaled(img.width() * ZOOM, img.height() * ZOOM)          # nearest pixel: the real pixels, larger
        bx, by = x + (CELL_W - big.width()) // 2, y + 6
        p.drawImage(bx, by, big)
        p.setPen(QPen(QColor("#ff2020"), 1))
        p.drawRect(bx + hot.x() * ZOOM, by + hot.y() * ZOOM, ZOOM - 1, ZOOM - 1)
        cx = x + 14
        for s in (1.0, 1.5, 2.0):
            im, h = picture(kind, angle, badge, s)
            p.drawImage(cx, y + 226 - im.height() // 2, im)
            cx += im.width() + 12
        p.setPen(QColor(fg))
        p.drawText(QRect(x, y + CELL_H - 30, CELL_W, 20), Qt.AlignmentFlag.AlignHCenter, label)
    return rows * CELL_H + 40


def main():
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    items = cells()
    rows = (len(items) + COLS - 1) // COLS
    h = rows * CELL_H + 40
    sheet = QImage(COLS * CELL_W, 2 * h, QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(sheet)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    panel(p, 0, "#ededed", "#202020", items)
    panel(p, h, "#1c1c1c", "#e0e0e0", items)
    p.end()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not sheet.save(str(OUT)):
        raise SystemExit(f"could not write {OUT}")
    print(OUT, f"{len(items)} pointers")


if __name__ == "__main__":
    main()
