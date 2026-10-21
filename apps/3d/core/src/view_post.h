// The live viewport's picture, finished on the graphics card (H20): Storm's scene-linear colour and depth go in,
// contact shading (screen-space ambient occlusion) and depth of field are laid in, then exposure, the background,
// OpenColorIO's display transform (ocio_gpu.h) and the selection ring; only the finished 8-bit picture comes back,
// top row first, straight into the screen's shared memory. Replaces reading back floats and the colour transform on
// the CPU (~70 ms a picture at 1280 x 720). The GL context must be current while it lives.
#pragma once
#include <pxr/base/gf/matrix4d.h>

#include <map>
#include <memory>
#include <optional>
#include <string>

#include "ocio_gpu.h"
#include "view_camera.h"

namespace r3d {

struct ViewPostIn {
  int width = 0, height = 0;
  unsigned color = 0, depth = 0, mask = 0;  // GL textures from Hydra::view; mask 0 = nothing selected
  PXR_NS::GfMatrix4d projection;            // the frustum's (USD row-vector convention)
  float background[3] = {0, 0, 0};          // linear RGB, where the picture is transparent
  double exposure = 0;                      // stops
  double ao = 0, aoRadius = 0.3;            // contact shading strength (0 = off) and reach in scene units
  std::optional<Lens> lens;                 // depth of field when set
  std::string config, display, view;        // OpenColorIO, as ColorOut uses for PNGs
};

class ViewPost {
 public:
  ViewPost();
  ~ViewPost();
  ViewPost(const ViewPost&) = delete;
  ViewPost& operator=(const ViewPost&) = delete;
  // writes width * height * 4 bytes of straight RGBA8, top row first, to dst; throws r3d::Error on a GL failure
  void run(const ViewPostIn& in, unsigned char* dst);

 private:
  struct Targets;
  unsigned program(const std::string& key, const std::string& fragment);
  std::unique_ptr<Targets> t_;
  std::map<std::string, unsigned> programs_;
  std::map<std::string, std::unique_ptr<OcioGpu>> ocio_;  // per view
  unsigned vao_ = 0;
};

}  // namespace r3d
