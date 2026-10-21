#include "hydra.h"

#include <pxr/base/gf/frustum.h>
#include <pxr/base/tf/errorMark.h>
#include <pxr/imaging/cameraUtil/conformWindow.h>
#include <pxr/imaging/cameraUtil/framing.h>
#include <pxr/imaging/glf/simpleMaterial.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/camera.h>
#include <pxr/usd/usdLux/domeLight.h>
#include <pxr/usd/usdLux/domeLight_1.h>
#include <pxr/usd/usdLux/lightAPI.h>
#include <pxr/usd/usdLux/tokens.h>

#include <chrono>
#include <cmath>
#include <optional>
#include <thread>

#include "error.h"
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

// Storm lights and draws the sky from one dome only, and only from a picture: the scene's first dome is handed
// to it as that one dome (a colour-only dome as a flat picture of its colour x intensity x 2^exposure)
std::optional<GlfSimpleLight> scene_sky(const UsdStageRefPtr& stage, int frame) {
  for (const UsdPrim& p : stage->Traverse()) {
    if (!p.IsA<UsdLuxDomeLight>() && !p.IsA<UsdLuxDomeLight_1>()) continue;
    const UsdTimeCode t(frame);
    SdfAssetPath tex;
    p.GetAttribute(UsdLuxTokens->inputsTextureFile).Get(&tex, t);
    if (!tex.GetResolvedPath().empty() || !tex.GetAssetPath().empty())
      return dome_light(tex.GetResolvedPath().empty() ? tex.GetAssetPath() : tex.GetResolvedPath(), "/RostrumViewport/sky");
    UsdLuxLightAPI l(p);
    GfVec3f colour(1);
    float intensity = 1, exposure = 0;
    l.GetColorAttr().Get(&colour, t);
    l.GetIntensityAttr().Get(&intensity, t);
    l.GetExposureAttr().Get(&exposure, t);
    return dome_light(flat_texture(colour * intensity * std::exp2(exposure)), "/RostrumViewport/sky");
  }
  return std::nullopt;
}

UsdGeomCamera camera_at(const UsdStageRefPtr& stage, const SdfPath& path) {
  UsdGeomCamera cam(stage->GetPrimAtPath(path));
  if (!cam) throw Error("render.camera: no camera at " + path.GetString());
  return cam;
}
}  // namespace

// The dome's camera visibility lives on UsdImagingGLEngine's protected members.
class Hydra::Engine : public UsdImagingGLEngine {
 public:
  void set_dome_camera_visibility(bool visible) {
    if (_domeLightCameraVisibility == visible) return;
    _domeLightCameraVisibility = visible;
    _UpdateDomeLightCameraVisibility();
  }
};

Hydra::Hydra(UsdStageRefPtr stage) : stage_(std::move(stage)) {}

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
  if (!e->SetRendererPlugin(id)) throw Error("render.renderer: Hydra could not start " + id.GetString());
  e->SetEnablePresentation(true);  // composite into the framebuffer we bind
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
  camera_at(stage_, camera);
  TfErrorMark mark;
  auto& e = engine(renderer);
  if (renderer == "cycles") {
    e.SetRendererSetting(TfToken("cycles:samples"), VtValue(s.samples));
    e.SetRendererSetting(TfToken("cycles:integrator:use_denoise"), VtValue(s.denoise));
  }
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
  const auto sky = look.sceneLights ? scene_sky(stage_, frame) : std::nullopt;
  e.SetLightingState(sky ? GlfSimpleLightVector{*sky} : studio_lights(look.studio), GlfSimpleMaterial(),
                     GfVec4f(0, 0, 0, 1));
  e.set_dome_camera_visibility(bool(sky));
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
  // The selection's mask: the selected items alone, unlit, in the same frustum (Storm tints a selection but
  // draws no outline; the outline is drawn from this mask after the colour transform, in requests.cpp).
  if (!look.selected.empty()) {
    UsdImagingGLRenderParams solo = params;
    solo.enableLighting = false;
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
