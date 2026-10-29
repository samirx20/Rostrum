#pragma once
// How far Cycles follows light, and how it keeps the rare bright paths from showing as spots: the same for the Final
// look and every render (the estimate's probe draws through the same settings, so its times include them).
// Cycles' own defaults (7 bounces in all, glossy never blurred, an indirect sample clamped only at 10) left glass with
// liquid in it blotchy at the few samples a 10-minute video budget allows (3E 3D bench "Drop", both judges: grain in
// the bottle's juice, a white blotch on the floor). What changed, from Blender's own render defaults, which won that
// brief's other half:
// - 12 bounces in all, 12 through glass: a ray through a bottle and the liquid in it crosses 4-6 surfaces before it
//   reaches what is behind, and more where it reflects inside; at 7 it was cut off and came back black.
// - 4 diffuse and 4 glossy bounces (7 before): light past the fourth matte or shiny bounce adds almost nothing and
//   costs time, which pays for the glass bounces above.
// - Glossy blurred after a rough bounce (filter_glossy 1): a matte surface seen through or beside sharp glass gets
//   its light through that glass only along rare exact paths (caustics); blurring the glass for those paths finds
//   them far more often. What the camera sees directly and through glass stays sharp.
// - A bounced sample is clamped at 5 (10 before): the one sample in thousands that finds a light through glass or
//   off gold stays a soft lift instead of a white spot the noise clean-up spreads into a blotch. Direct light is
//   never clamped, so highlights keep their brightness.
// The noise clean-up already reads each pixel's colour and surface direction (Cycles' albedo and normal passes, on
// by default), which keeps edges and labels sharp.
#include <pxr/base/vt/value.h>

#include <utility>
#include <vector>

namespace r3d {

// Cycles' integrator settings (its Hydra plug-in's "cycles:integrator:<name>" keys), each with the value's own type
// (an int or a float, as Cycles reads it back), so a setting already in place is never sent again.
inline const std::vector<std::pair<const char*, PXR_NS::VtValue>>& cycles_paths() {
  static const std::vector<std::pair<const char*, PXR_NS::VtValue>> kPaths = {
      {"cycles:integrator:max_bounce", PXR_NS::VtValue(12)},
      {"cycles:integrator:max_transmission_bounce", PXR_NS::VtValue(12)},
      {"cycles:integrator:transparent_max_bounce", PXR_NS::VtValue(8)},
      {"cycles:integrator:max_diffuse_bounce", PXR_NS::VtValue(4)},
      {"cycles:integrator:max_glossy_bounce", PXR_NS::VtValue(4)},
      {"cycles:integrator:filter_glossy", PXR_NS::VtValue(1.0f)},
      {"cycles:integrator:sample_clamp_indirect", PXR_NS::VtValue(5.0f)},
  };
  return kPaths;
}

}  // namespace r3d
