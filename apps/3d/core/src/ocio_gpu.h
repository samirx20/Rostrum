// OpenColorIO's display transform on the graphics card, for the live viewport: the same config, display and view
// as ColorOut's PNGs (image_out.h), as the GLSL function `vec4 OCIODisplay(vec4)` plus the lookup textures and
// values it reads. Made once per view; the GL context must be current while it lives.
#pragma once
#include <memory>
#include <string>

namespace r3d {

class OcioGpu {
 public:
  OcioGpu(const std::string& config, const std::string& display, const std::string& view);  // throws r3d::Error
  ~OcioGpu();
  OcioGpu(const OcioGpu&) = delete;
  OcioGpu& operator=(const OcioGpu&) = delete;
  const std::string& glsl() const;  // the function, to be put after "#version" and before main()
  // binds its lookup textures from texture unit `first_unit` up and sets its samplers and values in `program`
  // (which must be in use)
  void bind(unsigned program, int first_unit) const;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

}  // namespace r3d
