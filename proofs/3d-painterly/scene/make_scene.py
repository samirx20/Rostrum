"""Write stilllife.usda: our own still life (enamel jug, bowl of pears, folded cloth, wooden
table) under low warm sun, in front of a painted background card. Every surface takes a
hand-painted texture from ../paint/textures/<name>.png through UVs (primvars:st).

Run:  python -I make_scene.py [--ramp] [--checker] [--out name.usda]   (stdlib only)
  --ramp     key-light colour ramps (raycast shadow test -> rgb_ramp) instead of real shading
  --checker  UV test texture (../paint/textures/_checker.png) on every surface
Units: centimetres, Y up. Materials are Cycles nodes (see materials.py).
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I drops the script folder
from geo import lathe, tube, heightfield, box, norm, sub, cross, dist
from materials import material_usda

HERE = os.path.dirname(os.path.abspath(__file__))
CAMERA = dict(pos=(4.0, 30.0, 80.0), target=(1.0, 6.0, 0.0), focal=50.0, fstop=4.0,
              h_aperture=36.0, v_aperture=20.25, focus=(-6.0, 9.0, 0.0))
SUN = dict(to_sun=norm((-0.8, 0.42, -0.45)), intensity=1.2, kelvin=3500, angle=1.2)
FILL = dict(intensity=0.3, color=(0.50, 0.64, 1.0))   # cool room light, all directions
BOUNCE = dict(pos=(55.0, 10.0, 30.0), size=(60.0, 40.0), intensity=0.6, kelvin=4200)
BG_DISTANCE = 190.0                                    # painted card behind everything

JUG = [(0, 0), (5.4, 0), (6.0, 0.6), (7.2, 4), (7.6, 8), (7.0, 12), (5.6, 16), (5.0, 18.5),
       (5.4, 20.6), (6.0, 21.6), (5.7, 21.9), (4.8, 20.6), (4.6, 18.5), (5.2, 16), (6.6, 12),
       (7.1, 8), (6.7, 4), (5.3, 1.0), (0, 1.0)]
BOWL = [(0, 0), (5.0, 0), (5.4, 0.8), (6.2, 1.3), (9.0, 3.0), (11.4, 5.8), (12.4, 8.2), (12.6, 8.7),
        (12.0, 8.5), (10.9, 6.0), (8.5, 3.6), (5.0, 2.1), (0, 1.8)]
PEAR = [(0, 0), (2.4, 0.25), (3.6, 1.4), (4.0, 3.0), (3.7, 4.9), (2.8, 6.4), (2.1, 7.8), (1.6, 9.2),
        (0.9, 10.2), (0, 10.5)]
STEM = [(0, 10.0), (0.3, 11.4), (0.9, 12.3)]
HANDLE = [(-6.4, 17.5), (-9.5, 17.2), (-11.2, 14.0), (-10.6, 9.0), (-7.4, 5.5)]


def smooth(pts, k=6):
    """Catmull-Rom resample of a 2D polyline (k samples per segment)."""
    out, P = [], [pts[0]] + list(pts) + [pts[-1]]
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i-1], P[i], P[i+1], P[i+2]
        for s in range(k):
            t = s / k
            out.append(tuple(0.5*(2*p1[d] + (p2[d]-p0[d])*t + (2*p0[d]-5*p1[d]+4*p2[d]-p3[d])*t*t
                                  + (3*p1[d]-p0[d]-3*p2[d]+p3[d])*t**3) for d in range(2)))
    return out + [pts[-1]]


def cloth_height(x, z):
    edge = max(0.0, abs(x)/19 - 0.5)
    return 0.1 + 1.6*edge*edge*(1 + math.sin(z*0.5 + x*0.3)) + 0.18*math.sin(x*0.4 + z*0.15)**2


def parts():
    """name -> (mesh, material, translate, rotateY, rotateZ, scale). Lathes face u=0.5 to +Z."""
    pear = lathe(smooth(PEAR, 5), n=64, v0=0.0, v1=0.9)
    stem = tube([(x, y, 0.0) for x, y in smooth(STEM, 3)], 0.2, n=8, uv_rect=(0, 0.92, 1, 1))
    jug_at = ((-12, 0, -6), 18, 0, 1)
    p = {"Table": (box(150, 4, 80, 75.0), "Table", (0, 0, -8), 0, 0, 1),
         "Cloth": (heightfield(38, 30, 76, 60, cloth_height), "Cloth", (11, 0, 5), -12, 0, 1),
         "Jug": (lathe(smooth(JUG, 4), n=128, v0=0.2, v1=1.0), "Jug") + jug_at,
         "JugHandle": (tube([(x, y, 0.0) for x, y in smooth(HANDLE, 6)], 0.85,
                            uv_rect=(0, 0, 1, 0.18)), "Jug") + jug_at,
         "Bowl": (lathe(smooth(BOWL, 4), n=128), "Bowl", (11, 0.15, 5), 0, 0, 1)}
    for k, at in enumerate([((7.6, 2.6, 3.4), 40, -8, 1.0), ((15.2, 2.6, 7.4), -70, 10, 0.92),
                            ((-2.0, 3.7, 16.0), 125, 84, 1.05)]):
        p[f"Pear{k}"] = (pear, "Pear") + at
        p[f"PearStem{k}"] = (stem, "Pear") + at
    return p


def f3(v): return "(%.5g, %.5g, %.5g)" % tuple(v)


def mesh_usda(name, m, mat, t, ry, rz, s):
    j = ", ".join
    return f'''    def Mesh "{name}" (prepend apiSchemas = ["MaterialBindingAPI"])
    {{
        uniform token subdivisionScheme = "none"
        int[] faceVertexCounts = [{j(map(str, m.counts))}]
        int[] faceVertexIndices = [{j(map(str, m.idx))}]
        point3f[] points = [{j(f3(p) for p in m.P)}]
        normal3f[] normals = [{j(f3(n) for n in m.N)}] (interpolation = "vertex")
        texCoord2f[] primvars:st = [{j("(%.5g, %.5g)" % uv for uv in m.UV)}] (interpolation = "vertex")
        rel material:binding = </Looks/{mat}>
        double3 xformOp:translate = {f3(t)}
        float xformOp:rotateY = {ry}
        float xformOp:rotateZ = {rz}
        float3 xformOp:scale = ({s}, {s}, {s})
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:rotateY", "xformOp:rotateZ", "xformOp:scale"]
    }}
'''


def frame(pos, target):
    fwd = norm(sub(target, pos)); right = norm(cross(fwd, (0.0, 1.0, 0.0))); up = cross(right, fwd)
    return fwd, right, up


def matrix(pos, right, up, back):
    rows = [tuple(right) + (0.0,), tuple(up) + (0.0,), tuple(back) + (0.0,), tuple(pos) + (1.0,)]
    return "( " + ", ".join("(%s)" % ", ".join("%.6g" % x for x in r) for r in rows) + " )"


def background_card():
    """Camera-facing quad at BG_DISTANCE that fills the frame with a 6 % margin, UV 0..1."""
    c = CAMERA
    fwd, right, up = frame(c["pos"], c["target"])
    hw = BG_DISTANCE * c["h_aperture"] / (2 * c["focal"]) * 1.06
    hh = BG_DISTANCE * c["v_aperture"] / (2 * c["focal"]) * 1.06
    centre = tuple(c["pos"][k] + fwd[k]*BG_DISTANCE for k in range(3))
    corners = [tuple(centre[k] + sx*hw*right[k] + sy*hh*up[k] for k in range(3))
               for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
    back = tuple(-x for x in fwd)
    return f'''    def Mesh "BackgroundCard" (prepend apiSchemas = ["MaterialBindingAPI"])
    {{
        int[] faceVertexCounts = [4]
        int[] faceVertexIndices = [0, 1, 2, 3]
        point3f[] points = [{", ".join(f3(p) for p in corners)}]
        normal3f[] normals = [{", ".join([f3(back)] * 4)}] (interpolation = "vertex")
        texCoord2f[] primvars:st = [(0, 0), (1, 0), (1, 1), (0, 1)] (interpolation = "vertex")
        rel material:binding = </Looks/Background>
    }}
'''


def camera_and_lights():
    c = CAMERA
    fwd, right, up = frame(c["pos"], c["target"])
    sun_back = SUN["to_sun"]                       # a light shines down its local -Z
    s_right = norm(cross((0.0, 1.0, 0.0), sun_back)); s_up = cross(sun_back, s_right)
    bfwd, bright, bup = frame(BOUNCE["pos"], (0.0, 6.0, 0.0))
    return f'''    def Camera "Camera"
    {{
        float focalLength = {c["focal"]}
        float horizontalAperture = {c["h_aperture"]}
        float verticalAperture = {c["v_aperture"]}
        float fStop = {c["fstop"]}
        float focusDistance = {dist(c["pos"], c["focus"]):.3f}
        float2 clippingRange = (1, 5000)
        matrix4d xformOp:transform = {matrix(c["pos"], right, up, tuple(-x for x in fwd))}
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }}
    def DistantLight "Sun"
    {{
        float inputs:intensity = {SUN["intensity"]}
        float inputs:angle = {SUN["angle"]}
        bool inputs:normalize = true   # Cycles' delegate: without this a sun with angle > 0 is ~3000x too dim
        bool inputs:enableColorTemperature = true
        float inputs:colorTemperature = {SUN["kelvin"]}
        matrix4d xformOp:transform = {matrix((0, 0, 0), s_right, s_up, sun_back)}
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }}
    def DomeLight "RoomFill"
    {{
        float inputs:intensity = {FILL["intensity"]}
        color3f inputs:color = {f3(FILL["color"])}
    }}
    def RectLight "WarmBounce"
    {{
        float inputs:intensity = {BOUNCE["intensity"]}
        float inputs:width = {BOUNCE["size"][0]}
        float inputs:height = {BOUNCE["size"][1]}
        bool inputs:enableColorTemperature = true
        float inputs:colorTemperature = {BOUNCE["kelvin"]}
        matrix4d xformOp:transform = {matrix(BOUNCE["pos"], bright, bup, tuple(-x for x in bfwd))}
        uniform token[] xformOpOrder = ["xformOp:transform"]
    }}
'''


def main():
    out_name = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "stilllife.usda"
    ramp, checker = "--ramp" in sys.argv, "--checker" in sys.argv
    out = ['#usda 1.0\n(\n    defaultPrim = "World"\n    metersPerUnit = 0.01\n    upAxis = "Y"\n)\n',
           'def Xform "World"\n{\n']
    out += [mesh_usda(name, *v) for name, v in parts().items()]
    out += [background_card(), camera_and_lights(), "}\n\n", 'def Scope "Looks"\n{\n']
    for name in ["Table", "Cloth", "Jug", "Bowl", "Pear", "Background"]:
        out.append(material_usda(name, ramp=ramp, checker=checker, to_sun=SUN["to_sun"]))
    out.append("}\n")
    path = os.path.join(HERE, out_name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out))
    print("wrote", path)


if __name__ == "__main__":
    main()
