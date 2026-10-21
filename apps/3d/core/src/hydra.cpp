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

#include <chrono>
#include <thread>

#include "cycles_lights.h"
#include "dome_cycles.h"
#include "error.h"
#include "sky.h"
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
    show_sky(bool(sky));
    if (storm) {
      const std::optional<StormSun> sun = sky ? sky->sun : std::nullopt;
      set_storm_sun(sun, sun ? sun_shadow(stage, frame, view) : SunShadow{});
      enable_shadows(bool(sun));
      if (sun_out) *sun_out = sun;
    }
    return bool(sky);
  }
  bool storm = false;  // set when made: Storm alone gets the sun light (storm_sun.h)

 private:
  // Storm's shadow pass runs only when the task controller says so (hdx simpleLightTask: enableShadows)
  void enable_shadows(bool on) {
    if (_taskControllerSceneIndex) _taskControllerSceneIndex->SetEnableShadows(on);
    else if (_taskController) _taskController->SetEnableShadows(on);
  }
};

Hydra::Hydra(UsdStageRefPtr stage) : stage_(std::move(stage)) {
  register_cycles_dome_fix();
  register_cycles_lights();
  register_storm_sun();
}

Hydra::~Hydra() {
  engines_.clear();  // release Hydra while the GL context is still there
  fb_.reset();
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

Picture Hydra::draw(const std::string& renderer, const SdfPath& camera, int frame, int w, int h,
                    const DrawSettings& s, GpuMemWatch& mem) {
  const UsdGeomCamera cam = camera_at(stage_, camera);
  TfErrorMark mark;
  auto& e = engine(renderer);
  if (renderer == "cycles") {
    e.SetRendererSetting(TfToken("cycles:samples"), VtValue(s.samples));
    e.SetRendererSetting(TfToken("cycles:integrator:use_denoise"), VtValue(s.denoise));
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
  return p;
}

Picture Hydra::view(const std::string& renderer, const GfFrustum& frustum, int frame, int w, int h,
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
  Picture pic{w, h, fb.read_rgba()};
  pic.sceneDome = scene_dome;
  if (sun) pic.sun = SunSeen{{sun->toward[0], sun->toward[1], sun->toward[2]}, sun->share, sun->angleDeg};
  // The selection's mask: the selected items alone, unlit, in the same frustum (Storm tints a selection but
  // draws no outline; the outline is drawn from this mask after the colour transform, in requests.cpp).
  if (!look.selected.empty()) {
    UsdImagingGLRenderParams solo = params;
    solo.enableLighting = false;
    e.show_sky(false);  // the mask is the selection alone: no sky behind it
    fb.bind_and_clear();
    for (const auto& path : look.selected) e.Render(stage_->GetPrimAtPath(path), solo);
    gl_.finish();
    throw_usd_errors(mark, "view (selection mask)");
    const auto px = fb.read_rgba();
    pic.mask.resize(size_t(w) * h);
    for (size_t i = 0; i < pic.mask.size(); ++i) pic.mask[i] = px[i * 4 + 3] > 0.5f;
  }
  return pic;
}

SdfPath Hydra::pick(const GfFrustum& f, int frame, int w, int h, double x, double y, GfVec3d* point) {
  const GfVec2d ndc(2.0 * (x + 0.5) / w - 1.0, 1.0 - 2.0 * (y + 0.5) / h);
  GfFrustum narrow = f.ComputeNarrowedFrustum(ndc, GfVec2d(1.0 / w, 1.0 / h));
  UsdImagingGLRenderParams params;
  params.frame = UsdTimeCode(frame);
  TfErrorMark mark;
  auto& e = engine("storm", true);  // picking is the viewport's Storm; the answer is the same whatever drew the picture
  GfVec3d normal;
  SdfPath hit;
  framebuffer(w, h).bind_and_clear();
  const bool any = e.TestIntersection(narrow.ComputeViewMatrix(), narrow.ComputeProjectionMatrix(),
                                      stage_->GetPseudoRoot(), params, point, &normal, &hit);
  throw_usd_errors(mark, "pick");
  return any ? hit : SdfPath();
}

}  // namespace r3d
