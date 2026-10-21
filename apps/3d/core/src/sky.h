// The scene's own dome as the viewport's sky and light (Storm). Storm reads a dome only as a picture and shows it
// in units π smaller than Cycles (measured H15: a flat dome and the floor it lights both came out exactly 1/π, i.e.
// −1.65 stops), and ignores a dome's colour, intensity and exposure. So Storm is handed a picture in Cycles' units:
// the dome's picture (or a flat one) × colour × intensity × 2^exposure × π, made once into the core's cache.
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
};

// the scene's first dome; none when the scene has no dome. `take_sun`: split the sun off its picture (Storm)
std::optional<SceneSky> scene_sky(const PXR_NS::UsdStageRefPtr& stage, int frame, bool take_sun);

}  // namespace r3d
