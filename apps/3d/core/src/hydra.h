// Hydra: one UsdImagingGLEngine per renderer (made on first use, kept warm), all drawing the one stage
// on the one hidden GL context. The only place pictures are made, for look tools and export alike.
#pragma once
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
  // the prim under pixel (x, y) of a width x height picture; empty path when nothing is there
  PXR_NS::SdfPath pick(const PXR_NS::SdfPath& camera, int frame, int width, int height, double x, double y,
                       PXR_NS::GfVec3d* point);

 private:
  PXR_NS::UsdImagingGLEngine& engine(const std::string& renderer);
  Framebuffer& framebuffer(int width, int height);

  PXR_NS::UsdStageRefPtr stage_;
  GlContext gl_;  // before the engines: made first, destroyed last
  std::map<std::string, std::unique_ptr<PXR_NS::UsdImagingGLEngine>> engines_;
  std::unique_ptr<Framebuffer> fb_;
};

}  // namespace r3d
