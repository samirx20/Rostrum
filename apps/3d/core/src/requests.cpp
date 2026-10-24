#include "requests.h"

#include <windows.h>
#include <psapi.h>

#include <pxr/base/gf/vec3d.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/camera.h>

#include <algorithm>
#include <chrono>
#include <cmath>

#include "args.h"
#include "error.h"
#include "ghosts.h"
#include "inspect.h"
#include "cycles_lights.h"
#include "light_extras.h"
#include "view_camera.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
using Clock = std::chrono::steady_clock;
double ms_since(Clock::time_point t) { return std::chrono::duration<double, std::milli>(Clock::now() - t).count(); }
double r1(double v) { return std::round(v * 10) / 10; }
JsValue vec3(const GfVec3d& v) { return JsValue(JsArray{JsValue(v[0]), JsValue(v[1]), JsValue(v[2])}); }

double ram_peak_mb() {
  PROCESS_MEMORY_COUNTERS c{};
  GetProcessMemoryInfo(GetCurrentProcess(), &c, sizeof(c));
  return double(c.PeakWorkingSetSize) / (1 << 20);
}

// world.background, which the stage builder keeps on /World as rostrum:background (linear RGB)
void background(const UsdStageRefPtr& stage, float rgb[3]) {
  rgb[0] = rgb[1] = rgb[2] = 0;
  UsdPrim world = stage->GetPrimAtPath(SdfPath("/World"));
  VtValue v;
  if (!world || !world.GetAttribute(TfToken("rostrum:background")).Get(&v)) return;
  if (v.IsHolding<GfVec3f>()) {
    auto c = v.UncheckedGet<GfVec3f>();
    for (int i = 0; i < 3; ++i) rgb[i] = c[i];
  } else if (v.IsHolding<GfVec3d>()) {
    auto c = v.UncheckedGet<GfVec3d>();
    for (int i = 0; i < 3; ++i) rgb[i] = float(c[i]);
  }
}
}  // namespace

Core::Core() : stage_(UsdStage::CreateInMemory()) {}

Hydra& Core::hydra() {
  if (!hydra_) hydra_ = std::make_unique<Hydra>(stage_);
  return *hydra_;
}

void Core::need_scene(const char* request) const {
  if (!loaded_) throw Error(std::string(request) + ": no scene loaded yet; send {\"scene\": {...}} first");
}

SdfPath Core::camera(const std::string& id, const char* request) const {
  std::string list;
  for (UsdPrim p : stage_->Traverse()) {
    if (!p.IsA<UsdGeomCamera>()) continue;
    if (p.GetName() == id) return p.GetPath();
    list += (list.empty() ? "" : ", ") + p.GetName().GetString();
  }
  throw Error(std::string(request) + ".camera: no camera \"" + id + "\". Accepted: " + (list.empty() ? "(none)" : list));
}

void Core::check_frame(int f, const char* where) const {
  if (f < built_.start || f > built_.end)
    throw Error(std::string(where) + ": frame " + std::to_string(f) + " is outside the shot (" +
                std::to_string(built_.start) + ".." + std::to_string(built_.end) + ")");
}

JsObject Core::scene(const JsObject& a) {
  const auto t0 = Clock::now();
  built_ = build_stage(a, stage_);  // throws with the held stage untouched
  scene_ = a;
  announce_light_extras();
  loaded_ = true;
  return JsObject{{"ok", JsValue(true)}, {"items", JsValue(built_.items)}, {"prims", JsValue(built_.prims)},
                  {"frames", JsValue(JsArray{JsValue(built_.start), JsValue(built_.end)})},
                  {"timing", JsValue(JsObject{{"buildMs", JsValue(r1(ms_since(t0)))}})}};
}

JsObject Core::render(const JsObject& o, const std::function<void(const JsObject&)>& progress) {
  Args a(o, "render", {"camera", "renderer", "frame", "frames", "width", "height", "samples", "denoise", "exr",
                       "png", "view", "exposure", "timeoutS", "progress"});
  need_scene("render");
  const std::string renderer = a.str("renderer");
  Hydra::plugin_for(renderer);  // an unknown name fails before anything else
  const SdfPath cam = camera(a.str("camera"), "render");
  if (a.has("frame") == a.has("frames")) throw Error("render: give exactly one of frame or frames");
  int first, last;
  if (a.has("frame")) {
    first = last = a.whole("frame");
  } else {
    const auto& fr = a.need("frames");
    if (!fr.IsArray() || fr.GetJsArray().size() != 2 || !fr.GetJsArray()[0].IsInt() || !fr.GetJsArray()[1].IsInt())
      throw Error("render.frames: needs [first, last], two whole numbers");
    first = fr.GetJsArray()[0].GetInt();
    last = fr.GetJsArray()[1].GetInt();
    if (last < first) throw Error("render.frames: last is before first");
  }
  check_frame(first, "render.frame");
  check_frame(last, "render.frames");
  const int w = a.whole("width"), h = a.whole("height");
  if (w < 16 || h < 16 || w > 8192 || h > 8192) throw Error("render.width/height: each must be 16..8192");
  const std::string exr = a.str("exr", ""), png = a.str("png", "");
  if (exr.empty() && png.empty()) throw Error("render: give exr, png or both (file paths)");
  for (const auto& p : {exr, png})
    if (!p.empty() && last > first && p.find("{frame}") == std::string::npos)
      throw Error("render: a frame range needs {frame} in each file name, got " + p);
  const std::string view = png.empty() ? "" : color_.check_view(a.str("view", ""));
  const double exposure = a.num("exposure", 0);
  DrawSettings s;
  s.samples = a.whole("samples", s.samples);
  s.denoise = a.flag("denoise", s.denoise);
  s.timeoutS = a.num("timeoutS", s.timeoutS);
  if (s.samples < 1 || s.samples > 65536) throw Error("render.samples: must be 1..65536");
  const bool report = a.flag("progress", false);
  float bg[3];
  background(stage_, bg);

  auto& hy = hydra();
  mem_.reset_peak();
  JsArray frames;
  const auto t0 = Clock::now();
  double first_ms = 0;
  for (int f = first; f <= last; ++f) {
    const auto tf = Clock::now();
    Picture pic = hy.draw(renderer, cam, f, w, h, s, mem_);
    JsObject fo{{"frame", JsValue(f)}};
    if (!exr.empty()) {
      color_.write_exr(pic, frame_path(exr, f));
      fo["exr"] = JsValue(frame_path(exr, f));
    }
    if (!png.empty()) {
      color_.write_png(pic, frame_path(png, f), view, exposure, bg);
      fo["png"] = JsValue(frame_path(png, f));
    }
    const double ms = ms_since(tf);
    if (f == first) first_ms = ms;
    fo["ms"] = JsValue(r1(ms));
    frames.push_back(JsValue(fo));
    if (report)
      progress(JsObject{{"progress", JsValue(f - first + 1)}, {"of", JsValue(last - first + 1)},
                        {"frame", JsValue(f)}, {"ms", JsValue(r1(ms))}});
  }
  const double total = ms_since(t0);
  const GpuMem now = mem_.sample();
  return JsObject{
      {"ok", JsValue(true)}, {"frames", JsValue(frames)}, {"renderer", JsValue(renderer)},
      {"camera", JsValue(cam.GetString())}, {"view", JsValue(view)}, {"gpu", JsValue(hy.gl_renderer())},
      {"timing", JsValue(JsObject{{"totalMs", JsValue(r1(total))}, {"firstMs", JsValue(r1(first_ms))},
                                  {"meanMs", JsValue(r1(total / (last - first + 1)))}})},
      {"vram", JsValue(JsObject{{"processPeakMb", JsValue(r1(mem_.peak_mb()))},
                                {"gpuUsedMb", JsValue(r1(now.gpuUsedMb))},
                                {"gpuTotalMb", JsValue(r1(now.gpuTotalMb))}})},
      {"ramPeakMb", JsValue(r1(ram_peak_mb()))}};
}

JsObject Core::view(const JsObject& o) {
  Args a(o, "view", {"camera", "eye", "target", "fov", "frame", "width", "height", "renderer", "exposure", "studio",
                     "sceneLights", "selected", "view", "ao", "aoRadius", "dof", "samples", "denoise", "ghosts"});
  need_scene("view");
  const std::string renderer = a.str("renderer", "storm");
  const bool final_look = renderer == "cycles";  // the Final look: progressive Cycles with the render's settings
  DrawSettings s;
  s.samples = a.whole("samples", s.samples);
  s.denoise = a.flag("denoise", s.denoise);
  if (s.samples < 1 || s.samples > 65536) throw Error("view.samples: must be 1..65536");
  if (!final_look && (a.has("samples") || a.has("denoise")))
    throw Error("view.samples/denoise: only for renderer cycles (the Final look)");
  const ViewCamera vc = read_view_camera(a, [&](const std::string& id) { return camera(id, "view"); });
  const int f = a.whole("frame"), w = a.whole("width"), h = a.whole("height");
  check_frame(f, "view.frame");
  if (w < 16 || h < 16 || w > 4096 || h > 4096) throw Error("view.width/height: each must be 16..4096");
  ViewLook look;
  look.studio = a.num("studio", 1.0);
  if (look.studio < 0 || look.studio > 4) throw Error("view.studio: must be 0..4");
  look.sceneLights = a.flag("sceneLights", true);
  if (a.has("selected")) {
    const auto& sel = a.need("selected");
    if (!sel.IsArray()) throw Error("view.selected: needs a list of item ids");
    for (const auto& v : sel.GetJsArray()) {
      if (!v.IsString()) throw Error("view.selected: needs a list of item ids");
      const SdfPath p = item_path(stage_, v.GetString());
      if (p.IsEmpty()) throw Error("view.selected: no item \"" + v.GetString() + "\" in the scene");
      look.selected.push_back(p);
    }
  }
  if (a.has("ghosts")) {
    if (final_look) throw Error("view.ghosts: onion skin is drawn in the quick look only (storm or stylized), not "
                                "the Final look (cycles)");
    look.ghosts = read_ghosts(a.need("ghosts"), stage_,
                              [&](int g, const std::string& where) { check_frame(g, where.c_str()); });
  }
  ViewPostIn post;
  post.width = w;
  post.height = h;
  post.config = color_.config_name();
  post.display = color_.display();
  post.view = color_.check_view(a.str("view", ""));
  post.exposure = a.num("exposure", 0);
  post.ao = a.num("ao", 1.0);
  if (post.ao < 0 || post.ao > 2) throw Error("view.ao: contact shading strength must be 0..2 (0 = off)");
  post.aoRadius = a.num("aoRadius", post.aoRadius);
  if (post.aoRadius <= 0 || post.aoRadius > 100) throw Error("view.aoRadius: must be more than 0, up to 100 (scene units)");
  const std::optional<Lens> lens = lens_of(stage_, vc, f);
  if (a.flag("dof", true) && !final_look) post.lens = lens;  // Cycles blurs with the camera's own lens
  if (final_look) post.ao = 0;  // contact shading is the quick view's stand-in; Cycles shades contacts itself
  background(stage_, post.background);
  const GfFrustum frustum = frustum_of(stage_, vc, f, w, h);
  post.projection = frustum.ComputeProjectionMatrix();
  const auto t0 = Clock::now();
  auto& hy = hydra();
  const ViewDrawn pic = final_look ? hy.view_final(vc.camera, frustum, f, w, h, s, mem_)
                                   : hy.view(renderer, frustum, f, w, h, look, mem_);
  post.color = pic.color;
  post.depth = pic.depth;
  post.mask = pic.mask;
  for (size_t i = 0; i < pic.ghosts.size(); ++i) {
    GhostIn g;
    g.tex = pic.ghosts[i];
    std::copy(look.ghosts[i].tint, look.ghosts[i].tint + 3, g.tint);
    g.opacity = look.ghosts[i].opacity;
    post.ghosts.push_back(g);
  }
  const double draw_ms = ms_since(t0);
  const size_t bytes = size_t(w) * h * 4;
  if (!shm_ || shm_->slot_bytes() != bytes) {
    shm_.reset();
    shm_ = std::make_unique<Shm>(bytes);
  }
  JsObject info;
  if (!post_) post_ = std::make_unique<ViewPost>();
  post_->run(post, shm_->next(w, h, &info));
  JsValue sun;  // null: no sun light (no scene dome, no sun in its picture, or not Storm)
  if (pic.sun)
    sun = JsValue(JsObject{{"toward", vec3(GfVec3d(pic.sun->toward[0], pic.sun->toward[1], pic.sun->toward[2]))},
                           {"share", JsValue(pic.sun->share)}, {"angleDeg", JsValue(pic.sun->angleDeg)}});
  JsValue final;  // null: the quick look
  if (pic.final)
    final = JsValue(JsObject{{"fraction", JsValue(pic.final->fraction)}, {"converged", JsValue(pic.final->converged)},
                             {"samples", JsValue(int(std::lround(pic.final->fraction * s.samples)))},
                             {"of", JsValue(s.samples)}, {"seconds", JsValue(r1(pic.final->seconds))},
                             {"cyclesMb", JsValue(r1(pic.final->cyclesMb))}, {"status", JsValue(pic.final->status)}});
  const GpuMem now = mem_.sample();
  JsArray missing;  // product lighting the quick view can't show (light_extras.h): said, never faked
  for (const std::string& note : light_extras().stormNotes) missing.push_back(JsValue(note));
  return JsObject{{"ok", JsValue(true)}, {"width", JsValue(w)}, {"height", JsValue(h)}, {"shm", JsValue(info)},
                  {"sceneDome", JsValue(pic.sceneDome)}, {"sun", sun}, {"cameraDof", JsValue(bool(lens))},
                  {"notInQuickView", JsValue(missing)}, {"final", final},
                  {"vram", JsValue(JsObject{{"processMb", JsValue(r1(now.processMb))},
                                            {"gpuUsedMb", JsValue(r1(now.gpuUsedMb))},
                                            {"gpuTotalMb", JsValue(r1(now.gpuTotalMb))}})},
                  {"timing", JsValue(JsObject{{"drawMs", JsValue(r1(draw_ms))}, {"totalMs", JsValue(r1(ms_since(t0)))}})}};
}

JsObject Core::pick(const JsObject& o) {
  Args a(o, "pick", {"camera", "eye", "target", "fov", "frame", "width", "height", "x", "y"});
  need_scene("pick");
  const ViewCamera vc = read_view_camera(a, [&](const std::string& id) { return camera(id, "pick"); });
  const int f = a.whole("frame"), w = a.whole("width"), h = a.whole("height");
  check_frame(f, "pick.frame");
  const double x = a.num("x"), y = a.num("y");
  if (x < 0 || y < 0 || x >= w || y >= h) throw Error("pick.x/y: the point is outside the " +
                                                      std::to_string(w) + "x" + std::to_string(h) + " picture");
  GfVec3d point, normal;
  const GfFrustum fr = frustum_of(stage_, vc, f, w, h);
  const SdfPath hit = hydra().pick(fr, f, w, h, x, y, &point, &normal);
  if (hit.IsEmpty()) return JsObject{{"ok", JsValue(true)}, {"hit", JsValue(false)}};
  return JsObject{{"ok", JsValue(true)}, {"hit", JsValue(true)}, {"prim", JsValue(hit.GetString())},
                  {"item", JsValue(item_of(stage_, hit))}, {"material", JsValue(material_of(stage_, hit))},
                  {"point", vec3(point)}, {"normal", vec3(normal)}, {"distance", JsValue((point - fr.GetPosition()).GetLength())}};
}

JsObject Core::save(const JsObject& o) {
  Args a(o, "save", {"file", "flatten"});
  need_scene("save");
  const std::string file = a.str("file");
  save_stage(stage_, file, a.flag("flatten", false));
  return JsObject{{"ok", JsValue(true)}, {"file", JsValue(file)}};
}

JsObject Core::info() {
  JsArray renderers;
  for (const auto& n : hydra().available()) renderers.push_back(JsValue(n));
  JsObject vmap;
  for (const auto& [d, vs] : color_.views()) {
    JsArray arr;
    for (const auto& v : vs) arr.push_back(JsValue(v));
    vmap[d] = JsValue(arr);
  }
  return JsObject{{"ok", JsValue(true)}, {"renderers", JsValue(renderers)}, {"display", JsValue(color_.display())},
                  {"views", JsValue(vmap)}, {"gpu", JsValue(hydra().gl_renderer())},
                  {"adapter", JsValue(mem_.adapter())}, {"usd", JsValue(int(PXR_VERSION))},
                  {"ocio", JsValue(color_.config())}};
}

}  // namespace r3d
