// Copies on the held stage (copies.h): the live `copies` request (a Count or Spacing drag, a copy moved by the gizmo,
// like `xform`: no new scene), `sees` (which points a camera sees: the minimum of brief 21a's camera-sees request),
// the seen test after each scene (a copies item seen by the shot's camera draws only the copies it sees) and a pick
// that hit a copy, and `copies_box` (what a copies item takes in the world at a frame: framing it).
#include <pxr/base/gf/rotation.h>
#include <pxr/usd/usdGeom/camera.h>

#include <algorithm>
#include <chrono>
#include <cmath>

#include "args.h"
#include "error.h"
#include "inspect.h"
#include "requests.h"
#include "view_camera.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
using Clock = std::chrono::steady_clock;
double ms_since(Clock::time_point t) { return std::chrono::duration<double, std::milli>(Clock::now() - t).count(); }
double r1(double v) { return std::round(v * 10) / 10; }
constexpr int kSeenWidth = 480;  // the seen test's pictures: small, depth only
constexpr int kSeenFrames = 8;   // at most this many frames of the shot, every 12th with the first and last

std::vector<int> seen_frames(int start, int end) {
  std::vector<int> all;
  for (int f = start; f < end; f += 12) all.push_back(f);
  all.push_back(end);
  if (all.size() <= size_t(kSeenFrames)) return all;
  std::vector<int> out;
  for (int i = 0; i < kSeenFrames; ++i) out.push_back(all[size_t(std::lround(double(i) * (all.size() - 1) / (kSeenFrames - 1)))]);
  return out;
}
}  // namespace

JsObject Core::copies_live(const JsObject& o) {
  Args a(o, "copies", {"item", "props", "held"});
  need_scene("copies");
  const std::string id = a.str("item");
  auto it = copies_.find(id);
  if (it == copies_.end()) {
    std::string list;
    for (const auto& [k, v] : copies_) list += (list.empty() ? "" : ", ") + k;
    throw Error("copies.item: no copies item \"" + id + "\". Accepted: " + (list.empty() ? "(none in the scene)" : list));
  }
  static const JsObject none;
  const JsValue& props = a.has("props") ? a.need("props") : JsValue(none);
  if (!props.IsObject()) throw Error("copies.props: needs an object of copies fields, got " + props.GetTypeName());
  const double ms = copies::relay(stage_, it->second, props.GetJsObject(), a.has("held") ? &a.need("held") : nullptr);
  return JsObject{{"ok", JsValue(true)}, {"count", JsValue(int(it->second.laid.size()))}, {"ms", JsValue(r1(ms))}};
}

JsObject Core::copies_box(const JsObject& o) {
  Args a(o, "copies_box", {"item", "frame"});
  need_scene("copies_box");
  const std::string id = a.str("item");
  auto it = copies_.find(id);
  if (it == copies_.end()) throw Error("copies_box.item: no copies item \"" + id + "\" in the scene");
  const int f = a.whole("frame", it->second.start);
  check_frame(f, "copies_box.frame");
  const GfRange3d r = copies::world_box(stage_, it->second, f);
  const auto vec = [](const GfVec3d& v) { return JsValue(JsArray{JsValue(v[0]), JsValue(v[1]), JsValue(v[2])}); };
  if (r.IsEmpty()) return JsObject{{"ok", JsValue(true)}, {"lo", JsValue()}, {"hi", JsValue()}};
  return JsObject{{"ok", JsValue(true)}, {"lo", vec(r.GetMin())}, {"hi", vec(r.GetMax())}};
}

JsObject Core::sees(const JsObject& o) {
  Args a(o, "sees", {"camera", "frame", "width", "height", "points", "hide"});
  need_scene("sees");
  const auto t0 = Clock::now();
  const SdfPath cam = camera(a.str("camera"), "sees");
  const int f = a.whole("frame"), w = a.whole("width"), h = a.whole("height");
  check_frame(f, "sees.frame");
  if (w < 16 || h < 16 || w > 4096 || h > 4096) throw Error("sees.width/height: each must be 16..4096");
  const JsValue& list = a.need("points");
  if (!list.IsArray()) throw Error("sees.points: needs a list of [x, y, z] (world)");
  std::vector<GfVec3d> points;
  for (size_t i = 0; i < list.GetJsArray().size(); ++i) {
    const JsValue& p = list.GetJsArray()[i];
    const std::string where = "sees.points[" + std::to_string(i) + "]";
    if (!p.IsArray() || p.GetJsArray().size() != 3) throw Error(where + ": needs [x, y, z]");
    GfVec3d v;
    for (int k = 0; k < 3; ++k) {
      const JsValue& n = p.GetJsArray()[k];
      if (!n.IsReal() && !n.IsInt() && !n.IsUInt64()) throw Error(where + ": needs [x, y, z] numbers");
      v[k] = n.IsReal() ? n.GetReal() : n.IsInt() ? double(n.GetInt64()) : double(n.GetUInt64());
    }
    points.push_back(v);
  }
  SdfPathVector hide;
  if (a.has("hide")) {
    const JsValue& ids = a.need("hide");
    if (!ids.IsArray()) throw Error("sees.hide: needs a list of item ids");
    for (const JsValue& v : ids.GetJsArray()) {
      if (!v.IsString()) throw Error("sees.hide: needs a list of item ids");
      const SdfPath p = item_path(stage_, v.GetString());
      if (p.IsEmpty()) throw Error("sees.hide: no item \"" + v.GetString() + "\" in the scene");
      hide.push_back(p);
    }
  }
  clay_->pose_frame(f);  // a skinned clay hides what it hides at this frame
  ViewCamera vc;
  vc.camera = cam;
  const std::vector<bool> seen = hydra().sees(frustum_of(stage_, vc, f, w, h), f, w, h, hide, points);
  JsArray out;
  int count = 0;
  for (bool s : seen) {
    out.push_back(JsValue(s));
    count += s;
  }
  return JsObject{{"ok", JsValue(true)}, {"seen", JsValue(out)}, {"count", JsValue(count)}, {"ms", JsValue(r1(ms_since(t0)))}};
}

JsObject Core::seen_test(double* ms) {
  const auto t0 = Clock::now();
  JsObject info;
  for (auto& [id, s] : copies_) {
    const int n = int(s.laid.size());
    if (s.p.seenBy.empty()) {
      info[id] = JsValue(JsObject{{"count", JsValue(n)}, {"seen", JsValue()}, {"camera", JsValue()}});
      continue;
    }
    const SdfPath cam = camera(s.p.seenBy, "scene.copies");
    ViewCamera vc;
    vc.camera = cam;
    const int w = kSeenWidth, h = std::max(16, int(std::lround(double(kSeenWidth) * s.p.seenH / s.p.seenW)));
    s.shown.assign(size_t(n), false);
    for (int f : seen_frames(s.start, s.end)) {
      clay_->pose_frame(f);
      const std::vector<GfVec3d> points = copies::seen_points(stage_, s, f);  // two per copy
      const std::vector<bool> seen = hydra().sees(frustum_of(stage_, vc, f, w, h), f, w, h, {s.path}, points);
      for (int i = 0; i < n; ++i) s.shown[size_t(i)] = s.shown[size_t(i)] || seen[2 * i] || seen[2 * i + 1];
    }
    s.seen = int(std::count(s.shown.begin(), s.shown.end(), true));
    copies::write_shown(stage_, s);
    info[id] = JsValue(JsObject{{"count", JsValue(n)}, {"seen", JsValue(s.seen)}, {"camera", JsValue(s.p.seenBy)}});
  }
  *ms = ms_since(t0);
  return info;
}

bool Core::pick_copy(const SdfPath& hit, const SdfPath& instancer, int instance, int frame, const GfVec3d& point,
                     JsObject* out) const {
  for (const auto& [id, s] : copies_) {
    if (!(instancer == s.path || hit.HasPrefix(s.path))) continue;
    // the source: the child of the copies item on the hit's path
    int proto = -1;
    for (SdfPath p = hit; p.GetPathElementCount() > s.path.GetPathElementCount(); p = p.GetParentPath())
      if (p.GetParentPath() == s.path) {
        const auto at = std::find(s.sources.begin(), s.sources.end(), p.GetName());
        if (at != s.sources.end()) proto = int(at - s.sources.begin());
      }
    const int copy = copies::copy_at(stage_, s, frame, point, instance, proto);
    (*out)["item"] = JsValue(id);
    (*out)["copy"] = copy >= 0 ? JsValue(copy) : JsValue();
    const int src = proto >= 0 ? proto : copy >= 0 ? s.laid[size_t(copy)].proto : -1;
    (*out)["source"] = src >= 0 && src < int(s.sources.size()) ? JsValue(s.sources[size_t(src)]) : JsValue();
    if (copy >= 0) {  // where the layout put it (held, varied, on a surface), before effectors: the gizmo's start
      const copies::Copy& c = s.laid[size_t(copy)];
      const GfVec3d r = GfRotation(GfQuatd(c.rot.GetReal(), GfVec3d(c.rot.GetImaginary())))
                            .Decompose(GfVec3d::XAxis(), GfVec3d::YAxis(), GfVec3d::ZAxis());
      (*out)["place"] = JsValue(JsObject{{"x", JsValue(double(c.pos[0]))}, {"y", JsValue(double(c.pos[1]))},
                                         {"z", JsValue(double(c.pos[2]))}, {"rx", JsValue(r[0])}, {"ry", JsValue(r[1])},
                                         {"rz", JsValue(r[2])}, {"s", JsValue(double(c.scale))}});
    }
    return true;
  }
  return false;
}

}  // namespace r3d
