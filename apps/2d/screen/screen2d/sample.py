"""A small document to open the screen on while developing (a few layers, an effect, a mask, some keys).
Not a template: it only exercises the screen's panels."""
SOURCE = '''
comp("screen_sample", width=1920, height=1080, fps=30, duration=4, background="#0b0d14")
card = shape("card", w=1000, h=460, radius=36, fill="#1b2233", y=540)
card.effect("shadow", dy=30, radius=60, strength=0.6)
card.key("scale", {0.0: 0.92, 0.8: 1.0}, ease="snappy")
title = text("title", body="Rostrum", size=200, weight=760, y=500)
title.key("opacity", {0.2: 0, 0.9: 1}, ease="snappy")
title.key("y", {0.2: 560, 1.0: 500}, ease="natural")
with group("lockup", y=660, w=600, h=80):
    dot = shape("dot", shape="ellipse", w=24, h=24, fill="#ff7a59", x=300, y=40)
    dot.key("x", {1.0: 60, 2.2: 540}, ease="easeInOut")
    line = shape("rule", w=420, h=4, radius=2, fill="#ff7a59", x=300, y=40, opacity=0.5)
    line.mask("rule_wipe", w=420, h=4).key("w", {1.0: 0, 2.0: 420})
'''
