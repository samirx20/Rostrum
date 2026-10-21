// The dome's sun as a distant light with a shadow, for Storm only (dome_sun.h takes it out of Storm's dome picture).
// Storm casts shadows only from a light whose scene hands over shadow settings (HdxShadowParams with a shadow-matrix
// maker and a shadow collection; hdx/simpleLightTask.cpp), which USD lights never do. So a Hydra filter in front of
// Storm ("GL") alone adds one distant light at /_RostrumStormSun carrying them; its shadow map is an orthographic view
// from the sun over the part of the scene the camera sees. Cycles and the stylized renderer never see it.
#pragma once
#include <pxr/base/gf/frustum.h>
#include <pxr/base/gf/range3d.h>
#include <pxr/base/gf/vec3d.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/usd/usd/stage.h>

#include <optional>

namespace r3d {

struct StormSun {
  PXR_NS::GfVec3d toward;      // world unit direction towards the sun
  PXR_NS::GfVec3f irradiance;  // light on a surface facing it, in Storm's units (sky.cpp: π × Cycles')
  double angleDeg = 0.53;      // the sun's apparent size
  double share = 0;            // its part of the dome's light (reported, not used for drawing)

  bool operator==(const StormSun& o) const {
    return toward == o.toward && irradiance == o.irradiance && angleDeg == o.angleDeg;
  }
};

// where the sun's shadow map looks: across `seen`, deep enough to catch everything in `scene` that can cast into it
struct SunShadow {
  PXR_NS::GfRange3d seen;   // the scene's drawn things, cut down to what the camera can see
  PXR_NS::GfRange3d scene;  // all of the scene's drawn things
};

// register the filter for Storm; call once, before any Storm engine is made
void register_storm_sun();
// the sun every Storm engine draws from now on (none = no sun)
void set_storm_sun(const std::optional<StormSun>& sun, const SunShadow& shadow);
// the shadow box for a camera looking through `view` at frame `frame`
SunShadow sun_shadow(const PXR_NS::UsdStageRefPtr& stage, int frame, const PXR_NS::GfFrustum& view);

}  // namespace r3d
