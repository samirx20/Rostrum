// A render's extra outputs (Hydra AOVs) read back from the renderer after the picture: the light passes, depth,
// surface direction and prim ids that core passes.* turns into EXR layers. Cycles only (its Hydra plug-in names
// them: libs/cycles-rostrum.patch, session.cpp kAovToPass).
#pragma once
#include <pxr/usd/sdf/path.h>
#include <pxr/usdImaging/usdImagingGL/engine.h>

#include <functional>
#include <map>
#include <string>
#include <vector>

namespace r3d {

struct Aovs {
  int width = 0, height = 0;
  std::map<std::string, std::vector<float>> planes;  // name -> pixels, top row first, `channels` floats a pixel
  std::map<std::string, int> channels;
  std::vector<int> primIds;                          // Hydra's prim id a pixel, top row first; -1 = nothing there
  std::map<int, PXR_NS::SdfPath> prims;              // each prim id seen -> its prim path
  const std::vector<float>& plane(const std::string& name) const;  // loud when the renderer didn't make it
};

// Reads `names` from `engine` (primId too when asked: its pixels and the paths `prim_of` names for them).
// A name the renderer has no output for, or one of the wrong size, is an error naming it.
Aovs read_aovs(PXR_NS::UsdImagingGLEngine& engine, const std::vector<std::string>& names, int width, int height,
               const std::function<PXR_NS::SdfPath(int)>& prim_of);

}  // namespace r3d
