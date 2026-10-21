"""Write product.usda: our own small device (anodized slab, glass top, knurled lens dial)
on a dark seamless backdrop, lit with softboxes and strip lights, for Cycles via Hydra.

Run:  python -I make_scene.py   (stdlib only; writes product.usda next to this file)
Units: centimetres (metersPerUnit = 0.01), Y up. See NOTES.md for what each part is.
"""
import math, os

# ---------------------------------------------------------------- parameters
BODY_W, BODY_D, BODY_H = 7.4, 9.8, 1.7     # footprint X, Z and height (cm)
CORNER_R, BOTTOM_R, CHAMFER = 1.9, 0.35, 0.09
GLASS_T, GLASS_INSET = 0.14, 0.06           # top glass thickness, inset from chamfer
DIAL_POS = (0.0, -1.2)                      # dial centre on the top (x, z)
DIAL_R_OUT, DIAL_R_IN, DIAL_H, DIAL_C = 2.15, 1.55, 0.32, 0.05
KNURL_COUNT, KNURL_DEPTH = 120, 0.018
LENS_SAG = 0.26                             # lens dome height
YAW_DEG = 28.0                              # device rotation on the floor

MATERIALS = {  # name: cycles principled_bsdf inputs
    "Anodized":  dict(base_color=(0.16, 0.17, 0.19), metallic=1.0, roughness=0.32),
    "Chamfer":   dict(base_color=(0.86, 0.86, 0.88), metallic=1.0, roughness=0.05),
    "Ink":       dict(base_color=(0.008, 0.008, 0.01), roughness=0.35),
    "Glass":     dict(base_color=(0.97, 0.99, 0.98), transmission_weight=1.0, roughness=0.0, ior=1.52),
    "Lens":      dict(base_color=(1.0, 1.0, 1.0), transmission_weight=1.0, roughness=0.0, ior=1.77,
                      thin_film_thickness=280.0, thin_film_ior=1.38),
    "Steel":     dict(base_color=(0.66, 0.64, 0.62), metallic=1.0, roughness=0.06),
    "Knurl":     dict(base_color=(0.62, 0.60, 0.58), metallic=1.0, roughness=0.2),
    "Sensor":    dict(base_color=(0.05, 0.04, 0.07), metallic=1.0, roughness=0.08,
                      thin_film_thickness=520.0, thin_film_ior=1.6),
    "Backdrop":  dict(base_color=(0.03, 0.031, 0.034), roughness=0.42),
}

CAMERA = dict(pos=(15.0, 13.0, 31.0), target=(0.3, 1.2, -0.2), focal=100.0, fstop=4.0,
              h_aperture=36.0, v_aperture=20.25)   # apertures in mm (tenths of a cm)
FOCUS_ON = None   # world point to focus on; None = the dial bezel's edge nearest the camera

# (name, kind, position, aim point, size (w,h) or radius, intensity, colour temperature K)
LIGHTS = [
    ("KeyTop",    "Rect", (-6.0, 48.0, -26.0), (0, 0, 0), (70.0, 45.0), 7.0, 5600),
    ("StripLeft", "Rect", (-34.0, 14.0, -18.0), (0, 2, 0), (8.0, 90.0), 30.0, 6500),
    ("StripRight", "Rect", (32.0, 12.0, -22.0), (0, 2, 0), (8.0, 90.0), 22.0, 6500),
    ("FrontFill", "Rect", (6.0, 6.0, 55.0), (0, 1, 0), (60.0, 20.0), 0.6, 7000),
    ("WallGlow",  "Rect", (0.0, 6.0, -12.0), (0, 22, -48), (80.0, 30.0), 2.5, 4800),
    ("Ambient",   "Dome", None, None, None, 0.02, 6500),
]

# ---------------------------------------------------------------- vector helpers
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    l = math.sqrt(sum(x*x for x in a)) or 1.0
    return tuple(x / l for x in a)
def dist(a, b): return math.sqrt(sum((x - y)**2 for x, y in zip(a, b)))

# ---------------------------------------------------------------- mesh builders
class Mesh:
    """Triangle/quad mesh with per-vertex normals; parts with hard edges don't share vertices."""
    def __init__(self): self.P, self.N, self.counts, self.idx = [], [], [], []

    def grid(self, rows, closed_u=True, flip=False):
        """rows[j][i]: point at profile step j, around-step i. Normals from the surface itself."""
        nv, nu = len(rows), len(rows[0])
        base = len(self.P)
        for j in range(nv):
            for i in range(nu):
                ip, im = ((i+1) % nu, (i-1) % nu) if closed_u else (min(i+1, nu-1), max(i-1, 0))
                jp, jm = min(j+1, nv-1), max(j-1, 0)
                du = sub(rows[j][ip], rows[j][im])
                dv = sub(rows[jp][i], rows[jm][i])
                n = norm(cross(dv, du))
                self.P.append(rows[j][i]); self.N.append(tuple(-x for x in n) if flip else n)
        for j in range(nv - 1):
            for i in range(nu if closed_u else nu - 1):
                a, b = base + j*nu + i, base + j*nu + (i+1) % nu
                c, d = b + nu, a + nu
                self.counts.append(4)
                self.idx += [a, b, c, d] if flip else [a, d, c, b]  # winding agrees with N
        return self

    def fan(self, ring, center, normal, flip=False):
        """Flat cap: a fan from center to a closed ring (all vertices get the same normal)."""
        base = len(self.P)
        self.P += [center] + list(ring); self.N += [normal] * (len(ring) + 1)
        for i in range(len(ring)):
            a, b = base + 1 + i, base + 1 + (i+1) % len(ring)
            self.counts.append(3); self.idx += [base, b, a] if flip else [base, a, b]
        return self

def outline(w, d, r, inset, n_corner=28, n_edge=14):
    """Rounded rectangle (x, z) shrunk by inset; same sample count for every inset (so grids line up)."""
    pts, rr = [], r - inset
    cx, cz = w/2 - r, d/2 - r
    for k, (sx, sz, a0) in enumerate([(1, 1, 0), (-1, 1, 90), (-1, -1, 180), (1, -1, 270)]):
        for s in range(n_corner):
            a = math.radians(a0 + 90.0 * s / n_corner)
            pts.append((sx*cx + rr*math.cos(a), sz*cz + rr*math.sin(a)))
        # straight edge to next corner (counter-clockwise seen from +Y is x->z; we keep order consistent)
        a = math.radians(a0 + 90.0)
        p0 = (sx*cx + rr*math.cos(a), sz*cz + rr*math.sin(a))
        nx, nz = [(-1, 1), (-1, -1), (1, -1), (1, 1)][k]
        p1 = (nx*cx + rr*math.cos(a), nz*cz + rr*math.sin(a))
        for s in range(n_edge):
            t = s / n_edge
            pts.append((p0[0] + (p1[0]-p0[0])*t, p0[1] + (p1[1]-p0[1])*t))
    return pts

def loft(w, d, r, profile, y0=0.0):
    """Rows of a rounded-rect body: profile = [(inset, y)] from bottom to top."""
    return [[(x, y0 + y, z) for x, z in outline(w, d, r, inset)] for inset, y in profile]

def arc(c, rad, a0, a1, n):
    return [(c[0] + rad*math.cos(math.radians(a0 + (a1-a0)*s/n)),
             c[1] + rad*math.sin(math.radians(a0 + (a1-a0)*s/n))) for s in range(n + 1)]

def revolve(profile, n=256, radius_fn=None):
    """Rows around Y: profile = [(r, y)]; radius_fn(r, y, angle) can modulate the radius (knurl)."""
    rows = []
    for r, y in profile:
        row = []
        for i in range(n):
            a = 2*math.pi*i/n
            rr = radius_fn(r, y, a) if radius_fn else r
            row.append((rr*math.cos(a), y, -rr*math.sin(a)))
        rows.append(row)
    return rows

def lerp_profile(p0, p1, n):
    return [(p0[0] + (p1[0]-p0[0])*s/n, p0[1] + (p1[1]-p0[1])*s/n) for s in range(n + 1)]

# ---------------------------------------------------------------- the device
def build_parts():
    parts = {}
    W, D, H, R, C = BODY_W, BODY_D, BODY_H, CORNER_R, CHAMFER
    # body: rounded bottom edge + straight wall (one smooth band), polished chamfer, caps
    side = [(BOTTOM_R*(1 - math.sin(math.radians(a))), BOTTOM_R*(1 - math.cos(math.radians(a))))
            for a in [90*s/8 for s in range(9)]]
    side += [(0.0, BOTTOM_R + (H - C - BOTTOM_R)*s/6) for s in range(1, 7)]
    body = Mesh().grid(loft(W, D, R, side))
    body.fan([(x, 0.0, z) for x, z in outline(W, D, R, BOTTOM_R)], (0, 0, 0), (0, -1, 0))
    parts["Body"] = (body, "Anodized")
    parts["Chamfer"] = (Mesh().grid(loft(W, D, R, lerp_profile((0.0, H - C), (C, H), 2))), "Chamfer")
    parts["TopInk"] = (Mesh().fan([(x, H, z) for x, z in outline(W, D, R, C)], (0, H, 0), (0, 1, 0),
                                flip=True),
                       "Ink")
    # top glass: closed slab, half-round edge
    gi, gy, t = C + GLASS_INSET, H + 0.004, GLASS_T
    edge = [(gi + t/2*(1 - math.sin(math.radians(a))), t/2*(1 - math.cos(math.radians(a))))
            for a in [180*s/12 for s in range(13)]]
    glass = Mesh().grid(loft(W, D, R, edge, gy))
    glass.fan([(x, gy, z) for x, z in outline(W, D, R, gi + t/2)], (0, gy, 0), (0, -1, 0))
    glass.fan([(x, gy + t, z) for x, z in outline(W, D, R, gi + t/2)], (0, gy + t, 0), (0, 1, 0), flip=True)
    parts["TopGlass"] = (glass, "Glass")
    # dial: knurled outer wall, polished bezel with chamfers, inner wall
    y0, ro, ri, h, c = gy + t + 0.003, DIAL_R_OUT, DIAL_R_IN, DIAL_H, DIAL_C
    knurl = lambda r, y, a: r - KNURL_DEPTH*(0.5 - 0.5*math.cos(KNURL_COUNT*a))
    kt, rk = y0 + h - c, ro - KNURL_DEPTH
    knurl_m = Mesh().grid(revolve(lerp_profile((ro, y0), (ro, kt), 6), n=KNURL_COUNT*8,
                                  radius_fn=knurl), flip=True)
    knurl_m.grid(revolve(lerp_profile((rk, kt), (ro, kt), 1), n=KNURL_COUNT*8))  # ledge over teeth
    parts["DialKnurl"] = (knurl_m, "Knurl")
    bezel = Mesh()
    for prof in [lerp_profile((rk, kt), (rk - c, y0 + h), 2),
                 lerp_profile((rk - c, y0 + h), (ri + c, y0 + h), 3),
                 lerp_profile((ri + c, y0 + h), (ri, y0 + h - c), 2),
                 lerp_profile((ri, y0 + h - c), (ri, y0), 3)]:
        bezel.grid(revolve(prof), flip=True)
    parts["DialBezel"] = (bezel, "Steel")
    parts["DialFloor"] = (Mesh().fan([p for p in revolve([(ri, y0 + 0.004)])[0]], (0, y0 + 0.004, 0),
                                     (0, 1, 0)), "Ink")
    parts["Sensor"] = (Mesh().fan(revolve([(0.42, y0 + 0.012)])[0], (0, y0 + 0.012, 0), (0, 1, 0)),
                  "Sensor")
    # lens: plano-convex, flat bottom, short edge, spherical dome
    a, ly = ri - 0.02, y0 + 0.03
    sph_r = (a*a + LENS_SAG**2) / (2*LENS_SAG)
    cy = ly + 0.08 + LENS_SAG - sph_r
    dome = [(sph_r*math.sin(th), cy + sph_r*math.cos(th))
            for th in [math.asin(a/sph_r)*(1 - s/24) for s in range(24)]]
    lens = Mesh().grid(revolve(lerp_profile((a, ly), (a, ly + 0.08), 2)), flip=True)
    lens.grid(revolve(dome), flip=True)
    lens.fan(revolve([dome[-1]])[0], (0, cy + sph_r, 0), (0, 1, 0))
    lens.fan(revolve([(a, ly)])[0], (0, ly, 0), (0, -1, 0), flip=True)
    parts["Lens"] = (lens, "Lens")
    return parts

def button():
    """Side button: a small rounded slab built lying flat, rotated onto the +X wall by its xform."""
    prof = [(0.12*(1 - math.sin(math.radians(a))), 0.12*(1 - math.cos(math.radians(a))))
            for a in [90*s/8 for s in range(9)]] + [(0.12, 0.16)]
    m = Mesh().grid(loft(0.42, 1.9, 0.2, prof))
    m.fan([(x, 0.16, z) for x, z in outline(0.42, 1.9, 0.2, 0.12)], (0, 0.16, 0), (0, 1, 0), flip=True)
    return m

def backdrop():
    """Seamless cyc: floor toward camera, curve, back wall. Extruded along X."""
    prof = [(z, 0.0) for z in (90.0, 40.0, 0.0, -20.0)] + \
           [(p[0], p[1]) for p in arc((-20.0, 35.0), 35.0, 270, 180, 16)][1:] + [(-55.0, 140.0)]
    rows = [[(x, y, z) for x in [-120 + 240*i/8 for i in range(9)]] for z, y in prof]
    return Mesh().grid(rows, closed_u=False, flip=True)

# ---------------------------------------------------------------- USDA writing
def f3(v): return "(%.5g, %.5g, %.5g)" % tuple(v)

def mesh_usda(name, m, mat, ind, xform=""):
    pts = ", ".join(f3(p) for p in m.P)
    nrm = ", ".join(f3(n) for n in m.N)
    return f'''{ind}def Mesh "{name}" (prepend apiSchemas = ["MaterialBindingAPI"])
{ind}{{
{ind}    uniform token subdivisionScheme = "none"
{ind}    int[] faceVertexCounts = [{", ".join(map(str, m.counts))}]
{ind}    int[] faceVertexIndices = [{", ".join(map(str, m.idx))}]
{ind}    point3f[] points = [{pts}]
{ind}    normal3f[] normals = [{nrm}] (interpolation = "vertex")
{ind}    rel material:binding = </Looks/{mat}>
{xform}{ind}}}
'''

def material_usda(name, inputs):
    lines = []
    for k, v in inputs.items():
        lines.append(f"            color3f inputs:{k} = {f3(v)}" if isinstance(v, tuple)
                     else f"            float inputs:{k} = {v}")
    pv = {"diffuseColor": inputs.get("base_color", (0.8,) * 3), "metallic": inputs.get("metallic", 0.0),
          "roughness": inputs.get("roughness", 0.5), "ior": inputs.get("ior", 1.5),
          "opacity": 1.0 - 0.8 * inputs.get("transmission_weight", 0.0)}
    pv_lines = [f"            color3f inputs:{k} = {f3(v)}" if isinstance(v, tuple)
                else f"            float inputs:{k} = {v}" for k, v in pv.items()]
    nl = "\n"
    return f'''    def Material "{name}"
    {{
        token outputs:cycles:surface.connect = </Looks/{name}/Cycles.outputs:BSDF>
        token outputs:surface.connect = </Looks/{name}/Preview.outputs:surface>
        def Shader "Cycles"
        {{
            uniform token info:id = "cycles_principled_bsdf"
{nl.join(lines)}
            token outputs:BSDF
        }}
        def Shader "Preview"
        {{
            uniform token info:id = "UsdPreviewSurface"
{nl.join(pv_lines)}
            token outputs:surface
        }}
    }}
'''

def look_at(pos, target):
    """Row-major USD matrix whose local -Z points from pos to target (cameras and lights)."""
    fwd = norm(sub(target, pos))
    up = (0.0, 1.0, 0.0) if abs(fwd[1]) < 0.99 else (0.0, 0.0, -1.0)
    right = norm(cross(fwd, up)); upv = cross(right, fwd)
    back = tuple(-x for x in fwd)
    rows = [right + (0.0,), upv + (0.0,), back + (0.0,), tuple(pos) + (1.0,)]
    return "( " + ", ".join("(%s)" % ", ".join("%.6g" % x for x in r) for r in rows) + " )"

def light_usda(name, kind, pos, aim, size, intensity, kelvin):
    body = [f"        float inputs:intensity = {intensity}",
            f"        bool inputs:enableColorTemperature = true",
            f"        float inputs:colorTemperature = {kelvin}"]
    if kind == "Rect":
        body += [f"        float inputs:width = {size[0]}", f"        float inputs:height = {size[1]}",
                 f'        matrix4d xformOp:transform = {look_at(pos, aim)}',
                 '        uniform token[] xformOpOrder = ["xformOp:transform"]']
    return f'    def {kind}Light "{name}"\n    {{\n' + "\n".join(body) + "\n    }\n"

def focus_point():
    """FOCUS_ON, or the dial bezel's top edge on the side facing the camera (follows yaw/dial/camera)."""
    if FOCUS_ON:
        return FOCUS_ON
    yaw = math.radians(YAW_DEG)
    x, z = DIAL_POS
    cx, cz = x*math.cos(yaw) + z*math.sin(yaw), -x*math.sin(yaw) + z*math.cos(yaw)
    dx, dz = CAMERA["pos"][0] - cx, CAMERA["pos"][2] - cz
    l = math.hypot(dx, dz)
    top = BODY_H + 0.004 + GLASS_T + 0.003 + DIAL_H
    return (cx + DIAL_R_OUT*dx/l, top, cz + DIAL_R_OUT*dz/l)

def main():
    out = ['#usda 1.0\n(\n    defaultPrim = "World"\n    metersPerUnit = 0.01\n    upAxis = "Y"\n)\n',
           'def Xform "World"\n{\n']
    out.append('    def Xform "Device"\n    {\n'
               f'        float3 xformOp:rotateXYZ = (0, {YAW_DEG}, 0)\n'
               '        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]\n')
    parts = build_parts()
    for name, (m, mat) in parts.items():
        if name.startswith(("Dial", "Lens", "Sensor")):
            continue
        out.append(mesh_usda(name, m, mat, "        "))
    out.append(f'        def Xform "Dial"\n        {{\n'
               f'            double3 xformOp:translate = ({DIAL_POS[0]}, 0, {DIAL_POS[1]})\n'
               '            uniform token[] xformOpOrder = ["xformOp:translate"]\n')
    for name, (m, mat) in parts.items():
        if name.startswith(("Dial", "Lens", "Sensor")):
            out.append(mesh_usda(name, m, mat, "            "))
    out.append("        }\n")
    bx = ('            double3 xformOp:translate = (%g, %g, 1.6)\n'
          '            float3 xformOp:rotateXYZ = (0, 0, -90)\n'
          '            uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateXYZ"]\n'
          % (BODY_W / 2 - 0.02, BODY_H * 0.52))
    out.append(mesh_usda("SideButton", button(), "Chamfer", "        ", bx))
    out.append("    }\n")
    out.append(mesh_usda("Backdrop", backdrop(), "Backdrop", "    "))
    cam = CAMERA
    out.append(f'''    def Camera "HeroCamera"
    {{
        float focalLength = {cam["focal"]}
        float horizontalAperture = {cam["h_aperture"]}
        float verticalAperture = {cam["v_aperture"]}
        float fStop = {cam["fstop"]}
        float focusDistance = {dist(cam["pos"], focus_point()):.4f}
        float2 clippingRange = (1, 2000)
        matrix4d xformOp:transform = {look_at(cam["pos"], cam["target"])}
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }}
''')
    for l in LIGHTS:
        out.append(light_usda(*l))
    out.append("}\n\n")
    out.append('def Scope "Looks"\n{\n' + "".join(material_usda(k, v) for k, v in MATERIALS.items()) + "}\n")
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "product.usda")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out))
    print("wrote", path)

if __name__ == "__main__":
    main()
