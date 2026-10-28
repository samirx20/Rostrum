#include "hydra.h"

#include <pxr/base/gf/frustum.h>
#include <pxr/base/gf/vec4d.h>
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

#include <algorithm>
#include <chrono>
#include <cmath>
#include <set>
#include <thread>

#include "clay_whole.h"
#include "cycles_lights.h"
#include "dome_cycles.h"
#include "error.h"
#include "light_to_color.h"
#include "sky.h"
#include "storm_lights.h"
#include "storm_programs.h"
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
// `progressive`: the viewport's Final look, which shows the noise cleaned up as it refines. A render cleans up once,
// at its last sample: the plug-in's session is interactive, so it otherwise also cleans up the picture every time it
// updates the display, on a timer, which made a full HD frame at 128 samples cost 2x and vary from run to run (13d).
void cycles_settings(UsdImagingGLEngine& e, const DrawSettings& s, const UsdStageRefPtr& stage,
                     const SdfPath& camera, bool progressive) {
  const auto set = [&](const char* key, const VtValue& v) {
    if (e.GetRendererSetting(TfToken(key)) != v) e.SetRendererSetting(TfToken(key), v);
  };
  if (stage) set("stageMetersPerUnit", VtValue(UsdGeomGetStageMetersPerUnit(stage)));
  set("cycles:samples", VtValue(s.samples));
  set("cycles:integrator:use_denoise", VtValue(s.denoise));
  set("cycles:integrator:denoise_start_sample", VtValue(progressive ? 0 : s.samples));
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

// The stylized renderer's settings (apps/3d/stylized, renderPass.cpp): `rostrum:ss` x the picture's size (1 in the
// viewport for video memory, the render's `stylized.supersample`), its shadow maps 2048 square. Set only on a change.
void stylized_settings(UsdImagingGLEngine& e, int supersample) {
  const auto set = [&](const char* key, const VtValue& v) {
    if (e.GetRendererSetting(TfToken(key)) != v) e.SetRendererSetting(TfToken(key), v);
  };
  set("rostrum:ss", VtValue(supersample));
  set("rostrum:shadow:size", VtValue(2048));
}

// what a white floor shows under the viewport's studio (Rec.709 luminance)
double studio_floor_level(double strength) {
  const GfVec3f l = dome_floor_level(studio_texture(strength));
  return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2];
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
  // Storm reads a dome only as a picture handed over as a viewport light (sky.h), for the quick view and a final
  // render alike; without a scene dome, `fallback` lights (the studio, or none for a render).
  // Storm also gets the dome's sun as a distant light with a shadow over what `view` sees (storm_sun.h).
  // The stylized renderer reads every scene light, its dome too, as the UsdLux light it is (real brightness; a dome's
  // picture level from primvars:rostrum:domeLevel, light_to_color.h): handed the dome again as a viewport light it
  // would light twice, so it gets a viewport light only when no scene dome lights (the studio, a dome, in the view).
  // Returns whether a scene dome is in use, and the sun when Storm drew one.
  bool light_raster(const UsdStageRefPtr& stage, int frame, bool scene_lights, GlfSimpleLightVector fallback,
                    const GfFrustum& view, std::optional<StormSun>* sun_out = nullptr) {
    const auto sky = scene_lights ? scene_sky(stage, frame, storm) : std::nullopt;
    SetLightingState(sky ? (stylized ? GlfSimpleLightVector{} : GlfSimpleLightVector{sky->dome}) : std::move(fallback),
                     GlfSimpleMaterial(), GfVec4f(0, 0, 0, 1));
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
  bool stylized = false;  // set when made: reads the scene's dome itself (light_raster)
  // after a live picture: Storm's programs held, so a dab's clean-up doesn't drop the glass pass's (storm_programs.h)
  void keep_programs() {
    if (storm) programs_.keep(_renderer.Get(), _renderDelegate.Get());
  }

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
  StormPrograms programs_;
  // Storm's shadow pass runs only when the task controller says so (hdx simpleLightTask: enableShadows)
  void enable_shadows(bool on) {
    if (_taskControllerSceneIndex) _taskControllerSceneIndex->SetEnableShadows(on);
    else if (_taskController) _taskController->SetEnableShadows(on);
  }
  std::vector<std::string> aovs_;  // the extra outputs set now (use_aovs)
};

namespace {
void register_scene_fixes() {
  register_cycles_dome_fix();
  register_cycles_lights();
  clay::register_cycles_clay_whole();
  register_storm_sun();
  register_storm_lights();
}
}  // namespace

Hydra::Hydra(UsdStageRefPtr stage) : stage_(std::move(stage)) { register_scene_fixes(); }

Hydra::Hydra(UsdStageRefPtr stage, GlContext::Borrow b) : stage_(std::move(stage)), gl_(b) { register_scene_fixes(); }

Hydra::~Hydra() {
  engines_.clear();  // release Hydra while the GL context is still there
  fb_.reset();
  mask_fb_.reset();
  ghost_fbs_.clear();
  sees_fb_.reset();
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
  return *(engines_[key] = make_engine(renderer));
}

// The selection mask's own Storm engine (CL1b). Drawn by the viewport's engine with the selected prim as its root,
// the mask flipped that engine's draw list between the whole scene and the selection twice a picture, and every
// changed clay block was processed twice: the outline doubled the picture's time (22 -> 48 ms after a dab). Its own
// engine keeps one root until the selection changes, and never shows the sky. It also draws prim ids (brief 21:
// ids(), for `sees` and `texels`), set once when made: each change of outputs restarts Storm's tasks.
Hydra::Engine& Hydra::mask_engine() {
  auto it = engines_.find("mask:storm");
  if (it != engines_.end()) return *it->second;
  auto e = make_engine("storm");
  e->show_sky(false);
  // colour stays first: the masks are still presented as before; depth is read from Storm's own output (ids()): with
  // extra outputs the framebuffer's depth is not the one Storm drew
  e->use_aovs({HdAovTokens->primId.GetString(), HdAovTokens->depth.GetString()});
  return *(engines_["mask:storm"] = std::move(e));
}

std::unique_ptr<Hydra::Engine> Hydra::make_engine(const std::string& renderer) {
  const TfToken id = plugin_for(renderer);
  const auto have = available();
  if (std::find(have.begin(), have.end(), renderer) == have.end())
    throw Error("render.renderer: \"" + renderer + "\" (" + id.GetString() +
                ") is not installed on this machine. Available: " + join(have));
  auto e = std::make_unique<Engine>();
  e->storm = renderer == "storm";
  e->stylized = renderer == "stylized";
  if (!e->SetRendererPlugin(id)) throw Error("render.renderer: Hydra could not start " + id.GetString());
  // Draw into Hydra's own colour picture, then composite it into the framebuffer we bind. Storm starts without one
  // (hdx/taskController.cpp: "AOVs are OFF by default for Storm"), and its sky task draws only into a colour picture
  // (hdx/skydomeTask.cpp: no colour AOV -> it only clears), so without this the dome lights the scene but is never seen.
  if (!e->SetRendererAov(HdAovTokens->color)) throw Error("render.renderer: " + id.GetString() + " has no colour output");
  e->SetEnablePresentation(true);
  return e;
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
    cycles_settings(e, s, stage_, camera, false);
    e.use_aovs(s.aovs);
  }
  if (renderer == "stylized") stylized_settings(e, s.supersample);
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
  double told_ms = 0;
  for (bool first = true;; first = false) {
    fb.bind_and_clear();
    e.Render(stage_->GetPseudoRoot(), params);
    gl_.finish();
    mem.sample();
    throw_usd_errors(mark, "render (" + renderer + ", frame " + std::to_string(frame) + ")");
    if (e.IsConverged()) break;
    const double waited = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    if (s.onStep && waited * 1000 >= told_ms + 250) {  // the share done so far, for the caller's time left
      told_ms = waited * 1000;
      const VtDictionary st = e.GetRenderStats();
      const auto it = st.find("fractionDone");
      if (it != st.end() && it->second.IsHolding<double>()) s.onStep(it->second.UncheckedGet<double>(), told_ms);
    }
    if (waited > s.timeoutS)
      throw Error("render: " + renderer + " did not finish frame " + std::to_string(frame) + " within " +
                  std::to_string(int(s.timeoutS)) + " s (timeoutS); no file written");
    if (!first) std::this_thread::sleep_for(std::chrono::milliseconds(30));
  }
  if (s.aovs.empty()) return Picture{w, h, fb.read_rgba()};
  // With more outputs than colour the engine presents nothing into our framebuffer (brief 15: an empty picture), so
  // the colour is read from its own output like the others (on the CPU: the patch keeps Cycles' GL display off).
  std::vector<std::string> names = s.aovs;
  names.push_back(HdAovTokens->color.GetString());
  Aovs read = read_aovs(e, names, w, h, [&](int id) { return e.rprim(id); });
  if (read.channels[HdAovTokens->color.GetString()] != 4) throw Error("render: the colour output is not RGBA");
  Picture p{w, h, std::move(read.planes[HdAovTokens->color.GetString()])};
  read.planes.erase(HdAovTokens->color.GetString());
  if (aovs) *aovs = std::move(read);
  return p;
}

ViewDrawn Hydra::view(const std::string& renderer, const GfFrustum& frustum, int frame, int w, int h,
                      const ViewLook& look, GpuMemWatch& mem) {
  if (renderer != "storm" && renderer != "stylized")
    throw Error("view.renderer: \"" + renderer + "\" is not a live viewport renderer. Accepted: storm, stylized");
  TfErrorMark mark;
  auto& e = engine(renderer, true);
  if (renderer == "stylized") stylized_settings(e, 1);
  e.SetCameraState(frustum.ComputeViewMatrix(), frustum.ComputeProjectionMatrix());
  e.SetRenderBufferSize(GfVec2i(w, h));
  e.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), w, h)));
  // the scene's own dome is its sky and light; without one the studio lights the scene and is never seen
  std::optional<StormSun> sun;
  const auto tl = std::chrono::steady_clock::now();
  const bool scene_dome = e.light_raster(stage_, frame, look.sceneLights, studio_lights(look.studio), frustum, &sun);
  if (renderer == "stylized") {  // the studio's light when it lights: its picture's floor level (a viewport light
    // carries only the picture), as "how lit" counts a dome (light_to_color.h dome_floor_level); 0 = no studio
    const VtValue level(scene_dome || look.studio <= 0 ? 0.0 : studio_floor_level(look.studio));
    if (e.GetRendererSetting(TfToken("rostrum:studio:level")) != level)
      e.SetRendererSetting(TfToken("rostrum:studio:level"), level);
  }
  const double light_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - tl).count();
  UsdImagingGLRenderParams params;
  params.frame = UsdTimeCode(frame);
  params.colorCorrectionMode = TfToken("disabled");  // scene-linear out; OpenColorIO makes the picture
  params.clearColor = GfVec4f(0, 0, 0, 0);
  params.enableSceneLights = look.sceneLights;
  auto& fb = framebuffer(w, h);
  const auto t0 = std::chrono::steady_clock::now();
  double finish_ms = 0;
  for (bool first = true;; first = false) {
    fb.bind_and_clear();
    e.Render(stage_->GetPseudoRoot(), params);
    const auto tf = std::chrono::steady_clock::now();
    if (!gl_.borrowed() || !e.IsConverged()) gl_.finish();  // in the window: ordered on its context, no wait
    finish_ms += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - tf).count();
    e.keep_programs();
    mem.recent();
    throw_usd_errors(mark, "view (" + renderer + ", frame " + std::to_string(frame) + ")");
    if (e.IsConverged()) break;
    if (std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count() > 10)
      throw Error("view: " + renderer + " did not finish frame " + std::to_string(frame) + " within 10 s");
    if (!first) std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  ViewDrawn out{fb.color_texture(), fb.depth_texture()};
  out.lightMs = light_ms;
  out.finishMs = finish_ms;
  out.renderMs = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  out.sceneDome = scene_dome;
  if (sun) out.sun = SunSeen{{sun->toward[0], sun->toward[1], sun->toward[2]}, sun->share, sun->angleDeg};
  // The selection's mask: the selected items alone, unlit, in the same frustum, in a framebuffer of its own (Storm
  // tints a selection but draws no outline; view_post.h draws the ring from this mask after the colour transform).
  if (!look.selected.empty()) {
    UsdImagingGLRenderParams solo = params;
    solo.enableLighting = false;
    auto& m = mask_engine();  // its own engine, no sky (see mask_engine)
    m.SetCameraState(frustum.ComputeViewMatrix(), frustum.ComputeProjectionMatrix());
    m.SetRenderBufferSize(GfVec2i(w, h));
    m.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), w, h)));
    auto& mf = mask_framebuffer(w, h);
    mf.bind_and_clear();
    for (const auto& path : look.selected) m.Render(stage_->GetPrimAtPath(path), solo);
    throw_usd_errors(mark, "view (selection mask)");
    out.mask = mf.color_texture();
  }
  // The hover's mask (3d-v4): the hovered items alone, the same way, in a framebuffer of its own (view_post.h draws a
  // 1 px, softer outline from it). The selection's engine: the screen sent the hovered clay as `selected` before, so
  // its roots per picture are as many as before.
  if (!look.hovered.empty()) {
    UsdImagingGLRenderParams solo = params;
    solo.enableLighting = false;
    auto& m = mask_engine();
    m.SetCameraState(frustum.ComputeViewMatrix(), frustum.ComputeProjectionMatrix());
    m.SetRenderBufferSize(GfVec2i(w, h));
    m.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), w, h)));
    if (!hover_fb_ || hover_fb_->width() != w || hover_fb_->height() != h) {
      hover_fb_.reset();
      hover_fb_ = std::make_unique<Framebuffer>(w, h);
    }
    hover_fb_->bind_and_clear();
    for (const auto& path : look.hovered) m.Render(stage_->GetPrimAtPath(path), solo);
    throw_usd_errors(mark, "view (hover mask)");
    out.hoverMask = hover_fb_->color_texture();
  }
  // Onion skin: each ghost's items alone at the ghost's frame, lit like this picture, in a framebuffer of its own
  // (view_post.h tints them and lays them over the picture). The ghost's frame is a time change for the engine; the
  // next picture's own frame changes it back.
  if (!look.ghosts.empty()) {
    e.show_sky(false);
    if (ghost_fbs_.size() < look.ghosts.size()) ghost_fbs_.resize(look.ghosts.size());
    for (size_t i = 0; i < look.ghosts.size(); ++i) {
      const Ghost& g = look.ghosts[i];
      auto& gf = ghost_fbs_[i];
      if (!gf || gf->width() != w || gf->height() != h) {
        gf.reset();
        gf = std::make_unique<Framebuffer>(w, h);
      }
      UsdImagingGLRenderParams at = params;
      at.frame = UsdTimeCode(g.frame);
      gf->bind_and_clear();
      for (const auto& path : g.items) e.Render(stage_->GetPrimAtPath(path), at);
      throw_usd_errors(mark, "view (onion-skin ghost at frame " + std::to_string(g.frame) + ")");
      out.ghosts.push_back(gf->color_texture());
    }
  }
  return out;
}

ViewDrawn Hydra::view_final(const SdfPath& camera, const GfFrustum& frustum, int frame, int w, int h,
                            const DrawSettings& s, GpuMemWatch& mem) {
  TfErrorMark mark;
  auto& e = engine("cycles", true);
  cycles_settings(e, s, stage_, camera, true);
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
                    GfVec3d* normal, SdfPath* instancer, int* instance) {
  const GfVec2d ndc(2.0 * (x + 0.5) / w - 1.0, 1.0 - 2.0 * (y + 0.5) / h);
  GfFrustum narrow = f.ComputeNarrowedFrustum(ndc, GfVec2d(1.0 / w, 1.0 / h));
  UsdImagingGLRenderParams params;
  params.frame = UsdTimeCode(frame);
  TfErrorMark mark;
  auto& e = engine("storm", true);  // picking is the viewport's Storm; the answer is the same whatever drew the picture
  SdfPath hit, by;
  int index = -1;
  framebuffer(w, h).bind_and_clear();
  const bool any = e.TestIntersection(narrow.ComputeViewMatrix(), narrow.ComputeProjectionMatrix(),
                                      stage_->GetPseudoRoot(), params, point, normal, &hit, &by, &index);
  if (instancer) *instancer = any ? by : SdfPath();
  if (instance) *instance = any ? index : -1;
  throw_usd_errors(mark, "pick");
  if (!any) return SdfPath();
  if (normal->GetLength() < 1e-12) *normal = f.GetPosition() - *point;  // no normal from the hit: face the camera
  normal->Normalize();
  if (GfDot(*normal, f.GetPosition() - *point) < 0) *normal = -*normal;  // the side the camera sees
  return hit;
}

namespace {
// The prims to draw so that everything but `hide` (and what they hold) is drawn: the roots of the stage's tree with the
// hidden branches cut out (an item's ancestors are groups, so cutting at them loses no geometry of their own).
void roots_without(const UsdPrim& prim, const SdfPathVector& hide, SdfPathVector* out) {
  for (const SdfPath& h : hide)
    if (prim.GetPath() == h) return;
  bool holds = false;
  for (const SdfPath& h : hide) holds |= h.HasPrefix(prim.GetPath());
  if (!holds) {
    out->push_back(prim.GetPath());
    return;
  }
  for (const UsdPrim& child : prim.GetChildren()) roots_without(child, hide, out);
}
}  // namespace

// The one id + depth drawing: Storm through the frustum with the selection mask's engine (no sky, unlit; drawn rarely,
// after a scene or on request), everything but `hide`. Depth from the framebuffer it presents into, prim ids from
// the engine's own primId output.
IdPicture Hydra::ids(const GfFrustum& f, int frame, int w, int h, const SdfPathVector& hide, bool prim_ids) {
  TfErrorMark mark;
  auto& e = mask_engine();
  e.SetCameraState(f.ComputeViewMatrix(), f.ComputeProjectionMatrix());
  e.SetRenderBufferSize(GfVec2i(w, h));
  e.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), w, h)));
  UsdImagingGLRenderParams params;
  params.frame = UsdTimeCode(frame);
  params.enableLighting = false;
  params.colorCorrectionMode = TfToken("disabled");
  params.clearColor = GfVec4f(0, 0, 0, 0);
  // the id picture without the scene's materials: a see-through one (glass) makes Storm's see-through pass end with a
  // full-screen triangle that leaves every pixel's prim id the scene's first; drawn plain, glass is its front surface
  params.enableSceneMaterials = !prim_ids;
  SdfPathVector roots;
  roots_without(stage_->GetPseudoRoot(), hide, &roots);
  if (!sees_fb_ || sees_fb_->width() != w || sees_fb_->height() != h) {
    sees_fb_.reset();
    sees_fb_ = std::make_unique<Framebuffer>(w, h);
  }
  sees_fb_->bind_and_clear();
  e.PrepareBatch(stage_->GetPseudoRoot(), params);
  e.RenderBatch(roots, params);
  gl_.finish();
  throw_usd_errors(mark, "ids (frame " + std::to_string(frame) + ")");
  IdPicture out;
  out.width = w;
  out.height = h;
  std::vector<std::string> names{HdAovTokens->depth.GetString()};
  if (prim_ids) names.push_back(HdAovTokens->primId.GetString());
  Aovs read = read_aovs(e, names, w, h, [&](int id) { return e.rprim(id); });   // top row first
  out.depth = std::move(read.planes[HdAovTokens->depth.GetString()]);
  if (out.depth.size() != size_t(w) * h) throw Error("ids: Storm's depth output is not one value a pixel");
  if (prim_ids) {
    out.primIds = std::move(read.primIds);
    // (drawn without the scene's materials above: a see-through one would end Storm's pass with a full-screen triangle
    // that leaves every pixel's id the scene's first prim)
    std::set<int> shown;
    for (size_t i = 0, last = size_t(-1); i < out.primIds.size(); ++i) {
      const int id = out.primIds[i];
      if (id >= 0 && size_t(id) != last) {  // runs of one id: one look-up each
        shown.insert(id);
        last = size_t(id);
      }
    }
    for (int id : shown) out.prims[id] = read.prims[id];
    throw_usd_errors(mark, "ids (prim ids, frame " + std::to_string(frame) + ")");
  }
  return out;
}

// ids()' depth, each point projected and compared with the depth drawn there as distances from the eye.
std::vector<bool> Hydra::sees(const GfFrustum& f, int frame, int w, int h, const SdfPathVector& hide,
                              const std::vector<GfVec3d>& points) {
  const IdPicture pic = ids(f, frame, w, h, hide, false);
  const GfMatrix4d to_clip = f.ComputeViewMatrix() * f.ComputeProjectionMatrix(), from_clip = to_clip.GetInverse();
  const GfVec3d eye = f.GetPosition();
  std::vector<bool> out(points.size(), false);
  for (size_t i = 0; i < points.size(); ++i) {
    const GfVec4d c = GfVec4d(points[i][0], points[i][1], points[i][2], 1) * to_clip;
    if (c[3] <= 1e-9) continue;  // behind the camera
    const double x = c[0] / c[3], y = c[1] / c[3], z = c[2] / c[3];
    if (std::abs(x) > 1.05 || std::abs(y) > 1.05 || z > 1) continue;
    const int px = std::clamp(int((x * 0.5 + 0.5) * w), 0, w - 1), py = std::clamp(int((y * 0.5 + 0.5) * h), 0, h - 1);
    const float d = pic.depth[size_t(h - 1 - py) * w + px];  // py counts from the bottom
    if (d >= 1.f) { out[i] = true; continue; }  // nothing drawn there
    const GfVec4d q = GfVec4d(x, y, 2.0 * d - 1.0, 1) * from_clip;
    const double drawn = (GfVec3d(q[0], q[1], q[2]) / q[3] - eye).GetLength(), here = (points[i] - eye).GetLength();
    out[i] = here <= drawn * 1.01 + 0.02;  // on or in front of what is drawn (a point on a surface is seen)
  }
  return out;
}

}  // namespace r3d
