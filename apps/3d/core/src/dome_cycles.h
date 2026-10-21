// Cycles reads a dome's picture the Blender way, not the USD way, so the same dome showed a different part of the
// sky in Cycles than in Storm (H15's "horizon ~10° off" was this: Cycles looked at the ground under the camera).
//   USD / Storm (hdSt surfaceHelpers.glslfx ProjectToLatLong): top of the picture = the dome's +Y,
//     u = (atan2(z, x) + π/2) / 2π, v = acos(y) / π.
//   Cycles (kernel/camera/projection.h direction_to_equirectangular, used as is by hydra/light.cpp): top = +Z,
//     u = 1/2 − atan2(y, x) / 2π, v = 1 − acos(z) / π.
// They agree when Cycles' (x, y, z) is USD's (z, x, y): a fixed turn. A Hydra filter in front of Cycles alone
// adds that turn to every dome's transform, so the stage stays the USD truth and every dome (ours or an import's)
// is seen and lights the same in both renderers.
#pragma once

namespace r3d {

// register the filter for Hydra's "Cycles" renderer; call once, before any Cycles engine is made
void register_cycles_dome_fix();

}  // namespace r3d
