// The clay requests (ENGINE_CONTRACT.md § 1): `sculpt` (a live stroke from the screen), `clay_info`, and the check
// request `clay_bench`.
#include <pxr/base/gf/frustum.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/ray.h>
#include <pxr/usd/usdGeom/xformable.h>

#include <cmath>
#include <cstdio>

#include "args.h"
#include "clay_replay.h"
#include "error.h"
#include "inspect.h"
#include "requests.h"
#include "view_camera.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
JsValue vec3(const GfVec3d& v) { return JsValue(JsArray{JsValue(v[0]), JsValue(v[1]), JsValue(v[2])}); }
double r1(double v) { return std::round(v * 10) / 10; }
}  // namespace

JsObject Core::sculpt(const JsObject& o) {
  Args a(o, "sculpt", {"item", "phase", "camera", "eye", "target", "fov", "frame", "width", "height", "points",
                       "brush", "size", "strength", "mirror", "accumulate", "folder"});
  need_scene("sculpt");
  const std::string phase = a.str("phase");
  if (phase != "begin" && phase != "dab" && phase != "end" && phase != "cancel")
    throw Error("sculpt.phase: \"" + phase + "\" is unknown. Accepted: begin, dab, end, cancel");
  if (phase == "cancel") {
    clay_->sculpt_cancel();
    return JsObject{{"ok", JsValue(true)}};
  }
  if (phase == "begin") {
    clay::Brush b;
    const std::string op = a.str("brush");
    if (!clay::op_from_name(op.c_str(), b.op))
      throw Error("sculpt.brush: \"" + op + "\" is unknown. Accepted: add, carve, smooth, pull, flatten, crease");
    b.radius = float(a.num("size"));
    if (!(b.radius > 0)) throw Error("sculpt.size: must be above 0 (the brush radius, metres in the clay's space)");
    b.strength = float(a.num("strength"));
    if (b.strength < 0 || b.strength > 1) throw Error("sculpt.strength: must be 0..1");
    b.mirror = a.flag("mirror", false);
    b.accumulate = a.flag("accumulate", false);
    clay_->sculpt_begin(a.str("item"), b);
  } else if (!clay_->sculpting()) {
    throw Error("sculpt.phase: no stroke begun; send phase \"begin\" first");
  }
  const std::string item = clay_->sculpt_item();
  if (a.has("item") && a.str("item") != item)
    throw Error("sculpt.item: the stroke begun is on \"" + item + "\", not \"" + a.str("item") + "\"");
  if (phase == "end") {
    const clay::SculptReply r = clay_->sculpt_end(a.str("folder"), "sculpt.folder");
    return JsObject{{"ok", JsValue(true)}, {"dabs", JsValue(r.file)}, {"count", JsValue(r.dabs)},
                    {"ms", JsValue(r1(r.ms))}};
  }

  // begin / dab: the event's new pointer positions, through the camera, into the clay's own space at the frame
  std::vector<std::pair<float, float>> px;
  if (a.has("points")) {
    const JsValue& pts = a.need("points");
    if (!pts.IsArray()) throw Error("sculpt.points: needs a list of [x, y] pixels");
    for (const JsValue& p : pts.GetJsArray()) {
      if (!p.IsArray() || p.GetJsArray().size() != 2 || !(p.GetJsArray()[0].IsReal() || p.GetJsArray()[0].IsInt()) ||
          !(p.GetJsArray()[1].IsReal() || p.GetJsArray()[1].IsInt()))
        throw Error("sculpt.points: needs a list of [x, y] pixels");
      auto num = [](const JsValue& v) { return v.IsReal() ? v.GetReal() : double(v.GetInt()); };
      px.emplace_back(float(num(p.GetJsArray()[0])), float(num(p.GetJsArray()[1])));
    }
  }
  clay::SculptReply r;
  if (px.empty()) {
    if (phase == "dab") throw Error("sculpt.points: a dab event needs one or more [x, y] pixels");
    return JsObject{{"ok", JsValue(true)}, {"dabs", JsValue(0)}, {"ms", JsValue(0.0)}, {"hit", JsValue(false)}};
  }
  const ViewCamera vc = read_view_camera(a, [&](const std::string& id) { return camera(id, "sculpt"); });
  const int f = a.whole("frame"), w = a.whole("width"), h = a.whole("height");
  check_frame(f, "sculpt.frame");
  if (w < 16 || h < 16 || w > 8192 || h > 8192) throw Error("sculpt.width/height: each must be 16..8192");
  const GfFrustum fr = frustum_of(stage_, vc, f, w, h);
  const SdfPath path = item_path(stage_, item);
  if (path.IsEmpty()) throw Error("sculpt.item: no item \"" + item + "\" in the scene");
  const GfMatrix4d toWorld = UsdGeomXformable(stage_->GetPrimAtPath(path)).ComputeLocalToWorldTransform(UsdTimeCode(f));
  const GfMatrix4d toClay = toWorld.GetInverse();
  const double proj11 = fr.ComputeProjectionMatrix()[1][1];
  const bool ortho = fr.GetProjectionType() == GfFrustum::Orthographic;
  const double scale = std::cbrt(std::fabs(toWorld.ExtractRotationMatrix().GetDeterminant()));  // clay m -> world m
  const clay::RayFn ray = [&](float x, float y, clay::V3& origin, clay::V3& dir) {
    if (x < 0 || y < 0 || x >= w || y >= h) return false;  // off the picture
    const GfRay wr = fr.ComputeRay(GfVec2d(2.0 * (x + 0.5) / w - 1.0, 1.0 - 2.0 * (y + 0.5) / h));
    const GfVec3d s = toClay.Transform(wr.GetStartPoint());
    GfVec3d d = toClay.TransformDir(wr.GetDirection());
    if (d.Normalize() < 1e-12) return false;
    origin = {float(s[0]), float(s[1]), float(s[2])};
    dir = {float(d[0]), float(d[1]), float(d[2])};
    return true;
  };
  // pixels per clay-space metre at a clay-space distance (perspective: the scale cancels out)
  const clay::PixelsPerMetreFn ppm = [&](float depth) {
    return float(ortho ? scale * proj11 * h / 2 : proj11 * h / (2.0 * std::max(depth, 1e-6f)));
  };
  r = clay_->sculpt_points(px, ray, ppm);
  JsObject out{{"ok", JsValue(true)}, {"dabs", JsValue(r.dabs)}, {"ms", JsValue(r1(r.ms))}, {"hit", JsValue(r.hit)}};
  if (r.hit) {  // where the brush is (world), for the brush ring on the screen
    const GfVec3d p = toWorld.Transform(GfVec3d(r.point.x, r.point.y, r.point.z));
    GfVec3d n = toClay.GetTranspose().TransformDir(GfVec3d(r.normal.x, r.normal.y, r.normal.z));
    n.Normalize();
    out["point"] = vec3(p);
    out["normal"] = vec3(n);
  }
  return out;
}

JsObject Core::clay_bench(const JsObject& o) {
  Args a(o, "clay_bench", {"strokes", "threads"});
  const int strokes = a.whole("strokes", 2000), threads = a.whole("threads", 0);
  if (strokes < 1 || strokes > 20000) throw Error("clay_bench.strokes: must be 1..20000");
  if (threads < 0 || threads > 256) throw Error("clay_bench.threads: must be 0..256 (0 = every core)");
  const clay::BenchResult r = clay::bench(strokes, threads);
  auto hex = [](uint64_t h) {
    char s[17];
    std::snprintf(s, sizeof s, "%016llx", static_cast<unsigned long long>(h));
    return std::string(s);
  };
  return JsObject{{"ok", JsValue(true)},
                  {"strokes", JsValue(r.strokes)},
                  {"dabs", JsValue(uint64_t(r.dabs))},
                  {"threads", JsValue(r.threads)},
                  {"liveMs", JsValue(r1(r.liveMs))},
                  {"serialMs", JsValue(r1(r.serialMs))},
                  {"parallelMs", JsValue(r1(r.parallelMs))},
                  {"chain", JsValue(uint64_t(r.chain))},
                  {"liveHash", JsValue(hex(r.live))},
                  {"serialHash", JsValue(hex(r.serial))},
                  {"parallelHash", JsValue(hex(r.parallel))},
                  {"same", JsValue(r.live == r.serial && r.serial == r.parallel)}};
}

JsObject Core::clay_info(const JsObject& o) {
  Args a(o, "clay_info", {"item"});
  need_scene("clay_info");
  const clay::ClayInfo i = clay_->info(a.str("item"));
  return JsObject{{"ok", JsValue(true)}, {"hash", JsValue(i.hash)}, {"steps", JsValue(int(i.steps))},
                  {"voxels", JsValue(uint64_t(i.voxels))}, {"memoryMb", JsValue(r1(i.memoryMb))},
                  {"blocks", JsValue(int(i.blocks))}};
}

}  // namespace r3d
