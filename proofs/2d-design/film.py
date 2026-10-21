comp("launch", width=1920, height=1080, fps=30, duration=4, background="#06070b")

warm = shape("warm", shape="ellipse", w=760, h=760, x=700, y=520)
warm.effect("gradient", style="conic", angle=30, color1="#ff5a3c", color2="#ff5a3c", middle=True, color3="#7a3cff", mid=0.5)
warm.effect("blur", radius=70)
warm.key("x", {0: 660, 4: 760}, ease="natural")
warm.key("rotation", {0: 0, 4: 40}, ease="natural")

cool = shape("cool", shape="ellipse", w=600, h=600, x=1260, y=610)
cool.effect("gradient", style="radial", color1="#38d9ff", color2="#06070b")
cool.effect("blur", radius=40)
cool.key("x", {0: 1300, 4: 1220}, ease="natural")

ride = text("ride", body="MADE TO MOVE  \u00b7  MADE TO MOVE  \u00b7  MADE TO MOVE  \u00b7  MADE TO MOVE",
            font="Inter", size=28, weight=640, tracking=0.3, color="#ffd36b", x=0, y=0, anchorX=0, anchorY=0,
            path="M-60 794 C300 764 480 274 760 274 C1060 274 1120 674 1420 674 C1640 674 1800 404 1990 234",
            letterDelay=0.012)
ride.key("opacity", {0.35: 0, 0.7: 1}, ease="smooth")
ride.key("pathOffset", {0: -40, 4: 380}, ease="linear")

card = shape("card", w=820, h=400, radius=44, fill="#f4f6ff", x=960, y=560)
card.effect("backdrop", radius=46, fillAmount=0.14, saturate=1.7)
card.effect("shadow", dy=36, radius=70, strength=0.35)
card.key("y", {1.0: 660, 1.9: 560}, ease="snappy")
card.key("opacity", {1.0: 0, 1.5: 1}, ease="smooth")
card.key("scale", {1.9: 1.0, 4.0: 1.025}, ease="natural")

title = text("title", body="Rostrum2D", font="Inter", size=132, weight=720, tracking=-0.025, color="#ffffff",
             x=960, y=530, letterDelay=0.035, letterOrder="center")
title.key("y", {1.35: 585, 2.15: 530}, ease="snappy")
title.key("opacity", {1.35: 0, 1.8: 1}, ease="smooth")
title.effect("shadow", dy=6, radius=24, strength=0.25)

sub = text("sub", body="Draw it. Set it. Move it.", font="Inter", size=38, weight=460, tracking=0.03,
           color="#eef0f8", x=960, y=640)
wipe = sub.mask("sub_wipe", x=-1300, y=-260, w=1000, h=560, feather=150, angle=18)
wipe.key("x", {2.0: -1300, 3.1: 0}, ease="natural")
