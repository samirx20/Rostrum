# Lip sync proof (apps/2d/LIPSYNC.md): the H10 character (copied from proofs/2d-character/film.py, legs left out), standing
# and talking, framed waist-up (the rig scaled 2.6x) so the mouth reads. Nine drawn mouth shapes (X A B C D E F G H) sit on
# the face, bound to the neck bone; lipsync() keys them to line 1 of the voice-over. Run through MCP: lipsync_calls.json.
VO = r"C:\Users\Sam\.rostrum\waves\results\stage2\sound-voice\voice-over-on-cue.stems\vo.wav"
CLIP = (2.5, 9.0)                   # seconds of vo.wav; comp 0 = vo 2.5 s
LINE = "Every city keeps one hour for itself."
comp("talk", width=1920, height=1080, fps=30, duration=CLIP[1] - CLIP[0], background="#e9e3d7")
shape("wall", w=1920, h=1080, x=960, y=540, fill="#e9e3d7")
shape("wall_shade", shape="ellipse", w=1500, h=1100, x=960, y=600, fill="#ded6c6", opacity=0.8).effect("blur", radius=60)

HIP_X, HIP_Y = 580, 610
SHOULDER_Y = 440
MX, MY = 612, 385                   # the mouth's centre on the face (rig px)
INSIDE, TEETH, TONGUE, LIPS = "#5b2121", "#fbf7ef", "#d86a6a", "#c4786a"
W, H = 40, 28                       # every mouth is drawn in a 40 x 28 box


def capsule(id, cx, cy, w, h, color, **kw):
    return shape(id, w=w, h=h, radius=min(w, h) / 2, x=cx, y=cy, fill=color, **kw)


def part(id, d, color, line=0):
    if line:
        return path(id, d=d, w=W, h=H, x=W / 2, y=H / 2, filled=False, stroke=True, strokeColor=color, strokeWidth=line)
    return path(id, d=d, w=W, h=H, x=W / 2, y=H / 2, fill=color)


# Each shape: its parts back to front, (path data in the 40 x 28 box, colour, stroke width or 0 for a fill).
UPPER_C = ("M 11 9.6 C 17 8 23 8 29 9.6 L 28 12 C 22 11 18 11 12 12 Z", TEETH, 0)
MOUTHS = {
    "X": [("M 8 13 C 15 16 25 16 32 13 C 25 17.5 15 17.5 8 13 Z", INSIDE, 0)],
    "A": [("M 6 14 C 14 9 26 9 34 14 C 26 19 14 19 6 14 Z", LIPS, 0), ("M 8 14 L 32 14", INSIDE, 1.6)],
    "B": [("M 8 12 C 15 10 25 10 32 12 C 27 18 13 18 8 12 Z", INSIDE, 0),
          ("M 10 12 C 16 10.8 24 10.8 30 12 L 29 14.5 C 23 13.6 17 13.6 11 14.5 Z", TEETH, 0)],
    "C": [("M 8 10 C 15 7 25 7 32 10 C 30 22 10 22 8 10 Z", INSIDE, 0), UPPER_C,
          ("M 13 18 C 17 15 23 15 27 18 C 23 20.5 17 20.5 13 18 Z", TONGUE, 0)],
    "D": [("M 7 7 C 14 3 26 3 33 7 C 33 27 7 27 7 7 Z", INSIDE, 0),
          ("M 10 6.4 C 16 4.4 24 4.4 30 6.4 L 29.4 9 C 23 8 17 8 10.6 9 Z", TEETH, 0),
          ("M 12 21 C 16 16.5 24 16.5 28 21 C 24 24 16 24 12 21 Z", TONGUE, 0)],
    "E": [("M 12 14 C 12 6 28 6 28 14 C 28 23 12 23 12 14 Z", INSIDE, 0),
          ("M 15 19 C 18 16.5 22 16.5 25 19 C 22 21 18 21 15 19 Z", TONGUE, 0)],
    "F": [("M 14 14 C 14 8.5 26 8.5 26 14 C 26 19.5 14 19.5 14 14 Z", LIPS, 0),
          ("M 16.5 14 C 16.5 11 23.5 11 23.5 14 C 23.5 17 16.5 17 16.5 14 Z", INSIDE, 0)],
    "G": [("M 9 12 C 15 10 25 10 31 12 L 31 15 C 25 16 15 16 9 15 Z", INSIDE, 0),
          ("M 10 11.8 C 16 10.4 24 10.4 30 11.8 L 30 15.2 C 24 14.6 16 14.6 10 15.2 Z", TEETH, 0),
          ("M 9 15 C 15 19 25 19 31 15 C 25 16.5 15 16.5 9 15 Z", LIPS, 0)],
    "H": [("M 8 10 C 15 7 25 7 32 10 C 30 22 10 22 8 10 Z", INSIDE, 0), UPPER_C,
          ("M 14 19 C 15 12 25 12 26 19 C 22 21 18 21 14 19 Z", TONGUE, 0)],
}

with rig("puppet", w=1920, h=1080, x=960, y=560, anchorX=600 / 1920, anchorY=420 / 1080, scale=2.6):
    far_up = capsule("far_arm_up", HIP_X, SHOULDER_Y + 40, 30, 130, "#b3421f")
    far_lo = capsule("far_arm_lo", HIP_X, SHOULDER_Y + 135, 26, 116, "#a37a5a")
    torso = capsule("torso", HIP_X, 517, 92, 232, "#e4572e")
    neckl = capsule("neck_pic", HIP_X + 4, 410, 34, 70, "#e8b894")
    head = shape("head", shape="ellipse", w=104, h=116, x=HIP_X + 14, y=352, fill="#f0c7a2")
    hair = shape("hair", shape="ellipse", w=100, h=72, x=HIP_X - 6, y=318, fill="#2b2118")
    eye = shape("eye", shape="ellipse", w=11, h=15, x=HIP_X + 52, y=352, fill="#1a1a1a")
    nose = shape("nose", shape="ellipse", w=22, h=18, x=HIP_X + 68, y=368, fill="#e6b08a")
    mouths = {}
    for s, parts in MOUTHS.items():
        with group("mouth_" + s, w=W, h=H, x=MX, y=MY, scale=0.75) as g:
            for i, (d, color, line) in enumerate(parts):
                part("mouth_%s_%d" % (s, i), d, color, line)
        mouths[s] = g
    near_arm = capsule("near_arm", HIP_X, SHOULDER_Y + 92, 32, 217, "#f26a3a")

    hip = bone("hip", x=HIP_X, y=HIP_Y, angle=90, length=0)
    spine = bone("spine", parent=hip, x=HIP_X, y=HIP_Y, angle=-90, length=HIP_Y - SHOULDER_Y)
    neck = bone("neck", parent=spine, length=40)
    far_u = bone("far_arm_u", parent=spine, x=HIP_X, y=SHOULDER_Y, angle=90, length=95)
    far_l = bone("far_arm_l", parent=far_u, length=90)
    near_u = bone("near_arm_u", parent=spine, x=HIP_X, y=SHOULDER_Y, angle=90, length=95)
    near_l = bone("near_arm_l", parent=near_u, length=90)
    for layer, b in ((far_up, far_u), (far_lo, far_l), (torso, spine), (neckl, neck), (head, neck), (hair, neck),
                     (eye, neck), (nose, neck), *((m, neck) for m in mouths.values())):
        bind(layer=layer, bone=b)
    bind(layer=near_arm, bone=near_u, bone2=near_l, soft=34, grid=24)

    # a standing talk: slow breathing in the spine, small head nods on the stressed words, a hand that moves a little
    spine.key("rotation", {0: 0, 1.6: 1.2, 3.2: -0.4, 4.8: 1.0, 6.5: 0}, ease="smooth")
    neck.key("rotation", {0: 0, 0.7: -2, 1.3: 1.5, 2.1: -2.5, 2.9: 0.5, 3.6: -3, 4.4: 1, 5.2: -1.5, 6.5: 0}, ease="smooth")
    near_u.key("rotation", {0: 6, 1.2: 12, 2.6: 8, 4.0: 14, 5.6: 7, 6.5: 6}, ease="smooth")
    near_l.key("rotation", {0: -14, 1.2: -32, 2.6: -20, 4.0: -36, 5.6: -16, 6.5: -14}, ease="smooth")
    far_u.key("rotation", {0: -4, 6.5: -6}, ease="smooth")
    far_l.key("rotation", {0: -10, 6.5: -12}, ease="smooth")
    eye.key("scaleY", {0: 1, 1.9: 1, 1.95: 0.1, 2.05: 1, 4.7: 1, 4.75: 0.1, 4.85: 1}, ease="linear")

    said = lipsync(VO, at=0, start=CLIP[0], end=CLIP[1], text=LINE, shapes=mouths)
