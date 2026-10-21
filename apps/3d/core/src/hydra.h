// Hydra: one UsdImagingGLEngine per renderer (made on first use, kept warm), all drawing the one stage
// on the one hidden GL context. The only place pictures are made, for look tools and export alike.
#pragma once
#include <pxr/base/gf/frustum.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usdImaging/usdImagingGL/engine.h>

#include <map>
#include <memory>
#include <string>
#include <vector>

#include "gl_context.h"
#include "gpu_mem.h"
#include "image_out.h"

namespace r3d {

// what the live viewport adds over a render (viewport only; renders never see these)
struct ViewLook {
  double studio = 1.0;      // studio environment strength, 0 = off
  bool sceneLights = true;  // the scene's own lights
  PXR_NS::SdfPathVector selected;  // drawn with an outline
};

struct DrawSettings {
  int samples = 128;      // Cycles
  bool denoise = true;    // Cycles
  double timeoutS = 600;  // a progressive renderer must finish within this
};

class Hydra {
 public:
  explicit Hydra(PXR_NS::UsdStageRefPtr stage);
  ~Hydra();
  // "storm" | "cycles" | "stylized" -> Hydra plug-in id; unknown names are an error listing the accepted ones
  static PXR_NS::TfToken plugin_for(const std::string& name);
  static std::vector<std::string> names();
  std::vector<std::string> available() const;  // the names whose plug-in this machine has
  std::string gl_renderer() const { return gl_.renderer(); }

  Picture draw(const std::string& renderer, const PXR_NS::SdfPath& camera, int frame, int width, int height,
               const DrawSettings& s, GpuMemWatch& mem);
  // one live viewport picture through `frustum` (a scene camera's or the free camera's)
  Picture view(const std::string& renderer, const PXR_NS::GfFrustum& frustum, int frame, int width, int height,
               const ViewLook& look, GpuMemWatch& mem);
  // the prim under pixel (x, y) of a width x height picture through `frustum`; empty path when nothing is there
  PXR_NS::SdfPath pick(const PXR_NS::GfFrustum& frustum, int frame, int width, int height, double x, double y,
                       PXR_NS::GfVec3d* point);

 private:
  class Engine;  // UsdImagingGLEngine plus showing or hiding the dome behind the scene
  Engine& engine(const std::string& renderer, bool viewport = false);
  Framebuffer& framebuffer(int width, int height);

  PXR_NS::UsdStageRefPtr stage_;
  GlContext gl_;  // before the engines: made first, destroyed last
  std::map<std::string, std::unique_ptr<Engine>> engines_;  // renders and the viewport keep separate engines
  std::unique_ptr<Framebuffer> fb_;
};

}  // namespace r3d
