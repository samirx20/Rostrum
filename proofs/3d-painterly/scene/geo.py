"""Geometry with UVs for the P-3D-2 still life: lathes (jug, bowl, pears), a tube (handle),
a folded cloth, a table slab. Every mesh carries per-vertex normals and `st` UVs.
Stdlib only. Units: centimetres, Y up.
"""
import math


def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def add(a, b): return tuple(x + y for x, y in zip(a, b))
def mul(a, s): return tuple(x * s for x in a)
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dist(a, b): return math.dist(a, b)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return tuple(x / l for x in a)


class Mesh:
    def __init__(self): self.P, self.N, self.UV, self.counts, self.idx = [], [], [], [], []

    def grid(self, P, N, UV):
        """P/N/UV: rows[j][i]; quads between neighbouring rows and columns (no wrap: seams are
        duplicated columns so UVs can jump)."""
        nv, nu, base = len(P), len(P[0]), len(self.P)
        for j in range(nv):
            self.P += P[j]; self.N += N[j]; self.UV += UV[j]
        for j in range(nv - 1):
            for i in range(nu - 1):
                a = base + j*nu + i
                q = [a, a + 1, a + nu + 1, a + nu]
                n = cross(sub(self.P[q[2]], self.P[q[0]]), sub(self.P[q[3]], self.P[q[1]]))
                if dot(n, self.N[a]) < 0:  # wind every face to agree with its normals
                    q.reverse()
                self.counts.append(4); self.idx += q
        return self


def lathe(profile, n=96, v0=0.0, v1=1.0, u_front=0.5):
    """Revolve profile [(r, y)] around Y. u runs around (u_front faces +Z, the camera side),
    v runs along the profile by arc length from v0 to v1. Normals from the profile tangent
    (outward = to the right of the walking direction, so walk outside surfaces bottom-up)."""
    L = [0.0]
    for a, b in zip(profile, profile[1:]):
        L.append(L[-1] + math.dist(a, b))
    P, N, UV = [], [], []
    for j, (r, y) in enumerate(profile):
        a, b = profile[max(j-1, 0)], profile[min(j+1, len(profile)-1)]
        tr, ty = norm((b[0]-a[0], b[1]-a[1]))
        nr, ny = ty, -tr  # outward when walking up an outside wall
        v = v0 + (v1 - v0) * L[j] / (L[-1] or 1)
        rowP, rowN, rowUV = [], [], []
        for i in range(n + 1):
            u = i / n
            ang = 2*math.pi*(u - u_front)  # u_front -> angle 0 -> +Z
            s, c = math.sin(ang), math.cos(ang)
            rowP.append((r*s, y, r*c)); rowN.append(norm((nr*s, ny, nr*c))); rowUV.append((u, v))
        P.append(rowP); N.append(rowN); UV.append(rowUV)
    return Mesh().grid(P, N, UV)


def tube(path, radius, n=24, uv_rect=(0, 0, 1, 1)):
    """Sweep a circle along path [(x, y, z)]; u along the path, v around, packed in uv_rect."""
    P, N, UV = [], [], []
    u0, v0, u1, v1 = uv_rect
    up = (0.0, 0.0, 1.0)
    for j, p in enumerate(path):
        t = norm(sub(path[min(j+1, len(path)-1)], path[max(j-1, 0)]))
        b = norm(cross(t, up)); nn = cross(b, t)
        rowP, rowN, rowUV = [], [], []
        for i in range(n + 1):
            a = 2*math.pi*i/n
            d = add(mul(b, math.cos(a)), mul(nn, math.sin(a)))
            rowP.append(add(p, mul(d, radius))); rowN.append(d)
            rowUV.append((u0 + (u1-u0)*j/(len(path)-1), v0 + (v1-v0)*i/n))
        P.append(rowP); N.append(rowN); UV.append(rowUV)
    return Mesh().grid(P, N, UV)


def heightfield(w, d, nx, nz, h, uv_scale=1.0):
    """Plane in XZ (centred) displaced by h(x, z); normals by finite differences; planar UVs."""
    P, N, UV = [], [], []
    e = 0.01
    for j in range(nz + 1):
        z = -d/2 + d*j/nz
        rowP, rowN, rowUV = [], [], []
        for i in range(nx + 1):
            x = -w/2 + w*i/nx
            hx = (h(x+e, z) - h(x-e, z)) / (2*e); hz = (h(x, z+e) - h(x, z-e)) / (2*e)
            rowP.append((x, h(x, z), z)); rowN.append(norm((-hx, 1.0, -hz)))
            rowUV.append(((i/nx) * uv_scale, (1 - j/nz) * uv_scale))
        P.append(rowP); N.append(rowN); UV.append(rowUV)
    return Mesh().grid(P, N, UV)


def box(w, h, d, uv_size):
    """Axis-aligned slab, top at y=0. Each face is mapped planar in world cm / uv_size, so a
    texture painted as a plank surface reads at the same scale on top and sides."""
    m = Mesh()
    faces = [((0, 1, 0), (1, 0, 0), (0, 0, -1)), ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
             ((1, 0, 0), (0, 0, -1), (0, 1, 0)), ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
             ((0, 0, -1), (-1, 0, 0), (0, 1, 0)), ((0, -1, 0), (1, 0, 0), (0, 0, 1))]
    half = (w/2, h/2, d/2)
    centre = (0.0, -h/2, 0.0)
    for n, uax, vax in faces:
        c = add(centre, tuple(n[k]*half[k] for k in range(3)))
        su = sum(abs(uax[k])*half[k] for k in range(3)); sv = sum(abs(vax[k])*half[k] for k in range(3))
        P, N, UV = [], [], []
        for j in range(2):
            rp, rn, ruv = [], [], []
            for i in range(2):
                p = add(c, add(mul(uax, su*(2*i-1)), mul(vax, sv*(2*j-1))))
                rp.append(p); rn.append(n)
                ruv.append((dot(p, uax) / uv_size + 0.5, dot(p, vax) / uv_size + 0.5))
            P.append(rp); N.append(rn); UV.append(ruv)
        m.grid(P, N, UV)
    return m
