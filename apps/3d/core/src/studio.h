// The viewport's studio environment: a soft studio made by the core (a lat-long HDR picture: a grey sweep, a
// big soft box overhead-left, two tall strips, a floor bounce), used as a dome light so metal and glass have
// something to reflect in Storm. Viewport only: renders never see it. Written once per strength into
// %USERPROFILE%\.rostrum\cache\3d\ (strength is baked into the picture, quantized to 0.1).
#pragma once
#include <pxr/imaging/glf/simpleLight.h>

#include <string>

namespace r3d {

// the picture for this strength (made when missing); strength 0..4
std::string studio_texture(double strength);
// the lights to give Hydra for the viewport: the studio dome, or none when strength is 0
PXR_NS::GlfSimpleLightVector studio_lights(double strength);

}  // namespace r3d
