// Hydra: one UsdImagingGLEngine per renderer (made on first use, kept warm), all drawing the one stage
// on the one hidden GL context. The only place pictures are made, for look tools and export alike.
#pragma once
#include <pxr/base/gf/frustum.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usdImaging/usdImagingGL/engine.h>

#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

#include "aovs.h"
#include "ghosts.h"
#include "gl_context.h"
#include "gpu_mem.h"
#include "image_out.h"

namespace r3d {

// what the live viewport adds over a render (viewport only; renders never see these)
struct ViewLook {
  double studio = 1.0;      // studio environment strength, 0 = off
  bool sceneLights = true;  // the scene's own lights
  PXR_NS::SdfPathVector selected;  // drawn with an outline
  PXR_NS::SdfPathVector hovered;   // drawn with the thin hover outline (3d-v4: the clay under the pointer)
  std::vector<Ghost> ghosts;       // onion skin: items at other frames, tinted and see-through (ghosts.h)
};

// the sun Storm took out of the scene's dome and drew as a light with a shadow (dome_sun.h)
struct SunSeen {
  double toward[3] = {0, 0, 0};  // world direction towards it
  double share = 0;              // its part of the dome's light
  double angleDeg = 0;           // its apparent size
};

// how far the viewport's Final look (progressive Cycles) has got
struct FinalPass {
  double fraction = 0;    // 0..1 of the samples
  bool converged = false; // all samples done (and the noise clean-up, when on)
  double seconds = 0;     // Cycles' own render time since it last started over
  double cyclesMb = 0;    // Cycles' own memory use (device), MB
  std::string status;     // Cycles' status line ("Sample 12/128", or its error)
};

// one live viewport picture, left on the graphics card for view_post.h (valid until the next draw)
struct ViewDrawn {
  unsigned color = 0, depth = 0;  // scene-linear RGBA32F and Storm's depth, GL rows bottom up
  unsigned mask = 0;              // the selected items alone (alpha > 0.5 where they are); 0 = nothing selected
  unsigned hoverMask = 0;         // the hovered items alone, the same way; 0 = nothing hovered
  std::vector<unsigned> ghosts;   // one picture per ViewLook ghost: its items alone, lit, at its frame
  bool sceneDome = false;         // the scene's own dome lit it (the studio light was not used)
  std::optional<SunSeen> sun;     // Storm drew the dome's sun as a light
  std::optional<FinalPass> final; // the Final look's progress (Cycles only)
  // where the time went: the lights set up, Storm's draw (GPU work finished), of that the wait for the GPU
  double lightMs = 0, renderMs = 0, finishMs = 0;
};

struct DrawSettings {
  int samples = 128;      // Cycles
  bool denoise = true;    // Cycles
  double timeoutS = 600;  // a progressive renderer must finish within this
  std::vector<std::string> aovs;  // Cycles: the extra outputs to read back (passes.h aovs_for), into draw()'s `aovs`
  bool castShadows = true;        // Cycles: off, no light casts a shadow (the Shadow pass's second render)
};

class Hydra {
 public:
  explicit Hydra(PXR_NS::UsdStageRefPtr stage);
  Hydra(PXR_NS::UsdStageRefPtr stage, GlContext::Borrow);  // on the context current now (the window's view)
  ~Hydra();
  // "storm" | "cycles" | "stylized" -> Hydra plug-in id; unknown names are an error listing the accepted ones
  static PXR_NS::TfToken plugin_for(const std::string& name);
  static std::vector<std::string> names();
  std::vector<std::string> available() const;  // the names whose plug-in this machine has
  std::string gl_renderer() const { return gl_.renderer(); }

  // one render through a scene camera; with `s.aovs` (Cycles only) their outputs are read into `aovs`
  Picture draw(const std::string& renderer, const PXR_NS::SdfPath& camera, int frame, int width, int height,
               const DrawSettings& s, GpuMemWatch& mem, Aovs* aovs = nullptr);
  // one live viewport picture through `frustum` (a scene camera's or the free camera's)
  ViewDrawn view(const std::string& renderer, const PXR_NS::GfFrustum& frustum, int frame, int width, int height,
                 const ViewLook& look, GpuMemWatch& mem);
  // the viewport's Final look: one step of progressive Cycles, with the render's settings and, for a scene `camera`,
  // the render's own camera path (so it matches the Render button); empty `camera` = the free camera's `frustum`.
  // Returns at once with the picture as far as it has got; the same request again continues, any change starts over.
  ViewDrawn view_final(const PXR_NS::SdfPath& camera, const PXR_NS::GfFrustum& frustum, int frame, int width,
                       int height, const DrawSettings& s, GpuMemWatch& mem);
  // the prim under pixel (x, y) of a width x height picture through `frustum`; empty path when nothing is there.
  // `point` is where the surface was hit and `normal` its direction there (world space, unit length, turned to face
  // the camera, so a shape placed along it sits on the side that was clicked)
  PXR_NS::SdfPath pick(const PXR_NS::GfFrustum& frustum, int frame, int width, int height, double x, double y,
                       PXR_NS::GfVec3d* point, PXR_NS::GfVec3d* normal);

 private:
  class Engine;  // UsdImagingGLEngine plus showing or hiding the dome behind the scene
  Engine& engine(const std::string& renderer, bool viewport = false);
  Engine& mask_engine();  // the selection mask's own Storm engine (hydra.cpp)
  std::unique_ptr<Engine> make_engine(const std::string& renderer);
  Framebuffer& framebuffer(int width, int height);
  Framebuffer& mask_framebuffer(int width, int height);

  PXR_NS::UsdStageRefPtr stage_;
  GlContext gl_;  // before the engines: made first, destroyed last
  std::map<std::string, std::unique_ptr<Engine>> engines_;  // renders and the viewport keep separate engines
  std::unique_ptr<Framebuffer> fb_, mask_fb_, hover_fb_;  // hover_fb_: the hover outline's mask (3d-v4)
  std::vector<std::unique_ptr<Framebuffer>> ghost_fbs_;  // one per onion-skin ghost
};

}  // namespace r3d
