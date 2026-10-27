"""Pictures and drag timings of the kit's block view (BlockView, BLOCKS.md) on a toy material graph: 10 block types,
30 blocks. Every request the view sends goes to the toy, which changes its data and gives it back, as an app would.

    python shared/gui-kit/demo/blocks_preview.py [out folder]     # pictures <out>/*.png and the timings, then quits

It drives the window with real mouse and key events (QTest on the window): a block dragged, a wire drawn, a wire
dropped on nothing, the add list typed into, the wheel. A block drag and a wire drag print the window thread's cost
per move (median / 95th, ms): the move itself (event, bindings, the dragged item and its wires), and the move plus
one full frame drawn (a picture grab, so an upper bound: it includes reading the picture back).
"""
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Property, QObject, QPoint, QPointF, Qt, QTimer, Signal, Slot  # noqa: E402

from rostrum_gui import blocks as rules  # noqa: E402
from rostrum_gui.app import offscreen_env  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = r"C:\Users\Sam\.rostrum\waves\scratch\hem-3d23-k5"

N, C = "number", "colour"
CATALOGUE = [
    {"type": "image", "label": "Image", "group": "Patterns", "words": "picture texture file",
     "inputs": [], "outputs": [{"name": "colour", "label": "Colour", "kind": C}, {"name": "value", "label": "Value", "kind": N}]},
    {"type": "noise", "label": "Noise", "group": "Patterns", "words": "random cloud grain",
     "inputs": [{"name": "scale", "label": "Scale", "kind": N}, {"name": "detail", "label": "Detail", "kind": N},
                {"name": "roughness", "label": "Roughness", "kind": N}, {"name": "distortion", "label": "Distortion", "kind": N}],
     "outputs": [{"name": "value", "label": "Value", "kind": N}, {"name": "colour", "label": "Colour", "kind": C}]},
    {"type": "mix", "label": "Mix", "group": "Colour", "words": "blend multiply add screen overlay",
     "inputs": [{"name": "factor", "label": "Factor", "kind": N}, {"name": "a", "label": "A", "kind": C},
                {"name": "b", "label": "B", "kind": C}],
     "outputs": [{"name": "colour", "label": "Colour", "kind": C}]},
    {"type": "ramp", "label": "Ramp", "group": "Colour", "words": "gradient stops map",
     "inputs": [{"name": "factor", "label": "Factor", "kind": N}],
     "outputs": [{"name": "colour", "label": "Colour", "kind": C}, {"name": "value", "label": "Value", "kind": N}]},
    {"type": "colourAdjust", "label": "Colour adjust", "group": "Colour", "words": "hue saturation brightness contrast",
     "inputs": [{"name": "colour", "label": "Colour", "kind": C}, {"name": "hue", "label": "Hue", "kind": N},
                {"name": "saturation", "label": "Saturation", "kind": N}, {"name": "brightness", "label": "Brightness", "kind": N},
                {"name": "contrast", "label": "Contrast", "kind": N}],
     "outputs": [{"name": "colour", "label": "Colour", "kind": C}]},
    {"type": "curve", "label": "Curve", "group": "Numbers", "words": "remap shape",
     "inputs": [{"name": "value", "label": "Value", "kind": N}], "outputs": [{"name": "value", "label": "Value", "kind": N}]},
    {"type": "bevel", "label": "Bevel shading", "group": "Shape", "words": "rounded edges",
     "inputs": [{"name": "radius", "label": "Radius", "kind": N}], "outputs": [{"name": "normal", "label": "Normal", "kind": "normal"}]},
    {"type": "occlusion", "label": "Ambient occlusion", "group": "Shape", "words": "dirt corners shadow",
     "inputs": [{"name": "distance", "label": "Distance", "kind": N}, {"name": "colour", "label": "Colour", "kind": C}],
     "outputs": [{"name": "value", "label": "Value", "kind": N}, {"name": "colour", "label": "Colour", "kind": C}]},
    {"type": "lines", "label": "Lines", "group": "Stylized", "words": "outline ink edges",
     "inputs": [{"name": "width", "label": "Width", "kind": N}, {"name": "colour", "label": "Colour", "kind": C}],
     "outputs": [{"name": "style", "label": "Style", "kind": "style"}]},
    {"type": "halftone", "label": "Halftone", "group": "Stylized", "words": "dots print comic",
     "inputs": [{"name": "size", "label": "Dot size", "kind": N}], "outputs": [{"name": "style", "label": "Style", "kind": "style"}]},
]
SURFACE = {"type": "surface", "label": "Surface", "removable": False, "outputs": [],
           "inputs": [{"name": "baseColor", "label": "Base colour", "kind": C}, {"name": "roughness", "label": "Roughness", "kind": N},
                      {"name": "metallic", "label": "Metallic", "kind": N}, {"name": "emissionColor", "label": "Glow colour", "kind": C},
                      {"name": "normal", "label": "Normal", "kind": "normal"}, {"name": "style", "label": "Style", "kind": "style"}]}
CONVERTS = {N: [C], C: [N]}           # a number feeds a colour (grey), a colour a number (its brightness)
SUMMARY = {"image": "brick_wall.png", "noise": "Scale 5 · Detail 2", "mix": "Multiply · 50 %", "ramp": "3 stops",
           "colourAdjust": "Saturation 1.2", "curve": "4 points", "bevel": "Radius 5 mm", "occlusion": "Distance 0.2 m",
           "lines": "Width 2 px", "halftone": "Dot size 6 px"}
NOTE = {"bevel": "Final only", "occlusion": "Final only"}
COLUMNS = [["mix", "ramp", "bevel", "lines", "curve"], ["noise", "colourAdjust", "image", "occlusion", "noise", "halftone"],
           ["image", "noise", "mix", "ramp", "curve", "noise"], ["noise", "curve", "image", "ramp", "colourAdjust", "noise"],
           ["image", "noise", "curve", "image", "noise", "ramp"]]


class Toy(QObject):
    """A stand-in document: the view's requests change it, and it gives the new data back."""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._blocks = [{"id": "surface", "x": 0, "y": -120, "values": {}, **SURFACE}]
        self._wires: list[dict] = []
        self._selected = ""
        self.refused: list[str] = []
        by_type = {c["type"]: c for c in CATALOGUE}
        prev = [self._blocks[0]]
        for col, types in enumerate(COLUMNS):
            y, made = -360, []
            for t in types:
                b = self._make(t, -270 * (col + 1) - 40, y, by_type)
                y += rules.height(self._view(b)) + 36
                made.append(b)
            for i, b in enumerate(made):         # each block feeds a free input in the column to its right
                for target in sorted(prev, key=lambda p: abs(prev.index(p) - i * len(prev) / len(made))):
                    if self._wire_first(b, target):
                        break
            prev = made

    def _make(self, t, x, y, by_type):
        n = sum(1 for b in self._blocks if b["type"] == t) + 1
        b = {"id": f"{t}_{n}", "x": x, "y": y, **{k: v for k, v in by_type[t].items() if k not in ("group", "words")}}
        self._blocks.append(b)
        return b

    def _wire_first(self, a, b) -> bool:
        taken = {w["to"] for w in self._wires}
        for o in a["outputs"]:
            for i in b["inputs"]:
                to = f"{b['id']}.{i['name']}"
                if to not in taken and rules.compatible(o["kind"], i["kind"], CONVERTS) \
                        and not rules.refusal(self._blocks, self._wires, f"{a['id']}.{o['name']}", to, CONVERTS):
                    self._wires.append({"from": f"{a['id']}.{o['name']}", "to": to})
                    return True
        return False

    def _view(self, b):
        linked = {w["to"] for w in self._wires}
        return {"id": b["id"], "type": b["type"], "label": b["label"], "x": b["x"], "y": b["y"],
                "summary": SUMMARY.get(b["type"], ""), "note": NOTE.get(b["type"], ""), "removable": b.get("removable", True),
                "inputs": [{**p, "linked": f"{b['id']}.{p['name']}" in linked} for p in b["inputs"]], "outputs": b["outputs"]}

    def _get(self, bid):
        return next(b for b in self._blocks if b["id"] == bid)

    catalogue = Property("QVariantList", lambda self: CATALOGUE, constant=True)
    kindColours = Property("QVariantMap", lambda self: rules.KIND_COLOURS, constant=True)
    converts = Property("QVariantMap", lambda self: CONVERTS, constant=True)
    blocks = Property("QVariantList", lambda self: [self._view(b) for b in self._blocks], notify=changed)
    wires = Property("QVariantList", lambda self: list(self._wires), notify=changed)
    selected = Property(str, lambda self: self._selected, notify=changed)

    @Slot(str, float, float, str)
    def add(self, t, x, y, from_port):
        b = self._make(t, x, y, {c["type"]: c for c in CATALOGUE})
        if from_port:
            name = rules.first_input(b, self._kind(from_port), CONVERTS)
            self._wires.append({"from": from_port, "to": f"{b['id']}.{name}"})
        self._selected = b["id"]
        self.changed.emit()

    def _kind(self, port):
        b = self._get(rules.block_of(port))
        return next(o["kind"] for o in b["outputs"] if o["name"] == port.rsplit(".", 1)[1])

    @Slot(str, float, float)
    def move(self, bid, x, y):
        b = self._get(bid)
        b["x"], b["y"] = x, y
        self.changed.emit()

    @Slot(str, str)
    def connect(self, frm, to):
        why = rules.refusal(self._blocks, self._wires, frm, to, CONVERTS)
        if why:
            self.refused.append(why)
            return
        self._wires = [w for w in self._wires if w["to"] != to] + [{"from": frm, "to": to}]
        self.changed.emit()

    @Slot(str)
    def disconnect(self, to):
        self._wires = [w for w in self._wires if w["to"] != to]
        self.changed.emit()

    @Slot("QVariantList")
    def remove(self, ids):
        ids = set(ids)
        self._blocks = [b for b in self._blocks if b["id"] not in ids]
        self._wires = [w for w in self._wires if rules.block_of(w["from"]) not in ids and rules.block_of(w["to"]) not in ids]
        self._selected = ""
        self.changed.emit()

    @Slot(str)
    def pick(self, bid):
        if bid != self._selected:
            self._selected = bid
            self.changed.emit()


def find(item, name):
    if item.objectName() == name:
        return item
    return next(filter(None, (find(c, name) for c in item.childItems())), None)


def at(win, name, fx=0.5, fy=0.5):
    obj = find(win.contentItem(), name)
    if obj is None:
        raise RuntimeError(f"no control named {name!r}")
    p = obj.mapToScene(QPointF(obj.width() * fx, obj.height() * fy))
    return QPoint(round(p.x()), round(p.y()))


def ms(ns):
    return ns / 1e6


def stats(xs):
    xs = sorted(xs)
    return statistics.median(xs), xs[max(0, round(0.95 * len(xs)) - 1)]


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else OUT)
    out.mkdir(parents=True, exist_ok=True)
    for k, v in offscreen_env().items():
        os.environ.setdefault(k, v)
    os.environ.setdefault("QSG_RENDER_LOOP", "basic")     # frames drawn on the window thread: what the timings count
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest
    from rostrum_gui import start

    toy = Toy()
    app, engine, win = start(HERE / "qml" / "BlocksPreview.qml", {"toy": toy}, (1646, 900))
    view = find(win.contentItem(), "blockView")
    L = Qt.LeftButton

    def settle(n=6):
        for _ in range(n):
            QTest.qWait(30)

    def shot(name):
        settle()
        win.grabWindow().save(str(out / f"{name}.png"))
        print("picture:", out / f"{name}.png")

    def timed_drag(p0, p1, steps=80, mid_shot=""):
        QTest.mousePress(win, L, Qt.NoModifier, p0)
        move, frame = [], []
        for i in range(1, steps + 1):
            p = QPoint(round(p0.x() + (p1.x() - p0.x()) * i / steps), round(p0.y() + (p1.y() - p0.y()) * i / steps))
            t0 = time.perf_counter_ns()
            QTest.mouseMove(win, p)
            t1 = time.perf_counter_ns()
            win.grabWindow()
            t2 = time.perf_counter_ns()
            move.append(ms(t1 - t0))
            frame.append(ms(t2 - t0))
            if mid_shot and i == steps:
                shot(mid_shot)
        return move, frame

    def drag(p0, p1, button=L, steps=10):
        QTest.mousePress(win, button, Qt.NoModifier, p0)
        for i in range(1, steps + 1):
            QTest.mouseMove(win, p0 + (p1 - p0) * (i / steps))
        QTest.mouseRelease(win, button, Qt.NoModifier, p1)
        settle(2)

    def report(what, move, frame, base):
        m, m95 = stats(move)
        f, f95 = stats(frame)
        print(f"{what}: move {m:.2f} / {m95:.2f} ms (median / 95th); move + frame {f:.2f} / {f95:.2f} ms "
              f"(a still frame's grab alone: {base:.2f} ms)")

    def run():
        try:
            settle(10)
            base = statistics.median([ms(-time.perf_counter_ns() + (win.grabWindow(), time.perf_counter_ns())[1])
                                      for _ in range(10)])
            print(f"{len(toy.blocks)} blocks, {len(toy.wires)} wires; zoom {view.property('zoom'):.2f}")
            shot("1-overview")

            # a block dragged by its header, 80 moves
            p0 = at(win, "blockHeader:noise_1", 0.3)
            before = dict(next(b for b in toy.blocks if b["id"] == "noise_1"))
            move, frame = timed_drag(p0, p0 + QPoint(160, 120))
            QTest.mouseRelease(win, L, Qt.NoModifier, p0 + QPoint(160, 120))
            after = next(b for b in toy.blocks if b["id"] == "noise_1")
            print(f"block drag: noise_1 {before['x']:.0f},{before['y']:.0f} -> {after['x']:.0f},{after['y']:.0f}")
            report("block drag", move, frame, base)
            shot("2-moved-and-picked")

            # a wire drawn from an output toward the Surface: compatible ports lit, the rest dim (picture mid-drag)
            src = at(win, "port:noise_2:out:colour")
            dst = at(win, "port:surface:in:emissionColor")
            n0 = len(toy.wires)
            move, frame = timed_drag(src, dst, mid_shot="3-wiring")
            QTest.mouseRelease(win, L, Qt.NoModifier, dst)
            print(f"wire drag: wires {n0} -> {len(toy.wires)}; noise_2.colour -> surface.emissionColor "
                  f"{any(w == {'from': 'noise_2.colour', 'to': 'surface.emissionColor'} for w in toy.wires)}")
            report("wire drag", move, frame, base)

            # a wired input's end picked up and dropped on nothing: that wire goes
            end = at(win, "port:surface:in:baseColor")
            drag(end, end + QPoint(-80, 260))
            print(f"unwire: surface.baseColor still wired {any(w['to'] == 'surface.baseColor' for w in toy.wires)}")
            # a loop is never offered: from surface's feeder mix_1, the blocks upstream of it stay dim
            src = at(win, "port:mix_1:out:colour")
            QTest.mousePress(win, L, Qt.NoModifier, src)
            QTest.mouseMove(win, src + QPoint(20, 20))
            upstream = rules.reach(toy.wires, "mix_1", "up")
            looped = [b["id"] for b in toy.blocks if b["id"] in upstream
                      and any(view.portState(b["id"], "in", p["name"], p["kind"]) == 1 for p in b["inputs"])]
            QTest.keyClick(win, Qt.Key_Escape)
            QTest.mouseRelease(win, L, Qt.NoModifier, src + QPoint(20, 20))
            print(f"loop guard: {len(upstream) - 1} blocks upstream of mix_1, lit: {looped or 'none'}; wires after Esc {len(toy.wires)}")
            # Esc in a block drag puts the block back
            b0 = next(b for b in toy.blocks if b["id"] == "mix_1")
            h = at(win, "blockHeader:mix_1", 0.3)
            QTest.mousePress(win, L, Qt.NoModifier, h)
            for i in range(1, 6):
                QTest.mouseMove(win, h + QPoint(20 * i, 10 * i))
            QTest.keyClick(win, Qt.Key_Escape)
            QTest.mouseMove(win, h + QPoint(140, 70))
            QTest.mouseRelease(win, L, Qt.NoModifier, h + QPoint(140, 70))
            b1 = next(b for b in toy.blocks if b["id"] == "mix_1")
            item = find(win.contentItem(), "block:mix_1")
            print(f"Esc in a drag: mix_1 data {b0['x']},{b0['y']} -> {b1['x']},{b1['y']}; drawn at "
                  f"{item.property('x'):.0f},{item.property('y'):.0f}")
            # pan: a drag on empty space, then a middle-drag over a block
            p0 = (view.property("panX"), view.property("panY"))
            drag(QPoint(1560, 820), QPoint(1500, 780))
            drag(at(win, "block:noise_3"), at(win, "block:noise_3") - QPoint(30, 20), Qt.MiddleButton)
            print(f"pan: {p0[0]:.0f},{p0[1]:.0f} -> {view.property('panX'):.0f},{view.property('panY'):.0f} (expect -90,-60)")
            settle()
            # a new wire dropped on nothing: the add list opens there, filtered to what the wire can feed
            src = at(win, "port:image_1:out:value")
            drop = QPoint(src.x() + 140, src.y() + 260)
            QTest.mousePress(win, L, Qt.NoModifier, src)
            for i in range(1, 11):
                QTest.mouseMove(win, src + (drop - src) * i / 10)
            QTest.mouseRelease(win, L, Qt.NoModifier, drop)
            shot("4-wire-dropped-add-list")
            n0 = (len(toy.blocks), len(toy.wires))
            QTest.mouseClick(win, L, Qt.NoModifier, at(win, "blockAddItem:curve"))
            settle()
            print(f"add from a dropped wire: blocks/wires {n0} -> {(len(toy.blocks), len(toy.wires))}; "
                  f"new wire {toy.wires[-1]}")
            shot("5-added-from-wire")

            # Tab: the add list at the pointer; typing filters it; Enter adds
            QTest.mouseMove(win, QPoint(820, 820))
            QTest.keyClick(win, Qt.Key_Tab)
            shot("6-add-list")
            for ch in "sat":
                QTest.keyClick(win, getattr(Qt.Key, f"Key_{ch.upper()}"))
            shot("7-add-list-search")
            QTest.keyClick(win, Qt.Key_Return)
            settle()
            print(f"typed 'sat' + Enter added {toy.blocks[-1]['type']}")
            # Delete removes the picked block
            n0 = len(toy.blocks)
            QTest.keyClick(win, Qt.Key_Delete)
            settle()
            print(f"Delete: blocks {n0} -> {len(toy.blocks)}")

            # the wheel zooms about the pointer
            pt = at(win, "block:surface", 0.5, 0.3)
            for _ in range(8):
                ev = QWheelEvent(QPointF(pt), QPointF(win.mapToGlobal(pt)), QPoint(), QPoint(0, 120), Qt.NoButton,
                                 Qt.NoModifier, Qt.NoScrollPhase, False)
                QCoreApplication.sendEvent(win, ev)
            print(f"wheel: zoom {view.property('zoom'):.2f}")
            shot("8-zoomed")
            QTest.keyClick(win, Qt.Key_F)
            print(f"F: zoom {view.property('zoom'):.2f}")
            print(f"refused by the toy: {toy.refused or 'none'}")
        except Exception as e:  # noqa: BLE001  a step that fails fails the run, loudly
            import traceback
            traceback.print_exc()
            print(f"FAIL: {e}", file=sys.stderr)
            return app.exit(3)
        app.exit(0)

    QTimer.singleShot(300, run)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
