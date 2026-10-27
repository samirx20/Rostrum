// Light to colour in Cycles (ENGINE_CONTRACT.md § 2, Materials, "How lit"): a material whose Stylized shader has
// lightToColor on gets, on outputs:cycles:surface, a node graph that adds up how lit each point is from the scene's
// own lights (the 8 strongest: max(N·L, 0) × a raycast shadow test × the light's brightness, 1/d² for lights with a
// place, plus each dome's hemisphere term), looks that up in a ramp (shadow / mid / lit colours, steps or smooth) ×
// the base colour (or its image), and shows it unlit through an emission node with the material's own glow added.
// Brightness is the light's real one, in the units every renderer uses (H19, apps/3d/tools/light_check.py): "how
// lit 1" is what white paper facing the light shows at exposure 0. Lights that move or change get time samples, one
// per frame of the shot. Node and socket names checked against Cycles' scene/shader_nodes.cpp (geometry,
// vector_math, math, raycast, map_range, rgb_ramp, emission) and hydra/material.cpp (inputs and links matched by
// the sockets' own names ignoring case; the terminal output by its UI name, "Emission").
#pragma once
#include <string>
#include <vector>

#include <pxr/base/gf/vec3f.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

namespace r3d {

// One light as the graph sees it, one value per frame of the shot.
struct LightTerm {
  enum class Kind { distant, sphere, disk, rect, dome };
  PXR_NS::SdfPath path;
  Kind kind = Kind::distant;
  bool spot = false;     // a sphere with a shaping cone
  bool shadows = true;   // shadow:enable
  std::vector<float> k;  // brightness: what a white surface facing it shows (at 1 m for lights with a place)
  std::vector<PXR_NS::GfVec3f> where;  // distant: towards the light; sphere / disk / rect: its place; dome: its up
  std::vector<PXR_NS::GfVec3f> back;   // disk / rect / spot: the way it shines, reversed (from the light, -emit)
  std::vector<float> cosOuter, cosInner;  // spot: the cone's edge and where its soft edge ends
  double rank = 0;  // the largest k over the shot: the 8 strongest are used
};

// The scene's lights over frames start..end (the 8 strongest; lights with no brightness left out).
std::vector<LightTerm> scene_light_terms(const PXR_NS::UsdStageRefPtr& stage, int start, int end);

// Rewires `material`'s outputs:cycles:surface (on `stage`) to the light-to-colour graph when its Stylized shader has
// lightToColor on; `lights` from scene_light_terms. Returns whether it did.
bool apply_light_to_color(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& material,
                          const std::vector<LightTerm>& lights, int start);

// Every material under /World/Looks of a built stage (after its lights): the lights gathered only when one needs them.
void build_light_to_color(const PXR_NS::UsdStageRefPtr& stage, int start, int end);

// Each dome light's picture level (dome_floor_level of its texture) as primvars:rostrum:domeLevel (color3f, constant):
// what the stylized renderer multiplies by the dome's colour × intensity × 2^exposure for its hemisphere term.
void publish_dome_levels(const PXR_NS::UsdStageRefPtr& stage);

// What a white floor facing a dome's up shows under its picture (gain 1): (1/π) ∫ picture · cos over the upper half,
// per channel; "" = a flat white picture (1, 1, 1). Cached per file.
PXR_NS::GfVec3f dome_floor_level(const std::string& texture);

}  // namespace r3d
