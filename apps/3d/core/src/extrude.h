// Extruded, bevelled meshes from 2D outlines (ENGINE_CONTRACT.md § 2, shape `outline`): text and logos.
// The outline lies in XY facing +Z; the solid runs from z = -depth/2 to +depth/2. A rounded bevel
// (quarter circle of radius `bevel`) joins each cap, inset by `bevel`, to the side wall at the full outline.
#pragma once
#include <array>
#include <string>
#include <vector>

#include "outline_offset.h"
#include "primitives.h"

namespace r3d {

enum FacePart { kFront, kBevel, kSide, kBack };
constexpr const char* kFacePartNames[4] = {"front", "bevel", "side", "back"};
using FaceGroups = std::array<PXR_NS::VtArray<int>, 4>;  // face indices of each FacePart

struct Extruded {
  MeshData mesh;
  FaceGroups groups;
};

// Bevel steps per quarter circle for a `segments` value (the same meaning as a box's bevel, capped).
int outline_bevel_steps(int segments);

// bevel <= depth / 2 is the caller's check. When the bevel is too big for an outline (the inset edges would
// cross or a shape would turn inside out), throws r3d::Error at "<where>.bevel" naming the largest bevel that
// works. `where` = the item's id.
Extruded make_extrusion(const std::vector<OutlineShape>& shapes, double depth, double bevel, int segments,
                        bool smooth, const std::string& where);

}  // namespace r3d
