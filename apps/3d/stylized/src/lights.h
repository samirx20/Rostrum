// P-3D-3: lights packed for the shade shader: per-light uniforms, ramp table rows, shadow cameras.
#pragma once

#include "scene.h"

#include <pxr/base/gf/vec4f.h>
#include <pxr/base/gf/matrix4f.h>

#include <vector>

PXR_NAMESPACE_OPEN_SCOPE

constexpr int kMaxLights = 8, kMaxShadows = 4, kRampSize = 256;

struct RostrumFrameLights {
    int count = 0, shadows = 0;
    GfVec4f pos[kMaxLights];      // xyz: to-light direction (w 0), position (w 1 sphere/disk, 2 rect), dome (w 3)
    GfVec4f axis[kMaxLights];     // rect/disk: emit direction; dome: hemisphere up
    GfVec4f color[kMaxLights];    // rgb: colour x gain; a: wrap
    float shadowLayer[kMaxLights];  // -1 = no shadow
    GfMatrix4f shadowMat[kMaxShadows];  // world -> light clip
    std::vector<float> ramps;     // kMaxLights rows x kRampSize texels x RGBA
};

// centre/radius: bounds of what casts and receives light (shadow cameras are fitted to it)
RostrumFrameLights RostrumPackLights(std::map<SdfPath, RostrumLightData> const &lights,
                                     GfVec3d const &centre, double radius);

PXR_NAMESPACE_CLOSE_SCOPE
