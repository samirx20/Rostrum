// P-3D-3: plain scene data the Hydra prims write (in parallel Sync) and the render pass reads.
#pragma once

#include <pxr/pxr.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/gf/vec4f.h>
#include <pxr/base/tf/token.h>
#include <pxr/usd/sdf/path.h>

#include <map>
#include <mutex>
#include <string>
#include <vector>

PXR_NAMESPACE_OPEN_SCOPE

// Per-camera shape bending, authored as constant primvars on a mesh (rostrum:bend:*).
struct RostrumBend {
    std::string camera;          // applies only when this camera renders ("" = never)
    float squash = 1.0f;         // scale along the screen's up axis around the pivot (volume kept)
    GfVec2f lean = {0, 0};       // shear on screen per unit of height above the pivot
    float swell = 0.0f;          // grow in the screen plane around the pivot (0 = none)
};

struct RostrumMeshData {
    // triangle soup, world space is applied in the shader with `xform`
    std::vector<GfVec3f> P, N;
    std::vector<GfVec2f> UV;
    GfMatrix4d xform{1.0};
    SdfPath material;
    GfVec3f displayColor{0.6f, 0.6f, 0.6f};
    bool visible = true;
    RostrumBend bend;
    GfVec3f pivot{0, 0, 0};      // world-space bottom centre of the bounds (bend pivot)
    GfVec3f center{0, 0, 0};     // world-space bounds centre
    float radius = 1.0f;         // world-space bounds radius
    unsigned version = 0;        // bumped on every geometry change (GPU re-upload)
};

struct RostrumMaterialData {
    GfVec3f baseColor{0.6f, 0.6f, 0.6f};
    std::string texture;         // albedo image (sRGB), "" = none
    bool unlit = false;          // emission-only material (a painted card): shown as painted
};

struct RostrumRamp {
    std::vector<float> positions;    // 0..1, ascending
    std::vector<GfVec3f> colors;     // tint at each position (multiplied with the albedo)
    float smooth = 0.0f;             // 0 = hard painted steps, 1 = linear blend
};

struct RostrumLightData {
    TfToken type;                    // distantLight, domeLight, rectLight, sphereLight, diskLight
    GfMatrix4d xform{1.0};
    GfVec3f color{1, 1, 1};          // colour x colour temperature
    float gain = 1.0f;               // rostrum:gain (stylized brightness; physical intensity is Cycles')
    float wrap = 0.0f;               // rostrum:wrap: light wraps past the terminator (0..1)
    bool shadow = true;              // rostrum:shadow
    GfVec3f hemiUp{0, 1, 0};         // dome: "how lit" = facing this direction (bounce: point it down)
    RostrumRamp ramp;                // rostrum:ramp:* ; empty = plain lambert to the light colour
    bool enabled = true;             // rostrum:enable
};

class RostrumScene {
public:
    std::mutex lock;
    std::map<SdfPath, RostrumMeshData> meshes;
    std::map<SdfPath, RostrumMaterialData> materials;
    std::map<SdfPath, RostrumLightData> lights;
    unsigned materialsVersion = 0, lightsVersion = 0;
};

PXR_NAMESPACE_CLOSE_SCOPE
