#include "texels.h"

#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec4d.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/pointInstancer.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>
#include <pxr/usd/usdGeom/subset.h>
#include <pxr/usd/usdShade/material.h>
#include <pxr/usd/usdShade/materialBindingAPI.h>
#include <pxr/usd/usdShade/shader.h>

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

namespace {
// a mesh in world space and on the picture: x, y in pixel-centre coordinates and w (<= 0: behind the eye)
struct ScreenMesh {
  VtIntArray counts, indices;
  std::vector<GfVec3d> world, screen;
};

// False for a broken mesh (a face naming a missing point): nothing rather than something wrong.
bool screen_mesh(const UsdGeomMesh& m, UsdTimeCode t, const PixelRays& rays, ScreenMesh* sm) {
  VtVec3fArray pts;
  m.GetPointsAttr().Get(&pts, t);
  m.GetFaceVertexCountsAttr().Get(&sm->counts, t);
  m.GetFaceVertexIndicesAttr().Get(&sm->indices, t);
  size_t corners = 0;
  for (int n : sm->counts) corners += size_t(std::max(n, 0));
  if (corners != sm->indices.size()) return false;
  for (int i : sm->indices)
    if (i < 0 || size_t(i) >= pts.size()) return false;
  const GfMatrix4d to_world = m.ComputeLocalToWorldTransform(t);
  const GfVec3f* ps = pts.cdata();  // read-only: no copy-on-write check per access
  const int W = rays.width, H = rays.height;
  sm->world.resize(pts.size());
  sm->screen.resize(pts.size());
  for (size_t i = 0; i < pts.size(); ++i) {
    const GfVec3d p = to_world.Transform(GfVec3d(ps[i]));
    sm->world[i] = p;
    const GfVec4d c = GfVec4d(p[0], p[1], p[2], 1) * rays.toClip;
    sm->screen[i] = c[3] > 1e-9 ? GfVec3d((c[0] / c[3] * 0.5 + 0.5) * W - 0.5, (0.5 - c[1] / c[3] * 0.5) * H - 0.5, c[3])
                                : GfVec3d(0, 0, -1);
  }
  return true;
}

// Each triangle (faces as fans) tests the pixel centres it covers on screen inside the box x0..x1, y0..y1 (a corner
// behind the eye: the whole box): `want(px)` first, then for each ray that meets it
// `take(px, distance from the eye, its 3 face-vertex corners, weights of corners 1 and 2)`.
template <typename Want, typename Take>
void each_hit(const ScreenMesh& sm, const PixelRays& rays, int x0, int x1, int y0, int y1, Want&& want, Take&& take) {
  const int* ix = sm.indices.cdata();
  const int W = rays.width;
  size_t first = 0;
  for (size_t f = 0; f < sm.counts.size(); first += size_t(std::max(sm.counts[f], 0)), ++f) {
    for (int k = 1; k + 1 < sm.counts[f]; ++k) {
      const size_t c[3] = {first, first + size_t(k), first + size_t(k) + 1};
      const GfVec3d &s0 = sm.screen[ix[c[0]]], &s1 = sm.screen[ix[c[1]]], &s2 = sm.screen[ix[c[2]]];
      int xa = x0, xb = x1, ya = y0, yb = y1;
      if (s0[2] > 0 && s1[2] > 0 && s2[2] > 0) {
        xa = std::max(xa, int(std::floor(std::min({s0[0], s1[0], s2[0]}))));
        xb = std::min(xb, int(std::ceil(std::max({s0[0], s1[0], s2[0]}))));
        ya = std::max(ya, int(std::floor(std::min({s0[1], s1[1], s2[1]}))));
        yb = std::min(yb, int(std::ceil(std::max({s0[1], s1[1], s2[1]}))));
      }
      const GfVec3d &a = sm.world[ix[c[0]]], &b = sm.world[ix[c[1]]], &cc = sm.world[ix[c[2]]];
      for (int y = ya; y <= yb; ++y)
        for (int x = xa; x <= xb; ++x) {
          const size_t px = size_t(y) * W + x;
          if (!want(px)) continue;
          GfVec3d o, d;
          rays.ray(x, y, &o, &d);
          double hit_t, wb, wc;
          if (!meet(o, d, a, b, cc, &hit_t, &wb, &wc)) continue;
          take(px, (o + d * hit_t - rays.eye).GetLength(), c, wb, wc);
        }
    }
  }
}

bool in_point_instancer(const UsdPrim& prim) {
  for (UsdPrim a = prim.GetParent(); a; a = a.GetParent())
    if (a.IsA<UsdGeomPointInstancer>()) return true;
  return false;
}

// Storm draws a material see-through (its translucent pass) when its UsdPreviewSurface opacity is below 1 or comes
// from a picture, unless an opacity threshold makes it a cut-out
bool see_through_material(const UsdShadeMaterial& mat, UsdTimeCode t) {
  if (!mat) return false;
  const UsdShadeShader s = mat.ComputeSurfaceSource();
  if (!s) return false;
  const UsdShadeInput opacity = s.GetInput(TfToken("opacity"));
  if (!opacity) return false;
  float threshold = 0;
  if (const UsdShadeInput th = s.GetInput(TfToken("opacityThreshold"))) th.Get(&threshold, t);
  if (threshold > 0) return false;
  if (opacity.HasConnectedSource()) return true;
  float v = 1;
  opacity.Get(&v, t);
  return v < 1.f;
}

bool see_through(const UsdPrim& prim, UsdTimeCode t) {
  UsdShadeMaterialBindingAPI bind(prim);
  const UsdShadeMaterial mat = bind.ComputeBoundMaterial(UsdShadeTokens->preview);
  if (see_through_material(mat, t)) return true;
  for (const UsdGeomSubset& sub : bind.GetMaterialBindSubsets())  // faces with a material of their own
    if (see_through_material(UsdShadeMaterialBindingAPI(sub.GetPrim()).ComputeBoundMaterial(UsdShadeTokens->preview), t))
      return true;
  if (mat) return false;
  VtFloatArray op;  // no material: Storm's fallback draws displayOpacity
  const UsdGeomPrimvar pv = UsdGeomGprim(prim).GetDisplayOpacityPrimvar();
  if (pv && pv.ComputeFlattened(&op, t))
    for (float v : op)
      if (v < 1.f) return true;
  return false;
}
}  // namespace

SdfPathVector see_through_meshes(const UsdStageRefPtr& stage, int frame) {
  const UsdTimeCode t(frame);
  SdfPathVector out;
  for (const UsdPrim& p : stage->Traverse()) {
    if (!p.IsA<UsdGeomMesh>()) continue;
    const UsdGeomImageable im(p);
    if (im.ComputeVisibility(t) == UsdGeomTokens->invisible || im.ComputePurpose() != UsdGeomTokens->default_) continue;
    if (see_through(p, t)) out.push_back(p.GetPath());
  }
  return out;
}

void claim_pixels(const UsdStageRefPtr& stage, const SdfPath& path, int frame, const PixelRays& rays, int id,
                  std::vector<int>* primIds, std::vector<double>* drawn) {
  const UsdPrim prim = stage->GetPrimAtPath(path);
  const UsdGeomMesh m(prim);
  ScreenMesh sm;
  if (!m || prim.IsInstanceProxy() || in_point_instancer(prim) || !screen_mesh(m, UsdTimeCode(frame), rays, &sm)) return;
  each_hit(sm, rays, 0, rays.width - 1, 0, rays.height - 1, [](size_t) { return true; },
           [&](size_t px, double dist, const size_t*, double, double) {
             double& there = (*drawn)[px];
             if (there >= 0 && dist >= there) return;  // behind what is there
             there = dist;
             (*primIds)[px] = id;
           });
}

bool mesh_texels(const UsdStageRefPtr& stage, const SdfPath& path, int frame, const PixelRays& rays,
                 const std::vector<int>& primIds, int id, const std::vector<int>& pixels,
                 const std::vector<double>& drawn, std::vector<float>* out) {
  const UsdPrim prim = stage->GetPrimAtPath(path);
  const UsdGeomMesh m(prim);
  if (!m || pixels.empty()) return false;
  // an instance is drawn with its instancer's transform, which Hydra's prim id (instance 0) doesn't tell: no st
  if (prim.IsInstanceProxy() || in_point_instancer(prim)) return false;
  const UsdTimeCode t(frame);
  ScreenMesh sm;
  if (!screen_mesh(m, t, rays, &sm)) return false;
  VtVec2fArray st;
  const UsdGeomPrimvar pv = UsdGeomPrimvarsAPI(prim).GetPrimvar(TfToken("st"));
  if (!pv || !pv.ComputeFlattened(&st, t)) return false;
  const TfToken interp = pv.GetInterpolation();
  const bool face_varying = interp == UsdGeomTokens->faceVarying && st.size() == sm.indices.size();
  if (!face_varying &&
      !((interp == UsdGeomTokens->vertex || interp == UsdGeomTokens->varying) && st.size() == sm.world.size()))
    return false;
  const int* ix = sm.indices.cdata();
  const GfVec2f* uvs = st.cdata();

  // the prim's pixels' box: no triangle looks further, and each pixel's best hit so far is kept in it
  const int W = rays.width;
  int x0 = W, x1 = -1, y0 = rays.height, y1 = -1;
  for (int i : pixels) {
    x0 = std::min(x0, i % W), x1 = std::max(x1, i % W);
    y0 = std::min(y0, i / W), y1 = std::max(y1, i / W);
  }
  const int bw = x1 - x0 + 1;
  std::vector<double> best(size_t(bw) * (y1 - y0 + 1), std::numeric_limits<double>::infinity());
  each_hit(sm, rays, x0, x1, y0, y1, [&](size_t px) { return primIds[px] == id; },
           [&](size_t px, double dist, const size_t* c, double wb, double wc) {
             const double score = drawn[px] >= 0 ? std::abs(dist - drawn[px]) : dist;  // the face Storm drew there
             const int x = int(px % W), y = int(px / W);
             double& keep = best[size_t(y - y0) * bw + (x - x0)];
             if (score >= keep) return;
             keep = score;
             const double w[3] = {1 - wb - wc, wb, wc};
             GfVec2f uv(0, 0);
             for (int q = 0; q < 3; ++q) uv += uvs[face_varying ? c[q] : size_t(ix[c[q]])] * float(w[q]);
             (*out)[4 * px] = uv[0];
             (*out)[4 * px + 1] = uv[1];
             (*out)[4 * px + 3] = float(dist);
           });
  return true;
}

}  // namespace r3d
