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
#include <utility>

#include "args.h"
#include "error.h"
#include "ghosts.h"
#include "inspect.h"
#include "cycles_lights.h"
#include "light_extras.h"
#include "passes.h"
#include "perf_counters.h"
#include "surface_spot.h"
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

Core::Core() : stage_(UsdStage::CreateInMemory()) { clay_ = std::make_unique<clay::Store>(stage_); }

Core::Core(GlContext::Borrow) : Core() { borrow_gl_ = true; }

Hydra& Core::hydra() {
  if (!hydra_) hydra_ = borrow_gl_ ? std::make_unique<Hydra>(stage_, GlContext::Borrow{}) : std::make_unique<Hydra>(stage_);
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
  const double build_ms = ms_since(t0);
  const auto tc = Clock::now();
  clay_->sync(built_.clays);  // the clays brought to their steps (clay_store.h)
  built_.clays.clear();
  return JsObject{{"ok", JsValue(true)}, {"items", JsValue(built_.items)}, {"prims", JsValue(built_.prims)},
                  {"frames", JsValue(JsArray{JsValue(built_.start), JsValue(built_.end)})},
                  {"timing", JsValue(JsObject{{"buildMs", JsValue(r1(build_ms))}, {"clayMs", JsValue(r1(ms_since(tc)))}})}};
}

JsObject Core::render(const JsObject& o, const std::function<void(const JsObject&)>& progress) {
  Args a(o, "render", {"camera", "renderer", "frame", "frames", "width", "height", "samples", "denoise", "exr",
                       "png", "view", "exposure", "timeoutS", "progress", "passes"});
  need_scene("render");
  if (clay_->previewing())  // 3d-cl4: the stage holds the stroke's coarse preview, never rendered
    throw Error("render: a clay stroke is being drawn (on its quick preview); render once it has ended");
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
  const std::vector<std::string> passes = a.has("passes") ? read_passes(a.need("passes"), "render.passes")
                                                          : std::vector<std::string>{};
  if (!passes.empty() && exr.empty()) throw Error("render.passes: passes are layers of the EXR; give exr too");
  if (!passes.empty() && renderer != "cycles") throw Error("render.passes: only the cycles renderer makes passes");
  s.aovs = aovs_for(passes);
  const bool report = a.flag("progress", false);
  float bg[3];
  background(stage_, bg);

  auto& hy = hydra();
  mem_.reset_peak();
  JsArray frames;
  const auto t0 = Clock::now();
  double first_ms = 0;
  JsArray channels;  // the EXR's channel names, the same for every frame
  for (int f = first; f <= last; ++f) {
    const auto tf = Clock::now();
    clay_->pose_frame(f);  // CL5: each skinned clay posed for this frame
    const double weldMs = renderer == "cycles" ? clay_->whole_for_cycles() : 0.0;  // CL6: one closed mesh per clay
    Aovs lit, unshadowed;
    Picture pic = hy.draw(renderer, cam, f, w, h, s, mem_, &lit);
    if (needs_unshadowed(passes)) {  // the Shadow pass: the same frame again with no shadows
      DrawSettings no_shadows = s;
      no_shadows.castShadows = false;
      hy.draw(renderer, cam, f, w, h, no_shadows, mem_, &unshadowed);
    }
    JsObject fo{{"frame", JsValue(f)}};
    if (weldMs > 0) fo["clayWeldMs"] = JsValue(r1(weldMs));
    if (!exr.empty()) {
      const std::vector<ExrLayer> layers = pass_layers(passes, lit, unshadowed, stage_);
      check_beauty(pic, layers, f);
      color_.write_exr(pic, frame_path(exr, f), layers);
      fo["exr"] = JsValue(frame_path(exr, f));
      if (channels.empty()) {
        for (const char* c : {"R", "G", "B", "A"}) channels.push_back(JsValue(std::string(c)));
        for (const auto& l : layers)
          for (const auto& c : l.channels) channels.push_back(JsValue(c));
      }
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
      {"channels", JsValue(channels)},
      {"timing", JsValue(JsObject{{"totalMs", JsValue(r1(total))}, {"firstMs", JsValue(r1(first_ms))},
                                  {"meanMs", JsValue(r1(total / (last - first + 1)))}})},
      {"vram", JsValue(JsObject{{"processPeakMb", JsValue(r1(mem_.peak_mb()))},
                                {"gpuUsedMb", JsValue(r1(now.gpuUsedMb))},
                                {"gpuTotalMb", JsValue(r1(now.gpuTotalMb))}})},
      {"ramPeakMb", JsValue(r1(ram_peak_mb()))}};
}

JsObject Core::view(const JsObject& o) {
  Args a(o, "view", {"camera", "eye", "target", "fov", "frame", "width", "height", "renderer", "exposure", "studio",
                     "sceneLights", "selected", "hovered", "view", "ao", "aoRadius", "dof", "samples", "denoise", "ghosts"});
  need_scene("view");
  const std::string renderer = a.str("renderer", "storm");
  const bool final_look = renderer == "cycles";  // the Final look: progressive Cycles with the render's settings
  final_look_ = final_look;
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
  clay_->pose_frame(f);  // CL5: each skinned clay posed for the frame shown (a clay_pose's moves while they hold)
  if (final_look) clay_->whole_for_cycles();  // CL6: Cycles draws each clay as one closed mesh (clay_whole.h)
  ViewLook look;
  look.studio = a.num("studio", 1.0);
  if (look.studio < 0 || look.studio > 4) throw Error("view.studio: must be 0..4");
  look.sceneLights = a.flag("sceneLights", true);
  // `selected`: the selection ring; `hovered` (3d-v4): the thin hover outline (the clay under the pointer)
  for (const auto& [key, into] : {std::pair<const char*, SdfPathVector*>{"selected", &look.selected},
                                  std::pair<const char*, SdfPathVector*>{"hovered", &look.hovered}}) {
    if (!a.has(key)) continue;
    const std::string where = std::string("view.") + key;
    const auto& list = a.need(key);
    if (!list.IsArray()) throw Error(where + ": needs a list of item ids");
    for (const auto& v : list.GetJsArray()) {
      if (!v.IsString()) throw Error(where + ": needs a list of item ids");
      const SdfPath p = item_path(stage_, v.GetString());
      if (p.IsEmpty()) throw Error(where + ": no item \"" + v.GetString() + "\" in the scene");
      into->push_back(p);
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
  post.hover = pic.hoverMask;
  for (size_t i = 0; i < pic.ghosts.size(); ++i) {
    GhostIn g;
    g.tex = pic.ghosts[i];
    std::copy(look.ghosts[i].tint, look.ghosts[i].tint + 3, g.tint);
    g.opacity = look.ghosts[i].opacity;
    post.ghosts.push_back(g);
  }
  const double draw_ms = ms_since(t0);
  JsObject info;
  if (!post_) post_ = std::make_unique<ViewPost>();
  ++views_drawn_;
  if (target_.fbo) {  // inside the window: into its texture, no read-back
    post_->run(post, nullptr, &target_);
  } else {
    const size_t bytes = size_t(w) * h * 4;
    if (!shm_ || shm_->slot_bytes() != bytes) {
      shm_.reset();
      shm_ = std::make_unique<Shm>(bytes);
    }
    post_->run(post, shm_->next(w, h, &info));
  }
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
  const GpuMem now = mem_.recent();  // a view is asked for every dab: a sample a quarter-second old is fine
  JsArray missing;  // product lighting the quick view can't show (light_extras.h): said, never faked
  for (const std::string& note : light_extras().stormNotes) missing.push_back(JsValue(note));
  JsObject reply{{"ok", JsValue(true)}, {"width", JsValue(w)}, {"height", JsValue(h)},
                  {"sceneDome", JsValue(pic.sceneDome)}, {"sun", sun}, {"cameraDof", JsValue(bool(lens))},
                  {"notInQuickView", JsValue(missing)}, {"final", final},
                  {"vram", JsValue(JsObject{{"processMb", JsValue(r1(now.processMb))},
                                            {"gpuUsedMb", JsValue(r1(now.gpuUsedMb))},
                                            {"gpuTotalMb", JsValue(r1(now.gpuTotalMb))}})},
                  {"timing", JsValue(JsObject{{"drawMs", JsValue(r1(draw_ms))}, {"totalMs", JsValue(r1(ms_since(t0)))},
                                              {"lightMs", JsValue(r1(pic.lightMs))}, {"stormMs", JsValue(r1(pic.renderMs))}, {"finishMs", JsValue(r1(pic.finishMs))}})}};
  if (!target_.fbo) reply["shm"] = JsValue(info);
  if (perf_on()) reply["perf"] = JsValue(perf_moved());  // ROSTRUM3D_PERF=1: Storm's counters that moved
  return reply;
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
  clay_->pose_frame(f);  // CL5: a skinned clay is picked as drawn at this frame
  const SdfPath hit = hydra().pick(fr, f, w, h, x, y, &point, &normal);
  if (hit.IsEmpty()) return JsObject{{"ok", JsValue(true)}, {"hit", JsValue(false)}};
  JsObject out{{"ok", JsValue(true)}, {"hit", JsValue(true)}, {"prim", JsValue(hit.GetString())},
               {"item", JsValue(item_of(stage_, hit))}, {"material", JsValue(material_of(stage_, hit))},
               {"point", vec3(point)}, {"normal", vec3(normal)}, {"distance", JsValue((point - fr.GetPosition()).GetLength())}};
  const GfRay ray = fr.ComputeRay(GfVec2d(2.0 * (x + 0.5) / w - 1.0, 1.0 - 2.0 * (y + 0.5) / h));
  if (const auto spot = surface_spot(stage_, hit, f, ray)) {  // the face and its (u, v): where a brush lands
    out["face"] = JsValue(spot->face);
    if (spot->uv) out["uv"] = JsValue(JsArray{JsValue(double((*spot->uv)[0])), JsValue(double((*spot->uv)[1]))});
    if (clay_->has(out["item"].GetString())) {  // 3d-cl4: where on the clay, in its own space (a stroke's anchors)
      out["local"] = vec3(spot->local);
      out["localNormal"] = vec3(spot->localNormal);
      // CL5: a clay with bones: the same spot on its rest shape (clay space), `local` staying the drawn one
      if (const auto rest = clay_->rest_spot(out["item"].GetString(), hit, spot->face, spot->local))
        out["rest"] = vec3(*rest);
    }
  }
  return out;
}

JsObject Core::save(const JsObject& o) {
  Args a(o, "save", {"file", "flatten"});
  need_scene("save");
  const std::string file = a.str("file");
  save_stage(stage_, file, a.flag("flatten", false));
  return JsObject{{"ok", JsValue(true)}, {"file", JsValue(file)}};
}

JsObject Core::info() {
  trace_report();
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
