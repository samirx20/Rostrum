// The sun inside a dome's picture, taken out for Storm. A sunny HDR keeps most of its light in a few pixels (the
// beach HDR: 83% in ~10 pixels); Storm lights only from a blurred copy of the dome, so that light is smeared away and
// casts no shadow. So, once per picture, the brightest connected patch is found, measured (direction, light, size)
// and painted over with the sky around it; Storm gets the painted picture plus a distant light carrying exactly the
// light that was taken out (storm_sun.h), so the total light is unchanged. Cycles keeps the full dome.
// Directions follow the USD / Storm lat-long reading (dome_cycles.h): top row = the dome's +Y,
// u = (atan2(z, x) + π/2) / 2π, v = acos(y) / π.
#pragma once
#include <pxr/base/gf/vec3d.h>
#include <pxr/base/gf/vec3f.h>

#include <optional>
#include <string>

namespace r3d {

struct DomeSun {
  PXR_NS::GfVec3d toward;      // dome-local unit direction towards the sun
  PXR_NS::GfVec3f irradiance;  // the light taken out, in the picture's units × steradians (light on a facing surface)
  double solidAngle = 0;       // steradians the patch covered
  double share = 0;            // the patch's part of the whole dome's light, 0..1
};

struct DomeSplit {
  std::string picture;         // the picture Storm should use: the painted copy, or `source` when there is no sun
  std::optional<DomeSun> sun;  // none when no small patch holds enough of the light
};

// "<path hash>-<last write time>-<size>": names a picture's cached derivatives; throws when it can't be read
std::string picture_stamp(const std::string& source);
// the split for a lat-long picture, analysed once and stored in the core's cache (studio.h cache_dir)
DomeSplit split_dome_sun(const std::string& source);

}  // namespace r3d
