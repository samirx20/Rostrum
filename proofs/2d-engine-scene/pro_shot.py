# P-2D's 3-second animated shot (proofs/2d-renderer/driver/shot.py: two glowing orbs drifting, a turning ring,
# "Pro" rising in heavier and tighter, a glass card with "BEYOND PRO"), written again as a Rostrum2D script so it
# goes through the scene description. Same layout and timing; what the scene description can't say yet is noted.
# "out" in shot.py = snappy, "inout" = easeInOut (shot.py eases into a key; here the ease is on the key it leaves).

W, H = 1920, 1080
comp("pro", width=W, height=H, fps=60, duration=3, background="#000000")

# The page's radial background (shot.py: radial-gradient(120% 90% at 50% 110%, #1a0b2e, #07040d 55%, #000)).
sky = shape("sky", shape="ellipse", w=2600, h=1700, x=960, y=1180)
sky.effect("gradient", id="sky_fill", style="radial", color1="#1a0b2e", color2="#000000", middle=True,
           color3="#07040d", mid=0.55)

orb1 = shape("orb1", shape="ellipse", w=640, h=640, x=480, y=500)
orb1.effect("gradient", id="orb1_fill", style="radial", color1="#ff6a3d", color3="#c2185b", middle=True, mid=0.6,
            color2="#4a148c")
orb1.effect("blur", id="orb1_soft", radius=80)
orb1.key("x", {0: 480, 3: 680}, ease="easeInOut")
orb1.key("opacity", {0: 0, 1.0: 1}, ease="snappy")

orb2 = shape("orb2", shape="ellipse", w=720, h=560, x=1620, y=640)
orb2.effect("gradient", id="orb2_fill", angle=140, color1="#00c6ff", color3="#0072ff", middle=True, mid=0.5,
            color2="#7b2ff7")
orb2.effect("blur", id="orb2_soft", radius=80)
orb2.key("x", {0: 1620, 3: 1360}, ease="easeInOut")
orb2.key("opacity", {0.2: 0, 1.2: 1}, ease="snappy")

# The ring (shot.py's conic-gradient ring has no scene equivalent yet: an outlined ellipse with a glow).
ring = shape("ring", shape="ellipse", w=780, h=780, x=960, y=540, fill="#000000", blend="screen", stroke=True,
             strokeColor="#ff8a5c", strokeWidth=6)
ring.effect("glow", id="ring_glow", radius=30, strength=1.2)
ring.key("rotation", {0: -40, 3: 40}, ease="linear")
ring.key("scale", {0: 0.8, 1.6: 1}, ease="snappy")
ring.key("opacity", {0: 0, 1.0: 1}, ease="snappy")

# "Pro": rises, gains weight, tightens; a wipe from the top (shot.py's soft-edged mask: a hard edge here, since
# a feathered rect mask isn't drawn yet).
pro = text("pro_word", body="Pro", size=400, weight=200, lineHeight=1.0, color="#ffffff", x=960, y=450)
pro.key("weight", {0.3: 200, 2.2: 860}, ease="snappy")
pro.key("tracking", {0.3: 0.12, 2.2: -0.06}, ease="snappy")
pro.key("y", {0.3: 530, 1.8: 450}, ease="snappy")
pro.effect("glow", id="pro_glow", radius=60, ownColor=False, color="#ff8c5a").key(
    "strength", {1.2: 0, 2.6: 0.8}, ease="snappy")
pro.mask("pro_wipe", x=-400, y=0, w=1800, h=0).key("h", {0.3: 0, 2.0: 520}, ease="snappy")

# The glass card (no backdrop blur in the scene description yet: a dark gradient card with a fine outline).
with group("card", x=960, y=1075, w=800, h=150) as card:
    card.key("y", {1.4: 1075, 2.6: 895}, ease="snappy")
    card.key("opacity", {1.4: 0, 2.2: 1}, ease="snappy")
    slab = shape("card_slab", w=800, h=150, x=400, y=75, radius=75, stroke=True, strokeColor="#5b5068", strokeWidth=1)
    slab.effect("gradient", id="card_fill", angle=160, color1="#2b2238", color2="#120d1a")
    slab.effect("shadow", id="card_shadow", dy=40, radius=120, strength=0.5)
    words = text("card_words", body="BEYOND PRO", size=52, weight=300, color="#ffffff", x=400, y=75)
    words.key("tracking", {1.4: 0.5, 3.0: 0.16}, ease="snappy")
