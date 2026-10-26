// P-Clay proof: the pictures (view.h). Throwaway proof code.
//
// Stage (in memory, metres, Y up):
//   /Clay          Xform, the clay material bound; block meshes /Clay/b_<x>_<y>_<z> (Storm only)
//   /Final         one mesh, made by the first render_cycles and updated in place after; visible only while a Final
//                  renders (Cycles only)
//   /Looks/Clay    UsdPreviewSurface, warm light grey, rough. Outside /Clay so excluding /Clay keeps it.
//   /Lights/...    key (rect), fill (sphere), rim (rect), a dim flat dome; placed around the camera's target
//   /Cam           the camera
// Block prims are written straight into the root layer's specs (Sdf), not through UsdGeomMesh: inside an
// SdfChangeBlock the stage doesn't recompose, so UsdStage::DefinePrim would hand back an invalid prim there. It is
// also the fast path (one SetField per attribute, the VtArray moved in).
// Two Hydra engines, each made once and kept for the View's lifetime (as apps/3d/core/src/hydra.cpp keeps its engines
// warm): Storm (made with the View, /Final excluded) and Cycles (made by the first render_cycles, /Clay excluded and
// also made invisible while it renders, in case the engine's exclusion isn't honoured). A second Cycles engine made
// after the first was destroyed crashed (access violation, part 1), so the one engine is reused for every Final and
// released in ~View while the GL context is still alive. Note: it keeps its scene in memory between Finals.
#include "view.h"

#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/tf/errorMark.h>
#include <pxr/imaging/cameraUtil/conformWindow.h>
#include <pxr/imaging/cameraUtil/framing.h>
#include <pxr/imaging/glf/simpleLight.h>
#include <pxr/imaging/glf/simpleMaterial.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/usd/sdf/attributeSpec.h>
#include <pxr/usd/sdf/changeBlock.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/sdf/schema.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/camera.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/metrics.h>
#include <pxr/usd/usdGeom/tokens.h>
#include <pxr/usd/usdGeom/xform.h>
#include <pxr/usd/usdLux/domeLight.h>
#include <pxr/usd/usdLux/rectLight.h>
#include <pxr/usd/usdLux/sphereLight.h>
#include <pxr/usd/usdShade/material.h>
#include <pxr/usd/usdShade/materialBindingAPI.h>
#include <pxr/usd/usdShade/shader.h>
#include <pxr/usdImaging/usdImagingGL/engine.h>

#include <OpenImageIO/imageio.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cfloat>
#include <chrono>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <iterator>
#include <map>
#include <optional>
#include <stdexcept>
#include <thread>

#include "gl_context.h"  // apps/3d/core/src

PXR_NAMESPACE_USING_DIRECTIVE

namespace clay {

namespace {
using Clock = std::chrono::steady_clock;
constexpr float kPi = 3.14159265358979323846f;

const TfToken kStorm("HdStormRendererPlugin");
const TfToken kCycles("HdCyclesPlugin");
const SdfPath kClay("/Clay"), kFinal("/Final"), kLook("/Looks/Clay"), kCam("/Cam");

// Storm lights from the stage's UsdLux lights (as apps/3d/core/src/hydra.cpp draw() does for a Storm render). If the
// first run shows unlit (black) clay in Storm, set this false: Storm then gets the same three lights as GlfSimpleLights
// through SetLightingState, scene lights off.
// Storm is lit by the same lights handed over as simple lights (no scene-light passes: the live view must stay fast,
// measured 6.9 -> 19.7 ms a frame with the studio panels as scene lights); CLAY_STORM_SCENE=1 uses the scene lights
const bool kStormSceneLights = std::getenv("CLAY_STORM_SCENE") != nullptr;

// Look of the Final picture: a clay "turntable" studio (as Nomad Sculpt / ZBrush pieces are shown). Linear values.
// Clay: a warm light clay (sRGB about 205 / 192 / 178), a little sheen (roughness 0.4 with the default 4 % specular),
// so the highlights describe the forms without looking wet or plastic.
const GfVec3f kClayColor(0.61f, 0.53f, 0.46f);
constexpr float kClayRoughness = 0.4f;
// Background: dark neutral grey, never pure black, a touch lighter behind the clay than in the corners (a soft
// vignette, sRGB about 46 at the centre to 22 in the corners) so the piece sits in a pool of light. The dome is never seen.
constexpr float kBackgroundCentre = 0.027f, kBackgroundEdge = 0.008f;

// The lights, for a clay ~0.25-0.35 units tall near the target. `dir` is in camera terms (x right, y up, z toward the
// camera); `radiance` is UsdLux intensity with normalize off. Irradiance E ≈ radiance · area / dist² for a surface
// facing the light; what the camera sees is albedo · E / π (albedo ≈ 0.55).
//  Key: a big soft panel (0.5 × 0.5 at 1.0, about 28° across: soft-edged shadows) high and well to the side (~50° off
//       the view), so the forms turn from light to shade across the face. E ≈ 19 · 0.25 / 1 = 4.75 → ~0.83 (the tone
//       curve's shoulder rolls it off).
//  Fill: a large, faint, slightly cool panel low on the other side, E ≈ 2.6 · 0.36 / 1.44 = 0.65 → ~0.11: the shadow
//       side stays readable at about 1/7 of the key (2.8 stops), dark enough that the forms read.
//  Rim: a narrow strip behind and above on the fill side, strong (E ≈ 50 · 0.06 / 0.64 = 4.7 where it hits face-on) so
//       it draws a bright edge along the silhouette and separates the clay from the dark background.
//  Dome: flat and very low (0.03 → ~0.017 on an upward face): only keeps the deepest crevices from going black.
struct LightDef {
  const char* name;
  bool rect;          // rect panel, else sphere
  float dir[3];       // toward the light from the target, camera frame
  float dist;         // from the target
  float w, h;         // rect size, or sphere radius in w
  float radiance;
  GfVec3f color;
};
const LightDef kLights[] = {
    {"Key", true, {0.85f, 0.75f, 0.55f}, 1.0f, 0.5f, 0.5f, 19.0f, GfVec3f(1.0f, 0.96f, 0.90f)},
    {"Fill", true, {-0.9f, -0.05f, 0.55f}, 1.2f, 0.6f, 0.6f, 2.6f, GfVec3f(0.88f, 0.94f, 1.0f)},
    {"Rim", true, {-0.6f, 0.55f, -0.85f}, 0.8f, 0.5f, 0.12f, 50.0f, GfVec3f(1.0f, 1.0f, 1.0f)},
};
constexpr float kDomeIntensity = 0.03f;

// the area a light shows the clay: a panel's, a bulb's disk (πr²); E = radiance · this / dist²
float light_area(const LightDef& d) { return d.rect ? d.w * d.h : kPi * d.w * d.w; }

void throw_usd_errors(const TfErrorMark& mark, const std::string& where) {
  if (mark.IsClean()) return;
  std::string msg;
  for (auto it = mark.GetBegin(); it != mark.GetEnd(); ++it) msg += (msg.empty() ? "" : "; ") + it->GetCommentary();
  throw std::runtime_error(where + ": USD/Hydra reported errors: " + msg);
}

std::string coord(int v) { return v < 0 ? "n" + std::to_string(-v) : std::to_string(v); }

SdfPath block_path(const BlockKey& k) {
  return kClay.AppendChild(TfToken("b_" + coord(k.x) + "_" + coord(k.y) + "_" + coord(k.z)));
}

// up for a look-at: world Y unless looking (nearly) along it
GfVec3d up_for(const GfVec3d& dir) { return std::abs(GfDot(dir.GetNormalized(), GfVec3d(0, 1, 0))) > 0.99 ? GfVec3d(0, 0, 1) : GfVec3d(0, 1, 0); }

// object-to-world for something at `from` whose -Z looks at `to` (USD cameras and UsdLux panels face -Z)
GfMatrix4d look_at(const GfVec3d& from, const GfVec3d& to) {
  GfMatrix4d view;
  view.SetLookAt(from, to, up_for(to - from));
  return view.GetInverse();
}

// Tone: linear up to 0.6, then an exponential shoulder to 1 (slope 1 at the knee), so the key side's highlights roll
// off instead of clipping. Then sRGB.
float tone(float x) {
  constexpr float k = 0.6f;
  if (x <= k) return std::max(x, 0.0f);
  return k + (1 - k) * (1 - std::exp(-(x - k) / (1 - k)));
}
// `dither` in [-0.5, 0.5): a per-pixel offset of under one step, so the background's gradient doesn't band
uint8_t srgb8(float x, float dither) {
  x = std::clamp(tone(x), 0.0f, 1.0f);
  const float s = x <= 0.0031308f ? 12.92f * x : 1.055f * std::pow(x, 1 / 2.4f) - 0.055f;
  return uint8_t(std::clamp(std::lround(s * 255 + dither), 0L, 255L));
}

// the background at pixel (x, y): kBackgroundCentre in the middle, easing to kBackgroundEdge in the corners
float background(int x, int y, int w, int h) {
  const float u = (x + 0.5f) / w - 0.5f, v = (y + 0.5f) / h - 0.5f;
  const float r = std::min(1.0f, std::sqrt(u * u + v * v) / 0.7071f);  // 0 centre, 1 corner
  const float t = r * r * (3 - 2 * r);
  return kBackgroundCentre + (kBackgroundEdge - kBackgroundCentre) * t;
}

// a fixed per-pixel value in [-0.5, 0.5) (integer hash), so the same picture writes the same file
float dither_at(size_t i) {
  uint32_t x = uint32_t(i) * 0x9E3779B1u;
  x ^= x >> 15, x *= 0x85EBCA77u, x ^= x >> 13;
  return float(x >> 8) / float(1u << 24) - 0.5f;
}

// RGBA (premultiplied, top row first) over the background -> opaque 8-bit sRGB PNG. Written to a side file and
// renamed, so a failure leaves nothing at `path`.
void write_png(const std::vector<float>& rgba, int w, int h, const std::string& path) {
  std::vector<uint8_t> px(size_t(w) * h * 3);
  for (size_t i = 0, n = size_t(w) * h; i < n; ++i) {
    const float a = std::clamp(rgba[i * 4 + 3], 0.0f, 1.0f);
    const float bg = background(int(i % w), int(i / w), w, h), d = dither_at(i);
    for (int c = 0; c < 3; ++c) px[i * 3 + c] = srgb8(rgba[i * 4 + c] + (1 - a) * bg, d);
  }
  namespace fs = std::filesystem;
  const fs::path file(path), partial = fs::path(path + ".partial.png");
  if (file.has_parent_path()) fs::create_directories(file.parent_path());
  auto out = OIIO::ImageOutput::create(partial.string());
  if (!out) throw std::runtime_error("png: OpenImageIO has no writer for " + partial.string() + ": " + OIIO::geterror());
  const OIIO::ImageSpec spec(w, h, 3, OIIO::TypeDesc::UINT8);
  const bool ok = out->open(partial.string(), spec) && out->write_image(OIIO::TypeDesc::UINT8, px.data()) && out->close();
  if (!ok) {
    const std::string err = out->geterror();
    out.reset();
    std::error_code ec;
    fs::remove(partial, ec);
    throw std::runtime_error("png: could not write " + partial.string() + ": " + err);
  }
  out.reset();
  std::error_code ec;
  fs::rename(partial, file, ec);
  if (ec) throw std::runtime_error("png: could not rename " + partial.string() + " to " + path + ": " + ec.message());
}

// A Hydra engine for `plugin` with `excluded` left out of its scene, drawing into its colour output and compositing
// that into the bound framebuffer (as hydra.cpp's engine()).
std::unique_ptr<UsdImagingGLEngine> make_engine(const TfToken& plugin, const SdfPath& excluded) {
  const auto plugins = UsdImagingGLEngine::GetRendererPlugins();
  if (std::find(plugins.begin(), plugins.end(), plugin) == plugins.end())
    throw std::runtime_error("view: Hydra renderer " + plugin.GetString() +
                             " is not installed (check PATH and PXR_PLUGINPATH_NAME)");
  UsdImagingGLEngine::Parameters prm;
  prm.rendererPluginId = plugin;
  prm.excludedPaths = {excluded};
  auto e = std::make_unique<UsdImagingGLEngine>(prm);
  if (e->GetCurrentRendererId() != plugin) throw std::runtime_error("view: Hydra could not start " + plugin.GetString());
  if (!e->SetRendererAov(HdAovTokens->color)) throw std::runtime_error("view: " + plugin.GetString() + " has no colour output");
  e->SetEnablePresentation(true);
  return e;
}

UsdImagingGLRenderParams render_params() {
  UsdImagingGLRenderParams p;
  p.frame = UsdTimeCode::Default();
  p.colorCorrectionMode = TfToken("disabled");  // scene-linear out; write_png makes sRGB
  p.clearColor = GfVec4f(0, 0, 0, 0);
  return p;
}
}  // namespace

struct View::Impl {
  // declaration order = reverse destruction order: engines go before the framebuffer and the GL context
  r3d::GlContext gl;
  r3d::Framebuffer fb;
  int w, h;
  UsdStageRefPtr stage;
  SdfLayerHandle layer;
  SdfPrimSpecHandle claySpec;
  std::map<BlockKey, SdfPath> blocks;
  std::optional<SdfChangeBlock> changes;
  std::vector<UsdGeomXformable> lights;  // in kLights order
  GlfSimpleLightVector stormLights;      // used when !kStormSceneLights
  Camera camera;                         // the last set_camera
  std::unique_ptr<UsdImagingGLEngine> storm;
  // Final: one Cycles engine for the View's lifetime (made by the first render_cycles) and its own framebuffer (the
  // Storm frame stays for save_storm_png). finalSig: what the last finished Final showed (final_signature).
  std::unique_ptr<r3d::Framebuffer> cyclesFb;
  std::unique_ptr<UsdImagingGLEngine> cycles;
  uint64_t finalSig = 0;

  Impl(int width, int height) : fb(width, height), w(width), h(height) {}
  // the engines go first, while the framebuffers and the GL context they draw with are still there
  ~Impl() {
    cycles.reset();
    cyclesFb.reset();
    storm.reset();
  }

  void place(const Camera& c) {
    const GfVec3d eye(c.eye[0], c.eye[1], c.eye[2]), target(c.target[0], c.target[1], c.target[2]);
    GfVec3d back = eye - target;  // toward the camera
    if (back.GetLength() < 1e-9) back = GfVec3d(0, 0, 1);
    back.Normalize();
    GfVec3d right = GfCross(up_for(back), back).GetNormalized();
    const GfVec3d up = GfCross(back, right);
    stormLights.clear();
    for (size_t i = 0; i < std::size(kLights); ++i) {
      const LightDef& d = kLights[i];
      const GfVec3d dir = (right * d.dir[0] + up * d.dir[1] + back * d.dir[2]).GetNormalized();
      const GfVec3d pos = target + dir * d.dist;
      lights[i].MakeMatrixXform().Set(look_at(pos, target));
      GlfSimpleLight l;  // a point light whose 1/d² fall-off gives the same irradiance as the panel / bulb
      l.SetID(SdfPath(std::string("/Lights/") + d.name));
      l.SetPosition(GfVec4f(float(pos[0]), float(pos[1]), float(pos[2]), 1.0f));
      const GfVec3f e = d.color * (d.radiance * light_area(d));
      l.SetDiffuse(GfVec4f(e[0], e[1], e[2], 1));
      l.SetSpecular(GfVec4f(e[0], e[1], e[2], 1));
      l.SetAmbient(GfVec4f(0));
      l.SetAttenuation(GfVec3f(0, 0, 1));
      stormLights.push_back(l);
    }
  }
};

View::View(int width, int height) : p_(std::make_unique<Impl>(width, height)) {
  std::fprintf(stderr, "GL renderer: %s\n", p_->gl.renderer().c_str());  // which chip draws Storm
  TfErrorMark mark;
  auto& s = p_->stage;
  s = UsdStage::CreateInMemory();
  p_->layer = s->GetRootLayer();
  UsdGeomSetStageMetersPerUnit(s, 1.0);
  UsdGeomSetStageUpAxis(s, UsdGeomTokens->y);

  const UsdPrim clay = UsdGeomXform::Define(s, kClay).GetPrim();
  p_->claySpec = p_->layer->GetPrimAtPath(kClay);

  const UsdShadeMaterial mat = UsdShadeMaterial::Define(s, kLook);
  UsdShadeShader sh = UsdShadeShader::Define(s, kLook.AppendChild(TfToken("Surface")));
  sh.CreateIdAttr(VtValue(TfToken("UsdPreviewSurface")));
  sh.CreateInput(TfToken("diffuseColor"), SdfValueTypeNames->Color3f).Set(kClayColor);
  sh.CreateInput(TfToken("roughness"), SdfValueTypeNames->Float).Set(kClayRoughness);
  sh.CreateInput(TfToken("metallic"), SdfValueTypeNames->Float).Set(0.0f);
  mat.CreateSurfaceOutput().ConnectToSource(sh.CreateOutput(TfToken("surface"), SdfValueTypeNames->Token));
  UsdShadeMaterialBindingAPI::Apply(clay).Bind(mat);

  for (const LightDef& d : kLights) {
    const SdfPath path(std::string("/Lights/") + d.name);
    UsdLuxBoundableLightBase light;
    if (d.rect) {
      auto r = UsdLuxRectLight::Define(s, path);
      r.CreateWidthAttr().Set(d.w);
      r.CreateHeightAttr().Set(d.h);
      light = r;
    } else {
      auto b = UsdLuxSphereLight::Define(s, path);
      b.CreateRadiusAttr().Set(d.w);
      light = b;
    }
    light.CreateIntensityAttr().Set(d.radiance);
    light.CreateColorAttr().Set(d.color);
    light.CreateNormalizeAttr().Set(false);  // UsdLux radiance; Cycles' normalize on panels is wrong (cycles_lights.h)
    p_->lights.push_back(light);
  }
  // flat dome (no picture: Cycles' dome strength bug only bites a textured, sampled dome; cycles_lights.h)
  UsdLuxDomeLight dome = UsdLuxDomeLight::Define(s, SdfPath("/Lights/Dome"));
  dome.CreateIntensityAttr().Set(kDomeIntensity);

  UsdGeomCamera::Define(s, kCam);
  throw_usd_errors(mark, "view: building the stage");

  set_camera(Camera{});
  p_->storm = make_engine(kStorm, kFinal);
  throw_usd_errors(mark, "view: starting Storm");
}

View::~View() = default;

void View::set_camera(const Camera& c) {
  TfErrorMark mark;
  UsdGeomCamera cam(p_->stage->GetPrimAtPath(kCam));
  // apertures in tenths of a unit (USD's convention); only their ratio to the focal length matters
  const float vAp = 24.0f, hAp = vAp * float(p_->w) / float(p_->h);
  const float focal = vAp / 2 / std::tan(c.fovYDeg * kPi / 360.0f);
  cam.CreateVerticalApertureAttr().Set(vAp);
  cam.CreateHorizontalApertureAttr().Set(hAp);
  cam.CreateFocalLengthAttr().Set(focal);
  cam.CreateClippingRangeAttr().Set(GfVec2f(0.01f, 100.0f));
  cam.MakeMatrixXform().Set(look_at(GfVec3d(c.eye[0], c.eye[1], c.eye[2]), GfVec3d(c.target[0], c.target[1], c.target[2])));
  p_->place(c);
  p_->camera = c;
  throw_usd_errors(mark, "view: set_camera");
}

void View::begin_changes() {
  if (!p_->changes) p_->changes.emplace();
}

void View::end_changes() { p_->changes.reset(); }

size_t View::block_count() const { return p_->blocks.size(); }

void View::set_block(const BlockKey& key, const BlockMesh& m) {
  TfErrorMark mark;
  const SdfLayerHandle& layer = p_->layer;
  auto found = p_->blocks.find(key);
  if (m.empty()) {
    if (found == p_->blocks.end()) return;
    if (SdfPrimSpecHandle spec = layer->GetPrimAtPath(found->second)) p_->claySpec->RemoveNameChild(spec);
    p_->blocks.erase(found);
    throw_usd_errors(mark, "view: removing a block");
    return;
  }
  const SdfPath path = found != p_->blocks.end() ? found->second : block_path(key);
  const auto attr = [&](const char* name) { return path.AppendProperty(TfToken(name)); };
  if (found == p_->blocks.end()) {  // new prim: its specs, uniform values once
    SdfPrimSpecHandle prim = SdfPrimSpec::New(p_->claySpec, path.GetName(), SdfSpecifierDef, "Mesh");
    if (!prim) throw std::runtime_error("view: could not create " + path.GetString());
    SdfAttributeSpec::New(prim, "points", SdfValueTypeNames->Point3fArray);
    SdfAttributeSpecHandle normals = SdfAttributeSpec::New(prim, "normals", SdfValueTypeNames->Normal3fArray);
    normals->SetInfo(UsdGeomTokens->interpolation, VtValue(UsdGeomTokens->vertex));
    SdfAttributeSpec::New(prim, "faceVertexCounts", SdfValueTypeNames->IntArray);
    SdfAttributeSpec::New(prim, "faceVertexIndices", SdfValueTypeNames->IntArray);
    SdfAttributeSpec::New(prim, "extent", SdfValueTypeNames->Float3Array);
    SdfAttributeSpec::New(prim, "subdivisionScheme", SdfValueTypeNames->Token, SdfVariabilityUniform)
        ->SetDefaultValue(VtValue(UsdGeomTokens->none));
    SdfAttributeSpec::New(prim, "doubleSided", SdfValueTypeNames->Bool, SdfVariabilityUniform)
        ->SetDefaultValue(VtValue(false));
    p_->blocks.emplace(key, path);
  }

  const size_t nv = m.points.size() / 3, nt = m.triangles();
  VtVec3fArray pts(nv), nrm(nv);
  std::memcpy(pts.data(), m.points.data(), nv * sizeof(GfVec3f));
  std::memcpy(nrm.data(), m.normals.data(), std::min(m.normals.size() / 3, nv) * sizeof(GfVec3f));
  VtIntArray idx(nt * 3), counts(nt, 3);
  std::memcpy(idx.data(), m.indices.data(), nt * 3 * sizeof(int32_t));
  GfVec3f lo(FLT_MAX), hi(-FLT_MAX);
  for (const GfVec3f& q : pts)
    for (int c = 0; c < 3; ++c) lo[c] = std::min(lo[c], q[c]), hi[c] = std::max(hi[c], q[c]);
  VtVec3fArray extent{lo, hi};

  const TfToken& dflt = SdfFieldKeys->Default;
  layer->SetField(attr("points"), dflt, VtValue::Take(pts));
  layer->SetField(attr("normals"), dflt, VtValue::Take(nrm));
  layer->SetField(attr("faceVertexCounts"), dflt, VtValue::Take(counts));
  layer->SetField(attr("faceVertexIndices"), dflt, VtValue::Take(idx));
  layer->SetField(attr("extent"), dflt, VtValue::Take(extent));
  throw_usd_errors(mark, "view: writing " + path.GetString());
}

double View::render_storm() {
  if (p_->changes) throw std::runtime_error("view: render_storm inside begin_changes / end_changes");
  TfErrorMark mark;
  auto& e = *p_->storm;
  const auto t0 = Clock::now();
  e.SetLightingState(kStormSceneLights ? GlfSimpleLightVector{} : p_->stormLights, GlfSimpleMaterial(),
                     GfVec4f(0, 0, 0, 1));
  e.SetCameraPath(kCam);
  e.SetRenderBufferSize(GfVec2i(p_->w, p_->h));
  e.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), p_->w, p_->h)));
  e.SetOverrideWindowPolicy(CameraUtilMatchVertically);
  UsdImagingGLRenderParams params = render_params();
  params.enableSceneLights = kStormSceneLights;
  params.cullStyle = UsdImagingGLCullStyle::CULL_STYLE_BACK_UNLESS_DOUBLE_SIDED;
  // normally one pass; Storm may want a second while it loads things (textures, shaders on first use)
  for (bool first = true;; first = false) {
    p_->fb.bind_and_clear();
    e.Render(p_->stage->GetPseudoRoot(), params);
    p_->gl.finish();
    throw_usd_errors(mark, "view: Storm frame");
    if (e.IsConverged()) break;
    if (std::chrono::duration<double>(Clock::now() - t0).count() > 10)
      throw std::runtime_error("view: Storm did not finish a frame within 10 s");
    if (!first) std::this_thread::sleep_for(std::chrono::milliseconds(1));
  }
  return std::chrono::duration<double, std::milli>(Clock::now() - t0).count();
}

void View::save_storm_png(const std::string& path) { write_png(p_->fb.read_rgba(), p_->w, p_->h, path); }

namespace {
// What a Final shows: the mesh's bytes, the camera and the samples (64-bit FNV-1a over 8-byte words). Equal for two
// Finals in a row means Cycles may rightly have nothing new to render.
uint64_t final_signature(const BlockMesh& m, const Camera& c, int samples) {
  uint64_t h = 1469598103934665603ull;
  const auto eat = [&](const void* data, size_t bytes) {
    const auto* p = static_cast<const unsigned char*>(data);
    size_t i = 0;
    for (; i + 8 <= bytes; i += 8) {
      uint64_t v;
      std::memcpy(&v, p + i, 8);
      h = (h ^ v) * 1099511628211ull;
    }
    for (; i < bytes; ++i) h = (h ^ p[i]) * 1099511628211ull;
    h = (h ^ bytes) * 1099511628211ull;
  };
  eat(m.points.data(), m.points.size() * sizeof(m.points[0]));
  eat(m.normals.data(), m.normals.size() * sizeof(m.normals[0]));
  eat(m.indices.data(), m.indices.size() * sizeof(m.indices[0]));
  eat(&c, sizeof c);
  eat(&samples, sizeof samples);
  return h;
}
}  // namespace

double View::render_cycles(const BlockMesh& whole, int samples, const std::string& path) {
  if (p_->changes) throw std::runtime_error("view: render_cycles inside begin_changes / end_changes");
  if (whole.empty()) throw std::runtime_error("view: render_cycles got an empty mesh");
  const auto t0 = Clock::now();
  auto& s = p_->stage;
  TfErrorMark mark;
  const uint64_t sig = final_signature(whole, p_->camera, samples);
  // put the stage back however the render ends: /Final hidden (it stays, with its arrays, for the next Final), /Clay shown
  struct Restore {
    UsdStageRefPtr s;
    ~Restore() {
      if (UsdGeomImageable f{s->GetPrimAtPath(kFinal)}) f.MakeInvisible();
      UsdGeomImageable(s->GetPrimAtPath(kClay)).MakeVisible();
    }
  } restore{s};

  // /Final: made once, then its arrays replaced in place (the engine sees points / topology change and starts over)
  const bool fresh = !s->GetPrimAtPath(kFinal);
  UsdGeomMesh mesh = UsdGeomMesh::Define(s, kFinal);
  {
    const size_t nv = whole.points.size() / 3, nt = whole.triangles();
    VtVec3fArray pts(nv), nrm(nv);
    std::memcpy(pts.data(), whole.points.data(), nv * sizeof(GfVec3f));
    std::memcpy(nrm.data(), whole.normals.data(), std::min(whole.normals.size() / 3, nv) * sizeof(GfVec3f));
    VtIntArray idx(nt * 3), counts(nt, 3);
    std::memcpy(idx.data(), whole.indices.data(), nt * 3 * sizeof(int32_t));
    VtVec3fArray extent(2);
    UsdGeomPointBased::ComputeExtent(pts, &extent);
    mesh.CreatePointsAttr().Set(pts);
    mesh.CreateNormalsAttr().Set(nrm);
    mesh.CreateFaceVertexCountsAttr().Set(counts);
    mesh.CreateFaceVertexIndicesAttr().Set(idx);
    mesh.CreateExtentAttr().Set(extent);
    if (fresh) {
      mesh.SetNormalsInterpolation(UsdGeomTokens->vertex);
      mesh.CreateSubdivisionSchemeAttr().Set(UsdGeomTokens->none);
      mesh.CreateDoubleSidedAttr().Set(false);
    }
  }
  if (fresh) UsdShadeMaterialBindingAPI::Apply(mesh.GetPrim()).Bind(UsdShadeMaterial(s->GetPrimAtPath(kLook)));
  mesh.MakeVisible();
  UsdGeomImageable(s->GetPrimAtPath(kClay)).MakeInvisible();
  throw_usd_errors(mark, "view: Final mesh");

  if (!p_->cycles) {
    p_->cyclesFb = std::make_unique<r3d::Framebuffer>(p_->w, p_->h);
    p_->cycles = make_engine(kCycles, kClay);
    p_->cycles->SetRendererSetting(HdRenderSettingsTokens->domeLightCameraVisibility, VtValue(false));
    throw_usd_errors(mark, "view: starting Cycles");
  }
  auto& e = *p_->cycles;
  // Cycles' plug-in starts over on every samples / integrator setting, even an equal one: set only what differs
  // (hydra.cpp cycles_settings)
  const auto set = [&](const char* key, const VtValue& v) {
    if (e.GetRendererSetting(TfToken(key)) != v) e.SetRendererSetting(TfToken(key), v);
  };
  set("stageMetersPerUnit", VtValue(1.0));  // else the plug-in takes centimetres (hydra.cpp cycles_settings)
  set("cycles:samples", VtValue(samples));
  set("cycles:integrator:use_denoise", VtValue(true));
  set("cycles:integrator:denoise_start_sample", VtValue(samples));  // one clean-up, at the last sample
  e.SetCameraPath(kCam);
  e.SetRenderBufferSize(GfVec2i(p_->w, p_->h));
  e.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), p_->w, p_->h)));
  e.SetOverrideWindowPolicy(CameraUtilMatchVertically);
  const UsdImagingGLRenderParams params = render_params();

  // A converged answer counts only once Cycles has been seen working on this Final (a not-converged pass): right
  // after a change, IsConverged could still describe the previous picture. The exception is a Final identical to the
  // last finished one (same mesh, camera, samples), where Cycles may have nothing to redo. A change Cycles never
  // picks up fails loudly instead of writing the old picture.
  const bool same = p_->finalSig == sig;
  p_->finalSig = 0;  // until this one finishes
  bool working = false;
  constexpr double kTimeoutS = 600, kStartS = 20;
  for (bool first = true;; first = false) {
    p_->cyclesFb->bind_and_clear();
    e.Render(s->GetPseudoRoot(), params);
    p_->gl.finish();
    throw_usd_errors(mark, "view: Cycles Final");
    const bool converged = e.IsConverged();
    if (!converged) working = true;
    if (converged && (working || same)) break;
    const double waited = std::chrono::duration<double>(Clock::now() - t0).count();
    if (!working && waited > kStartS)
      throw std::runtime_error("view: Cycles still reports the previous Final after " + std::to_string(int(kStartS)) +
                               " s (the change to the mesh / camera was not picked up); no file written");
    if (waited > kTimeoutS)
      throw std::runtime_error("view: Cycles did not finish the Final picture (" + std::to_string(samples) +
                               " samples) within 600 s; no file written");
    if (!first) std::this_thread::sleep_for(std::chrono::milliseconds(30));
  }
  write_png(p_->cyclesFb->read_rgba(), p_->w, p_->h, path);
  p_->finalSig = sig;
  return std::chrono::duration<double>(Clock::now() - t0).count();
}

void View::export_usda(const std::string& path) {
  if (!p_->stage->GetRootLayer()->Export(path)) throw std::runtime_error("view: could not export " + path);
}

}  // namespace clay
