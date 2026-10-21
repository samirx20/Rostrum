comp("slides", width=1920, height=1080, fps=30, duration=10, background="#0a0b10")

# --- title: snaps in (scale 1.3 -> 1 with opacity, 0.12 s) ------------------------------------------------------
title = text("title", body="Everything, faster.", size=124, weight=760, x=960, y=150, color="#f5f5f7", tracking=-0.02,
             opacity=0)
title.key("opacity", {0.30: 0, 0.42: 1}, ease="snappy")
title.key("scale", {0.30: 1.3, 0.42: 1.0}, ease="snappy")


def card(id, label, w, h, x, y, c1, c2):
    """A rounded card with a title: one group, so it moves as one."""
    g = group(id, w=w, h=h, x=x, y=y)
    with g:
        s = shape(id + "_bg", shape="rect", w=w, h=h, radius=34, x=w / 2, y=h / 2, fill=c1)
        s.effect("gradient", style="linear", angle=135, color1=c1, color2=c2)
        s.effect("shadow", dx=0, dy=24, radius=50, color="#000000", strength=0.55)
        text(id + "_label", body=label, size=58, weight=700, color="#ffffff", x=w / 2, y=h / 2)
    return g


# --- 1. one big slow slide from the left (0.8 s, long travel) -----------------------------------------------------
big = card("card_big", "Design", 600, 340, 480, 500, "#3d5afe", "#7c4dff")
big.key("x", {1.00: (-420, "heavy"), 1.80: (480, "linear"), 8.20: (480, "easeIn"), 8.60: -420})

# --- 2. a quick flick in from the right (0.25 s) ------------------------------------------------------------------
flick = card("card_flick", "Motion", 520, 240, 1440, 400, "#ff7a59", "#ff3d71")
flick.key("x", {2.60: (2300, "snappy"), 2.85: (1440, "linear"), 8.50: (1440, "easeIn"), 8.78: 2300})

# --- 3. slides in from the left and lands with a snap (spring overshoot) ---------------------------------------
snap = card("card_snap", "Sound", 520, 190, 1440, 730, "#00c2a8", "#2ee6d6")
snap.key("x", {3.40: (-320, "spring"), 3.80: (1440, "linear"), 8.80: (1440, "easeIn"), 9.15: 2300})

# --- 4. a vertical move: rises from below ---------------------------------------------------------------------
up = card("card_up", "Edit", 400, 200, 480, 800, "#ffb300", "#ff8f00")
up.key("y", {4.20: (1400, "natural"), 4.70: (800, "linear"), 9.00: (800, "easeIn"), 9.40: 1400})

# --- counter: ten text layers, each shown for one tick (text can't be keyed, opacity with hold can) -----------
TICK = 0.2
for i in range(10):
    t0 = 5.0 + TICK * i
    c = text("counter_%d" % i, body=str(i), size=300, weight=800, color="#f5f5f7", x=960, y=520, opacity=0)
    if i == 9:
        c.key("opacity", {0.0: (0, "hold"), t0: 1})
    else:
        c.key("opacity", {0.0: (0, "hold"), t0: (1, "hold"), t0 + TICK: 0})

# --- button: fades in, then gets tapped (1 -> 0.92 -> 1 in 0.18 s) ------------------------------------------------
with group("button", w=300, h=96, x=960, y=830, opacity=0) as btn:
    shape("button_bg", shape="rect", w=300, h=96, radius=48, x=150, y=48, fill="#f5f5f7")
    text("button_label", body="Get started", size=40, weight=650, color="#0a0b10", x=150, y=48)
btn.key("opacity", {4.60: (0, "snappy"), 4.85: 1})
btn.key("scale", {7.40: (1.0, "easeOut"), 7.49: (0.92, "easeOut"), 7.58: 1.0})
