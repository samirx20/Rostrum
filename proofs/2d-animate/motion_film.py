comp("motion", width=1920, height=1080, fps=30, duration=3, background="#15171d", shutter=180, shutterSamples=12)

# ---- lane 1: a whip across the frame and back, smeared (a stretch along its real velocity) ----
shape("whip_lane", w=1700, h=4, x=960, y=230, fill="#2a2e38")
whip = shape("whip", w=220, h=110, radius=28, x=220, y=230, fill="#f2b134")
whip.key("x", {0: 220, 0.45: (220, "easeInOut"), 0.75: 1700, 1.7: (1700, "snappy"), 2.0: 220})
whip.effect("smear", amount=1.0, max=5, minSpeed=4, stretch="behind", keepArea=True)

# ---- lane 2: a ball bouncing along the floor, with a trail of its earlier selves ----
FLOOR = 820
shape("floor", w=1920, h=260, x=960, y=FLOOR + 130, fill="#1d2029")
ball = shape("ball", shape="ellipse", w=100, h=100, x=180, y=420, fill="#e4572e")
ball.key("x", {0: 180, 3: 1080}, ease="linear")
ground = FLOOR - 50
tops = [420, 500, 590, 670]
ys, t = {}, 0.0
for i, top in enumerate(tops):
    fall = math.sqrt((ground - top) / 1750)          # time to fall from this top (a constant pull)
    ys[t] = (top, "easeIn")                          # speeding up on the way down
    t += fall
    ys[round(t, 4)] = (ground, "easeOut")            # slowing down on the way up
    if i + 1 < len(tops):
        t += math.sqrt((ground - tops[i + 1]) / 1750)
ball.key("y", ys)
ball.effect("trail", copies=6, spacing=2, fade=0.65)

# ---- lane 3: a spinner that speeds up and slows down (motion blur shows the spin) ----
with group("spinner", w=380, h=380, x=1480, y=600) as spinner:
    shape("bar_a", w=380, h=44, radius=22, x=190, y=190, fill="#5fb3f0")
    shape("bar_b", w=44, h=380, radius=22, x=190, y=190, fill="#5fb3f0")
    shape("hub", shape="ellipse", w=90, h=90, x=190, y=190, fill="#f4f1ea")
    shape("tip", shape="ellipse", w=60, h=60, x=190, y=22, fill="#f4f1ea")
spinner.key("rotation", {0.3: (0, "easeInOut"), 2.7: 1440})
