// Each contour is lofted through rows of a profile (front bevel, side, back bevel), like primitives.cpp's
// loft, but the rows move the contour along its mitred corner directions so straight edges stay straight.
// Caps are the contours at the full inset, cut into triangles by earcut.
#include "extrude.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

#include <pxr/base/gf/vec3d.h>

#include "json_read.h"
#include "third_party/earcut/earcut.hpp"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr double kSharpDeg = 30.0;  // the outline turning more than this at a corner = a hard edge

double cross(const GfVec2d& a, const GfVec2d& b) { return a[0] * b[1] - a[1] * b[0]; }

struct Face {
  std::array<int, 4> v;
  std::array<GfVec2f, 4> t;  // face-varying UV per corner
  int n;
};

struct Builder {
  std::vector<GfVec3d> points;
  VtArray<GfVec3f> normals;
  std::vector<Face> faces[4];  // per FacePart, so each part is one run of face indices

  int add(const GfVec3d& p, const GfVec3d& n) {
    points.push_back(p);
    normals.push_back(GfVec3f(n));
    return int(points.size()) - 1;
  }

  GfVec3d face_normal(const Face& f) const {  // Newell's method, unnormalised
    GfVec3d n(0.0);
    for (int i = 0; i < f.n; ++i) {
      const GfVec3d &p = points[f.v[i]], &q = points[f.v[(i + 1) % f.n]];
      n += GfVec3d((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]), (p[0] - q[0]) * (p[1] + q[1]));
    }
    return n;
  }

  void face(FacePart part, const Face& f) {  // zero-area faces (a side of zero height, hairpin corners) are dropped
    if (face_normal(f).GetLength() > 1e-18) faces[part].push_back(f);
  }

  Extruded done(bool smooth) const {
    Extruded out;
    MeshData& m = out.mesh;
    if (smooth) {
      for (const GfVec3d& p : points) m.points.push_back(GfVec3f(p));
      m.normals = normals;
    }
    for (int g = 0; g < 4; ++g)
      for (const Face& f : faces[g]) {
        const GfVec3f fn(face_normal(f).GetNormalized());
        out.groups[g].push_back(int(m.counts.size()));
        m.counts.push_back(f.n);
        for (int k = 0; k < f.n; ++k) {
          int i = f.v[k];
          if (!smooth) {  // flat: every face gets its own corners, all with the face normal
            i = int(m.points.size());
            m.points.push_back(GfVec3f(points[f.v[k]]));
            m.normals.push_back(fn);
          }
          m.indices.push_back(i);
          m.st.push_back(f.t[k]);
        }
      }
    return out;
  }
};

struct Row {
  double inset, z, a;  // inset towards the solid, height, normal angle up from the outline's plane (radians)
  FacePart below;      // part of the band between this row and the next
};

std::vector<Row> rows_of(double depth, double bevel, int steps) {
  std::vector<Row> rows;
  const double h = depth / 2 - bevel;
  for (int k = 0; k <= steps; ++k) {  // front bevel: from the cap's edge (facing +Z) round to the side
    const double a = steps ? kPi / 2 * (1.0 - double(k) / steps) : 0.0;
    rows.push_back({bevel * (1 - std::cos(a)), h + bevel * std::sin(a), a, k < steps ? kBevel : kSide});
  }
  for (int k = 0; k <= steps; ++k) {  // back bevel: from the side round to the back cap's edge
    const double a = steps ? -kPi / 2 * double(k) / steps : 0.0;
    rows.push_back({bevel * (1 - std::cos(a)), -h + bevel * std::sin(a), a, kBevel});
  }
  return rows;
}

void loft(Builder& b, const Contour& c, const ContourFrame& f, const std::vector<Row>& rows, double bevel) {
  const size_t n = c.size();
  const std::vector<double> share = inset_share(c, f, bevel);  // the same narrowing as the caps' inset
  std::vector<double> u(n + 1, 0.0), v(rows.size(), 0.0);  // perimeter distance; distance from the front
  for (size_t i = 0; i < n; ++i) u[i + 1] = u[i] + (c[(i + 1) % n] - c[i]).GetLength();
  for (size_t j = 1; j < rows.size(); ++j)
    v[j] = v[j - 1] + std::hypot(rows[j].inset - rows[j - 1].inset, rows[j].z - rows[j - 1].z);
  // Columns of vertices: a sharp corner has two (one per edge's normal), a smooth one shares the bisector.
  std::vector<GfVec2d> col_n;
  std::vector<size_t> col_corner;
  std::vector<int> col_in(n), col_out(n);
  auto column = [&](size_t i, const GfVec2d& nrm) {
    col_n.push_back(nrm);
    col_corner.push_back(i);
    return int(col_n.size()) - 1;
  };
  for (size_t i = 0; i < n; ++i) {
    if (f.sharp[i]) {
      col_in[i] = column(i, f.n_in[i]);
      col_out[i] = column(i, f.n_out[i]);
      continue;
    }
    const GfVec2d s = f.n_in[i] + f.n_out[i];
    col_in[i] = col_out[i] = column(i, s.GetLength() > 1e-9 ? s / s.GetLength() : f.n_out[i]);
  }
  const size_t nc = col_n.size();
  std::vector<int> id(rows.size() * nc);
  for (size_t j = 0; j < rows.size(); ++j)
    for (size_t k = 0; k < nc; ++k) {
      const Row& r = rows[j];
      const double s = share[col_corner[k]];  // a narrowed bevel is a quarter ellipse: s × as wide, as tall
      const GfVec2d p = c[col_corner[k]] - f.miter[col_corner[k]] * (r.inset * s);
      const GfVec3d nrm(col_n[k][0] * std::cos(r.a), col_n[k][1] * std::cos(r.a), s * std::sin(r.a));
      id[j * nc + k] = b.add(GfVec3d(p[0], p[1], r.z), nrm.GetNormalized());
    }
  // Quads seen from outside: u grows to the right, v (0 at the back, 1 at the front) upwards.
  for (size_t i = 0; i < n; ++i) {
    const size_t e = (i + 1) % n;
    const float u0 = float(u[i] / u[n]), u1 = float(u[i + 1] / u[n]);
    for (size_t j = 0; j + 1 < rows.size(); ++j) {
      const float vt = float(1.0 - v[j] / v.back()), vb = float(1.0 - v[j + 1] / v.back());
      const size_t top = j * nc, bot = (j + 1) * nc;
      b.face(rows[j].below, Face{{id[bot + col_out[i]], id[bot + col_in[e]], id[top + col_in[e]], id[top + col_out[i]]},
                                 {GfVec2f(u0, vb), GfVec2f(u1, vb), GfVec2f(u1, vt), GfVec2f(u0, vt)}, 4});
    }
  }
}

struct Box {
  GfVec2d lo, size;
};

// One shape's flat cap at height z, its contours inset by `by`. UVs 0..1 over the whole outline's box,
// mirrored on the back so a texture reads right from behind.
void cap(Builder& b, const OutlineShape& s, const std::vector<ContourFrame>& frames, double by, double z, bool front,
         const Box& box, const std::string& where) {
  using Point = std::array<double, 2>;
  std::vector<std::vector<Point>> poly;
  std::vector<GfVec2d> flat;
  std::vector<int> ids;
  for (size_t k = 0; k <= s.holes.size(); ++k) {
    poly.emplace_back();
    for (const GfVec2d& p : inset(k ? s.holes[k - 1] : s.outer, frames[k], by)) {
      poly.back().push_back({p[0], p[1]});
      flat.push_back(p);
      ids.push_back(b.add(GfVec3d(p[0], p[1], z), GfVec3d(0.0, 0.0, front ? 1.0 : -1.0)));
    }
  }
  const std::vector<uint32_t> tri = mapbox::earcut<uint32_t>(poly);
  if (tri.empty()) fail(where, "its cap could not be cut into triangles", "an outline whose edges don't touch or overlap");
  auto st = [&](uint32_t i) {
    const double x = (flat[i][0] - box.lo[0]) / box.size[0], y = (flat[i][1] - box.lo[1]) / box.size[1];
    return GfVec2f(float(front ? x : 1.0 - x), float(y));
  };
  for (size_t k = 0; k + 2 < tri.size(); k += 3) {
    uint32_t p = tri[k], q = tri[k + 1], r = tri[k + 2];
    if ((cross(flat[q] - flat[p], flat[r] - flat[p]) > 0) != front) std::swap(q, r);  // front CCW, back CW from +Z
    b.face(front ? kFront : kBack, Face{{ids[p], ids[q], ids[r], 0}, {st(p), st(q), st(r), GfVec2f(0.0f)}, 3});
  }
}

// Index of the first shape whose contours, inset by d, cross or turn inside out; -1 when all fit.
int misfit(const std::vector<OutlineShape>& shapes, const std::vector<std::vector<ContourFrame>>& frames, double d) {
  for (size_t si = 0; si < shapes.size(); ++si) {
    std::vector<Contour> in;
    for (size_t k = 0; k <= shapes[si].holes.size(); ++k) {
      const Contour& c = k ? shapes[si].holes[k - 1] : shapes[si].outer;
      in.push_back(inset(c, frames[si][k], d));
      if (signed_area(in.back()) * signed_area(c) <= 0) return int(si);
    }
    if (crosses(in)) return int(si);
  }
  return -1;
}

}  // namespace

int outline_bevel_steps(int segments) { return std::clamp(segments, 1, 16); }

Extruded make_extrusion(const std::vector<OutlineShape>& given, double depth, double bevel, int segments,
                        bool smooth, const std::string& where) {
  const std::vector<OutlineShape> shapes = bevel > 0 ? without_stray_edges(given, bevel) : given;
  std::vector<std::vector<ContourFrame>> frames(shapes.size());
  GfVec2d lo(1e300), hi(-1e300);
  for (size_t si = 0; si < shapes.size(); ++si) {
    frames[si].push_back(frame_of(shapes[si].outer, kSharpDeg));
    for (const Contour& h : shapes[si].holes) frames[si].push_back(frame_of(h, kSharpDeg));
    for (const GfVec2d& p : shapes[si].outer)
      for (int i = 0; i < 2; ++i) lo[i] = std::min(lo[i], p[i]), hi[i] = std::max(hi[i], p[i]);
  }
  if (bevel > 0) {
    const int bad = misfit(shapes, frames, bevel);
    if (bad >= 0) {  // halve until it fits, then narrow the gap: the largest bevel that works, to ~1/64
      double ok = bevel / 2;
      while (ok > 1e-6 && misfit(shapes, frames, ok) >= 0) ok /= 2;
      for (double step = ok / 2; ok > 1e-6 && step > ok / 64; step /= 2)
        if (misfit(shapes, frames, ok + step) < 0) ok += step;
      fail(where + ".bevel",
           std::to_string(bevel) + " m is too big for " + where + ".outline[" + std::to_string(bad) +
               "] (the inset outline would cross itself or turn inside out)",
           ok > 1e-6 ? "at most " + std::to_string(ok) + " m for this outline" : "0 (this outline is too thin for a bevel)");
    }
  }
  const Box box{lo, hi - lo};
  const std::vector<Row> rows = rows_of(depth, bevel, bevel > 0 ? outline_bevel_steps(segments) : 0);
  Builder b;
  for (size_t si = 0; si < shapes.size(); ++si) {
    const std::string w = where + ".outline[" + std::to_string(si) + "]";
    cap(b, shapes[si], frames[si], bevel, depth / 2, true, box, w);
    cap(b, shapes[si], frames[si], bevel, -depth / 2, false, box, w);
    if (depth <= 0) continue;  // a flat card: front and back only
    loft(b, shapes[si].outer, frames[si][0], rows, bevel);
    for (size_t k = 0; k < shapes[si].holes.size(); ++k) loft(b, shapes[si].holes[k], frames[si][k + 1], rows, bevel);
  }
  return b.done(smooth);
}

}  // namespace r3d
