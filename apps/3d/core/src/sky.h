// The scene's own dome as the viewport's sky and light (Storm). Storm reads a dome only as a picture and shows it
// in units π smaller than Cycles (measured H15: a flat dome and the floor it lights both came out exactly 1/π, i.e.
// −1.65 stops), and ignores a dome's colour, intensity and exposure. So Storm is handed a picture in Cycles' units:
// the dome's picture (or a flat one) × colour × intensity × 2^exposure × π, made once into the core's cache.
#pragma once
#include <pxr/imaging/glf/simpleLight.h>
#include <pxr/usd/usd/stage.h>

#include <optional>

namespace r3d {

// the scene's first dome as a viewport dome light, turned as the scene turns it; none when the scene has no dome
std::optional<PXR_NS::GlfSimpleLight> scene_sky(const PXR_NS::UsdStageRefPtr& stage, int frame);

}  // namespace r3d
