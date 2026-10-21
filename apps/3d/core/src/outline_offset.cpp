#include "outline_offset.h"

#include <algorithm>
#include <cmath>

#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr double kMiterLimit = 4.0;   // a needle-sharp corner moves at most 4 x the offset
constexpr double kSamePoint = 1e-9;   // m: closer points are one point

double cross(const GfVec2d& a, const GfVec2d& b) { return a[0] * b[1] - a[1] * b[0]; }

GfVec2d edge_normal(const Contour& c, size_t i) {  // right of the walking direction = away from the solid
  const GfVec2d d = c[(i + 1) % c.size()] - c[i];
  const double len = d.GetLength();
  return len > 0 ? GfVec2d(d[1] / len, -d[0] / len) : GfVec2d(0.0);
}

// Proper crossings only: touching or collinear edges are left to the area and earcut checks.
bool segments_cross(const GfVec2d& p1, const GfVec2d& p2, const GfVec2d& q1, const GfVec2d& q2) {
  if (std::max(p1[0], p2[0]) < std::min(q1[0], q2[0]) || std::max(q1[0], q2[0]) < std::min(p1[0], p2[0]) ||
      std::max(p1[1], p2[1]) < std::min(q1[1], q2[1]) || std::max(q1[1], q2[1]) < std::min(p1[1], p2[1]))
    return false;
  const double a = cross(p2 - p1, q1 - p1), b = cross(p2 - p1, q2 - p1);
  const double c = cross(q2 - q1, p1 - q1), d = cross(q2 - q1, p2 - q1);
  return ((a > 0 && b < 0) || (a < 0 && b > 0)) && ((c > 0 && d < 0) || (c < 0 && d > 0));
}

GfVec2d read_point(const JsValue& v, const std::string& where) {
  if (!v.IsArray() || v.GetJsArray().size() != 2) fail(where, "is not a list of 2", "[x, y] numbers");
  GfVec2d p;
  for (int i = 0; i < 2; ++i) {
    const JsValue& n = v.GetJsArray()[i];
    if (!is_number(n)) fail(where, "holds " + n.GetTypeName(), "[x, y] numbers");
    p[i] = to_number(n);
    if (!std::isfinite(p[i])) fail(where, "holds a number that is not finite", "[x, y] finite numbers");
  }
  return p;
}

Contour read_contour(const JsValue& v, const std::string& where) {
  if (!v.IsArray()) fail(where, "is " + v.GetTypeName(), "a list of [x, y] points");
  const JsArray& a = v.GetJsArray();
  Contour c;
  for (size_t i = 0; i < a.size(); ++i) {
    const GfVec2d p = read_point(a[i], where + "[" + std::to_string(i) + "]");
    if (c.empty() || (p - c.back()).GetLength() > kSamePoint) c.push_back(p);
  }
  while (c.size() > 1 && (c.front() - c.back()).GetLength() <= kSamePoint) c.pop_back();
  if (c.size() < 3) fail(where, std::to_string(c.size()) + " different points", "at least 3 points");
  if (std::abs(signed_area(c)) < 1e-14) fail(where, "encloses no area (its points lie on a line)", "an outline around an area");
  return c;
}

}  // namespace

double signed_area(const Contour& c) {
  double a = 0.0;
  for (size_t i = 0; i < c.size(); ++i) a += cross(c[i], c[(i + 1) % c.size()]);
  return a / 2.0;
}

ContourFrame frame_of(const Contour& c, double sharp_deg) {
  const size_t n = c.size();
  const double cos_sharp = std::cos(sharp_deg * kPi / 180.0);
  ContourFrame f;
  for (size_t i = 0; i < n; ++i) {
    const GfVec2d a = edge_normal(c, (i + n - 1) % n), b = edge_normal(c, i);
    f.n_in.push_back(a);
    f.n_out.push_back(b);
    f.sharp.push_back(GfDot(a, b) < cos_sharp);
    GfVec2d m = a + b;
    const double len = m.GetLength();
    if (len < 1e-9) {  // the outline doubles back on itself: no bisector
      f.miter.push_back(b);
      continue;
    }
    m /= len;
    f.miter.push_back(m / std::max(GfDot(m, a), 1.0 / kMiterLimit));
  }
  return f;
}

Contour inset(const Contour& c, const ContourFrame& f, double d) {
  Contour out;
  for (size_t i = 0; i < c.size(); ++i) out.push_back(c[i] - f.miter[i] * d);
  return out;
}

namespace {

void merge_stray_edges(Contour& c, double bevel) {
  auto len = [&](size_t i) { return (c[(i + 1) % c.size()] - c[i]).GetLength(); };
  for (bool merged = true; merged && c.size() > 3;) {
    merged = false;
    for (size_t i = 0; i < c.size() && c.size() > 3; ++i) {
      const size_t n = c.size(), j = (i + 1) % n;
      const double e = len(i);
      if (e >= bevel / 3 || e >= 0.5 * std::min(len((i + n - 1) % n), len(j))) continue;
      c[i] = (c[i] + c[j]) / 2.0;
      c.erase(c.begin() + std::ptrdiff_t(j));
      merged = true;
    }
  }
}

}  // namespace

std::vector<OutlineShape> without_stray_edges(std::vector<OutlineShape> shapes, double bevel) {
  for (OutlineShape& s : shapes) {
    merge_stray_edges(s.outer, bevel);
    for (Contour& h : s.holes) merge_stray_edges(h, bevel);
  }
  return shapes;
}

bool crosses(const std::vector<Contour>& contours) {
  for (size_t ci = 0; ci < contours.size(); ++ci)
    for (size_t cj = ci; cj < contours.size(); ++cj) {
      const Contour &p = contours[ci], &q = contours[cj];
      for (size_t i = 0; i < p.size(); ++i)
        for (size_t j = (ci == cj ? i + 1 : 0); j < q.size(); ++j) {
          if (ci == cj && (j == i + 1 || (i == 0 && j == p.size() - 1))) continue;  // neighbours share a corner
          if (segments_cross(p[i], p[(i + 1) % p.size()], q[j], q[(j + 1) % q.size()])) return true;
        }
    }
  return false;
}

std::vector<OutlineShape> read_outline(const JsArray& a, const std::string& where) {
  const char* accepted = "a list of {\"outer\": [[x, y], …], \"holes\": [[[x, y], …], …]}";
  if (a.empty()) fail(where, "is empty", accepted);
  std::vector<OutlineShape> shapes;
  for (size_t i = 0; i < a.size(); ++i) {
    const std::string w = where + "[" + std::to_string(i) + "]";
    if (!a[i].IsObject()) fail(w, "is " + a[i].GetTypeName(), accepted);
    Reader r(a[i].GetJsObject(), w);
    OutlineShape s;
    s.outer = read_contour(r.get("outer", "a list of [x, y] points"), r.at("outer"));
    if (signed_area(s.outer) < 0) std::reverse(s.outer.begin(), s.outer.end());
    const JsArray& holes = r.list("holes");
    for (size_t j = 0; j < holes.size(); ++j) {
      s.holes.push_back(read_contour(holes[j], r.at("holes") + "[" + std::to_string(j) + "]"));
      if (signed_area(s.holes.back()) > 0) std::reverse(s.holes.back().begin(), s.holes.back().end());
    }
    r.finish();
    std::vector<Contour> all{s.outer};
    all.insert(all.end(), s.holes.begin(), s.holes.end());
    if (crosses(all))
      fail(w, "its edges cross (the outer outline crosses itself or a hole)",
           "one outer outline per shape, holes inside it, no edges crossing (overlapping glyph parts merged first)");
    shapes.push_back(std::move(s));
  }
  return shapes;
}

}  // namespace r3d
