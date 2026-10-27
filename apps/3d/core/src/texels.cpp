#include "texels.h"

#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec4d.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/pointInstancer.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>

#include <algorithm>
#include <cmath>
#include <limits>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

PixelRays::PixelRays(const GfFrustum& f, int w, int h)
    : width(w), height(h), toClip(f.ComputeViewMatrix() * f.ComputeProjectionMatrix()),
      fromClip(toClip.GetInverse()), eye(f.GetPosition()) {}

namespace {
GfVec3d unproject(const GfMatrix4d& from_clip, double x, double y, double z) {
  const GfVec4d q = GfVec4d(x, y, z, 1) * from_clip;
  return GfVec3d(q[0], q[1], q[2]) / q[3];
}

// Möller–Trumbore, both sides: the ray's t and the weights of corners 1 and 2 where it meets the triangle
bool meet(const GfVec3d& o, const GfVec3d& d, const GfVec3d& a, const GfVec3d& b, const GfVec3d& c, double* t,
          double* wb, double* wc) {
  constexpr double kEdge = 1e-6;  // a pixel centre on an edge between two triangles lands on one of them
  const GfVec3d e1 = b - a, e2 = c - a, p = GfCross(d, e2);
  const double det = GfDot(e1, p);
  if (det == 0) return false;
  const double inv = 1.0 / det;
  const GfVec3d s = o - a;
  const double u = GfDot(s, p) * inv;
  if (u < -kEdge || u > 1 + kEdge) return false;
  const GfVec3d q = GfCross(s, e1);
  const double v = GfDot(d, q) * inv;
  if (v < -kEdge || u + v > 1 + kEdge) return false;
  *t = GfDot(e2, q) * inv;
  *wb = u;
  *wc = v;
  return *t >= 0;
}
}  // namespace

void PixelRays::ray(int x, int y, GfVec3d* from, GfVec3d* along) const {
  const double nx = 2.0 * (x + 0.5) / width - 1.0, ny = 1.0 - 2.0 * (y + 0.5) / height;
  *from = unproject(fromClip, nx, ny, -1);
  *along = unproject(fromClip, nx, ny, 1) - *from;
}

double PixelRays::distance(int x, int y, float depth) const {
  const double nx = 2.0 * (x + 0.5) / width - 1.0, ny = 1.0 - 2.0 * (y + 0.5) / height;
  return (unproject(fromClip, nx, ny, 2.0 * depth - 1.0) - eye).GetLength();
}

bool mesh_texels(const UsdStageRefPtr& stage, const SdfPath& path, int frame, const PixelRays& rays,
                 const std::vector<int>& primIds, int id, const std::vector<int>& pixels,
                 const std::vector<double>& drawn, std::vector<float>* out) {
  const UsdPrim prim = stage->GetPrimAtPath(path);
  const UsdGeomMesh m(prim);
  if (!m || pixels.empty()) return false;
  // an instance is drawn with its instancer's transform, which Hydra's prim id (instance 0) doesn't tell: no st
  if (prim.IsInstanceProxy()) return false;
  for (UsdPrim a = prim.GetParent(); a; a = a.GetParent())
    if (a.IsA<UsdGeomPointInstancer>()) return false;
  const UsdTimeCode t(frame);
  VtVec3fArray pts;
  VtIntArray counts, indices;
  m.GetPointsAttr().Get(&pts, t);
  m.GetFaceVertexCountsAttr().Get(&counts, t);
  m.GetFaceVertexIndicesAttr().Get(&indices, t);
  VtVec2fArray st;
  const UsdGeomPrimvar pv = UsdGeomPrimvarsAPI(prim).GetPrimvar(TfToken("st"));
  if (!pv || !pv.ComputeFlattened(&st, t)) return false;
  const TfToken interp = pv.GetInterpolation();
  const bool face_varying = interp == UsdGeomTokens->faceVarying && st.size() == indices.size();
  if (!face_varying && !((interp == UsdGeomTokens->vertex || interp == UsdGeomTokens->varying) && st.size() == pts.size()))
    return false;
  size_t corners = 0;
  for (int n : counts) corners += size_t(std::max(n, 0));
  if (corners != indices.size()) return false;  // a broken mesh: no st rather than a wrong one
  for (int i : indices)
    if (i < 0 || size_t(i) >= pts.size()) return false;
  const int* ix = indices.cdata();  // read-only from here: no copy-on-write check per access
  const GfVec2f* uvs = st.cdata();
  const GfVec3f* ps = pts.cdata();

  // the mesh in world space, and on the picture (pixel-centre coordinates; w <= 0 behind the eye)
  const GfMatrix4d to_world = m.ComputeLocalToWorldTransform(t);
  const int W = rays.width, H = rays.height;
  std::vector<GfVec3d> world(pts.size());
  std::vector<GfVec3d> screen(pts.size());  // x, y, w
  for (size_t i = 0; i < pts.size(); ++i) {
    world[i] = to_world.Transform(GfVec3d(ps[i]));
    const GfVec4d c = GfVec4d(world[i][0], world[i][1], world[i][2], 1) * rays.toClip;
    screen[i] = c[3] > 1e-9 ? GfVec3d((c[0] / c[3] * 0.5 + 0.5) * W - 0.5, (0.5 - c[1] / c[3] * 0.5) * H - 0.5, c[3])
                            : GfVec3d(0, 0, -1);
  }
  // the prim's pixels' box: no triangle looks further, and each pixel's best hit so far is kept in it
  int x0 = W, x1 = -1, y0 = H, y1 = -1;
  for (int i : pixels) {
    x0 = std::min(x0, i % W), x1 = std::max(x1, i % W);
    y0 = std::min(y0, i / W), y1 = std::max(y1, i / W);
  }
  const int bw = x1 - x0 + 1;
  std::vector<double> best(size_t(bw) * (y1 - y0 + 1), std::numeric_limits<double>::infinity());

  size_t first = 0;
  for (size_t f = 0; f < counts.size(); first += size_t(std::max(counts[f], 0)), ++f) {
    for (int k = 1; k + 1 < counts[f]; ++k) {
      const size_t c[3] = {first, first + size_t(k), first + size_t(k) + 1};
      const GfVec3d &s0 = screen[ix[c[0]]], &s1 = screen[ix[c[1]]], &s2 = screen[ix[c[2]]];
      int xa = x0, xb = x1, ya = y0, yb = y1;  // a corner behind the eye: the whole box
      if (s0[2] > 0 && s1[2] > 0 && s2[2] > 0) {
        xa = std::max(xa, int(std::floor(std::min({s0[0], s1[0], s2[0]}))));
        xb = std::min(xb, int(std::ceil(std::max({s0[0], s1[0], s2[0]}))));
        ya = std::max(ya, int(std::floor(std::min({s0[1], s1[1], s2[1]}))));
        yb = std::min(yb, int(std::ceil(std::max({s0[1], s1[1], s2[1]}))));
      }
      const GfVec3d &a = world[ix[c[0]]], &b = world[ix[c[1]]], &cc = world[ix[c[2]]];
      for (int y = ya; y <= yb; ++y)
        for (int x = xa; x <= xb; ++x) {
          const size_t px = size_t(y) * W + x;
          if (primIds[px] != id) continue;
          GfVec3d o, d;
          rays.ray(x, y, &o, &d);
          double hit_t, wb, wc;
          if (!meet(o, d, a, b, cc, &hit_t, &wb, &wc)) continue;
          const double dist = (o + d * hit_t - rays.eye).GetLength();
          const double score = drawn[px] >= 0 ? std::abs(dist - drawn[px]) : dist;  // the face Storm drew there
          double& keep = best[size_t(y - y0) * bw + (x - x0)];
          if (score >= keep) continue;
          keep = score;
          const double w[3] = {1 - wb - wc, wb, wc};
          GfVec2f uv(0, 0);
          for (int q = 0; q < 3; ++q) uv += uvs[face_varying ? c[q] : size_t(ix[c[q]])] * float(w[q]);
          (*out)[4 * px] = uv[0];
          (*out)[4 * px + 1] = uv[1];
          (*out)[4 * px + 3] = float(dist);
        }
    }
  }
  return true;
}

}  // namespace r3d
