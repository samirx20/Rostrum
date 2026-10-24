"""A busy document for timing edits (about 60 top-level layers, shadows, keys, one big group). Not a template: a dev/perf scene
with the sample's layer names (card, title, lockup, dot, rule) so the `edittime` / `dragtime` steps run on it."""
from .sample import SOURCE as _BASE

_MORE = ['''
for i in range(24):
    s = shape(f"tile{i}", w=140, h=90, radius=14, fill="#2a3450", x=100 + (i % 12) * 150, y=90 + (i // 12) * 120)
    s.effect("shadow", dy=10, radius=20, strength=0.4)
    s.key("scale", {0.0: 0.9, 0.6 + i * 0.05: 1.0}, ease="snappy")
for i in range(16):
    t = text(f"label{i}", body=f"Label {i}", size=36, weight=600, x=120 + (i % 8) * 220, y=900 + (i // 8) * 60)
    t.key("opacity", {0.1 * i: 0, 0.1 * i + 0.8: 1}, ease="snappy")
for i in range(18):
    e = shape(f"orb{i}", shape="ellipse", w=30, h=30, fill="#ff7a59", x=60, y=300 + i * 30)
    e.key("x", {0.0: 60, 3.5: 1800 - i * 40}, ease="easeInOut")
with group("crowd", y=200, w=1200, h=120):
    for i in range(10):
        c = shape(f"crowd{i}", shape="ellipse", w=40, h=40, fill="#7aa8ff", x=60 + i * 110, y=60)
        c.key("y", {0.0: 40, 1.0 + i * 0.1: 80}, ease="easeInOut")
''']
SOURCE = _BASE + _MORE[0]
