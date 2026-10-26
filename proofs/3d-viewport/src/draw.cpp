// The render-thread side (draw.h): stage, clay, Storm drawing into the Qt Quick item's own colour texture.
#include "draw.h"

#include <epoxy/gl.h>

#include <pxr/base/gf/frustum.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/ray.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/tf/token.h>
#include <pxr/imaging/cameraUtil/framing.h>
#include <pxr/imaging/glf/simpleLight.h>
#include <pxr/imaging/glf/simpleMaterial.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/cone.h>
#include <pxr/usd/usdGeom/cube.h>
#include <pxr/usd/usdGeom/cylinder.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/metrics.h>
#include <pxr/usd/usdGeom/sphere.h>
#include <pxr/usd/usdGeom/xform.h>
#include <pxr/usdImaging/usdImagingGL/engine.h>
#include <tbb/parallel_for.h>

#include <chrono>
#include <cmath>
#include <cstdio>
#include <random>
#include <set>

#include "clay_stroke.h"
#include "clay_usd.h"
#include "clay_volume.h"
#include "head.h"

PXR_NAMESPACE_USING_DIRECTIVE
using namespace r3d::clay;

namespace pview {

double now_ms() {
  using namespace std::chrono;
  return duration<double, std::milli>(steady_clock::now().time_since_epoch()).count();
}

namespace {

GfFrustum frustum_of(const Cam& c, double aspect) {
  const GfVec3d target(c.target[0], c.target[1], c.target[2]);
  const GfVec3d eye = target + c.dist * GfVec3d(std::cos(c.pitch) * std::sin(c.yaw), std::sin(c.pitch),
                                                std::cos(c.pitch) * std::cos(c.yaw));
  GfMatrix4d view;
  view.SetLookAt(eye, target, GfVec3d(0, 1, 0));
  GfFrustum f;
  f.SetPositionAndRotationFromMatrix(view.GetInverse());
  f.SetPerspective(c.fovDeg, aspect, 0.01, 100.0);
  return f;
}

// 300 plain prims around the clay (the orbit scene): spheres, cubes, cylinders and cones on a widening spiral
void add_items(const UsdStageRefPtr& stage, int n) {
  std::mt19937 rng(7);
  std::uniform_real_distribution<float> u(0, 1);
  for (int i = 0; i < n; ++i) {
    const SdfPath path("/World/Items/item_" + std::to_string(i));
    const double a = i * 2.39996, r = 0.45 + 2.6 * std::sqrt((i + 0.5) / n);
    const double s = 0.04 + 0.08 * u(rng);
    UsdGeomGprim g;
    switch (i % 4) {
      case 0: g = UsdGeomSphere::Define(stage, path); UsdGeomSphere(g).CreateRadiusAttr(VtValue(s)); break;
      case 1: g = UsdGeomCube::Define(stage, path); UsdGeomCube(g).CreateSizeAttr(VtValue(2 * s)); break;
      case 2: g = UsdGeomCylinder::Define(stage, path); UsdGeomCylinder(g).CreateRadiusAttr(VtValue(s));
              UsdGeomCylinder(g).CreateHeightAttr(VtValue(3 * s)); break;
      default: g = UsdGeomCone::Define(stage, path); UsdGeomCone(g).CreateRadiusAttr(VtValue(s));
               UsdGeomCone(g).CreateHeightAttr(VtValue(3 * s)); break;
    }
    g.AddTranslateOp().Set(GfVec3d(r * std::cos(a), -0.15 + s * 1.5, r * std::sin(a)));
    g.CreateDisplayColorAttr(VtValue(VtVec3fArray{GfVec3f(0.25f + 0.7f * u(rng), 0.25f + 0.7f * u(rng),
                                                          0.25f + 0.7f * u(rng))}));
  }
}

void add_floor(const UsdStageRefPtr& stage) {
  auto m = UsdGeomMesh::Define(stage, SdfPath("/World/Floor"));
  const float y = -0.16f, e = 4.0f;
  m.CreatePointsAttr(VtValue(VtVec3fArray{{-e, y, -e}, {e, y, -e}, {e, y, e}, {-e, y, e}}));
  m.CreateFaceVertexCountsAttr(VtValue(VtIntArray{4}));
  m.CreateFaceVertexIndicesAttr(VtValue(VtIntArray{0, 3, 2, 1}));
  m.CreateDisplayColorAttr(VtValue(VtVec3fArray{GfVec3f(0.32f, 0.33f, 0.35f)}));
}

}  // namespace

struct Scene::Impl {
  Options o;
  UsdStageRefPtr stage;
  SdfPath clayPath{"/World/Clay"};
  std::unique_ptr<Volume> vol;
  std::unique_ptr<Blocks> blocks;
  std::set<BlockKey> have;
  std::unique_ptr<UsdImagingGLEngine> engine;
  // the live stroke
  std::unique_ptr<StrokeDabs> stroke;
  std::unique_ptr<Resampler> resample;
  Brush brush;
  // the framebuffer around the item's texture
  GLuint fbo = 0, depth = 0, tex = 0;
  int fw = 0, fh = 0;

  void publish(bool all, FrameTimes& t) {
    std::vector<BlockKey> keys;
    if (all) {
      vol->take_dirty();
      keys = vol->all_blocks();
    } else {
      const auto d = vol->take_dirty();
      keys.assign(d.begin(), d.end());
    }
    t.blocks += int(keys.size());
    if (keys.empty()) return;
    double t0 = now_ms();
    std::vector<BlockMesh> meshes(keys.size());
    tbb::parallel_for(size_t(0), keys.size(), [&](size_t i) { vol->mesh(keys[i], meshes[i]); });
    double t1 = now_ms();
    blocks->begin();
    for (size_t i = 0; i < keys.size(); ++i) blocks->set(clayPath, keys[i], meshes[i], have);
    blocks->end();
    t.mesh += t1 - t0;
    t.usd += now_ms() - t1;
  }

  void target(unsigned colorTex, int w, int h) {
    if (!fbo) glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    if (colorTex != tex) {
      glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, colorTex, 0);
      tex = colorTex;
    }
    if (w != fw || h != fh) {
      if (!depth) glGenRenderbuffers(1, &depth);
      glBindRenderbuffer(GL_RENDERBUFFER, depth);
      glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, w, h);
      glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, depth);
      fw = w;
      fh = h;
    }
  }
};

Scene::Scene(const Options& o) : p_(new Impl) {
  p_->o = o;
  p_->stage = UsdStage::CreateInMemory();
  UsdGeomSetStageUpAxis(p_->stage, UsdGeomTokens->y);
  UsdGeomXform::Define(p_->stage, SdfPath("/World"));
  UsdGeomXform::Define(p_->stage, p_->clayPath);
  add_floor(p_->stage);
  if (o.items > 0) add_items(p_->stage, o.items);

  if (o.head) {
    p_->vol = std::make_unique<Volume>(0.000625f);
    sculpt_head(*p_->vol);
  } else {
    p_->vol = std::make_unique<Volume>(o.detail);
    Step ball;
    ball.kind = Kind::Piece;
    ball.op = Op::Add;
    ball.radius = o.clayRadius;
    p_->vol->apply(ball);
  }
  p_->blocks = std::make_unique<Blocks>(p_->stage);
  FrameTimes t;
  p_->publish(true, t);

  p_->brush.op = Op::Add;
  p_->brush.radius = o.brushRadius;
  p_->brush.strength = o.strength;

  // Storm on Qt's context (current: we are inside the item renderer's render)
  std::fprintf(stderr, "GL: %s | %s | GLSL %s\n", (const char*)glGetString(GL_RENDERER),
               (const char*)glGetString(GL_VERSION), (const char*)glGetString(GL_SHADING_LANGUAGE_VERSION));
  p_->engine = std::make_unique<UsdImagingGLEngine>();
  p_->engine->SetRendererAov(HdAovTokens->color);
  p_->engine->SetEnablePresentation(true);
  GlfSimpleLight key;
  key.SetIsCameraSpaceLight(true);
  key.SetPosition(GfVec4f(0.5f, 0.8f, 1.0f, 0.0f));
  key.SetDiffuse(GfVec4f(0.95f, 0.93f, 0.9f, 1));
  key.SetSpecular(GfVec4f(0.15f, 0.15f, 0.15f, 1));
  GlfSimpleMaterial mat;
  mat.SetAmbient(GfVec4f(0.25f, 0.25f, 0.27f, 1));
  p_->engine->SetLightingState(GlfSimpleLightVector{key}, mat, GfVec4f(0.3f, 0.3f, 0.32f, 1));
}

Scene::~Scene() {
  p_->engine.reset();  // on the render thread, context current (the renderer's destructor)
  if (p_->fbo) glDeleteFramebuffers(1, &p_->fbo);
  if (p_->depth) glDeleteRenderbuffers(1, &p_->depth);
}

void Scene::apply(const std::vector<Input>& in, const Cam& cam, int w, int h, FrameTimes& t) {
  if (in.empty()) return;
  const double t0 = now_ms();
  const GfFrustum f = frustum_of(cam, double(w) / h);
  const double pxPerM = h / (2 * cam.dist * std::tan(cam.fovDeg * M_PI / 360));
  auto& P = *p_;
  bool changed = false;
  for (const Input& e : in) {
    ++t.inputs;
    if (e.kind == Input::Orbit) continue;
    if (e.kind == Input::Begin) {
      P.vol->begin_stroke();
      P.stroke = std::make_unique<StrokeDabs>(*P.vol, P.brush);
      P.resample = std::make_unique<Resampler>(float(P.brush.spacing * P.brush.radius * pxPerM));
    }
    if (!P.stroke) continue;
    if (e.kind == Input::End) {
      P.vol->end_stroke(P.stroke->dabs());
      P.stroke.reset();
      changed = true;
      continue;
    }
    std::vector<V3> samples;
    P.resample->push(V3{e.x, e.y, 0}, samples);
    for (const V3& s : samples) {
      const GfRay ray = f.ComputeRay(GfVec2d(2.0 * s.x / w - 1, 1 - 2.0 * s.y / h));
      const GfVec3d o = ray.GetStartPoint(), d = ray.GetDirection().GetNormalized();
      if (P.stroke->add(V3{float(o[0]), float(o[1]), float(o[2])}, V3{float(d[0]), float(d[1]), float(d[2])}, 100.f)) {
        ++t.dabs;
        changed = true;
      }
    }
  }
  t.dab += now_ms() - t0;
  if (changed) P.publish(false, t);
}

void Scene::draw(unsigned colorTex, int w, int h, const Cam& cam, FrameTimes& t) {
  const double t0 = now_ms();
  GLint prev = 0;
  glGetIntegerv(GL_FRAMEBUFFER_BINDING, &prev);
  p_->target(colorTex, w, h);
  glViewport(0, 0, w, h);
  // Qt Quick's own state, left as its last draw set it: Storm assumes GL's defaults
  glDisable(GL_SCISSOR_TEST);
  glDisable(GL_STENCIL_TEST);
  glDisable(GL_BLEND);
  glDisable(GL_CULL_FACE);
  glDisable(GL_FRAMEBUFFER_SRGB);
  glDisable(GL_PRIMITIVE_RESTART);
  glEnable(GL_DEPTH_TEST);
  glDepthFunc(GL_LESS);
  glDepthMask(GL_TRUE);
  glDepthRange(0, 1);
  glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
  glFrontFace(GL_CCW);
  glBindVertexArray(0);
  glUseProgram(0);
  glBindBuffer(GL_ARRAY_BUFFER, 0);
  glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
  glActiveTexture(GL_TEXTURE0);
  glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
  glClearColor(0.11f, 0.115f, 0.125f, 1);
  glClearDepth(1);
  glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT);
  const GfFrustum f = frustum_of(cam, double(w) / h);
  auto& e = *p_->engine;
  e.SetCameraState(f.ComputeViewMatrix(), f.ComputeProjectionMatrix());
  e.SetRenderBufferSize(GfVec2i(w, h));
  e.SetFraming(CameraUtilFraming(GfRect2i(GfVec2i(0, 0), w, h)));
  UsdImagingGLRenderParams params;
  params.colorCorrectionMode = TfToken("sRGB");
  params.clearColor = GfVec4f(0.11f, 0.115f, 0.125f, 1);
  params.enableLighting = true;
  // the presentation step composites Storm's colour into the framebuffer bound now (the item's texture)
  e.Render(p_->stage->GetPseudoRoot(), params);
  if (p_->o.finish) glFinish();
  glBindFramebuffer(GL_FRAMEBUFFER, GLuint(prev));
  t.storm += now_ms() - t0;
}

std::vector<unsigned char> Scene::read(int w, int h) {
  std::vector<unsigned char> px(size_t(w) * h * 4), out(px.size());
  GLint prev = 0;
  glGetIntegerv(GL_FRAMEBUFFER_BINDING, &prev);
  glBindFramebuffer(GL_FRAMEBUFFER, p_->fbo);
  glPixelStorei(GL_PACK_ALIGNMENT, 1);
  glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, px.data());
  glBindFramebuffer(GL_FRAMEBUFFER, GLuint(prev));
  for (int y = 0; y < h; ++y)
    std::copy_n(px.data() + size_t(h - 1 - y) * w * 4, size_t(w) * 4, out.data() + size_t(y) * w * 4);
  return out;
}

std::string Scene::gl_renderer() const {
  const auto* s = reinterpret_cast<const char*>(glGetString(GL_RENDERER));
  return s ? s : "?";
}

int Scene::clay_blocks() const { return int(p_->have.size()); }

}  // namespace pview

// ---- probe: the core's own way of making a GL context (hidden window, legacy context, then 4.6 compatibility) ----
#include <epoxy/wgl.h>
namespace pview {
std::string probe_raw_wgl() {
  WNDCLASSW wc{};
  wc.lpfnWndProc = DefWindowProcW;
  wc.hInstance = GetModuleHandleW(nullptr);
  wc.lpszClassName = L"pview_probe";
  RegisterClassW(&wc);
  HWND w = CreateWindowExW(0, wc.lpszClassName, L"p", WS_OVERLAPPEDWINDOW, 0, 0, 64, 64, nullptr, nullptr,
                           wc.hInstance, nullptr);
  HDC dc = GetDC(w);
  PIXELFORMATDESCRIPTOR pfd{};
  pfd.nSize = sizeof(pfd);
  pfd.nVersion = 1;
  pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER;
  pfd.iPixelType = PFD_TYPE_RGBA;
  pfd.cColorBits = 32;
  pfd.cDepthBits = 24;
  pfd.cStencilBits = 8;
  int pf = ChoosePixelFormat(dc, &pfd);
  SetPixelFormat(dc, pf, &pfd);
  HGLRC legacy = wglCreateContext(dc);
  wglMakeCurrent(dc, legacy);
  std::string r = std::string("legacy ") + (const char*)glGetString(GL_VERSION);
  const int attrs[] = {WGL_CONTEXT_MAJOR_VERSION_ARB, 4, WGL_CONTEXT_MINOR_VERSION_ARB, 6,
                       WGL_CONTEXT_PROFILE_MASK_ARB, WGL_CONTEXT_COMPATIBILITY_PROFILE_BIT_ARB, 0};
  HGLRC rc = wglCreateContextAttribsARB(dc, nullptr, attrs);
  wglMakeCurrent(dc, rc);
  r += std::string(" | 4.6 ask: ") + (rc ? (const char*)glGetString(GL_VERSION) : "failed");
  wglMakeCurrent(nullptr, nullptr);
  return r;
}
}  // namespace pview
