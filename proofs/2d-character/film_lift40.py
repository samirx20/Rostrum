comp("walk", width=1920, height=1080, fps=30, duration=2, background="#e9e3d7")

# ---- numbers (px). The body walks left to right; one stride cycle = 1 s, a foot is planted for half of it ----
HIP_X, HIP_Y = 580, 610            # rest: legs straight, ankle on y = 870, sole on the floor at y = 900
THIGH, SHIN, FOOT = 135, 125, 70
ANKLE_Y, FLOOR = 870, 900
SPEED = 380                         # body px per second (hips moveX)
REACH = 90                          # foot lands this far ahead of the hips and leaves this far behind
LIFT = 40                           # foot height at mid swing
SHOULDER_Y, NECK_Y = 440, 440 - 40  # shoulder joint, neck joint

# ---- floor, floor marks and a soft shadow that follows the body ----
shape("floor", w=1920, h=180, x=0, y=900, anchorX=0, anchorY=0, fill="#cfc4b0")
for i in range(10):
    shape("mark%d" % i, w=70, h=8, radius=4, x=120 + i * 200, y=960, fill="#b3a68f")
sh = shape("shadow", shape="ellipse", w=330, h=34, x=HIP_X, y=FLOOR + 2, fill="#8f836f", opacity=0.55)
sh.effect("blur", radius=10)
sh.key("x", {0: HIP_X, 2: HIP_X + 2 * SPEED}, ease="linear")


def capsule(id, cx, cy, w, h, color, **kw):
    return shape(id, w=w, h=h, radius=min(w, h) / 2, x=cx, y=cy, fill=color, **kw)


with rig("puppet", w=1920, h=1080, x=0, y=0, anchorX=0, anchorY=0):
    # ---- pictures (placed at rest), back to front: far arm, far leg, torso, head, near leg, near arm ----
    far_up = capsule("far_arm_up", HIP_X, SHOULDER_Y + 40, 30, 100 + 30, "#b3421f")
    far_lo = capsule("far_arm_lo", HIP_X, SHOULDER_Y + 95 + 40, 26, 90 + 26, "#a37a5a")
    far_th = capsule("far_thigh", HIP_X, HIP_Y + THIGH / 2, 48, THIGH + 48, "#1f2c3d")
    far_sh = capsule("far_shin", HIP_X, HIP_Y + THIGH + SHIN / 2, 38, SHIN + 38, "#1f2c3d")
    far_ft = capsule("far_foot", HIP_X + 22, FLOOR - 18, FOOT + 22, 36, "#0d1118")
    torso = capsule("torso", HIP_X, 517, 92, 232, "#e4572e")
    neckl = capsule("neck_pic", HIP_X + 4, 410, 34, 70, "#e8b894")
    head = shape("head", shape="ellipse", w=104, h=116, x=HIP_X + 14, y=352, fill="#f0c7a2")
    hair = shape("hair", shape="ellipse", w=100, h=72, x=HIP_X - 6, y=318, fill="#2b2118")
    eye = shape("eye", shape="ellipse", w=11, h=15, x=HIP_X + 52, y=352, fill="#1a1a1a")
    nose = shape("nose", shape="ellipse", w=22, h=18, x=HIP_X + 68, y=368, fill="#e6b08a")
    near_th = capsule("near_thigh", HIP_X, HIP_Y + THIGH / 2, 52, THIGH + 52, "#2e4057")
    near_sh = capsule("near_shin", HIP_X, HIP_Y + THIGH + SHIN / 2, 40, SHIN + 40, "#2e4057")
    near_ft = capsule("near_foot", HIP_X + 22, FLOOR - 18, FOOT + 22, 36, "#161c26")
    near_arm = capsule("near_arm", HIP_X, SHOULDER_Y + 92, 32, 185 + 32, "#f26a3a")   # ONE picture, bend-bound

    # ---- bones ----
    hip = bone("hip", x=HIP_X, y=HIP_Y, angle=90, length=0)
    spine = bone("spine", parent=hip, x=HIP_X, y=HIP_Y, angle=-90, length=HIP_Y - SHOULDER_Y)
    neck = bone("neck", parent=spine, length=40)
    far_u = bone("far_arm_u", parent=spine, x=HIP_X, y=SHOULDER_Y, angle=90, length=95)
    far_l = bone("far_arm_l", parent=far_u, length=90)
    near_u = bone("near_arm_u", parent=spine, x=HIP_X, y=SHOULDER_Y, angle=90, length=95)
    near_l = bone("near_arm_l", parent=near_u, length=90)
    legs = {}
    for side in ("near", "far"):
        th = bone(side + "_thigh_b", parent=hip, x=HIP_X, y=HIP_Y, angle=90, length=THIGH)
        sn = bone(side + "_shin_b", parent=th, length=SHIN)
        ft = bone(side + "_foot_b", parent=sn, x=HIP_X, y=ANKLE_Y, angle=0, length=FOOT)
        legs[side] = (th, sn, ft)

    # ---- binds: every part follows a bone. The near arm is the one bend bind (one picture, bends at the elbow) ----
    bind(layer=far_up, bone=far_u)
    bind(layer=far_lo, bone=far_l)
    bind(layer=torso, bone=spine)
    bind(layer=neckl, bone=neck)
    bind(layer=head, bone=neck)
    bind(layer=hair, bone=neck)
    bind(layer=eye, bone=neck)
    bind(layer=nose, bone=neck)
    bind(layer=near_arm, bone=near_u, bone2=near_l, soft=34, grid=24)
    for side, (a, b, c) in (("near", (near_th, near_sh, near_ft)), ("far", (far_th, far_sh, far_ft))):
        bind(layer=a, bone=legs[side][0])
        bind(layer=b, bone=legs[side][1])
        bind(layer=c, bone=legs[side][2])

    # ---- IK legs: the shin is the lower bone; the knee bends forward ----
    ik_n = ik("near_foot_ik", bone=legs["near"][1], bend="clockwise")
    ik_f = ik("far_foot_ik", bone=legs["far"][1], bend="clockwise")

    # ---- the walk ----
    def hip_pos(t):
        return HIP_X + SPEED * t, HIP_Y + 26 + 8 * math.cos(4 * math.pi * t)   # lowest at the steps, highest mid-stance

    def smooth(s):
        return s * s * (3 - 2 * s)

    def foot_model(phase, t):
        """Where the ankle target is at time t (my own copy of the keys below; only used to keep the foot flat)."""
        n = math.floor(t - phase + 0.0001)                  # stride number; the foot lands at phase + n and lifts half a second later
        u = t - phase - n                                   # 0..1 inside the stride: 0-0.5 planted, 0.5-1 swing
        land = lambda k: HIP_X + SPEED * (phase + k) + REACH
        if u < 0.5:
            return land(n), ANKLE_Y, 0.0
        s = (u - 0.5) * 2
        lift = LIFT * smooth(2 * s) if s < 0.5 else LIFT * smooth(2 - 2 * s)
        return land(n) + (land(n + 1) - land(n)) * smooth(s), ANKLE_Y - lift, s

    def flat_foot(phase, t):
        """FK turn of the foot bone: cancels the shin's turn so the sole stays flat, plus toe-down at lift, toe-up at landing."""
        x, y, s = foot_model(phase, t)
        hx, hy = hip_pos(t)
        dx, dy = x - hx, y - hy
        d = min(math.sqrt(dx * dx + dy * dy), THIGH + SHIN - 0.01)
        a = math.acos((THIGH * THIGH + d * d - SHIN * SHIN) / (2 * THIGH * d))
        thigh_a = math.atan2(dy, dx) - a
        kx, ky = hx + THIGH * math.cos(thigh_a), hy + THIGH * math.sin(thigh_a)
        shin_a = math.degrees(math.atan2(y - ky, x - kx))
        toe = 0.0
        if s > 0:
            toe = 28 * (1 - s / 0.4) if s < 0.4 else -16 * math.sin(math.pi * (s - 0.4) / 0.6)
        return 90 - shin_a + toe

    for ikh, side, phase in ((ik_n, "near", 0.0), (ik_f, "far", 0.5)):
        # target keys at the lift, mid swing and landing; "pin" 1 while the foot is on the floor (hold ease)
        k0 = phase - 1.0                                    # first stride seen starts before t = 0
        xs, ys, pins = {}, {}, {}
        for n in range(0, 4):
            land = phase - 1.0 + n                          # landing time of stride n
            lx = HIP_X + SPEED * land + REACH
            nx = lx + SPEED
            if 0 <= land <= 2.0:
                xs[land], ys[land], pins[land] = lx, ANKLE_Y, 1
            lift = land + 0.5
            if 0 <= lift <= 2.0:
                xs[lift], ys[lift], pins[lift] = lx, ANKLE_Y, 0
            mid = land + 0.75
            if 0 <= mid <= 2.0:
                ys[mid] = ANKLE_Y - LIFT
        if 0.0 not in xs:                                   # the foot is part-way through a swing at t = 0
            x0, y0, s0 = foot_model(phase, 0.0)
            xs[0.0], ys[0.0], pins[0.0] = x0, y0, 0
        ikh.key("targetX", {t: xs[t] for t in xs}, ease="smooth")
        ikh.key("targetY", {t: ys[t] for t in ys}, ease="smooth")
        ikh.key("pin", {t: pins[t] for t in pins}, ease="hold")
        legs[side][2].key("rotation", {round(i / 15, 4): round(flat_foot(phase, i / 15), 2) for i in range(0, 31)}, ease="linear")

    # hips travel and bob (root bone moves everything)
    hip.key("moveX", {0: 0, 2: 2 * SPEED}, ease="linear")
    hip.key("moveY", {i * 0.25: 26 + 8 * math.cos(4 * math.pi * i * 0.25) for i in range(0, 9)}, ease="smooth")

    # arms swing against the legs (FK); the elbow stays a little bent and bends more as the arm swings forward
    near_u.key("rotation", {0: 24, 0.5: -26, 1: 24, 1.5: -26, 2: 24}, ease="smooth")
    near_l.key("rotation", {0: -12, 0.5: -40, 1: -12, 1.5: -40, 2: -12}, ease="smooth")
    far_u.key("rotation", {0: -26, 0.5: 24, 1: -26, 1.5: 24, 2: -26}, ease="smooth")
    far_l.key("rotation", {0: -40, 0.5: -12, 1: -40, 1.5: -12, 2: -40}, ease="smooth")

    # a little lean with a twist of the body, and the head keeps itself level against it
    spine.key("rotation", {0: 4, 0.25: 6, 0.5: 4, 0.75: 6, 1: 4, 1.25: 6, 1.5: 4, 1.75: 6, 2: 4}, ease="smooth")
    neck.key("rotation", {0: -4, 0.25: -7, 0.5: -4, 0.75: -7, 1: -4, 1.25: -7, 1.5: -4, 1.75: -7, 2: -4}, ease="smooth")
