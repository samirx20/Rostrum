# Clay walk (CL1, CL2): the Clay tool tried by real input in the real window (behind the person's work, never focused).
# A scratch project with the sample scene; Q (the real key); a Lump click on the ground (a real click) makes a clay;
# then real drags across it: each of the six brushes that shape, its tile clicked (Add, Carve, Smooth, Pull, Flatten,
# Crease); Ctrl on Add (carves), Shift (smooths), Ctrl on Flatten (puffs out: the step keeps `invert`); a Mask stroke
# down the clay's left side and an Add across it (the masked band must not change in the picture, the free middle
# must, and the same Add with no mask changes the band: difference pictures show it); the pointer resting on the clay
# shows the ring, and F held with the pointer moved right (the ring grows live, nothing is kept until F comes up, then
# the new size is one undo step). (F typed in a text box still typing an F is a person's check: a window behind the
# person's work never gets the keyboard focus, so its text boxes get no keys.) Each pointer move is timed: the GUI
# thread's processor time for the move (cpu
# ms), the wait until the engine answered its dab (wall ms, and the engine's own ms), and the engine process's processor
# time over the dab. Each stroke must be
# exactly one undo step: one new step on the clay, gone after Ctrl+Z, back after Ctrl+Shift+Z. Pictures after each
# stroke and the numbers (clay_walk.json) go to the out folder. Needs the core built with clay; the lead runs it:
#   heavy.ps1 run "priyam: clay walk" gpu <venv python> apps\3d\tools\clay_walk.py [out folder]
# Exit 0 = every check passed; else the failed checks are printed and it exits 1.
import ctypes as ct
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("ROSTRUM_BACKGROUND_WINDOWS", "1")
APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
import main as app3d  # noqa: E402  (puts this checkout's code first)
from screen3d import clay_ring as R  # noqa: E402

from PySide6.QtCore import QCoreApplication, QPoint, QPointF, QRect, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QPainter, QPen  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from rostrum_core import Document  # noqa: E402
from rostrum3d import KIND  # noqa: E402
from rostrum3d.script import run_source  # noqa: E402
from rostrum_gui.app import qt_app  # noqa: E402
from screen3d.gizmo import View  # noqa: E402
from screen3d.sample import SOURCE  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Sam\.rostrum\waves\results\3d-cl2")
SIZE, BUDGET_MS = (1646, 900), 16.0
SEEN = 0.03                     # a picture box counts as changed with this share of its pixels changed
K32 = ct.windll.kernel32
K32.GetCurrentThread.restype = ct.c_void_p
K32.OpenProcess.restype = ct.c_void_p
FAILS: list[str] = []


def gui_cycles_ms():
    """This (GUI) thread's processor time so far in ms, from its cycle count at a nominal 1 GHz (QueryThreadCycleTime,
    as sound-fix-r9's drive.py: exact, unlike the 15.6 ms clock)."""
    c = ct.c_ulonglong()
    K32.QueryThreadCycleTime(ct.c_void_p(K32.GetCurrentThread()), ct.byref(c))
    return c.value / 1e6


def proc_cpu_ms(handle):
    """A process's user + kernel time so far, ms (GetProcessTimes, 100 ns units)."""
    t = [ct.c_ulonglong() for _ in range(4)]
    K32.GetProcessTimes(ct.c_void_p(handle), *(ct.byref(x) for x in t))
    return (t[2].value + t[3].value) / 1e4


def pump(seconds=0.0, until=None, what=""):
    end = time.perf_counter() + seconds
    while True:
        QCoreApplication.processEvents()
        if until is not None and until():
            return True
        if time.perf_counter() > end:
            if until is not None:
                FAILS.append(f"timed out waiting for {what}")
            return until is None
        time.sleep(0.002)


def clay_info(v, clay_id):
    """The live clay's clay_info (ENGINE_CONTRACT): from the window's own view when it draws one (it answers on this
    thread, so it is pumped for, never waited on), else from the viewport's engine."""
    if v.link is None:
        return clay_info(v, clay_id)
    box = []
    v.link.post({"clay_info": {"item": clay_id}}, box.append)
    pump(60, lambda: box, "the clay's info")
    if isinstance(box[0], str):
        raise RuntimeError(box[0])
    return box[0]


def core_pid(v, scene):
    """The process doing the live view's work: this one when the window draws it, else the engine program."""
    if v.link is not None:
        return os.getpid()
    return core_pid(v, scene)


def check(ok, line):
    print(("ok   " if ok else "FAIL ") + line)
    if not ok:
        FAILS.append(line)


def find(item, name):
    """The drawn item named `name` (objectName), through the visible tree."""
    if item.objectName() == name and item.isVisible():
        return item
    for c in item.childItems():
        hit = find(c, name)
        if hit is not None:
            return hit
    return None


def centre(item):
    p = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    return QPoint(round(p.x()), round(p.y()))


def click(win, item):
    at = centre(item)
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    pump(0.2)


def clay_on_screen(screen, clay_id, vp_item):
    """The window point of the clay's middle, and its radius in window px (to size the drags)."""
    v, frame = screen.bridge.viewport, screen.bridge.frame
    scene, cam = v.sent()
    view = View.of(cam, scene, frame, cam["width"], cam["height"])
    from rostrum3d import aim, through
    world = through.find_item(scene, clay_id, frame)[0]
    mid = aim.point(world, [0.0, 0.0, 0.0])
    x, y, depth = view.project(mid)
    to_win = 1.0 / (v._scale * vp_item.window().devicePixelRatio())
    radius_px = 0.6 * screen.bridge.doc.item(clay_id)["steps"][0].get("radius", 0.05) / view.units(depth) * to_win
    top = vp_item.mapToScene(QPointF(0, 0))
    return QPointF(top.x() + x * to_win, top.y() + y * to_win), radius_px


def stroke(screen, win, name, want, at, radius, mods, core, invert=False, frm=(-1.0, 0.0), to=(1.0, 0.0)):
    """One real drag across the clay, from `frm` to `to` (in its on-screen radius from its middle; the start is left of
    the middle by default), made as a `want` stroke (with `invert`: Ctrl's opposite); its moves timed, a little zigzag
    across the line; one undo step checked; a picture after."""
    tool, doc = screen.bridge.viewport.clay, screen.bridge.doc
    clay_id = tool.clayId
    before = len(doc.item(clay_id)["steps"])
    x0, y0, x1, y1 = at.x() + frm[0] * radius, at.y() + frm[1] * radius, at.x() + to[0] * radius, at.y() + to[1] * radius
    length = max(1e-6, ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
    side = (-(y1 - y0) / length * 0.1 * radius, (x1 - x0) / length * 0.1 * radius)     # the zigzag, across the line
    start = QPoint(round(x0), round(y0))
    QTest.mouseMove(win, start)
    pump(0.3)
    QTest.mousePress(win, Qt.LeftButton, mods, start)
    pump(5, lambda: not tool._busy and tool._phase in ("sculpt", "orbit", ""), "the stroke's begin")
    check(tool._phase == "sculpt", f"{name}: the press on the clay began a stroke (not a view turn)")
    moves, views = [], []
    worker = screen.bridge.viewport._r
    on_ready = lambda serial, ms, *rest: views.append(round(ms, 2))  # noqa: E731  the engine's own ms per picture
    worker.ready.connect(on_ready)
    for i in range(1, 25):
        p = QPoint(round(x0 + (x1 - x0) * i / 24 + side[0] * (i % 2)), round(y0 + (y1 - y0) * i / 24 + side[1] * (i % 2)))
        c0, w0, e0 = gui_cycles_ms(), time.perf_counter(), proc_cpu_ms(core)
        QTest.mouseMove(win, p)
        QCoreApplication.processEvents()
        gui = gui_cycles_ms() - c0
        n = len(tool.timings)
        pump(5, lambda: not tool._busy, "a dab's answer")
        last = tool.timings[-1] if len(tool.timings) > n else {}
        moves.append({"guiCpuMs": round(gui, 2), "wallMs": round((time.perf_counter() - w0) * 1000, 2),
                      "engineMs": last.get("engineMs"), "coreCpuMs": round(proc_cpu_ms(core) - e0, 2),
                      "dabs": last.get("dabs")})
    worker.ready.disconnect(on_ready)
    QTest.mouseRelease(win, Qt.LeftButton, mods, p)
    pump(10, lambda: not tool._ending and len(doc.item(clay_id)["steps"]) > before, "the stroke's step")
    steps = doc.item(clay_id)["steps"]
    check(len(steps) == before + 1, f"{name}: one new step on the clay ({before} -> {len(steps)})")
    check(steps[-1].get("brush") == want and str(steps[-1].get("dabs", "")).startswith("clay/"),
          f"{name}: the step is a {want} stroke with its dabs file ({steps[-1].get('brush')}, {steps[-1].get('dabs')})")
    check(bool(steps[-1].get("invert", False)) == invert, f"{name}: the step's invert is {invert} ({steps[-1].get('invert')})")
    pump(1.0)
    slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    win.grabWindow().save(str(OUT / f"clay-walk-{slug}.png"))
    QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
    pump(0.5)
    check(len(doc.item(clay_id)["steps"]) == before, f"{name}: Ctrl+Z takes back exactly the stroke")
    QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
    pump(0.5)
    check(len(doc.item(clay_id)["steps"]) == before + 1, f"{name}: Ctrl+Shift+Z puts it back")
    worst = max(m["wallMs"] for m in moves)
    check(worst <= BUDGET_MS * 2, f"{name}: slowest dab answered in {worst:.1f} ms (budget ~{BUDGET_MS:.0f} ms a dab)")
    return {"stroke": name, "brush": want, "invert": invert, "moves": moves, "timings": tool.timings, "viewMs": views}


def pick_tile(win, tool, label, value):
    """A real click on a brush tile; the clay's brush is then `value`."""
    tile = find(win.contentItem(), f"clayBrush{label}")
    check(tile is not None, f"the {label} tile is on the panel")
    if tile is not None:
        click(win, tile)
    check(tool.tool == value, f"clicking {label} chooses it ({tool.tool})")


def settled_picture(screen, win):
    """The window's picture with the viewport drawn and no ring (the pointer parked on the header)."""
    v = screen.bridge.viewport
    QTest.mouseMove(win, QPoint(8, 8))
    pump(30, lambda: v._r.idle() and not v._next.isActive(), "the picture to settle")
    pump(0.5)
    return win.grabWindow()


def changed_share(a, b, box, dpr, diff=None):
    """The share of the pixels in `box` (window px: x0, y0, x1, y1) that changed between pictures a and b (grabbed at
    `dpr` device px a window px); each changed pixel is marked in `diff` (a picture the size of a) when given."""
    x0, y0 = max(0, round(box[0] * dpr)), max(0, round(box[1] * dpr))
    x1, y1 = min(a.width() - 1, round(box[2] * dpr)), min(a.height() - 1, round(box[3] * dpr))
    n = changed = 0
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            pa, pb = a.pixelColor(x, y), b.pixelColor(x, y)
            d = max(abs(pa.red() - pb.red()), abs(pa.green() - pb.green()), abs(pa.blue() - pb.blue()))
            n, changed = n + 1, changed + (d > 8)
            if diff is not None:
                diff.setPixelColor(x, y, QColor(min(255, d * 8), min(255, d * 8), 0) if d > 8 else QColor(40, 40, 40))
    return changed / max(1, n)


def mask_then_add(screen, win, at, radius, core):
    """Mask, then Add across it, proved by the picture. A Mask stroke down the clay's left side; Mirror (left-right, the
    clay's own x, the picture's left-right from this camera) masks the same band on the right. Then an Add across the
    lit upper part, left to right: it crosses the left band, the free middle and the right band. In the picture the
    middle changes and the left band (the one stroked) does not. The control: both strokes undone, the same Add with no
    mask changes the left band too (so it was the mask that kept it, not the light or the stroke's place). The lower
    half of the clay is in shadow, where a bulge hardly changes the picture, so all of it happens in the upper half;
    each part is measured over the brush's width, every pixel. The engine's shape hash says the Add changed the clay
    at all. The pictures and difference pictures (changed pixels yellow; the band blue, the middle green) go to the out
    folder; the clay ends as it was before the Mask, plus the control's Add."""
    tool, v = screen.bridge.viewport.clay, screen.bridge.viewport
    clay_id = tool.clayId
    brush = radius / 0.6 * tool._item().get("brushSize", 0.025) / tool._item()["steps"][0].get("radius", 0.1)  # its px
    row, band = -0.5, 0.7                          # the Add's height and the band's distance from the middle (in radius)
    steps0 = len(screen.bridge.doc.item(clay_id)["steps"])
    pick_tile(win, tool, "Mask", "mask")
    out = {"mask": stroke(screen, win, "Mask", "mask", at, radius, Qt.NoModifier, core, frm=(-band, -1.0), to=(-band, 0.1))}
    before = settled_picture(screen, win)
    hash0 = clay_info(v, clay_id).get("hash")
    pick_tile(win, tool, "Add", "add")
    add = {"frm": (-0.95, row), "to": (0.95, row)}
    out["add"] = stroke(screen, win, "Add over the mask", "add", at, radius, Qt.NoModifier, core, **add)
    after = settled_picture(screen, win)
    hash1 = clay_info(v, clay_id).get("hash")
    for _ in range(4):              # the control: Ctrl+Z back to before the Mask (a tile's brush is an undo step too)
        if len(screen.bridge.doc.item(clay_id)["steps"]) == steps0:
            break
        QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
        pump(0.5)
    steps = len(screen.bridge.doc.item(clay_id)["steps"])
    check(steps == steps0, f"the control: Ctrl+Z takes back the Add and the Mask ({steps0} -> {steps} steps)")
    pick_tile(win, tool, "Add", "add")
    plain = settled_picture(screen, win)
    out["control"] = stroke(screen, win, "Add with no mask", "add", at, radius, Qt.NoModifier, core, **add)
    control = settled_picture(screen, win)
    dpr = after.width() / win.width()
    y = at.y() + row * radius
    band_box = (at.x() - band * radius - 0.2 * brush, y - 0.3 * brush, at.x() - band * radius + 0.2 * brush, y + 0.3 * brush)
    free_box = (at.x() - 0.25 * radius, y - 0.3 * brush, at.x() + 0.25 * radius, y + 0.3 * brush)
    whole = (at.x() - 1.8 * radius, at.y() - 1.8 * radius, at.x() + 1.8 * radius, at.y() + 1.8 * radius)
    shares = {}
    for name, a, b in (("mask", before, after), ("control", plain, control)):
        diff = after.copy()
        diff.setDevicePixelRatio(1.0)                          # drawn in device px, as the boxes are given
        diff.fill(QColor(20, 20, 20))
        changed_share(a, b, whole, dpr, diff)                  # the whole clay, for the eye
        shares[name] = {"band": changed_share(a, b, band_box, dpr), "free": changed_share(a, b, free_box, dpr)}
        paint = QPainter(diff)
        for box, colour in ((band_box, QColor(80, 160, 255)), (free_box, QColor(80, 255, 120))):
            paint.setPen(QPen(colour, 2))
            paint.drawRect(QRectF(box[0] * dpr, box[1] * dpr, (box[2] - box[0]) * dpr, (box[3] - box[1]) * dpr))
        paint.end()
        diff.copy(QRect(*(round(c * dpr) for c in (whole[0], whole[1], whole[2] - whole[0], whole[3] - whole[1])))).save(
            str(OUT / f"clay-walk-{name}-difference.png"))
    before.save(str(OUT / "clay-walk-mask-before-add.png"))
    after.save(str(OUT / "clay-walk-mask-then-add.png"))
    control.save(str(OUT / "clay-walk-add-with-no-mask.png"))
    m, c = shares["mask"], shares["control"]
    check(hash1 != hash0, f"Add over the mask: the engine's clay changed ({hash0} -> {hash1})")
    # (CL2b: one Add stroke shows as faint rings at the dabs' edges, not a raised ridge, so a few % of a box is a
    # change; the control is what proves the mask kept the band)
    check(m["free"] >= SEEN, f"Add over the mask: the free middle changed ({m['free']:.1%} of its pixels changed)")
    check(m["band"] <= 0.01, f"Add over the mask: the masked band did not change ({m['band']:.1%} of its pixels changed)")
    check(c["band"] >= SEEN, f"the control, the same Add with no mask: the band changed ({c['band']:.1%} of its pixels)")
    out["changed"] = {**shares, "brushPx": round(brush, 1), "hash": [hash0, hash1],
                      "bandBox": [round(q) for q in band_box], "freeBox": [round(q) for q in free_box]}
    return out


def size_drag(screen, win, at):
    """F held over the clay, the pointer moved right: the ring grows with each move, nothing is kept and no stroke
    starts; F up: the new, larger size is one undo step (Ctrl+Z takes it back)."""
    tool, doc, v = screen.bridge.viewport.clay, screen.bridge.doc, screen.bridge.viewport
    clay_id = tool.clayId
    size0, n0, steps0 = doc.item(clay_id).get("brushSize"), len(doc.history.changes), len(doc.item(clay_id)["steps"])
    for dx in (-12, -6, 0):                         # onto the clay as a hand comes: a few moves, the ring follows
        QTest.mouseMove(win, QPoint(at.toPoint().x() + dx, at.toPoint().y()))
        pump(0.05)
    pump(5, lambda: len(tool.ring) > 2, "the ring under the pointer")
    check(len(tool.ring) > 2, "resting the pointer on the clay shows the brush ring (no press)")
    ring_px = lambda: R.ring_px(tool._ring, tool._ring_c, *v._size)  # noqa: E731
    r0 = ring_px()
    QTest.keyPress(win, Qt.Key_F)
    pump(0.1)
    check(tool.sizing, f"holding F over the clay starts the size drag (status line: {v.status or '-'})")
    moves, p = [], at.toPoint()
    for i in range(1, 21):
        p = QPoint(at.toPoint().x() + 3 * i, at.toPoint().y())
        c0 = gui_cycles_ms()
        QTest.mouseMove(win, p)
        QCoreApplication.processEvents()
        moves.append(round(gui_cycles_ms() - c0, 2))
    r1 = ring_px()
    check(r1 > r0 * 1.3, f"F + drag right: the ring grew live ({r0:.0f} -> {r1:.0f} px)")
    check(doc.item(clay_id).get("brushSize") == size0 and len(doc.history.changes) == n0,
          "while F is held nothing is kept (no clay.set yet)")
    check(len(doc.item(clay_id)["steps"]) == steps0 and tool.strokeBrush == "", "F + drag makes no stroke")
    QTest.keyRelease(win, Qt.Key_F)
    pump(0.3)
    size1 = doc.item(clay_id).get("brushSize")
    check(not tool.sizing and size1 > size0, f"F up: the brush is bigger ({size0} -> {size1})")
    check(len(doc.history.changes) == n0 + 1, f"F up: one undo step ({n0} -> {len(doc.history.changes)})")
    QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier)
    pump(0.3)
    check(doc.item(clay_id).get("brushSize") == size0, "Ctrl+Z puts the size back")
    QTest.keyClick(win, Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier)
    pump(0.3)
    check(doc.item(clay_id).get("brushSize") == size1, "Ctrl+Shift+Z: the new size again")
    worst = max(moves)
    check(worst <= BUDGET_MS, f"F + drag: the slowest move took {worst:.1f} ms of the GUI thread (budget {BUDGET_MS:.0f})")
    return {"size": [size0, size1], "ringPx": [round(r0, 1), round(r1, 1)], "guiCpuMs": moves}


def lump_on_object(screen, win, vp_item, item_id):
    """CL1b's bug, checked: a Lump click on another thing (not the ground) makes a clay that shows in the picture, and
    how long that takes from the click (a new clay is built before it can be drawn)."""
    v, doc = screen.bridge.viewport, screen.bridge.doc
    lump = find(win.contentItem(), "clayMakeLump")
    check(lump is not None, "the Lump tile is on the panel")
    click(win, lump)
    scene, cam = v.sent()
    view = View.of(cam, scene, screen.bridge.frame, cam["width"], cam["height"])
    from rostrum3d import aim, through
    x, y, _ = view.project(aim.point(through.find_item(scene, item_id, screen.bridge.frame)[0], [0.0, 0.0, 0.0]))
    to_win = 1.0 / (v._scale * vp_item.window().devicePixelRatio())
    top = vp_item.mapToScene(QPointF(0, 0))
    at = QPointF(top.x() + x * to_win, top.y() + y * to_win).toPoint()
    before_ids, before = set(c["id"] for c in doc.data["items"] if c["type"] == "clay"), win.grabWindow()
    t0 = time.perf_counter()
    QTest.mouseMove(win, at)
    QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, at)
    pump(20, lambda: any(c["type"] == "clay" and c["id"] not in before_ids for c in doc.data["items"]), "the new clay")
    new = next((c["id"] for c in doc.data["items"] if c["type"] == "clay" and c["id"] not in before_ids), "")
    pump(30, lambda: v._r.idle() and not v._next.isActive() and not v.status.startswith("Error"), "the new clay's picture")
    pump(0.1)
    ms = (time.perf_counter() - t0) * 1000
    after = win.grabWindow()
    win.grabWindow().save(str(OUT / "clay-walk-on-box.png"))
    if not new:
        return check(False, f"a Lump click on {item_id} made a clay")
    c, r = clay_on_screen(screen, new, vp_item)
    changed = sum(1 for dx in range(-3, 4) for dy in range(-3, 4)
                  if before.pixelColor(int(c.x()) + dx * int(r / 4), int(c.y()) + dy * int(r / 4)) !=
                  after.pixelColor(int(c.x()) + dx * int(r / 4), int(c.y()) + dy * int(r / 4)))
    check(changed > 30, f"a Lump click on {item_id} made {new} and it is drawn ({changed} of 49 pixels over it changed)")
    check(ms < 2000, f"the new clay is in the picture {ms:.0f} ms after the click (under 2 s)")
    return round(ms)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    project = Path(tempfile.mkdtemp(prefix="rostrum-claywalk-"))
    app = qt_app()
    doc = Document.new(KIND, folder=project, item="scene")
    doc.run_script("sample.py", run_source(SOURCE, "sample.py"))
    doc.save()
    screen = app3d.Screen(SIZE)
    report = {"strokes": []}
    try:
        screen.show(doc, autosave=True)
        win, v = screen.win, screen.bridge.viewport
        pump(60, screen.ready, "the first picture")
        vp_item = find(win.contentItem(), "viewport3d")
        scene = v.sent()[0]
        core = K32.OpenProcess(0x1000, False, core_pid(v, scene))

        QTest.keyClick(win, Qt.Key_Q)                                   # Clay
        pump(0.3)
        check(v.clay.on and v.clay.tool == "lump", "Q turns the Clay tool on, Lump chosen (nothing to sculpt yet)")
        ground = vp_item.mapToScene(QPointF(vp_item.width() * 0.5, vp_item.height() * 0.85))
        QTest.mouseMove(win, ground.toPoint())
        QTest.mouseClick(win, Qt.LeftButton, Qt.NoModifier, ground.toPoint())
        pump(20, lambda: v.clay.clayId != "", "the Lump click's new clay")
        clay_id = v.clay.clayId
        check(bool(clay_id), f"a Lump click on the ground made a clay ({clay_id}), selected")
        serial = v.serial
        pump(30, lambda: v.serial > serial and not v.status.startswith("Error"), "the clay drawn")
        check(not v.status.startswith("Error"), f"the clay draws ({v.status or 'no error'})")
        win.grabWindow().save(str(OUT / "clay-walk-lump.png"))

        n = v.clay.brushObj.rows.rowCount()
        check(n == 6, f"the six brush rows show on the Clay panel in a fresh window ({n} rows)")
        QTest.keyClick(win, Qt.Key_V)
        pump(0.3)
        QTest.keyClick(win, Qt.Key_Q)
        pump(0.3)
        n = v.clay.brushObj.rows.rowCount()
        check(v.clay.on and n == 6, f"V then Q: Clay on again with its six brush rows ({n} rows)")
        pick_tile(win, v.clay, "Add", "add")
        at, radius = clay_on_screen(screen, clay_id, vp_item)
        info0 = clay_info(v, clay_id)
        idle = []                                          # the same picture with nothing changing: the scene's own cost
        grab = lambda serial, ms, *rest: idle.append(round(ms, 2))  # noqa: E731
        v._r.ready.connect(grab)
        for _ in range(8):
            v.redraw()
            pump(2, lambda: len(idle) > _, "an idle picture")
        v._r.ready.disconnect(grab)
        report["idleViewMs"] = idle
        for label in ("Add", "Carve", "Smooth", "Pull", "Flatten", "Crease"):          # the six that shape
            pick_tile(win, v.clay, label, label.lower())
            report["strokes"].append(stroke(screen, win, label, label.lower(), at, radius, Qt.NoModifier, core))
        pick_tile(win, v.clay, "Add", "add")                                            # Ctrl and Shift
        report["strokes"].append(stroke(screen, win, "Carve (Ctrl on Add)", "carve", at, radius, Qt.ControlModifier, core))
        report["strokes"].append(stroke(screen, win, "Smooth (Shift)", "smooth", at, radius, Qt.ShiftModifier, core))
        pick_tile(win, v.clay, "Flatten", "flatten")
        report["strokes"].append(stroke(screen, win, "Puff out (Ctrl on Flatten)", "flatten", at, radius,
                                        Qt.ControlModifier, core, invert=True))
        report["mask"] = mask_then_add(screen, win, at, radius, core)
        report["sizeDrag"] = size_drag(screen, win, at)
        info1 = clay_info(v, clay_id)
        report["lumpOnBoxMs"] = lump_on_object(screen, win, vp_item, "block")
        check(info1.get("hash") != info0.get("hash"), f"the clay's shape changed ({info0.get('hash')} -> {info1.get('hash')})")
        report["clayInfo"] = {"before": info0, "after": info1}
        K32.CloseHandle(ct.c_void_p(core))
    except Exception as e:  # noqa: BLE001  a crash is a failed walk, said with its reason
        FAILS.append(f"the walk stopped: {type(e).__name__}: {e}")
    finally:
        report["fails"] = FAILS
        (OUT / "clay_walk.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
        screen.close()
        pump(1.0)
        shutil.rmtree(project, ignore_errors=True)
    print(f"{len(FAILS)} failed check(s); numbers and pictures in {OUT}")
    for f in FAILS:
        print("  " + f)
    app.quit()
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
