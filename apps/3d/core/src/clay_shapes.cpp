// Clay (CL3): the drawn, spun and item piece shapes as distance fields (clay_shapes.h).
#include "clay_shapes.h"

#include <openvdb/openvdb.h>
#include <openvdb/tools/MeshToVolume.h>
#include <tbb/blocked_range.h>
#include <tbb/parallel_for.h>

#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/vec3d.h>
#include <pxr/base/vt/array.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/xformCache.h>

#include <algorithm>
#include <cmath>
#include <deque>
#include <limits>

#include "clay_box.h"
#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::clay {

namespace {

constexpr float kInf = 1e30f;
// a 2-D grid reaches this far (grains) past the shape: what Volume::run reads around a piece (the band, the widest
// blend and a chunk's centre to its farthest voxel), with room to spare; past it the grid's border cell answers
constexpr float kPad = detail::kBlendCap + kBand + 12.0f;
constexpr int kMaxCells = 512;  // per side of a 2-D grid

using P2 = std::array<float, 2>;

// signed distance from q to the closed polygon `poly` (even-odd: negative inside); exact
float poly_sdf(const std::vector<P2>& poly, float qx, float qy) {
  const size_t n = poly.size();
  float d = kInf, s = 1.0f;
  for (size_t i = 0, j = n - 1; i < n; j = i++) {
    const float ex = poly[j][0] - poly[i][0], ey = poly[j][1] - poly[i][1];
    const float wx = qx - poly[i][0], wy = qy - poly[i][1];
    const float ee = ex * ex + ey * ey;
    const float t = ee > 0 ? std::min(1.0f, std::max(0.0f, (wx * ex + wy * ey) / ee)) : 0.0f;
    const float bx = wx - ex * t, by = wy - ey * t;
    d = std::min(d, bx * bx + by * by);
    const bool c1 = qy >= poly[i][1], c2 = qy < poly[j][1], c3 = ex * wy > ey * wx;
    if ((c1 && c2 && c3) || (!c1 && !c2 && !c3)) s = -s;
  }
  return s * std::sqrt(d);
}

// Lower envelope of the parabolas (x - q)^2 + f[q] over the q in [0, n) with a finite f (Felzenszwalb & Huttenlocher's
// 1-D distance transform): d[x] = the least value at x, at[x] = the q giving it (-1 when no f is finite).
void envelope(const float* f, int n, float* d, int* at, std::vector<int>& v, std::vector<double>& z) {
  v.resize(n);
  z.resize(size_t(n) + 1);
  int k = -1;
  for (int q = 0; q < n; ++q) {
    if (!(f[q] < kInf)) continue;
    if (k < 0) {
      k = 0;
      v[0] = q;
      z[0] = -std::numeric_limits<double>::infinity();
      z[1] = std::numeric_limits<double>::infinity();
      continue;
    }
    auto meet = [&](int p) { return ((double(f[q]) + double(q) * q) - (double(f[p]) + double(p) * p)) / (2.0 * (q - p)); };
    double s = meet(v[k]);
    while (s <= z[k]) s = meet(v[--k]);  // z[0] is -infinity: stops at k = 0
    ++k;
    v[k] = q;
    z[k] = s;
    z[size_t(k) + 1] = std::numeric_limits<double>::infinity();
  }
  if (k < 0) {
    for (int x = 0; x < n; ++x) d[x] = kInf, at[x] = -1;
    return;
  }
  int j = 0;
  for (int x = 0; x < n; ++x) {
    while (z[size_t(j) + 1] < x) ++j;
    const int q = v[j];
    d[x] = float(double(x - q) * (x - q) + f[q]);
    at[x] = q;
  }
}

// the voxel-space box of the 8 points o + a u + b v + w n, a, b, w each at either end of its range
void plane_bounds(Field& f, float alo, float ahi, float blo, float bhi, float wlo, float whi) {
  f.lo = {kInf, kInf, kInf};
  f.hi = {-kInf, -kInf, -kInf};
  for (float a : {alo, ahi})
    for (float b : {blo, bhi})
      for (float w : {wlo, whi}) {
        const V3 p = add(add(f.o, mul(f.u, a)), add(mul(f.v, b), mul(f.n, w)));
        f.lo = {std::min(f.lo.x, p.x), std::min(f.lo.y, p.y), std::min(f.lo.z, p.z)};
        f.hi = {std::max(f.hi.x, p.x), std::max(f.hi.y, p.y), std::max(f.hi.z, p.z)};
      }
}

// the 2-D grid over [alo, ahi] x [blo, bhi] (grains) padded by kPad, cells of at least a grain, at most kMaxCells
void plane_grid(Field& f, float alo, float ahi, float blo, float bhi) {
  const float w = ahi - alo + 2 * kPad, h = bhi - blo + 2 * kPad;
  f.cell = std::max(1.0f, std::max(w, h) / float(kMaxCells - 1));
  f.a0 = alo - kPad;
  f.b0 = blo - kPad;
  f.nx = std::min(kMaxCells, int(std::ceil(w / f.cell)) + 1);
  f.ny = std::min(kMaxCells, int(std::ceil(h / f.cell)) + 1);
}

template <class F> void each_row(int ny, F&& fn) {
  tbb::parallel_for(tbb::blocked_range<int>(0, ny, 4), [&](const tbb::blocked_range<int>& r) {
    for (int j = r.begin(); j < r.end(); ++j) fn(j);
  });
}

}  // namespace

std::shared_ptr<const Field> make_outline(const ShapeSpec& s, float voxel, const std::string& where) {
  const float iv = 1.0f / voxel;
  auto f = std::make_shared<Field>();
  f->kind = Field::Kind::Outline;
  f->o = mul(s.o, iv);
  f->u = s.u;
  f->v = s.v;
  f->n = unit(cross(s.u, s.v));
  std::vector<P2> poly;
  float alo = kInf, ahi = -kInf, blo = kInf, bhi = -kInf;
  for (const P2& q : s.pts) {
    poly.push_back({q[0] * iv, q[1] * iv});
    alo = std::min(alo, poly.back()[0]), ahi = std::max(ahi, poly.back()[0]);
    blo = std::min(blo, poly.back()[1]), bhi = std::max(bhi, poly.back()[1]);
  }
  plane_grid(*f, alo, ahi, blo, bhi);
  const int nx = f->nx, ny = f->ny;
  const float c = f->cell;
  // each inside cell is the centre of a ball (on the plane) as big as its distance to the outline
  f->radius.assign(size_t(nx) * ny, 0.0f);
  each_row(ny, [&](int j) {
    for (int i = 0; i < nx; ++i) {
      const float d = poly_sdf(poly, f->a0 + i * c, f->b0 + j * c);
      if (d < 0) f->radius[size_t(j) * nx + i] = -d;
    }
  });
  float most = 0;
  for (float r : f->radius) most = std::max(most, r);
  if (!(most > 0))
    fail(where + ".outline", "covers no grain of the clay (thinner than its detail)", "an outline wider than a grain");
  // per cell, the ball whose power |x - c|^2 - r_c^2 is least (in cells): the union of the balls is exactly the set
  // where the field below is negative; two separable passes of the lower envelope, keeping which ball gave it
  const float ic = 1.0f / c;
  std::vector<float> g(size_t(nx) * ny);
  std::vector<int> gi(size_t(nx) * ny);
  each_row(ny, [&](int j) {
    std::vector<float> fr(nx);
    std::vector<int> v;
    std::vector<double> z;
    for (int i = 0; i < nx; ++i) {
      const float r = f->radius[size_t(j) * nx + i] * ic;
      fr[i] = r > 0 ? -r * r : kInf;
    }
    envelope(fr.data(), nx, &g[size_t(j) * nx], &gi[size_t(j) * nx], v, z);
  });
  f->arg.assign(size_t(nx) * ny, -1);
  tbb::parallel_for(tbb::blocked_range<int>(0, nx, 4), [&](const tbb::blocked_range<int>& r) {
    std::vector<float> fc(ny), dc(ny);
    std::vector<int> ac(ny), v;
    std::vector<double> z;
    for (int i = r.begin(); i < r.end(); ++i) {
      for (int j = 0; j < ny; ++j) fc[j] = g[size_t(j) * nx + i];
      envelope(fc.data(), ny, dc.data(), ac.data(), v, z);
      for (int j = 0; j < ny; ++j)
        if (ac[j] >= 0) f->arg[size_t(j) * nx + i] = ac[j] * nx + gi[size_t(ac[j]) * nx + i];
    }
  });
  f->inv_puff = 1.0f / s.puff;
  f->scale = std::min(1.0f, s.puff);
  plane_bounds(*f, alo, ahi, blo, bhi, -most * s.puff, most * s.puff);
  return f;
}

std::shared_ptr<const Field> make_spin(const ShapeSpec& s, float voxel, const std::string& where) {
  const float iv = 1.0f / voxel;
  auto f = std::make_shared<Field>();
  f->kind = Field::Kind::Spin;
  f->o = mul(s.o, iv);
  f->u = s.u;
  f->v = s.v;
  f->n = unit(cross(s.u, s.v));
  // the profile closed by the axis: (0, first h), the points, (0, last h)
  std::vector<P2> poly;
  poly.push_back({0.0f, s.pts.front()[1] * iv});
  float rmax = 0, hlo = kInf, hhi = -kInf;
  for (const P2& q : s.pts) {
    poly.push_back({q[0] * iv, q[1] * iv});
    rmax = std::max(rmax, poly.back()[0]);
    hlo = std::min(hlo, poly.back()[1]), hhi = std::max(hhi, poly.back()[1]);
  }
  poly.push_back({0.0f, s.pts.back()[1] * iv});
  if (!(rmax > 0.5f))
    fail(where + ".profile", "stays within half a grain of the axis", "a profile reaching out from the axis");
  // r from 0 (the axis) out: the grid starts at r = 0 (no padding below), h padded both ways
  plane_grid(*f, 0.0f, rmax, hlo, hhi);
  f->a0 = 0.0f;
  f->nx = std::min(kMaxCells, int(std::ceil((rmax + kPad) / f->cell)) + 1);
  const int nx = f->nx, ny = f->ny;
  const float c = f->cell;
  f->table.resize(size_t(nx) * ny);
  each_row(ny, [&](int j) {
    for (int i = 0; i < nx; ++i) f->table[size_t(j) * nx + i] = poly_sdf(poly, i * c, f->b0 + j * c);
  });
  // a cylinder round the axis segment [hlo, hhi] of radius rmax
  f->lo = {kInf, kInf, kInf};
  f->hi = {-kInf, -kInf, -kInf};
  const float vv[3] = {f->v.x, f->v.y, f->v.z};
  for (float h : {hlo, hhi}) {
    const V3 p = add(f->o, mul(f->v, h));
    const float pp[3] = {p.x, p.y, p.z};
    float lo[3], hi[3];
    for (int a = 0; a < 3; ++a) {
      const float e = rmax * std::sqrt(std::max(0.0f, 1.0f - vv[a] * vv[a]));
      lo[a] = pp[a] - e, hi[a] = pp[a] + e;
    }
    f->lo = {std::min(f->lo.x, lo[0]), std::min(f->lo.y, lo[1]), std::min(f->lo.z, lo[2])};
    f->hi = {std::max(f->hi.x, hi[0]), std::max(f->hi.y, hi[1]), std::max(f->hi.z, hi[2])};
  }
  return f;
}

struct Field::Grid {
  openvdb::FloatGrid::Ptr grid;
  float iv = 1;  // the grid's distances are metres: to grains
};

float item_half_width(float blend) { return kBand + std::min(blend, detail::kBlendCap) + 6.1f + 3.0f; }

std::shared_ptr<const Field> make_item(const ShapeSpec& spec, const UsdStageRefPtr& stage, const SdfPath& clay,
                                       float voxel, float halfWidth, const std::string& where) {
  const std::string at = where + ".source";
  // the item's prim: the shallowest prim of that name under /World (an item's prim is named by its id; a prim inside
  // an imported file of the same name sits deeper than the import item holding it)
  UsdPrim item;
  {
    std::deque<UsdPrim> queue;
    if (UsdPrim world = stage->GetPrimAtPath(SdfPath("/World"))) queue.push_back(world);
    while (!queue.empty() && !item) {
      const UsdPrim p = queue.front();
      queue.pop_front();
      for (const UsdPrim& ch : p.GetFilteredChildren(UsdTraverseInstanceProxies())) {
        if (ch.GetPath() == SdfPath("/World/Looks") || ch.GetPath() == clay) continue;
        if (ch.GetName() == spec.source) {
          item = ch;
          break;
        }
        queue.push_back(ch);
      }
    }
  }
  if (!item) fail(at, "no item \"" + spec.source + "\" in the scene", "the id of a part or import of this scene");
  const UsdPrim clayPrim = stage->GetPrimAtPath(clay);
  if (!clayPrim) fail(where, "the clay's prim " + clay.GetString() + " is missing", "a clay built in this scene");
  const UsdTimeCode time = UsdTimeCode::EarliestTime();
  UsdGeomXformCache xc(time);
  const GfMatrix4d toClay = xc.GetLocalToWorldTransform(clayPrim).GetInverse();
  std::vector<openvdb::Vec3s> points;
  std::vector<openvdb::Vec3I> tris;
  float lo[3] = {kInf, kInf, kInf}, hi[3] = {-kInf, -kInf, -kInf};
  for (const UsdPrim& p : UsdPrimRange(item, UsdTraverseInstanceProxies())) {
    if (!p.IsA<UsdGeomMesh>()) continue;
    const UsdGeomMesh mesh(p);
    VtArray<GfVec3f> pts;
    VtArray<int> counts, indices;
    mesh.GetPointsAttr().Get(&pts, time);
    mesh.GetFaceVertexCountsAttr().Get(&counts, time);
    mesh.GetFaceVertexIndicesAttr().Get(&indices, time);
    if (pts.empty() || counts.empty()) continue;
    const GfMatrix4d m = xc.GetLocalToWorldTransform(p) * toClay;
    const uint32_t base = uint32_t(points.size());
    for (const GfVec3f& q : pts) {
      const GfVec3d c = m.Transform(GfVec3d(q));
      points.emplace_back(float(c[0]), float(c[1]), float(c[2]));
      for (int a = 0; a < 3; ++a) lo[a] = std::min(lo[a], float(c[a])), hi[a] = std::max(hi[a], float(c[a]));
    }
    size_t k = 0;
    for (int cnt : counts) {
      if (cnt < 0 || k + size_t(cnt) > indices.size())
        fail(at, "mesh " + p.GetPath().GetString() + " lists more face corners than it has", "a well-formed mesh");
      for (int t = 1; t + 1 < cnt; ++t) {  // a fan of triangles
        const int i0 = indices[k], i1 = indices[k + t], i2 = indices[k + t + 1];
        if (i0 < 0 || i1 < 0 || i2 < 0 || size_t(i0) >= pts.size() || size_t(i1) >= pts.size() || size_t(i2) >= pts.size())
          fail(at, "mesh " + p.GetPath().GetString() + " has a face naming a missing point", "a well-formed mesh");
        tris.emplace_back(base + uint32_t(i0), base + uint32_t(i1), base + uint32_t(i2));
      }
      k += size_t(cnt);
    }
  }
  if (tris.empty())
    fail(at, "item \"" + spec.source + "\" has no mesh with faces", "a part or import made of meshes");
  auto g = std::make_shared<Field::Grid>();
  const openvdb::math::Transform::Ptr xform = openvdb::math::Transform::createLinearTransform(voxel);
  g->grid = openvdb::tools::meshToLevelSet<openvdb::FloatGrid>(*xform, points, tris, halfWidth);
  g->iv = 1.0f / voxel;
  auto f = std::make_shared<Field>();
  f->kind = Field::Kind::Item;
  f->grid = g;
  const float iv = 1.0f / voxel;
  f->lo = {lo[0] * iv, lo[1] * iv, lo[2] * iv};
  f->hi = {hi[0] * iv, hi[1] * iv, hi[2] * iv};
  return f;
}

struct FieldEval::Probe {
  openvdb::FloatTree::ConstUnsafeAccessor acc;
  float iv;
  Probe(const openvdb::FloatTree& t, float i) : acc(t), iv(i) {}
};

FieldEval::FieldEval(const Field& f, bool mirror) : f_(f), mirror_(mirror) {
  if (f.kind == Field::Kind::Item) probe_ = std::make_unique<Probe>(f.grid->grid->constTree(), f.grid->iv);
}

FieldEval::~FieldEval() = default;

float FieldEval::operator()(V3 p) {
  const float d = raw(p);
  return mirror_ ? std::min(d, raw(V3{-p.x, p.y, p.z})) : d;
}

float FieldEval::raw(V3 p) {
  const Field& f = f_;
  switch (f.kind) {
    case Field::Kind::Outline: {
      const V3 rel = sub(p, f.o);
      const float a = dot(rel, f.u), b = dot(rel, f.v), w = dot(rel, f.n) * f.inv_puff;
      const float ic = 1.0f / f.cell;
      const int i = std::min(f.nx - 1, std::max(0, int(std::lround((a - f.a0) * ic))));
      const int j = std::min(f.ny - 1, std::max(0, int(std::lround((b - f.b0) * ic))));
      // the cell's own ball and its 8 neighbours' (the power diagram's cell edges fall between grid cells)
      float best = kInf;
      for (int dj = -1; dj <= 1; ++dj)
        for (int di = -1; di <= 1; ++di) {
          const int ii = std::min(f.nx - 1, std::max(0, i + di)), jj = std::min(f.ny - 1, std::max(0, j + dj));
          const int c = f.arg[size_t(jj) * f.nx + ii];
          if (c < 0) continue;
          const float da = a - (f.a0 + float(c % f.nx) * f.cell), db = b - (f.b0 + float(c / f.nx) * f.cell);
          best = std::min(best, std::sqrt(da * da + db * db + w * w) - f.radius[size_t(c)]);
        }
      return best * f.scale;
    }
    case Field::Kind::Spin: {
      const V3 rel = sub(p, f.o);
      const float h = dot(rel, f.v);
      const float r = len(sub(rel, mul(f.v, h)));
      const float ic = 1.0f / f.cell;
      const float x = (r - f.a0) * ic, y = (h - f.b0) * ic;
      const float cx = std::min(float(f.nx - 1), std::max(0.0f, x)), cy = std::min(float(f.ny - 1), std::max(0.0f, y));
      const float out = std::sqrt((x - cx) * (x - cx) + (y - cy) * (y - cy)) * f.cell;  // past the grid: farther
      const int ix = std::min(f.nx - 2, int(cx)), iy = std::min(f.ny - 2, int(cy));
      const float fx = cx - ix, fy = cy - iy;
      const float* t = f.table.data();
      const size_t r0 = size_t(iy) * f.nx + ix, r1 = r0 + f.nx;
      const float v0 = t[r0] + (t[r0 + 1] - t[r0]) * fx, v1 = t[r1] + (t[r1 + 1] - t[r1]) * fx;
      return v0 + (v1 - v0) * fy + out;
    }
    case Field::Kind::Item: {
      auto& acc = probe_->acc;
      const float fx = std::floor(p.x), fy = std::floor(p.y), fz = std::floor(p.z);
      const int ix = int(fx), iy = int(fy), iz = int(fz);
      using openvdb::Coord;
      if (fx == p.x && fy == p.y && fz == p.z) return acc.getValue(Coord(ix, iy, iz)) * probe_->iv;
      const float tx = p.x - fx, ty = p.y - fy, tz = p.z - fz;
      auto v = [&](int a, int b, int c) { return acc.getValue(Coord(ix + a, iy + b, iz + c)); };
      const float c00 = v(0, 0, 0) + (v(1, 0, 0) - v(0, 0, 0)) * tx, c10 = v(0, 1, 0) + (v(1, 1, 0) - v(0, 1, 0)) * tx;
      const float c01 = v(0, 0, 1) + (v(1, 0, 1) - v(0, 0, 1)) * tx, c11 = v(0, 1, 1) + (v(1, 1, 1) - v(0, 1, 1)) * tx;
      const float c0 = c00 + (c10 - c00) * ty, c1 = c01 + (c11 - c01) * ty;
      return (c0 + (c1 - c0) * tz) * probe_->iv;
    }
  }
  return kInf;
}

}  // namespace r3d::clay
