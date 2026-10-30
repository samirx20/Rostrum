"""What a look at a film's frames can say in plain words, measured on the engine's own layout and pictures: text cut
by the frame's edge, an element painted over a text, a frame that is almost one colour, a stretch where nothing
changes. Notes only (information with times, never a refusal): the film is drawn as written.

    notes(session, film, [0.5, 1.5, …], stills=[…]) -> ["#headline is cut by the right edge from 4.2 to 6.0 s (up to 38 px outside)", …]

Boxes come from the engine (`frame` with boxes, boxes.rs): every element with an id, as laid out and painted this
frame (the camera's transform included), in paint order, with the union of its own text's glyph runs; a part inside
an `<svg>` (a shape, `<g>`, `<text>`) by the box of its drawn outline.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from .film import Film
from .render import TEXT_PREFIX, Session, stills as draw_stills

MAX_LINES = 10
EDGE_PX = 2.0             # glyphs further out than this count as cut
COVER_SHARE = 0.10        # the part of a text's glyphs another element must cover,
HIDDEN_SHARE = 0.9        # a text this much under one element is hidden by it (a screen over a screen), not marred
HIDER_SIZE = 4.0          # ... by an element at least this many times its area
SITS_ON = 0.5             # or the part of a smaller element that lies on the text
WRAPPER_SHARE = 0.30      # a later element this big (of the frame) is taken for a layout box, not something on top
EMPTY_SHARE = 0.98        # a frame this much one colour is "almost empty"
STILL_PIXELS = 0.001      # under this share of changed pixels two frames are the same picture
STILL_SPAN_S = 1.5        # a run of same pictures this long is said


def notes(session: Session, film: Film, times: list[float], stills: list[Path] | None = None) -> list[str]:
    """Plain-word observations over `times` (each drawn with boxes), merged across times, most important first, at most
    ten. `stills`: the pictures already drawn at those times (same order); without them a small picture is drawn per time
    for the empty-frame and nothing-moves notes and deleted after."""
    times = sorted(dict.fromkeys(float(t) for t in times))
    if not times:
        return []
    if stills is not None and len(stills) != len(times):
        raise ValueError(f"notes: {len(stills)} stills for {len(times)} times")
    with tempfile.TemporaryDirectory(prefix="rostrum-review-") as tmp:
        shots = draw_stills(session, film, times, Path(tmp), boxes=True, ext="jpg")
        frames = [b for _, _, b in shots]
        pictures = list(stills) if stills is not None else [p for p, _, _ in shots]
        found = _layout_notes(film, times, frames) + _picture_notes(film, times, pictures)
    found.sort(key=lambda n: -n[0])
    return [say for _, say in found[:MAX_LINES]]


# --- layout ---

def _layout_notes(film: Film, times: list[float], frames: list[list[dict]]) -> list[tuple[float, str]]:
    frame = (0.0, 0.0, float(film.width), float(film.height))
    cuts: dict[tuple, dict[float, float]] = {}     # (id, sides, text?) -> {t: px outside}
    covers: dict[tuple, dict[float, float]] = {}   # (top id, text id, sits?) -> {t: share covered}
    names: dict[str, str] = {}
    for t, boxes in zip(times, frames):
        for b in boxes:
            names[b["id"]] = _name(b)
            if not _measured(b):
                continue
            g = b.get("glyphs")
            text = g is not None
            r = g if text else b.get("box")
            if r is None or (not text and not _small_enough(r, frame)) or not _visible(r, _clip(b, frame)):
                continue                            # wholly hidden by a clipping parent: parked, not cut
            sides, px = _outside(r, frame, _clip(b, frame))
            if sides and _visible(r, frame):
                cuts.setdefault((b["id"], sides, text), {})[t] = max(px, cuts.get((b["id"], sides, text), {}).get(t, 0))
        for i, under in enumerate(boxes):
            g = under.get("glyphs")
            if g is None or not _measured(under) or not _visible(_meet(g, _clip(under, frame)), frame):
                continue
            g = _meet(g, _clip(under, frame))
            kin = _lineage(boxes, i)
            if _hidden(boxes, i, g, kin, frame):
                continue                            # under a later screen or panel: not seen, so not marred
            for j in range(i + 1, len(boxes)):
                top = boxes[j]
                if top["id"] in kin or not _measured(top) or under["id"] in _lineage(boxes, j):
                    continue
                box = top.get("box")
                if box is None or _area(box) > WRAPPER_SHARE * _area(frame):
                    continue
                box = _meet(box, _clip(top, frame))
                meet = _area(_meet(box, g))
                share = meet / max(1.0, _area(g))
                sits = top.get("glyphs") is None and meet >= SITS_ON * _area(box) > 0 and _area(box) < _area(g)
                screen = share > HIDDEN_SHARE and _area(box) >= HIDER_SIZE * _area(g)   # a screen over a screen
                if (share >= COVER_SHARE and not screen) or sits:
                    key = (top["id"], under["id"], sits)
                    covers.setdefault(key, {})[t] = max(share, covers.get(key, {}).get(t, 0))
    out = []
    cuts = _letters_together(cuts, names)
    for (ident, sides, text), at in cuts.items():
        px = max(at.values())
        what = f"{names[ident]} is cut by the {_sides(sides)}" if text else f"{names[ident]} runs past the {_sides(sides)}"
        out.append(((3 if text else 1) + _weight(at, times), ident, f"{what} {_when(at, times)} (up to {px:.0f} px outside)"))
    by_top: dict[tuple, list] = {}                  # one line per covering element: what it lies on, and when
    for (top, under, sits), at in covers.items():
        by_top.setdefault((top, sits), []).append((under, at))
    for (top, sits), unders in by_top.items():
        unders.sort(key=lambda u: -len(u[1]))
        at = {t: 1 for _, a in unders for t in a}
        listed = ", ".join(names[u] for u, _ in unders[:4]) + (f" and {len(unders) - 4} more" if len(unders) > 4 else "")
        if sits:
            out.append((2.5 + _weight(at, times), top, f"{names[top]} sits on {listed} {_when(at, times)}"))
        else:
            share = max(max(a.values()) for _, a in unders)
            part = f" (up to {share * 100:.0f} % of its text)" if len(unders) == 1 and COVER_SHARE <= share <= 0.9 else ""
            out.append((2 + _weight(at, times), top, f"{names[top]} covers {listed} {_when(at, times)}{part}"))
    # Each element its first line before any element a second, so ten lines name ten things.
    out.sort(key=lambda n: -n[0])
    seen: set = set()
    first = [n for n in out if not (n[1] in seen or seen.add(n[1]))]
    rest = [n for n in out if n not in first]
    return [(w, say) for w, _, say in first] + [(w - 10, say) for w, _, say in rest]


def _hidden(boxes: list[dict], i: int, g, kin: set, frame) -> bool:
    """Whether a later element much larger than this text (a screen, a panel; not a pointer or a badge, nor a
    frame-sized layout box), not one of its own parents, lies over nearly all of it."""
    for j in range(i + 1, len(boxes)):
        top = boxes[j]
        if top["id"] in kin or not _measured(top) or top.get("box") is None or boxes[i]["id"] in _lineage(boxes, j):
            continue
        box = _meet(top["box"], _clip(top, frame))
        if (HIDER_SIZE * _area(g) <= _area(box) <= WRAPPER_SHARE * _area(frame)
                and _area(_meet(box, g)) > HIDDEN_SHARE * max(1.0, _area(g))):
            return True
    return False


def _letters_together(cuts: dict, names: dict) -> dict:
    """Texts without an id cut on the same sides at the same times (split letters or words) as one text, in markup order."""
    groups: dict[tuple, list] = {}
    for (ident, sides, text), at in cuts.items():
        if ident.startswith(TEXT_PREFIX):
            groups.setdefault((sides, text, tuple(sorted(at))), []).append(ident)
    out = {k: v for k, v in cuts.items() if not k[0].startswith(TEXT_PREFIX)}
    for (sides, text, _), ids in groups.items():
        ids.sort(key=lambda i: int(i[len(TEXT_PREFIX):]))
        words = [names[i][len('the text "'):-1] for i in ids]
        joined = ("" if all(len(w) <= 2 for w in words) else " ").join(words)
        names[ids[0]] = f'the text "{joined if len(joined) <= 32 else joined[:30].rstrip() + "…"}"'
        out[(ids[0], sides, text)] = {t: max(cuts[(i, sides, text)].get(t, 0) for i in ids) for t in cuts[(ids[0], sides, text)]}
    return out


def _measured(b: dict) -> bool:
    return (not b["id"].startswith("rostrum-") or b["id"].startswith(TEXT_PREFIX)) and b.get("opacity", 1) >= 0.15


def _name(b: dict) -> str:
    return f'the text "{b["label"]}"' if b.get("label") else f"#{b['id']}"


def _clip(b: dict, frame):
    c = b.get("clip")
    return tuple(c) if c else frame


def _lineage(boxes: list[dict], i: int) -> set[str]:
    """The ids of the box's tagged ancestors (each box names its nearest one as `parent`)."""
    by_id = {b["id"]: b for b in boxes[:i]}
    out, p = set(), boxes[i].get("parent")
    while p and p not in out:
        out.add(p)
        p = by_id.get(p, {}).get("parent")
    return out


def _area(r) -> float:
    return max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])


def _meet(a, b):
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def _visible(r, frame) -> bool:
    return _area(_meet(r, frame)) > 0


def _small_enough(r, frame) -> bool:
    """A non-text element worth naming at an edge: smaller than the frame both ways (not a full-bleed background)."""
    return (r[2] - r[0]) < 0.8 * (frame[2] - frame[0]) and (r[3] - r[1]) < 0.8 * (frame[3] - frame[1])


def _outside(r, frame, clip=None) -> tuple[tuple[str, ...], float]:
    """The frame edges `r` passes, counting only edges its clipping parents reach (cut inside a parent is not by the frame)."""
    over = {"left": frame[0] - r[0], "top": frame[1] - r[1], "right": r[2] - frame[2], "bottom": r[3] - frame[3]}
    c = clip or frame
    reach = {"left": c[0] <= frame[0] + 1, "top": c[1] <= frame[1] + 1, "right": c[2] >= frame[2] - 1, "bottom": c[3] >= frame[3] - 1}
    sides = tuple(s for s, v in over.items() if v > EDGE_PX and reach[s])
    return sides, max((over[s] for s in sides), default=0.0)


def _sides(sides: tuple[str, ...]) -> str:
    return " and ".join(sides) + (" edges" if len(sides) > 1 else " edge")


# --- pictures ---

def _picture_notes(film: Film, times: list[float], pictures: list[Path]) -> list[tuple[float, str]]:
    from PIL import Image, ImageChops
    small = []
    for p in pictures:
        with Image.open(p) as im:
            small.append(im.convert("RGB").resize((160, max(1, round(160 * im.height / im.width))), Image.BILINEAR))
    bg = _hex(film.background)
    empty: dict[float, float] = {}
    colour: dict[float, tuple] = {}
    for t, im in zip(times, small):
        share, c = _one_colour(im)
        if share >= EMPTY_SHARE:
            empty[t], colour[t] = share, c
    out = []
    if empty:
        share = max(empty.values())
        c = colour[max(empty, key=empty.get)]
        name = "the background colour" if bg and _near(c, bg, 24) else "one colour (#%02x%02x%02x)" % c
        what = f"the frame {_when(empty, times)} is almost empty" if len(empty) == 1 else f"the frames {_when(empty, times)} are almost empty"
        out.append((1.5 + _weight(empty, times), f"{what}: {share * 100:.0f} % is {name}"))
    # Runs of consecutive frames that are the same picture.
    same = [_changed(a, b, ImageChops) < STILL_PIXELS for a, b in zip(small, small[1:])]
    i = 0
    while i < len(same):
        if not same[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(same) and same[j + 1]:
            j += 1
        a, b = times[i], times[j + 1]
        if b - a >= STILL_SPAN_S:
            out.append((1.2 + (b - a) / max(1e-6, times[-1] - times[0]),
                        f"nothing changes between {_s(a)} and {_s(b)} s ({j - i + 2} frames looked at)"))
        i = j + 1
    return out


def _one_colour(im) -> tuple[float, tuple]:
    """The share of pixels within a small distance of the most common colour, and that colour."""
    q = im.quantize(colors=8)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    top = counts[0][1]
    c = tuple(pal[top * 3: top * 3 + 3])
    near = sum(n for n, i in counts if _near(tuple(pal[i * 3: i * 3 + 3]), c, 10))
    return near / (im.width * im.height), c


def _changed(a, b, chops) -> float:
    d = chops.difference(a, b).convert("L").point(lambda v: 255 if v > 12 else 0)
    return d.histogram()[255] / (d.width * d.height)


def _near(a, b, tol) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def _hex(c: str) -> tuple | None:
    c = (c or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) if len(c) in (6, 8) else None
    except ValueError:
        return None


# --- times in words ---

def _s(t: float) -> str:
    return f"{t:.1f}" if abs(t * 10 - round(t * 10)) < 1e-6 else f"{t:.2f}"


def _runs(at: dict[float, object], times: list[float]) -> list[tuple[float, float]]:
    runs, start, prev = [], None, None
    for t in times:
        if t in at:
            start = t if start is None else start
            prev = t
        elif start is not None:
            runs.append((start, prev))
            start = None
    if start is not None:
        runs.append((start, prev))
    return runs


def _when(at: dict[float, object], times: list[float]) -> str:
    parts = [f"at {_s(a)} s" if a == b else f"from {_s(a)} to {_s(b)} s" for a, b in _runs(at, times)]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _weight(at: dict, times: list[float]) -> float:
    """How much of the looked-at film it holds for (0..1): longer problems first within a kind."""
    return len(at) / len(times)
