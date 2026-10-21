// Every shape is made of two pieces: a loft (a closed outline in XZ, pushed out along its normals by a
// profile of rows) and flat caps. Outline order: angle grows from +X towards -Z, so quads (a, b, c, d)
// face outwards and u grows to the right seen from outside.
#include "primitives.h"

#include <algorithm>
#include <cmath>
#include <vector>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

constexpr float kPi = 3.14159265358979f;
float rad(float deg) { return deg * kPi / 180.0f; }

// Closed outline in XZ: the point at offset o is c[i] + n[i] * o. The last entry repeats the first.
struct Outline {
  std::vector<GfVec2f> c, n;
};

Outline circle(float r, int segments) {
  Outline o;
  for (int i = 0; i <= segments; ++i) {
    const float a = 2.0f * kPi * float(i % segments) / float(segments);
    const GfVec2f n(std::cos(a), -std::sin(a));
    o.c.push_back(n * r);
    o.n.push_back(n);
  }
  return o;
}

// Rectangle of corner centres (±cx, ±cz); each corner turns 90° in `segments` steps.
Outline rounded_rect(float cx, float cz, int segments) {
  Outline o;
  const GfVec2f centre[4] = {{cx, -cz}, {-cx, -cz}, {-cx, cz}, {cx, cz}};
  for (int k = 0; k < 4; ++k)
    for (int s = 0; s <= segments; ++s) {
      const float a = rad(90.0f * (float(k) + float(s) / float(segments)));
      o.c.push_back(centre[k]);
      o.n.push_back(GfVec2f(std::cos(a), -std::sin(a)));
    }
  o.c.push_back(o.c.front());
  o.n.push_back(o.n.front());
  return o;
}

struct Row {
  float o, y, a;  // offset along the outline normal, height, normal angle up from horizontal (radians)
};

struct Builder {
  MeshData m;
  std::vector<GfVec2f> uv;  // per vertex while building

  int add(const GfVec3f& p, const GfVec3f& n, const GfVec2f& t) {
    m.points.push_back(p);
    m.normals.push_back(n);
    uv.push_back(t);
    return int(m.points.size()) - 1;
  }

  GfVec3f face_normal(const std::vector<int>& f) const {  // Newell's method, unnormalised
    GfVec3f n(0.0f);
    for (size_t i = 0; i < f.size(); ++i) {
      const GfVec3f &p = m.points[f[i]], &q = m.points[f[(i + 1) % f.size()]];
      n += GfVec3f((p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]),
                   (p[0] - q[0]) * (p[1] + q[1]));
    }
    return n;
  }

  void face(const std::vector<int>& f) {  // zero-area faces (collapsed corners, sharp edges) are dropped
    if (f.size() < 3 || face_normal(f).GetLength() < 1e-12f) return;
    m.counts.push_back(int(f.size()));
    for (int i : f) m.indices.push_back(i);
  }

  MeshData done(bool smooth) {
    if (!smooth) {  // flat: every face gets its own corners, all with the face normal
      Builder flat;
      size_t k = 0;
      for (int count : m.counts) {
        std::vector<int> f(m.indices.begin() + k, m.indices.begin() + k + count);
        const GfVec3f n = face_normal(f).GetNormalized();
        std::vector<int> g;
        for (int i : f) g.push_back(flat.add(m.points[i], n, uv[i]));
        flat.face(g);
        k += count;
      }
      return flat.done(true);
    }
    for (int i : m.indices) m.st.push_back(uv[i]);
    return m;
  }
};

GfVec3f at(const Outline& ol, size_t i, float o, float y) {
  const GfVec2f p = ol.c[i] + ol.n[i] * o;
  return GfVec3f(p[0], y, p[1]);
}

void loft(Builder& b, const Outline& ol, const std::vector<Row>& rows) {
  float o_ref = 0.0f;
  for (const Row& r : rows) o_ref = std::max(o_ref, r.o);
  std::vector<float> u(1, 0.0f), v(1, 0.0f);
  for (size_t i = 1; i < ol.c.size(); ++i) u.push_back(u.back() + (at(ol, i, o_ref, 0) - at(ol, i - 1, o_ref, 0)).GetLength());
  for (size_t j = 1; j < rows.size(); ++j) v.push_back(v.back() + std::hypot(rows[j].o - rows[j - 1].o, rows[j].y - rows[j - 1].y));
  const size_t nu = ol.c.size();
  const int base = int(b.m.points.size());
  for (size_t j = 0; j < rows.size(); ++j)
    for (size_t i = 0; i < nu; ++i) {
      const float c = std::cos(rows[j].a), s = std::sin(rows[j].a);
      b.add(at(ol, i, rows[j].o, rows[j].y), GfVec3f(ol.n[i][0] * c, s, ol.n[i][1] * c),
            GfVec2f(u[i] / std::max(u.back(), 1e-9f), v[j] / std::max(v.back(), 1e-9f)));
    }
  for (size_t j = 0; j + 1 < rows.size(); ++j)
    for (size_t i = 0; i + 1 < nu; ++i) {
      const int a = base + int(j * nu + i), d = a + int(nu);
      b.face({a, a + 1, d + 1, d});
    }
}

// Flat cap of the outline at offset o and height y; UVs span width x depth.
void cap(Builder& b, const Outline& ol, float o, float y, bool up, float width, float depth) {
  std::vector<int> f;
  for (size_t i = 0; i + 1 < ol.c.size(); ++i) {
    const GfVec3f p = at(ol, i, o, y);
    if (!f.empty() && (p - b.m.points[f.back()]).GetLength() < 1e-7f) continue;  // collapsed corner
    const GfVec2f t(p[0] / width + 0.5f, (up ? -p[2] : p[2]) / depth + 0.5f);
    f.push_back(b.add(p, GfVec3f(0, up ? 1.0f : -1.0f, 0), t));
  }
  if (f.size() > 1 && (b.m.points[f.back()] - b.m.points[f.front()]).GetLength() < 1e-7f) f.pop_back();
  if (!up) std::reverse(f.begin(), f.end());
  b.face(f);
}

// Rows of a straight wall of height h whose top and bottom edges round off with radius r in `steps`.
std::vector<Row> bevelled_wall(float h, float r, int steps) {
  std::vector<Row> rows;
  for (int half = 0; half < 2; ++half)
    for (int k = 0; k <= steps; ++k) {
      const float a = steps ? rad(90.0f * (float(k) / float(steps) - (half ? 0.0f : 1.0f))) : 0.0f;
      const float y = (half ? 1.0f : -1.0f) * (h / 2 - r) + r * std::sin(a);
      rows.push_back({(k == steps && half) || (k == 0 && !half && steps) ? 0.0f : r * std::cos(a), y, a});
    }
  return rows;
}

}  // namespace

MeshData make_box(float width, float height, float depth, float bevel, int segments, bool smooth) {
  const int steps = bevel > 0 ? segments : 0;
  const Outline ol = rounded_rect(width / 2 - bevel, depth / 2 - bevel, std::max(1, steps));
  Builder b;
  loft(b, ol, bevelled_wall(height, bevel, steps));
  cap(b, ol, 0.0f, height / 2, true, width, depth);
  cap(b, ol, 0.0f, -height / 2, false, width, depth);
  return b.done(smooth);
}

MeshData make_cylinder(float radius, float height, float bevel, int segments, bool smooth) {
  const int steps = bevel > 0 ? std::max(2, segments / 8) : 0;
  const Outline ol = circle(radius - bevel, segments);
  Builder b;
  loft(b, ol, bevelled_wall(height, bevel, steps));
  cap(b, ol, 0.0f, height / 2, true, 2 * radius, 2 * radius);
  cap(b, ol, 0.0f, -height / 2, false, 2 * radius, 2 * radius);
  return b.done(smooth);
}

MeshData make_sphere(float radius, int segments, bool smooth) {
  const int rings = std::max(2, segments / 2);
  std::vector<Row> rows;
  for (int k = 0; k <= rings; ++k) {
    const float a = rad(-90.0f + 180.0f * float(k) / float(rings));
    rows.push_back({(k == 0 || k == rings) ? 0.0f : radius * std::cos(a), radius * std::sin(a), a});
  }
  Builder b;
  loft(b, circle(0.0f, segments), rows);
  return b.done(smooth);
}

MeshData make_torus(float radius, float tube, int segments, bool smooth) {
  const int steps = std::max(3, segments / 2);
  std::vector<Row> rows;
  for (int k = 0; k <= steps; ++k) {
    const float a = rad(-180.0f + 360.0f * float(k % steps) / float(steps));
    rows.push_back({tube * std::cos(a), tube * std::sin(a), a});
  }
  Builder b;
  loft(b, circle(radius, segments), rows);
  return b.done(smooth);
}

MeshData make_plane(float width, float depth) {
  Builder b;
  cap(b, rounded_rect(width / 2, depth / 2, 1), 0.0f, 0.0f, true, width, depth);
  return b.done(true);
}

MeshData make_disc(float radius, int segments) {
  Builder b;
  cap(b, circle(radius, segments), 0.0f, 0.0f, true, 2 * radius, 2 * radius);
  return b.done(true);
}

}  // namespace r3d
