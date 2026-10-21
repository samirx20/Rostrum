# A ~4 s parallax shot for the camera proof (apps/2d/CAMERA.md): three depth planes of plain shapes, a title locked
# to the screen, and one camera that pans right, pushes in and rolls a little. Run through MCP: camera_calls.json.
comp("parallax", width=1920, height=1080, fps=30, duration=4, background="#bcd3e0")

# ---- far: hills (depth 3: a pan moves them a quarter as much, the push-in grows them least) ----
for i, (x, w, h, c) in enumerate([(-300, 1300, 520, "#8fa9b8"), (700, 1500, 640, "#7f9bab"), (1900, 1400, 560, "#8fa9b8"), (2900, 1300, 600, "#7f9bab")]):
    shape("hill%d" % i, shape="ellipse", w=w, h=h, x=x, y=760, anchorX=0, anchorY=0.5, fill=c, depth=3)
shape("sun", shape="ellipse", w=150, h=150, x=1420, y=250, fill="#f4e3b5", depth=6)

# ---- mid: a row of block trees on a strip of land (depth 1: half the pan) ----
shape("land", w=6000, h=420, x=-2000, y=760, anchorX=0, anchorY=0, fill="#5d7f5a", depth=1)
for i in range(14):
    x = -500 + i * 330 + (i % 3) * 40
    h = 170 + (i * 37) % 90
    shape("trunk%d" % i, w=18, h=60, x=x, y=780, anchorY=1, fill="#3b3a2c", depth=1)
    shape("crown%d" % i, shape="ellipse", w=110, h=h, x=x, y=730, anchorY=1, fill="#3f6a45", depth=1)

# ---- near: posts and a ground strip close to the camera (depth -0.4: about 1.7× the pan) ----
shape("ground", w=9000, h=260, x=-3000, y=930, anchorX=0, anchorY=0, fill="#2f3b2a", depth=-0.4)
for i in range(16):
    shape("post%d" % i, w=46, h=420, radius=6, x=-900 + i * 360, y=1000, anchorY=1, fill="#1e2420", depth=-0.4)

# ---- the title: locked to the screen, the camera never moves it ----
title = text("title", body="Parallax", size=120, weight=700, x=960, y=180, color="#1b2a33", screenLock=True)
title.key("opacity", {0.2: 0, 0.9: 1})

# ---- the camera: pan right, push in from 1.5 s, roll a little ----
cam = camera("cam")
cam.key("x", {0: 760, 4: 1300}, ease="smooth")
cam.key("zoom", {1.5: 1, 4: 1.35}, ease="smooth")
cam.key("rotation", {1.0: 0, 4: -3}, ease="smooth")
