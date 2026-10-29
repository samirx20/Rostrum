// Copies along a path (layout `path`, ENGINE_CONTRACT.md § 2, Copies): the compiler sends the path item's outlines as
// contours of points in the copies item's space; the copies are spread over all of them evenly by length, each contour its
// own run (a closed one wraps round), and each may turn to face along it.
#include <pxr/base/gf/matrix3d.h>
#include <pxr/base/gf/vec3d.h>

#include <algorithm>
#include <cmath>

#include "copies.h"
#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace copies {
namespace {

// One straight piece of the path: from a to b, `end` = the path's length so far at b.
struct Leg {
  GfVec3d a, b;
  double end;
};

std::vector<Leg> legs(const Params& p, double* total) {
  std::vector<Leg> out;
  double length = 0;
  for (size_t c = 0; c < p.pathPoints.size(); ++c) {
    const auto& pts = p.pathPoints[c];
    const size_t n = pts.size(), steps = c < p.pathClosed.size() && p.pathClosed[c] ? n : n - 1;
    for (size_t i = 0; n >= 2 && i < steps; ++i) {
      const GfVec3d a(pts[i]), b(pts[(i + 1) % n]);
      const double l = (b - a).GetLength();
      if (l <= 1e-9) continue;  // a repeated point
      length += l;
      out.push_back({a, b, length});
    }
  }
  *total = length;
  return out;
}

// The path's flat side (Newell's sum over its contours; an outline's outer turns one way and its holes the other, so the
// outers win), unit; the copies item's up when the path is a straight line.
GfVec3d facing(const Params& p) {
  GfVec3d n(0.0);
  for (const auto& pts : p.pathPoints)
    for (size_t i = 0; i < pts.size(); ++i) {
      const GfVec3d a(pts[i]), b(pts[(i + 1) % pts.size()]);
      n += GfVec3d((a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1]));
    }
  return n.Normalize() < 1e-12 ? GfVec3d::YAxis() : n;
}

// The turn that puts the source's +X along `along` and its +Y as near `up` as it goes.
GfRotation along_path(const GfVec3d& along, const GfVec3d& up) {
  GfVec3d y = up - along * GfDot(up, along);
  if (y.Normalize() < 1e-9) {  // the path runs straight along `up`: any up across it
    y = GfCross(along, std::abs(along[0]) < 0.9 ? GfVec3d::XAxis() : GfVec3d::ZAxis());
    y.Normalize();
  }
  const GfVec3d z = GfCross(along, y);
  return GfMatrix3d(along[0], along[1], along[2], y[0], y[1], y[2], z[0], z[1], z[2]).ExtractRotation();
}

}  // namespace

std::vector<std::vector<GfVec3f>> read_path_points(const JsValue& v, const std::string& where) {
  const std::string accepted = "a list of contours, each a list of 2 or more [x, y, z] (the copies item's space)";
  if (!v.IsArray()) fail(where, "is " + v.GetTypeName(), accepted);
  std::vector<std::vector<GfVec3f>> out;
  for (size_t c = 0; c < v.GetJsArray().size(); ++c) {
    const JsValue& contour = v.GetJsArray()[c];
    const std::string w = where + "[" + std::to_string(c) + "]";
    if (!contour.IsArray() || contour.GetJsArray().size() < 2) fail(w, "is not a list of 2 or more points", accepted);
    std::vector<GfVec3f> pts;
    for (size_t i = 0; i < contour.GetJsArray().size(); ++i) {
      const GfVec3f q = Reader::vec3_of(contour.GetJsArray()[i], w + "[" + std::to_string(i) + "]");
      if (!std::isfinite(q[0]) || !std::isfinite(q[1]) || !std::isfinite(q[2])) fail(w, "has a point that is not finite", accepted);
      pts.push_back(q);
    }
    out.push_back(std::move(pts));
  }
  return out;
}

std::vector<bool> read_path_closed(const JsValue& v, const std::string& where) {
  if (!v.IsArray()) fail(where, "is " + v.GetTypeName(), "a list of true / false, one per contour of pathPoints");
  std::vector<bool> out;
  for (size_t i = 0; i < v.GetJsArray().size(); ++i) {
    const JsValue& b = v.GetJsArray()[i];
    if (!b.IsBool()) fail(where + "[" + std::to_string(i) + "]", "is " + b.GetTypeName(), "true or false");
    out.push_back(b.GetBool());
  }
  return out;
}

void check_path(const Params& p, const std::string& where) {
  if (p.layout != "path") return;
  if (p.pathPoints.empty())
    fail(where + ".pathPoints", "no path", "the path item's contours (the compiler sends them with layout path)");
  if (p.pathClosed.size() != p.pathPoints.size())
    fail(where + ".pathClosed", std::to_string(p.pathClosed.size()) + " flags for " + std::to_string(p.pathPoints.size()) +
         " contours", "one true / false per contour of pathPoints");
  double total = 0;
  legs(p, &total);
  if (total <= 1e-9) fail(where + ".pathPoints", "has no length", "contours whose points are not all in one place");
}

void lay_path(const Params& p, std::vector<GfVec3f>* pos, std::vector<GfRotation>* turn) {
  double total = 0;
  const std::vector<Leg> path = legs(p, &total);
  const GfVec3d up = facing(p);
  for (int i = 0; i < p.count; ++i) {
    double share = double(i) / p.count + p.pathShift;
    share -= std::floor(share);
    const double at = share * total;
    const size_t k = std::min(size_t(std::upper_bound(path.begin(), path.end(), at,
                                                      [](double d, const Leg& l) { return d < l.end; }) - path.begin()),
                              path.size() - 1);
    const Leg& l = path[k];
    GfVec3d dir = l.b - l.a;
    const double len = dir.Normalize();
    const double u = std::clamp(1 - (l.end - at) / len, 0.0, 1.0);
    pos->push_back(GfVec3f(l.a + (l.b - l.a) * u));
    turn->push_back(p.alongPath ? along_path(dir, up) : GfRotation(GfVec3d::YAxis(), 0));
  }
}

}  // namespace copies
}  // namespace r3d
