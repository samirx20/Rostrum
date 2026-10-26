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
#include <vector>

#include "ocio_gpu.h"
#include "view_camera.h"

namespace r3d {

// one onion-skin ghost's picture (Hydra::view) and how it is laid over the scene
struct GhostIn {
  unsigned tex = 0;            // its items alone, lit, scene-linear RGBA
  float tint[3] = {1, 1, 1};   // linear RGB
  float opacity = 0.35f;       // 0..1
};

// where a `view` picture goes: the engine program's shared memory (ENGINE_CONTRACT § 4), or a GL framebuffer of the
// window that holds the core (window_core.h: the in-window viewport draws straight into its own texture)
struct ViewTarget {
  unsigned fbo = 0;  // 0 = shared memory
  int width = 0, height = 0;
};

struct ViewPostIn {
  int width = 0, height = 0;
  unsigned color = 0, depth = 0, mask = 0;  // GL textures from Hydra::view; mask 0 = nothing selected
  PXR_NS::GfMatrix4d projection;            // the frustum's (USD row-vector convention)
  float background[3] = {0, 0, 0};          // linear RGB, where the picture is transparent
  double exposure = 0;                      // stops
  double ao = 0, aoRadius = 0.3;            // contact shading strength (0 = off) and reach in scene units
  std::optional<Lens> lens;                 // depth of field when set
  std::vector<GhostIn> ghosts;              // onion skin, laid over the scene in turn (before the lens blur)
  std::string config, display, view;        // OpenColorIO, as ColorOut uses for PNGs
};

class ViewPost {
 public:
  ViewPost();
  ~ViewPost();
  ViewPost(const ViewPost&) = delete;
  ViewPost& operator=(const ViewPost&) = delete;
  // writes width * height * 4 bytes of straight RGBA8, top row first, to dst; throws r3d::Error on a GL failure.
  // With `target` (dst null): the finished picture is drawn into that framebuffer instead, scaled to its size, in
  // GL's own row order (the window's view, window_core.h)
  void run(const ViewPostIn& in, unsigned char* dst, const ViewTarget* target = nullptr);

 private:
  struct Targets;
  unsigned ghosts(const ViewPostIn& in, unsigned lit, const std::string& head);
  unsigned program(const std::string& key, const std::string& fragment);
  std::unique_ptr<Targets> t_;
  std::map<std::string, unsigned> programs_;
  std::map<std::string, std::unique_ptr<OcioGpu>> ocio_;  // per view
  unsigned vao_ = 0;
};

}  // namespace r3d
