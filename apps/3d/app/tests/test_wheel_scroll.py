"""Every scrolling list in the 3D window scrolls by the kit's WheelScroll. Qt's own wheel left a list gliding for ~0.75 s,
and a click during the glide only stopped it: a Material ▾ start picked right after a wheel scroll did nothing, the
picker stayed open and ate the next click, so the next pick went to the item before (critic 3d-final, 4 of 16 picks).
"""
import re
from pathlib import Path

QML = Path(__file__).resolve().parents[1] / "qml"
SCROLLER = re.compile(r"^\s*(?:contentItem:\s*)?(Flickable|ListView|GridView)\s*\{", re.M)


def _block(text, start):
    """The text of the QML block whose `{` is at or after `start`."""
    i, depth = text.index("{", start), 0
    for j in range(i, len(text)):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i:j + 1]
    raise AssertionError("unbalanced braces")


def _scrollers():
    for f in sorted(QML.glob("*.qml")):
        text = f.read_text(encoding="utf-8")
        for m in SCROLLER.finditer(text):
            yield f.name, _block(text, m.start())
        if re.search(r"^(ListView|Flickable|GridView)\s*\{", text, re.M):      # the file's root is itself a list
            yield f.name, text


def test_every_scroller_has_wheel_scroll():
    bad = []
    for name, body in _scrollers():
        ident = re.search(r"^\s*id:\s*(\w+)", body, re.M)
        if not ident or not re.search(r"WheelScroll\s*\{\s*flick:\s*%s\b" % ident.group(1), body):
            bad.append(f"{name}: {body.splitlines()[0].strip()}…")
    assert not bad, "lists without WheelScroll { flick: <its id> }:\n" + "\n".join(bad)
