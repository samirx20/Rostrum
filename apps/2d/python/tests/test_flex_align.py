"""`justify` / `align` in a row, column and stack place the children exactly where CSS would, inside the padding box,
on the real engine: row / column as CSS flexbox (justify along the line, align across it), a stack as one shared cell
(justify left to right, align top to bottom: the same axes as a row). A text is placed by its box, not its anchor."""
import pytest

from rostrum2d import layout, run_source, settings, textsize
from rostrum2d.evaluate import resolve

pytestmark = pytest.mark.skipif(settings.engine_missing_reason() is not None, reason=settings.engine_missing_reason() or "")

HEAD = 'comp("main", width=1920, height=1080, fps=30, duration=2)\n'
W, H, PX, PY, GAP = 400, 200, 20, 30, 10
KIDS = [(50, 30), (70, 20), (40, 44)]


def solved(src):
    comp = run_source(HEAD + src, "s.py")["comps"][0]
    return comp, layout.solve(comp, 0.0)


def boxes(kind, **words):
    args = ", ".join(f'{k}="{v}"' for k, v in words.items())
    kids = "\n".join(f'    shape("k{i}", w={w}, h={h})' for i, (w, h) in enumerate(KIDS))
    _, got = solved(f'with {kind}("box", x=0, y=0, w={W}, h={H}, padding_x={PX}, padding_y={PY}, gap={GAP}, {args}):\n{kids}\n')
    return flat((got[f"k{i}"]["x"] - w / 2, got[f"k{i}"]["y"] - h / 2) for i, (w, h) in enumerate(KIDS))     # top-lefts


def flat(pairs):
    return [v for pair in pairs for v in pair]


def flex_main(justify, sizes, room):
    """Where CSS justify-content puts each child along the line (from the padding edge)."""
    n, free = len(sizes), room - sum(sizes) - GAP * (len(sizes) - 1)
    first, extra = {"start": (0, 0), "center": (free / 2, 0), "end": (free, 0), "between": (0, free / (n - 1)),
                    "around": (free / n / 2, free / n), "evenly": (free / (n + 1), free / (n + 1))}[justify]
    out, at = [], first
    for s in sizes:
        out.append(at)
        at += s + GAP + extra
    return out


def cross(align, size, room):
    return {"start": 0, "stretch": 0, "center": (room - size) / 2, "end": room - size}[align]     # a fixed size never stretches


@pytest.mark.parametrize("kind", ["row", "column"])
@pytest.mark.parametrize("justify", ["start", "center", "end", "between", "around", "evenly"])
@pytest.mark.parametrize("align", ["start", "center", "end", "stretch"])
def test_row_and_column_are_css_flexbox(kind, justify, align):
    got = boxes(kind, justify=justify, align=align)
    iw, ih = W - 2 * PX, H - 2 * PY
    if kind == "row":
        xs = flex_main(justify, [w for w, _ in KIDS], iw)
        want = [(PX + x, PY + cross(align, h, ih)) for x, (_, h) in zip(xs, KIDS)]
    else:
        ys = flex_main(justify, [h for _, h in KIDS], ih)
        want = [(PX + cross(align, w, iw), PY + y) for y, (w, _) in zip(ys, KIDS)]
    assert got == pytest.approx(flat(want), abs=0.01)


@pytest.mark.parametrize("justify", ["start", "center", "end"])
@pytest.mark.parametrize("align", ["start", "center", "end"])
def test_stack_justify_is_left_to_right_and_align_top_to_bottom(justify, align):
    got = boxes("stack", justify=justify, align=align)
    at = {"start": 0, "center": 0.5, "end": 1}
    want = [(PX + at[justify] * (W - 2 * PX - w), PY + at[align] * (H - 2 * PY - h)) for w, h in KIDS]
    assert got == pytest.approx(flat(want), abs=0.01)


@pytest.mark.parametrize("justify, align, corner", [("start", "end", "bottom-left"), ("end", "start", "top-right"),
                                                    ("center", "center", "middle")])
def test_a_text_in_a_card_sits_by_its_box(justify, align, corner):
    """The phone card: a text in a padded stack lands in the asked corner of the padding box, whatever its anchor."""
    comp, got = solved(f'with stack("card", x=0, y=0, w=400, h=220, padding=36, justify="{justify}", align="{align}"):\n'
                       f'    text("t", body="Ask a question", size=40, anchor="bottom-right")\n')
    card = next(c for c in comp["layers"] if c["id"] == "card")
    p = resolve(card["layers"][0], 0.0)
    w, h = textsize.size(p)
    left, top = got["t"]["x"] - w, got["t"]["y"] - h        # anchor bottom-right: x, y is the box's bottom-right
    want = {"bottom-left": (36, 220 - 36 - h), "top-right": (400 - 36 - w, 36),
            "middle": (36 + (400 - 72 - w) / 2, 36 + (220 - 72 - h) / 2)}[corner]
    assert [left, top] == pytest.approx(list(want), abs=0.5)      # its laid-out and own widths agree to half a px
