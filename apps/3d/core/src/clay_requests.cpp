// The clay requests (ENGINE_CONTRACT.md § 1): `sculpt` (a live stroke from the screen), `clay_info`, and the check
// request `clay_bench`.
#include <pxr/base/gf/frustum.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/ray.h>
#include <pxr/base/js/json.h>
#include <pxr/usd/usdGeom/xformable.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <utility>

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

// a request's camera fields, as text: a dab started early (sculpt_ahead) uses the stroke's cached view only when its
// own camera is the one its begin had
std::string camera_key(const JsObject& o) {
  std::string k;
  for (const char* f : {"camera", "eye", "target", "fov", "frame", "width", "height"}) {
    auto it = o.find(f);
    k += f;
    k += '=';
    if (it != o.end()) k += JsWriteToString(it->second);
    k += ';';
  }
  return k;
}

// a request's points: [x, y] or [x, y, pressure] pixels -> x, y and the pen's pressure (1 without one)
std::vector<std::array<float, 3>> read_points(const JsObject& o) {
  std::vector<std::array<float, 3>> px;
  auto it = o.find("points");
  if (it == o.end()) return px;
  const JsValue& pts = it->second;
  const char* need = "sculpt.points: needs a list of [x, y] or [x, y, pressure 0..1] pixels";
  if (!pts.IsArray()) throw Error(need);
  auto isnum = [](const JsValue& v) { return v.IsReal() || v.IsInt(); };
  auto num = [](const JsValue& v) { return v.IsReal() ? v.GetReal() : double(v.GetInt()); };
  for (const JsValue& p : pts.GetJsArray()) {
    if (!p.IsArray()) throw Error(need);
    const JsArray& q = p.GetJsArray();
    if ((q.size() != 2 && q.size() != 3) || !isnum(q[0]) || !isnum(q[1]) || (q.size() == 3 && !isnum(q[2])))
      throw Error(need);
    const float pr = q.size() == 3 ? float(std::clamp(num(q[2]), 0.0, 1.0)) : 1.0f;
    px.push_back({float(num(q[0])), float(num(q[1])), pr});
  }
  return px;
}

std::string points_key(const JsObject& o) {
  auto it = o.find("points");
  return it == o.end() ? std::string() : JsWriteToString(it->second);
}
}  // namespace

// What a stroke's dabs need of the stage, worked out on the render thread: the camera's frustum and the clay's place.
// Kept from the stroke's begin so a dab's clay work can run on a worker (sculpt_ahead) without reading the stage.
struct Core::StrokeView {
  std::string item, key;  // the clay, and camera_key of the requests it was made for
  GfFrustum fr;
  int w = 0, h = 0;
  GfMatrix4d toWorld, toClay;
  double proj11 = 1, scale = 1;
  bool ortho = false;

  clay::RayFn ray() const {
    return [this](float x, float y, clay::V3& origin, clay::V3& dir) {
      if (x < 0 || y < 0 || x >= w || y >= h) return false;  // off the picture
      const GfRay wr = fr.ComputeRay(GfVec2d(2.0 * (x + 0.5) / w - 1.0, 1.0 - 2.0 * (y + 0.5) / h));
      const GfVec3d s = toClay.Transform(wr.GetStartPoint());
      GfVec3d d = toClay.TransformDir(wr.GetDirection());
      if (d.Normalize() < 1e-12) return false;
      origin = {float(s[0]), float(s[1]), float(s[2])};
      dir = {float(d[0]), float(d[1]), float(d[2])};
      return true;
    };
  }
  // pixels per clay-space metre at a clay-space distance (perspective: the scale cancels out)
  clay::PixelsPerMetreFn ppm() const {
    return [this](float depth) {
      return float(ortho ? scale * proj11 * h / 2 : proj11 * h / (2.0 * std::max(depth, 1e-6f)));
    };
  }
};

bool Core::sculpt_ahead(const JsObject& o) {
  std::lock_guard<std::mutex> l(ahead_m_);
  const std::shared_ptr<const StrokeView> sv = stroke_view_;
  if (!sv || !clay_ || !clay_->sculpting() || ahead_.valid() || ahead_done_ || ahead_error_) return false;
  auto ph = o.find("phase");
  if (ph == o.end() || !ph->second.IsString() || ph->second.GetString() != "dab") return false;
  auto it = o.find("item");
  if (it != o.end() && (!it->second.IsString() || it->second.GetString() != sv->item)) return false;
  if (camera_key(o) != sv->key) return false;
  std::vector<std::array<float, 3>> px;
  try {
    px = read_points(o);
  } catch (...) {
    return false;  // said by the request itself
  }
  if (px.empty()) return false;
  ahead_key_ = points_key(o);
  clay::Store* store = clay_.get();
  ahead_ = std::async(std::launch::async, [store, sv, px = std::move(px)] {
    return store->sculpt_compute(px, sv->ray(), sv->ppm());
  });
  return true;
}

void Core::join_ahead() {
  std::future<clay::SculptReply> f;
  {
    std::lock_guard<std::mutex> l(ahead_m_);
    if (!ahead_.valid()) return;
    f = std::move(ahead_);
    ahead_done_key_ = std::move(ahead_key_);
  }
  try {
    ahead_done_ = f.get();
  } catch (...) {
    ahead_error_ = std::current_exception();
  }
}

JsObject Core::sculpt(const JsObject& o) {
  Args a(o, "sculpt", {"item", "phase", "camera", "eye", "target", "fov", "frame", "width", "height", "points",
                       "brush", "size", "strength", "mirror", "accumulate", "folder", "view", "falloff", "spacing",
                       "frontOnly", "invert"});
  need_scene("sculpt");
  const std::string phase = a.str("phase");
  if (phase != "begin" && phase != "dab" && phase != "end" && phase != "cancel")
    throw Error("sculpt.phase: \"" + phase + "\" is unknown. Accepted: begin, dab, end, cancel");
  join_ahead();
  if ((ahead_done_ || ahead_error_) && !(phase == "dab" && points_key(o) == ahead_done_key_)) {
    // never in practice (the window starts a dab early only for the request it posts next): its dabs are in the
    // stroke all the same, so only its blocks are written out
    ahead_done_.reset();
    ahead_error_ = nullptr;
    clay::SculptReply flushed;
    clay_->sculpt_publish(flushed);
  }
  if (phase != "dab") stroke_view_.reset();  // a begin makes its own below
  if (phase == "cancel") {
    clay_->sculpt_cancel();
    return JsObject{{"ok", JsValue(true)}};
  }
  if (phase == "begin") {
    clay::Brush b;
    const std::string op = a.str("brush");
    if (!clay::op_from_name(op.c_str(), b.op))
      throw Error("sculpt.brush: \"" + op + "\" is unknown. Accepted: add, carve, smooth, pull, flatten, crease, mask");
    b.radius = float(a.num("size"));
    if (!(b.radius > 0)) throw Error("sculpt.size: must be above 0 (the brush radius, metres in the clay's space)");
    b.strength = float(a.num("strength"));
    if (b.strength < 0 || b.strength > 1) throw Error("sculpt.strength: must be 0..1");
    b.mirror = a.flag("mirror", false);
    b.accumulate = a.flag("accumulate", false);
    b.falloff = float(a.num("falloff", 0.5));
    if (b.falloff < 0 || b.falloff > 1) throw Error("sculpt.falloff: must be 0..1 (0 soft, 1 a hard edge)");
    b.spacing = float(a.num("spacing", 0.3));
    if (b.spacing < 0.05f || b.spacing > 1) throw Error("sculpt.spacing: must be 0.05..1 (a share of the brush radius)");
    b.frontOnly = a.flag("frontOnly", false);
    b.invert = a.flag("invert", false);
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
  clay::SculptReply r;
  if (ahead_error_ || ahead_done_) {  // this dab's clay work ran early (sculpt_ahead): only its blocks to write
    std::exception_ptr err = std::exchange(ahead_error_, nullptr);
    std::optional<clay::SculptReply> done = std::exchange(ahead_done_, std::nullopt);
    if (err) std::rethrow_exception(err);
    r = *done;
    clay_->sculpt_publish(r);
  } else {
    const std::vector<std::array<float, 3>> px = read_points(o);
    if (px.empty()) {
      if (phase == "dab") throw Error("sculpt.points: a dab event needs one or more [x, y] pixels");
      return JsObject{{"ok", JsValue(true)}, {"dabs", JsValue(0)}, {"ms", JsValue(0.0)}, {"hit", JsValue(false)}};
    }
    const ViewCamera vc = read_view_camera(a, [&](const std::string& id) { return camera(id, "sculpt"); });
    const int f = a.whole("frame"), w = a.whole("width"), h = a.whole("height");
    check_frame(f, "sculpt.frame");
    if (w < 16 || h < 16 || w > 8192 || h > 8192) throw Error("sculpt.width/height: each must be 16..8192");
    const SdfPath path = item_path(stage_, item);
    if (path.IsEmpty()) throw Error("sculpt.item: no item \"" + item + "\" in the scene");
    auto sv = std::make_shared<StrokeView>();
    sv->item = item;
    sv->key = camera_key(o);
    sv->fr = frustum_of(stage_, vc, f, w, h);
    sv->w = w;
    sv->h = h;
    sv->toWorld = UsdGeomXformable(stage_->GetPrimAtPath(path)).ComputeLocalToWorldTransform(UsdTimeCode(f));
    sv->toClay = sv->toWorld.GetInverse();
    sv->proj11 = sv->fr.ComputeProjectionMatrix()[1][1];
    sv->ortho = sv->fr.GetProjectionType() == GfFrustum::Orthographic;
    sv->scale = std::cbrt(std::fabs(sv->toWorld.ExtractRotationMatrix().GetDeterminant()));  // clay m -> world m
    stroke_view_ = sv;
    r = clay_->sculpt_points(px, sv->ray(), sv->ppm());
  }
  const GfMatrix4d& toWorld = stroke_view_->toWorld;
  const GfMatrix4d toClay = stroke_view_->toClay;
  JsObject out{{"ok", JsValue(true)}, {"dabs", JsValue(r.dabs)}, {"ms", JsValue(r1(r.ms))}, {"dabMs", JsValue(r1(r.ms))},
               {"applyMs", JsValue(r1(r.applyMs))}, {"meshMs", JsValue(r1(r.meshMs))}, {"usdMs", JsValue(r1(r.usdMs))},
               {"blocks", JsValue(r.blocks)},
               {"hit", JsValue(r.hit)}};  // dabMs: the dab's own time (the client overwrites `ms` with its round trip)
  if (r.hit) {  // where the brush is (world), for the brush ring on the screen
    const GfVec3d p = toWorld.Transform(GfVec3d(r.point.x, r.point.y, r.point.z));
    GfVec3d n = toClay.GetTranspose().TransformDir(GfVec3d(r.normal.x, r.normal.y, r.normal.z));
    n.Normalize();
    out["point"] = vec3(p);
    out["normal"] = vec3(n);
  }
  // the dab and its picture in one request (CL2): `view` holds the viewport's own view request, drawn right after
  // the dab, so the screen never waits for a second round trip queued behind the next pointer event
  if (a.has("view")) {
    const JsValue& v = a.need("view");
    if (!v.IsObject()) throw Error("sculpt.view: needs the view request's fields (an object)");
    out["view"] = JsValue(view(v.GetJsObject()));
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
                  {"same", JsValue(r.live == r.serial && r.serial == r.parallel)},
                  {"bigDabs", JsValue(uint64_t(r.bigDabs))},
                  {"bigCoarseMs", JsValue(r1(r.bigCoarseMs))},
                  {"bigCoarseP90", JsValue(r1(r.bigCoarseP90))},
                  {"bigFineMs", JsValue(r1(r.bigFineMs))},
                  {"bigFineP90", JsValue(r1(r.bigFineP90))},
                  {"bigLive", JsValue(hex(r.bigLive))},
                  {"bigSerial", JsValue(hex(r.bigSerial))},
                  {"bigParallel", JsValue(hex(r.bigParallel))},
                  {"bigSame", JsValue(r.bigLive == r.bigSerial && r.bigSerial == r.bigParallel)}};
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
