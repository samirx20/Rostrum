// The scene's own dome as the viewport's sky and light (Storm). Lights follow UsdLux's units (H19, light check): a
// dome's light is its picture × colour × intensity × 2^exposure (× its colour temperature), so a dome of intensity 1
// is seen as its picture's own values. Storm is handed the dome only as this picture, already multiplied, made once
// into the core's cache; the scene's dome prim itself is kept from Storm (storm_lights.cpp), which would light twice.
// (Cycles gets the same picture; cycles_lights.h says why.)
// For Storm the picture's sun is first taken out and handed over as a distant light with a shadow (dome_sun.h,
// storm_sun.h); the stylized renderer has no such light, so it keeps the whole picture.
#pragma once
#include <pxr/imaging/glf/simpleLight.h>
#include <pxr/usd/usd/stage.h>

#include <optional>

#include "storm_sun.h"

namespace r3d {

struct SceneSky {
  PXR_NS::GlfSimpleLight dome;  // a viewport dome light, turned as the scene turns it
  std::optional<StormSun> sun;  // the sun taken out of its picture (only when asked for, and found)
  bool seen = true;             // the camera sees it (rostrum:seenByCamera, light_extras.h); off = it only lights
};

// `source` (a lat-long picture; "" = a flat white one) × `gain`, as an EXR in the core's cache (named by what made
// it, so it is made once); returns its path
std::string dome_picture(const std::string& source, const PXR_NS::GfVec3f& gain);

// the scene's first dome; none when the scene has no dome. `take_sun`: split the sun off its picture (Storm)
std::optional<SceneSky> scene_sky(const PXR_NS::UsdStageRefPtr& stage, int frame, bool take_sun);

}  // namespace r3d
