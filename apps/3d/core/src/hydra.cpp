#include "hydra.h"

#include <pxr/base/gf/frustum.h>
#include <pxr/base/tf/errorMark.h>
#include <pxr/imaging/cameraUtil/conformWindow.h>
#include <pxr/imaging/cameraUtil/framing.h>
#include <pxr/imaging/glf/simpleMaterial.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hdx/taskController.h>
#include <pxr/imaging/hdx/taskControllerSceneIndex.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/camera.h>
#include <pxr/usd/usdGeom/metrics.h>

#include <chrono>
#include <thread>

#include "cycles_lights.h"
#include "dome_cycles.h"
#include "error.h"
#include "sky.h"
#include "storm_lights.h"
#include "storm_sun.h"
#include "studio.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
const std::vector<std::pair<std::string, std::string>> kRenderers = {
    {"storm", "HdStormRendererPlugin"}, {"cycles", "HdCyclesPlugin"}, {"stylized", "HdRostrumPlugin"}};

std::string join(const std::vector<std::string>& v) {
  std::string s;
  for (const auto& x : v) s += (s.empty() ? "" : ", ") + x;
  return s;
}

void throw_usd_errors(const TfErrorMark& mark, const std::string& where) {
  if (mark.IsClean()) return;
  std::string msg;
  for (auto it = mark.GetBegin(); it != mark.GetEnd(); ++it) msg += (msg.empty() ? "" : "; ") + it->GetCommentary();
  throw Error(where + ": USD/Hydra reported errors: " + msg);
}

// Cycles' Hydra plug-in counts every samples / integrator setting as a change and starts over (render_delegate.cpp,
// SetRenderSetting), even with the same value: set only what differs, so the Final look keeps refining.
// The stage's units go first: the plug-in scales every transform by them but not a bulb's radius or a panel's
// size, and without being told it takes centimetres (session.h: 0.01). In a metre scene that shrank the scene 100x
// around full-size bulbs (a small bulb hundreds of times too bright, the same at any radius) and made normalize
// 10 000x too bright (H23); brief 10b.
// Motion blur is on when the camera looked through has an open shutter (the shot's, lights_cameras.cpp); a free
// camera has none. Cycles then samples the camera's moves within the shutter, and every object's moves within the
// shutter it was told (rostrum:shutterOpen / Close, our patch: libs/cycles-rostrum.patch). That one is only set from
// an open shutter and kept while a free camera looks: objects sample their moves when they change, not when the
// camera does, so the samples are still right when the shot camera looks again (a new shutter rewrites them anyway).
void cycles_settings(UsdImagingGLEngine& e, const DrawSettings& s, const UsdStageRefPtr& stage,
                     const SdfPath& camera) {
  const auto set = [&](const char* key, const VtValue& v) {
    if (e.GetRendererSetting(TfToken(key)) != v) e.SetRendererSetting(TfToken(key), v);
  };
  if (stage) set("stageMetersPerUnit", VtValue(UsdGeomGetStageMetersPerUnit(stage)));
  set("cycles:samples", VtValue(s.samples));
  set("cycles:integrator:use_denoise", VtValue(s.denoise));
  // our patch (-r3); off only for the Shadow pass (passes.h). A plug-in without it reports nothing: left alone then,
  // as setting an unknown key would start the Final look over on every step.
  if (!s.castShadows || !e.GetRendererSetting(TfToken("rostrum:castShadows")).IsEmpty())
    set("rostrum:castShadows", VtValue(s.castShadows));
  double open = 0, close = 0;
  if (stage && !camera.IsEmpty())
    if (const UsdGeomCamera cam{stage->GetPrimAtPath(camera)}) {
      cam.GetShutterOpenAttr().Get(&open);
      cam.GetShutterCloseAttr().Get(&close);
    }
  set("cycles:integrator:motion_blur", VtValue(close > open));
  if (close > open) {
    set("rostrum:shutterOpen", VtValue(open));
    set("rostrum:shutterClose", VtValue(close));
  }
}

UsdGeomCamera camera_at(const UsdStageRefPtr& stage, const SdfPath& path) {
  UsdGeomCamera cam(stage->GetPrimAtPath(path));
  if (!cam) throw Error("render.camera: no camera at " + path.GetString());
  return cam;
}
}  // namespace

class Hydra::Engine : public UsdImagingGLEngine {
 public:
  // Whether the dome is seen behind the scene. Storm's sky task reads only this render setting (hdx/skydomeTask.cpp,
  // Prepare); the engine copies it to the scene's own domes for the other renderers. Changing it re-syncs nothing else.
  void show_sky(bool visible) {
    SetRendererSetting(HdRenderSettingsTokens->domeLightCameraVisibility, VtValue(visible));
  }
  // Storm and the stylized renderer read a dome only as a picture handed over as a viewport light (sky.h), for the
  // quick view and a final render alike; without a scene dome, `fallback` lights (the studio, or none for a render).
  // Storm also gets the dome's sun as a distant light with a shadow over what `view` sees (storm_sun.h).
  // Returns whether a scene dome is in use, and the sun when Storm drew one.
  bool light_raster(const UsdStageRefPtr& stage, int frame, bool scene_lights, GlfSimpleLightVector fallback,
                    const GfFrustum& view, std::optional<StormSun>* sun_out = nullptr) {
    const auto sky = scene_lights ? scene_sky(stage, frame, storm) : std::nullopt;
    SetLightingState(sky ? GlfSimpleLightVector{sky->dome} : std::move(fallback), GlfSimpleMaterial(),
                     GfVec4f(0, 0, 0, 1));
    show_sky(sky && sky->seen);  // a dome the camera doesn't see still lights (its seenByCamera)
    if (storm) {
      const std::optional<StormSun> sun = sky ? sky->sun : std::nullopt;
      set_storm_sun(sun, sun ? sun_shadow(stage, frame, view) : SunShadow{});
      enable_shadows(bool(sun));
      if (sun_out) *sun_out = sun;
    }
    return bool(sky);
  }
  bool storm = false;  // set when made: Storm alone gets the sun light (storm_sun.h)

  // The colour output plus `extra` (Cycles' passes, passes.h). Set only on a change: each change starts Cycles over.
  void use_aovs(const std::vector<std::string>& extra) {
    if (extra == aovs_) return;
    TfTokenVector want{HdAovTokens->color};
    for (const auto& n : extra) want.emplace_back(n);
    if (!SetRendererAovs(want)) throw Error("render.passes: the renderer could not make the outputs they need");
    aovs_ = extra;
  }
  // the scene prim a Hydra prim id (the primId output) stands for; empty when it names none. Through the engine's
  // public decoding, which works with Hydra 2.0 too: there the engine has no render index of its own (null), and
  // asking for one crashed the engine on the first render with masks (brief 15).
  SdfPath rprim(int id) {
    SdfPath path;
    return DecodeIntersection(id, 0, &path) ? path : SdfPath();
  }

 private:
  // Storm's shadow pass runs only when the task controller says so (hdx simpleLightTask: enableShadows)
  void enable_shadows(bool on) {
    if (_taskControllerSceneIndex) _taskControllerSceneIndex->SetEnableShadows(on);
    else if (_taskController) _taskController->SetEnableShadows(on);
  }
  std::vector<std::string> aovs_;  // the extra outputs set now (use_aovs)
};

Hydra::Hydra(UsdStageRefPtr stage) : stage_(std::move(stage)) {
  register_cycles_dome_fix();
  register_cycles_lights();
  register_storm_sun();
  register_storm_lights();
}

Hydra::~Hydra() {
  engines_.clear();  // release Hydra while the GL context is still there
  fb_.reset();
  mask_fb_.reset();
}

TfToken Hydra::plugin_for(const std::string& name) {
  for (const auto& [n, id] : kRenderers)
    if (n == name) return TfToken(id);
  throw Error("render.renderer: no renderer \"" + name + "\". Accepted: " + join(names()));
}

std::vector<std::string> Hydra::names() {
  std::vector<std::string> v;
  for (const auto& r : kRenderers) v.push_back(r.first);
  return v;
}

std::vector<std::string> Hydra::available() const {
  std::vector<std::string> v;
  const auto plugins = UsdImagingGLEngine::GetRendererPlugins();
  for (const auto& [n, id] : kRenderers)
    if (std::find(plugins.begin(), plugins.end(), TfToken(id)) != plugins.end()) v.push_back(n);
  return v;
}

Hydra::Engine& Hydra::engine(const std::string& renderer, bool viewport) {
  const std::string key = (viewport ? "view:" : "") + renderer;
  auto it = engines_.find(key);
  if (it != engines_.end()) return *it->second;
  const TfToken id = plugin_for(renderer);
  const auto have = available();
  if (std::find(have.begin(), have.end(), renderer) == have.end())
    throw Error("render.renderer: \"" + renderer + "\" (" + id.GetString() +
                ") is not installed on this machine. Available: " + join(have));
  auto e = std::make_unique<Engine>();
  e->storm = renderer == "storm";
  if (!e->SetRendererPlugin(id)) throw Error("render.renderer: Hydra could not start " + id.GetString());
  // Draw into Hydra's own colour picture, then composite it into the framebuffer we bind. Storm starts without one
  // (hdx/taskController.cpp: "AOVs are OFF by default for Storm"), and its sky task draws only into a colour picture
  // (hdx/skydomeTask.cpp: no colour AOV -> it only clears), so without this the dome lights the scene but is never seen.
  if (!e->SetRendererAov(HdAovTokens->color)) throw Error("render.renderer: " + id.GetString() + " has no colour output");
  e->SetEnablePresentation(true);
  return *(engines_[key] = std::move(e));
}

Framebuffer& Hydra::framebuffer(int w, int h) {
  if (!fb_ || fb_->width() != w || fb_->height() != h) {
    fb_.reset();
    fb_ = std::make_unique<Framebuffer>(w, h);
  }
  return *fb_;
}

Framebuffer& Hydra::mask_framebuffer(int w, int h) {
  if (!mask_fb_ || mask_fb_->width() != w || mask_fb_->height() != h) {
    mask_fb_.reset();
    mask_fb_ = std::make_unique<Framebuffer>(w, h);
  }
  return *mask_fb_;
}

Picture Hydra::draw(const std::string& renderer, const SdfPath& camera, int frame, int w, int h,
                    const DrawSettings& s, GpuMemWatch& mem, Aovs* aovs) {
  const UsdGeomCamera cam = camera_at(stage_, camera);
  TfErrorMark mark;
  auto& e = engine(renderer);
  if (!s.aovs.empty() && renderer != "cycles")
    throw Error("render.passes: only the cycles renderer makes passes, not " + renderer);
  if (renderer == "cycles") {
    cycles_settings(e, s, stage_, camera);
    e.use_aovs(s.aovs);
  }
  if (renderer != "cycles")  // a render never sees the studio
    e.light_raster(stage_, frame, true, {}, cam.GetCamera(UsdTimeCode(frame)).GetFrustum());
  e.SetCameraPath(camera);
  e.SetRenderBufferSize(GfVec2i(w, h));
  e.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), w, h)));
  e.SetOverrideWindowPolicy(CameraUtilMatchHorizontally);  // the sensor width holds; its height follows w:h
  UsdImagingGLRenderParams params;
  params.frame = UsdTimeCode(frame);
  params.colorCorrectionMode = TfToken("disabled");  // scene-linear out; OpenColorIO makes the PNG
  params.clearColor = GfVec4f(0, 0, 0, 0);

  auto& fb = framebuffer(w, h);
  const auto t0 = std::chrono::steady_clock::now();
  for (bool first = true;; first = false) {
    fb.bind_and_clear();
    e.Render(stage_->GetPseudoRoot(), params);
    gl_.finish();
    mem.sample();
    throw_usd_errors(mark, "render (" + renderer + ", frame " + std::to_string(frame) + ")");
    if (e.IsConverged()) break;
    const double waited = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    if (waited > s.timeoutS)
      throw Error("render: " + renderer + " did not finish frame " + std::to_string(frame) + " within " +
                  std::to_string(int(s.timeoutS)) + " s (timeoutS); no file written");
    if (!first) std::this_thread::sleep_for(std::chrono::milliseconds(30));
  }
  Picture p{w, h, fb.read_rgba()};
  if (aovs && !s.aovs.empty()) *aovs = read_aovs(e, s.aovs, w, h, [&](int id) { return e.rprim(id); });
  return p;
}

ViewDrawn Hydra::view(const std::string& renderer, const GfFrustum& frustum, int frame, int w, int h,
                      const ViewLook& look, GpuMemWatch& mem) {
  if (renderer != "storm" && renderer != "stylized")
    throw Error("view.renderer: \"" + renderer + "\" is not a live viewport renderer. Accepted: storm, stylized");
  TfErrorMark mark;
  auto& e = engine(renderer, true);
  e.SetCameraState(frustum.ComputeViewMatrix(), frustum.ComputeProjectionMatrix());
  e.SetRenderBufferSize(GfVec2i(w, h));
  e.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), w, h)));
  // the scene's own dome is its sky and light; without one the studio lights the scene and is never seen
  std::optional<StormSun> sun;
  const bool scene_dome = e.light_raster(stage_, frame, look.sceneLights, studio_lights(look.studio), frustum, &sun);
  UsdImagingGLRenderParams params;
  params.frame = UsdTimeCode(frame);
  params.colorCorrectionMode = TfToken("disabled");  // scene-linear out; OpenColorIO makes the picture
  params.clearColor = GfVec4f(0, 0, 0, 0);
  params.enableSceneLights = look.sceneLights;
  auto& fb = framebuffer(w, h);
  const auto t0 = std::chrono::steady_clock::now();
  for (bool first = true;; first = false) {
    fb.bind_and_clear();
    e.Render(stage_->GetPseudoRoot(), params);
    gl_.finish();
    mem.sample();
    throw_usd_errors(mark, "view (" + renderer + ", frame " + std::to_string(frame) + ")");
    if (e.IsConverged()) break;
    if (std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count() > 10)
      throw Error("view: " + renderer + " did not finish frame " + std::to_string(frame) + " within 10 s");
    if (!first) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  ViewDrawn out{fb.color_texture(), fb.depth_texture()};
  out.sceneDome = scene_dome;
  if (sun) out.sun = SunSeen{{sun->toward[0], sun->toward[1], sun->toward[2]}, sun->share, sun->angleDeg};
  // The selection's mask: the selected items alone, unlit, in the same frustum, in a framebuffer of its own (Storm
  // tints a selection but draws no outline; view_post.h draws the ring from this mask after the colour transform).
  if (!look.selected.empty()) {
    UsdImagingGLRenderParams solo = params;
    solo.enableLighting = false;
    e.show_sky(false);  // the mask is the selection alone: no sky behind it
    auto& mf = mask_framebuffer(w, h);
    mf.bind_and_clear();
    for (const auto& path : look.selected) e.Render(stage_->GetPrimAtPath(path), solo);
    throw_usd_errors(mark, "view (selection mask)");
    out.mask = mf.color_texture();
  }
  return out;
}

ViewDrawn Hydra::view_final(const SdfPath& camera, const GfFrustum& frustum, int frame, int w, int h,
                            const DrawSettings& s, GpuMemWatch& mem) {
  TfErrorMark mark;
  auto& e = engine("cycles", true);
  cycles_settings(e, s, stage_, camera);
  if (camera.IsEmpty()) {
    e.SetCameraPath(SdfPath());
    e.SetCameraState(frustum.ComputeViewMatrix(), frustum.ComputeProjectionMatrix());
  } else {  // exactly as draw(): the camera's own path, so its lens and depth of field are Cycles' own
    camera_at(stage_, camera);
    e.SetCameraPath(camera);
    e.SetOverrideWindowPolicy(CameraUtilMatchHorizontally);
  }
  e.SetRenderBufferSize(GfVec2i(w, h));
  e.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), w, h)));
  UsdImagingGLRenderParams params;
  params.frame = UsdTimeCode(frame);
  params.colorCorrectionMode = TfToken("disabled");
  params.clearColor = GfVec4f(0, 0, 0, 0);
  auto& fb = framebuffer(w, h);
  fb.bind_and_clear();
  e.Render(stage_->GetPseudoRoot(), params);
  gl_.finish();
  mem.sample();
  throw_usd_errors(mark, "view (cycles, frame " + std::to_string(frame) + ")");
  FinalPass fp;
  fp.converged = e.IsConverged();
  const VtDictionary st = e.GetRenderStats();
  const auto num = [&](const char* k) {
    auto it = st.find(k);
    return it != st.end() && it->second.IsHolding<double>() ? it->second.UncheckedGet<double>() : 0.0;
  };
  fp.fraction = fp.converged ? 1.0 : num("fractionDone");
  fp.seconds = num("totalClockTime") - num("loadClockTime");
  if (auto it = st.find("totalMemory"); it != st.end() && it->second.IsHolding<size_t>())
    fp.cyclesMb = double(it->second.UncheckedGet<size_t>()) / (1 << 20);
  if (auto it = st.find("renderProgressAnnotation"); it != st.end() && it->second.IsHolding<std::string>())
    fp.status = it->second.UncheckedGet<std::string>();
  ViewDrawn out{fb.color_texture(), fb.depth_texture()};
  out.final = fp;
  return out;
}

SdfPath Hydra::pick(const GfFrustum& f, int frame, int w, int h, double x, double y, GfVec3d* point,
                    GfVec3d* normal) {
  const GfVec2d ndc(2.0 * (x + 0.5) / w - 1.0, 1.0 - 2.0 * (y + 0.5) / h);
  GfFrustum narrow = f.ComputeNarrowedFrustum(ndc, GfVec2d(1.0 / w, 1.0 / h));
  UsdImagingGLRenderParams params;
  params.frame = UsdTimeCode(frame);
  TfErrorMark mark;
  auto& e = engine("storm", true);  // picking is the viewport's Storm; the answer is the same whatever drew the picture
  SdfPath hit;
  framebuffer(w, h).bind_and_clear();
  const bool any = e.TestIntersection(narrow.ComputeViewMatrix(), narrow.ComputeProjectionMatrix(),
                                      stage_->GetPseudoRoot(), params, point, normal, &hit);
  throw_usd_errors(mark, "pick");
  if (!any) return SdfPath();
  if (normal->GetLength() < 1e-12) *normal = f.GetPosition() - *point;  // no normal from the hit: face the camera
  normal->Normalize();
  if (GfDot(*normal, f.GetPosition() - *point) < 0) *normal = -*normal;  // the side the camera sees
  return hit;
}

}  // namespace r3d
