// Lights packed for the shade shader: per-light uniforms, legacy ramp rows, shadow cameras.
#pragma once

#include "scene.h"

#include <pxr/base/gf/vec4f.h>
#include <pxr/base/gf/matrix4f.h>
#include <pxr/base/gf/range3d.h>

#include <vector>

PXR_NAMESPACE_OPEN_SCOPE

constexpr int kMaxLights = 8, kMaxShadows = 4, kRampSize = 256;

// Brightness is in "shown" units: what a white matte surface facing the light shows on screen at
// exposure 0 (UsdLux's illuminance / pi). Local lights: that x 1/d^2 at distance d (point-like).
struct RostrumFrameLights {
    int count = 0, shadows = 0;
    // xyz: to-light direction (w 0, distant), position (w 1 sphere / spot, w 2 rect / disk panel), dome (w 3)
    GfVec4f pos[kMaxLights];
    GfVec4f axis[kMaxLights];     // xyz: emit direction (dome: hemisphere up); w: 1 = legacy ramp light
    GfVec4f color[kMaxLights];    // rgb: colour x brightness (legacy ramp: colour x gain); a: wrap
    // spot / panel: x = cos of the cone's edge (-2 = no cone), y = cos where it is full, z = the
    // smallest d^2 (no brighter than the light's own surface), w = shadow layer (-1 none);
    // dome: xyz = what a white surface facing down shows (colour x brightness), w = -1
    GfVec4f extra[kMaxLights];
    GfMatrix4f shadowMat[kMaxShadows];  // world -> light clip
    float shadowSpan[kMaxShadows] = {};   // how wide the map is at the bounds' centre (world units; / size = a texel)
    std::vector<float> ramps;     // kMaxLights rows x kRampSize texels x RGBA (legacy ramp lights' rows)
    bool legacy = false;          // some light has a legacy ramp
};

// The strongest kMaxLights lights at the bounds' centre (one dome: the brightest), the first
// kMaxShadows that cast with a shadow map fitted tightly around the bounds' corners as the light sees
// them (`lit`: what casts and receives light). The order depends only on the lights and the bounds.
RostrumFrameLights RostrumPackLights(std::map<SdfPath, RostrumLightData> const &lights, GfRange3d const &lit);

PXR_NAMESPACE_CLOSE_SCOPE
