# Brief 22 walk (stylized blocks): tried by real input in the real window (a background window at 1646 x 900, never
# focused): real mouse and keys on visible controls found by objectName or their words; the document is only read, to
# CHECK. The paint21 case scene (case with its lid on a plinth, walls, key softbox + sky, shot "Hero 01"; the case's
# material "shell" plain). Then:
#   1. a click on the case (click 1), "Lines" in its material's row of names (click 2): shell.lines on ... "1-lines-two-clicks"
#   2. the Camera and look menu offers Stylized; picked by a click ....................... "2-stylized-view"
#      (+ the viewport's own picture: viewport-stylized.png)
#   3. "Light to colour" in the row of names: cel-shaded with lines ...................... "3-light-to-colour"
#   4. Lines' Width dragged by the mouse (20+ moves): GUI thread ms a move, move -> next picture shown in the window;
#      one undo step (Ctrl+Z puts the width back) ........................................ "4-width-dragged"
#   5. the render sheet (▾ beside Render): Quality Stylized, This frame, Render: render-stylized.png; video memory
#      ..................................................................................... "5-render-sheet"
#   6. Lines removed (its heading's −) on every material that has them: Stylized leaves the menu, the look is Quick
#      again with the note ................................................................. "6-back-to-quick"
# Then viewport-vs-render.png (the viewport picture cropped to the shot frame beside the render, labelled).
# Every check and the numbers go to stylized22_walk.json. The lead runs it:
#   heavy.ps1 run "sam: 3d-22 walk" gpu <venv python> apps\3d\tools\stylized22_walk.py <out folder>
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-22\walk")
sys.argv = sys.argv[:1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import clay_walk as W  # noqa: E402  (puts this checkout's code first; its real-input helpers)
import clay_paint_walk as CP  # noqa: E402
import paint21_walk as P21  # noqa: E402  (its scene and on_screen)

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402

REPORT = CP.REPORT
REPORT["clicks"] = {}
chk, step, settle, shot = CP.chk, CP.step, CP.settle, CP.shot
CLICKS = [0]


def click(win, item):
    """A real click on a visible control (counted)."""
    CLICKS[0] += 1
    W.click(win, item)


def wait_for(seconds, until) -> bool:
    """Pump events until `until()` holds (True) or `seconds` pass (False); a miss is counted by the caller, not a fail."""
    end = time.perf_counter() + seconds
    while not until():
        if time.perf_counter() > end:
            return False
        W.pump(0.001)
    return True


def visible(win, item) -> bool:
    if item is None or not item.isVisible():
        return False
    p = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    if not (0 <= p.x() < win.width() and 0 <= p.y() < win.height()):
        return False
    a = item.parentItem()               # inside every clipping ancestor (a scrolled panel hides what it scrolled away;
    while a is not None:                # a click there lands on whatever is drawn under it)
        if a.clip():
            q = a.mapFromScene(p)
            if not (0 <= q.x() < a.width() and 0 <= q.y() < a.height()):
                return False
        a = a.parentItem()
    return True


def wheel(win, at: QPoint, notches: int):
    """The mouse wheel over `at` (negative: scroll down), as the system sends it."""
    for _ in range(abs(notches)):
        delta = QPoint(0, 120 if notches > 0 else -120)
        ev = QWheelEvent(QPointF(at), QPointF(win.mapToGlobal(at)), QPoint(), delta, Qt.NoButton, Qt.NoModifier,
                         Qt.NoScrollPhase, False)
        QGuiApplication.sendEvent(win, ev)
        W.pump(0.05)


def reveal(win, find, what, tries=12):
    """The control `find()` gives, scrolled into the window by the wheel over the settings panel when it is below."""
    for _ in range(tries):
        it = find()
        if visible(win, it):
            return it
        if it is None:
            W.pump(0.3)
            continue
        p = it.mapToScene(QPointF(it.width() / 2, 0))
        x = min(max(p.x(), 0), win.width() - 4)
        wheel(win, QPoint(round(x), win.height() // 3), -2 if p.y() >= win.height() // 3 else 2)   # below the panel's middle: down
    # the wheel stopped short (kit ask, brief 22: the inspector's wheel stops before its content's end): note it, then
    # scroll the panel's own Flickable to the row so the walk's real clicks can go on
    it, sc = find(), W.find(win.contentItem(), "inspectorScroll")
    if it is not None and sc is not None:
        ci = sc.property("contentItem")
        y = it.mapToItem(ci, QPointF(0, 0)).y()
        REPORT.setdefault("wheelStoppedShort", []).append(
            {"what": what, "contentY": sc.property("contentY"), "contentHeight": sc.property("contentHeight"),
             "height": sc.height(), "rowAt": y})
        sc.setProperty("contentY", max(0.0, y + it.height() + 8 - sc.height()))
        W.pump(0.3)
        if visible(win, it):
            return it
    chk(False, f"{what} is on screen")
    return None


def by_name(win, name):
    return W.find(win.contentItem(), name)


def menu_entries(win, prefix="menu:look:"):
    out = []

    def walk(it):
        for c in it.childItems():
            if c.isVisible() and c.objectName().startswith(prefix):
                out.append(c.objectName()[len(prefix):])
            walk(c)
    walk(win.contentItem())
    return out


def open_look_menu(win):
    btn = by_name(win, "viewLook")
    chk(btn is not None, "the Camera and look button is on screen")
    if btn is not None:
        click(win, btn)
    W.pump(3, lambda: bool(menu_entries(win)), "the Camera and look menu")
    W.pump(0.3)
    return menu_entries(win)


def close_menu(win):
    QTest.keyClick(win, Qt.Key_Escape)
    W.pump(0.3)


def grab_rgb(win):
    from PIL import Image
    img = win.grabWindow()
    path = OUT / "_tmp.png"
    img.save(str(path))
    with Image.open(path) as im:
        return im.convert("RGB").copy()


def viewport_box(win, vp, img):
    """The viewport item's area in the grab's pixels."""
    k = img.width / win.width()
    a, b = vp.mapToScene(QPointF(0, 0)), vp.mapToScene(QPointF(vp.width(), vp.height()))
    return tuple(round(c * k) for c in (a.x(), a.y(), b.x(), b.y()))


def pct(xs, q):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2) if xs else None


def gpu_used_mb():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return int(out[0]) if out else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def side_by_side(view_png: Path, render_png: Path, frame_rect, dest: Path):
    """The viewport picture cropped to the shot frame (frameRect: parts of the viewport) and the render, the same height,
    labelled."""
    from PIL import Image, ImageDraw
    with Image.open(view_png) as v0, Image.open(render_png) as r0:
        v, r = v0.convert("RGB"), r0.convert("RGB")
    x, y, w, h = frame_rect
    v = v.crop((round(x * v.width), round(y * v.height), round((x + w) * v.width), round((y + h) * v.height)))
    H = 540
    v = v.resize((max(1, round(v.width * H / v.height)), H))
    r = r.resize((max(1, round(r.width * H / r.height)), H))
    pad, top = 16, 36
    out = Image.new("RGB", (v.width + r.width + 3 * pad, H + top + pad), (24, 24, 26))
    out.paste(v, (pad, top))
    out.paste(r, (2 * pad + v.width, top))
    d = ImageDraw.Draw(out)
    d.text((pad, 12), "Viewport · Look: Stylized (live, 1x)", fill=(230, 230, 230))
    d.text((2 * pad + v.width, 12), "Render · Quality: Stylized (2x supersampled)", fill=(230, 230, 230))
    out.save(dest)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    CP.OUT = OUT
    folder = Path(tempfile.mkdtemp(prefix="rostrum-stylized22walk-"))
    app = qt_app()  # noqa: F841
    doc = Document.new(KIND, folder=folder, item="scene")
    # the paint21 scene with a lighter case, so dark ink lines read against it
    # the paint21 scene with a lighter case turned 35° (two faces in different light), so the bands and the dark
    # ink lines read against it
    src = (P21.SCENE.replace('shell = material("shell", baseColor="#2c3a4a"', 'shell = material("shell", baseColor="#c8553d"')
           .replace('depth=0.16, y=0.04, material=shell)', 'depth=0.16, y=0.04, ry=35, material=shell)')
           .replace('depth=0.17, y=0.095, material=top)', 'depth=0.17, y=0.095, ry=35, material=top)'))
    assert src.count("ry=35") == 2, "the paint21 scene changed: update the walk's turn"
    doc.run_script("scene.py", run_source(src, "scene.py"))
    doc.save()
    screen = W.app3d.Screen(W.SIZE)
    vram = {"before": gpu_used_mb()}
    try:
        screen.show(doc, autosave=True)
        win, v, b = screen.win, screen.bridge.viewport, screen.bridge
        W.pump(90, screen.ready, "the first picture")
        vp = W.find(win.contentItem(), "viewport3d")
        D = b.doc
        settle(v, time.perf_counter(), what="the first settled picture")
        vram["appOpen"] = gpu_used_mb()
        last_vram = {}
        v._r.ready.connect(lambda *a: last_vram.update((a[4] or {}).get("vram") or {}))
        shown = []                                   # when the window's view put a new picture on screen
        if v.link is not None:
            v.link.shown.connect(lambda *_: shown.append(time.perf_counter()))
        else:
            v.serialChanged.connect(lambda: shown.append(time.perf_counter()))
        REPORT["inWindowView"] = v.link is not None
        chk(not v.canStylize and "stylized" not in open_look_menu(win), "no Stylized in the menu before any material has lines")
        close_menu(win)

        # 1. two clicks: the case, then Lines in its material's row of names
        step("1 lines in two clicks")
        QTest.keyClick(win, Qt.Key_V)
        W.pump(0.3)
        CLICKS[0] = 0
        # low on the front face: the selected lid's gizmo ring reaches over the case's middle
        at = P21.on_screen(screen, "case", vp, (0.06, -0.028, 0.08)).toPoint()
        CLICKS[0] += 1
        QTest.mouseMove(win, at)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(10, lambda: b.selected == "case", "the case selected by the click")
        chk(b.selected == "case", f"click 1 on the case selects it ({b.selected})")
        W.pump(0.5)
        shot(win, v, "1a-case-selected")
        name = reveal(win, lambda: by_name(win, "fold:Lines"), '"+ Lines" in the material\'s row of names')
        if name is not None:
            click(win, name)
        W.pump(5, lambda: D.item("shell").get("lines") is True, "shell.lines on")
        REPORT["clicks"]["lines"] = CLICKS[0]
        chk(D.item("shell").get("lines") is True, f"shell.lines is on in the document ({D.item('shell').get('lines')})")
        chk(CLICKS[0] == 2, f"two clicks were used ({CLICKS[0]})")
        chk(by_name(win, "row:linesWidth") is not None, "the Lines settings show (Width)")
        shot(win, v, "1-lines-two-clicks")

        # 2. Look: Stylized from the menu
        step("2 stylized view")
        entries = open_look_menu(win)
        REPORT["lookMenu"] = entries
        chk("stylized" in entries, f"the Camera and look menu offers Stylized ({entries})")
        entry = by_name(win, "menu:look:stylized")
        if entry is not None:
            t0 = time.perf_counter()
            click(win, entry)
            W.pump(10, lambda: v.look == "stylized", "Look: Stylized")
            REPORT["timesMs"]["stylized-first-picture-settled"] = round(settle(v, t0, what="the first stylized picture"))
        chk(v.look == "stylized", f"the view's look is Stylized ({v.look})")
        chk(not v.status.startswith("Error") and not b.status.startswith("Error"),
            f"no error after picking Stylized ({v.status or b.status or '-'})")
        shot(win, v, "2-stylized-view")
        img = grab_rgb(win)
        img.crop(viewport_box(win, vp, img)).save(OUT / "viewport-stylized.png")
        REPORT["pictures"]["viewport-stylized"] = str(OUT / "viewport-stylized.png")
        REPORT["frameRect"] = list(v.frameRect)
        REPORT["viewMode"] = v.mode

        # 3. Light to colour on
        step("3 light to colour")
        name = reveal(win, lambda: by_name(win, "fold:Light to colour"), '"+ Light to colour" in the row of names')
        if name is not None:
            click(win, name)
        if not wait_for(2, lambda: D.item("shell").get("lightToColor") is True):
            W.pump(0.5)                      # the names were still settling after Lines opened: once more
            name = reveal(win, lambda: by_name(win, "fold:Light to colour"), '"+ Light to colour" in the row of names')
            if name is not None:
                click(win, name)
        W.pump(5, lambda: D.item("shell").get("lightToColor") is True, "shell.lightToColor on")
        chk(D.item("shell").get("lightToColor") is True, "Light to colour is on for shell")
        shot(win, v, "3-light-to-colour")

        # 4. Lines' Width dragged by the mouse
        step("4 width drag")
        row = reveal(win, lambda: by_name(win, "row:linesWidth"), "Lines' Width")
        field = W.find(row, "grid:field") if row is not None else None
        chk(field is not None, "Width's number field is on screen")
        if field is not None:
            w0 = D.item("shell").get("linesWidth", 1.5)
            n0 = len(D.history.changes)
            start = field.mapToScene(QPointF(field.width() / 2, field.height() / 2)).toPoint()
            QTest.mouseMove(win, start)
            W.pump(0.2)
            QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, start)
            gui, to_pic, missed = [], [], 0
            for k in range(1, 31):
                n_shown = len(shown)
                c0 = W.gui_cycles_ms()
                t0 = time.perf_counter()
                QTest.mouseMove(win, QPoint(start.x() + 4 * k, start.y()))
                W.pump(0)
                gui.append(W.gui_cycles_ms() - c0)
                if wait_for(0.5, lambda: len(shown) > n_shown):
                    to_pic.append((shown[n_shown] - t0) * 1000)
                else:
                    missed += 1
                W.pump(0.012)
            mid_doc = D.item("shell").get("linesWidth", 1.5)
            mid_changes = len(D.history.changes)
            QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, QPoint(start.x() + 120, start.y()))
            W.pump(5, lambda: len(D.history.changes) > n0, "the drag's one change")
            w1 = D.item("shell").get("linesWidth", 1.5)
            REPORT["widthDrag"] = {
                "moves": len(gui), "from": w0, "to": w1, "picturesMissed": missed,
                "guiMs": {"median": pct(gui, 0.5), "p95": pct(gui, 0.95), "max": pct(gui, 1.0)},
                "moveToPictureMs": {"median": pct(to_pic, 0.5), "p95": pct(to_pic, 0.95), "max": pct(to_pic, 1.0)},
                "guiMsInOrder": [round(x, 2) for x in gui], "moveToPictureMsInOrder": [round(x, 1) for x in to_pic]}
            chk(len(gui) >= 20, f"20+ pointer moves ({len(gui)})")
            chk(mid_doc == w0 and mid_changes == n0, f"the document stands still during the drag ({w0} -> {mid_doc})")
            chk(w1 != w0 and len(D.history.changes) == n0 + 1, f"one change at the release ({w0} -> {w1}, {n0} -> {len(D.history.changes)})")
            chk(missed == 0, f"every move was followed by a new picture in the view ({missed} missed)")
            chk(pct(gui, 0.95) is not None and pct(gui, 0.95) < 16.0, f"GUI thread within 16 ms a move (p95 {pct(gui, 0.95)} ms)")
            chk(pct(to_pic, 0.5) is not None and pct(to_pic, 0.5) < 33.0, f"move -> picture median under 33 ms ({pct(to_pic, 0.5)} ms)")
            shot(win, v, "4-width-dragged")
            QTest.mouseMove(win, QPoint(8, 8))
            QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
            W.pump(5, lambda: D.item("shell").get("linesWidth", 1.5) == w0, "Ctrl+Z to put the width back")
            chk(D.item("shell").get("linesWidth", 1.5) == w0, f"Ctrl+Z puts the width back ({D.item('shell').get('linesWidth', 1.5)})")
            chk(D.item("shell").get("lines") is True, "Ctrl+Z took back only the drag (Lines still on)")
            QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)     # redo: the dragged width again,
            W.pump(5, lambda: D.item("shell").get("linesWidth", 1.5) != w0, "redo of the drag")   # for the pictures
            REPORT["widthAfterRedo"] = D.item("shell").get("linesWidth")
        vram["viewStylized"] = gpu_used_mb()
        REPORT["viewVram"] = dict(last_vram)

        # 5. a Stylized render of this frame through the render sheet
        step("5 render sheet")
        # the viewport as it stands now (Lines + Light to colour), nothing selected (no gizmo), for the side by side
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(5, lambda: b.selected == "", "nothing selected")
        W.pump(1.0)
        img = grab_rgb(win)
        img.crop(viewport_box(win, vp, img)).save(OUT / "viewport-stylized.png")
        at = P21.on_screen(screen, "case", vp, (0.06, -0.028, 0.08)).toPoint()   # the case selected again (step 6)
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
        W.pump(5, lambda: b.selected == "case", "the case selected again")
        more = by_name(win, "renderMore")
        chk(visible(win, more), "the ▾ beside Render is on screen")
        if more is not None:
            click(win, more)
        ex = b.exporter
        W.pump(5, lambda: ex.open, "the render sheet")
        W.pump(0.5)
        quality = by_name(win, "sheetQuality")
        word = CP.find_text(quality, "Stylized") if quality is not None else None
        chk(word is not None, "the sheet's Quality offers Stylized")
        if word is not None:
            click(win, word)
        W.pump(5, lambda: ex.quality == "stylized", "Quality Stylized")
        chk(ex.quality == "stylized", f"Quality is Stylized ({ex.quality}; {ex.qualityText})")
        if ex._choice != "frame":
            w = CP.find_text(win.contentItem(), "This frame")
            if w is not None:
                click(win, w)
        chk(ex._choice == "frame", f"This frame is picked ({ex._choice})")
        go = CP.find_text(win.contentItem(), "Render this frame")
        chk(go is not None, "the sheet's Render this frame button is on screen")
        t0 = time.perf_counter()
        if go is not None:
            click(win, go)
        W.pump(5, lambda: ex.state == "running" or ex.state in ("done", "failed"), "the render to start")
        W.pump(300, lambda: ex.state in ("done", "failed", "cancelled"), "the stylized render")
        REPORT["timesMs"]["stylized-render"] = round((time.perf_counter() - t0) * 1000)
        chk(ex.state == "done", f"the render finished ({ex.state}: {ex.note})")
        files = [Path(f) for f in ex._result.get("files", [])]
        png = next((f for f in files if f.suffix == ".png"), None)
        if png is not None and png.is_file():
            shutil.copyfile(png, OUT / "render-stylized.png")
            REPORT["pictures"]["render-stylized"] = str(OUT / "render-stylized.png")
            man = png.parent / "manifest.json"
            if man.is_file():
                eng = json.loads(man.read_text(encoding="utf-8")).get("engine", "")
                REPORT["renderEngine"] = eng
                chk("stylized" in eng, f"the render's manifest says the stylized renderer ({eng})")
        chk(png is not None and png.is_file(), f"the render wrote a PNG ({png})")
        shot(win, v, "5-render-sheet")
        QTest.keyClick(win, Qt.Key_Escape)
        W.pump(2, lambda: not ex.open, "the sheet to close")
        vram["afterRender"] = gpu_used_mb()

        # 6. Lines off on every material that has them: Stylized leaves, Quick again with the note
        step("6 back to quick")
        for m in D.data.get("materials", []):
            if not (m.get("lines") or m.get("halftone")):
                continue
            user = next((i["id"] for i in D.items() if i.get("material") == m["id"]), None)
            chk(user is not None, f"{m['id']} is used by an item (to reach its rows)")
            if user is None:
                continue
            if b.selected != user:
                row = CP.find_text(win.contentItem(), next((i.get("name") or i["id"] for i in D.items() if i["id"] == user)))
                if row is not None:
                    click(win, row)
                W.pump(3, lambda: b.selected == user, f"{user} selected")
            for group, field in (("Lines", "lines"), ("Halftone", "halftone")):
                if D.item(m["id"]).get(field):
                    for _ in range(2):           # once more if the first click came while the rows were moving
                        rm = reveal(win, lambda: by_name(win, f"remove:{group}"), f"{group}'s remove control")
                        if rm is not None:
                            click(win, rm)
                        if wait_for(3, lambda: not D.item(m["id"]).get(field)):
                            break
                        W.pump(0.5)
        W.pump(5, lambda: v.look == "quick", "the look back to Quick")
        chk(not any(m.get("lines") or m.get("halftone") for m in D.data.get("materials", [])), "no material has Lines or Halftone")
        chk(v.look == "quick", f"the look fell back to Quick ({v.look})")
        note = b.status
        REPORT["fallbackNote"] = note
        chk("Quick" in note and "Lines" in note, f"the status line says why ({note!r})")
        entries = open_look_menu(win)
        chk("stylized" not in entries, f"Stylized left the menu ({entries})")
        close_menu(win)
        shot(win, v, "6-back-to-quick")

        if (OUT / "render-stylized.png").is_file():
            side_by_side(OUT / "viewport-stylized.png", OUT / "render-stylized.png",
                         REPORT["frameRect"] if REPORT.get("viewMode") == "shot" else [0, 0, 1, 1], OUT / "viewport-vs-render.png")
            REPORT["pictures"]["viewport-vs-render"] = str(OUT / "viewport-vs-render.png")
    finally:
        vram["end"] = gpu_used_mb()
        REPORT["gpuUsedMb"] = vram
        (OUT / "_tmp.png").unlink(missing_ok=True)
        REPORT["fails"] = list(W.FAILS)
        (OUT / "stylized22_walk.json").write_text(json.dumps(REPORT, indent=2), encoding="utf-8")
        screen.close() if hasattr(screen, "close") else None
    print("FAILS:" if W.FAILS else "ALL PASSED", *W.FAILS, sep="\n  ")
    sys.exit(1 if W.FAILS else 0)


if __name__ == "__main__":
    main()
