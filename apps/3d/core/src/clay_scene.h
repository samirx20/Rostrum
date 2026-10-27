// Clay items of the scene (ENGINE_CONTRACT.md § 2, item type `clay`): read loudly while the stage is built, handed
// to the clay store afterwards (BuildResult::clays). No OpenVDB here.
#pragma once
#include <string>
#include <vector>

#include <pxr/base/js/value.h>
#include <pxr/usd/sdf/path.h>

#include "clay_dabs.h"
#include "clay_shapes.h"
#include "clay_step.h"

namespace r3d {

class Item;
class Reader;

namespace clay {

struct StepNode {
  std::string key;     // the chain hash Python made; the core only compares keys
  std::string where;   // "<item id>.steps[i]", for errors while it is applied
  bool piece = true;
  Step shape;          // a piece (a sphere / capsule: shape.a, b, radius)
  ShapeSpec spec;      // a piece's shape (CL3: outline, spin, item; Ball = shape.a, b, radius)
  Brush brush;         // a stroke
  enum class Path { File, Inline, Along } path = Path::File;
  std::string file;    // Path::File: absolute path of the .dabs file
  std::string name;    // its file name ("<hash>.dabs"): a live stroke with the same name is adopted
  std::vector<DabRow> rows;  // Path::Inline
  std::vector<V3> along;     // Path::Along: an agent's points and direction (clay space)
  V3 dir;
};

struct Node {
  std::string id;
  PXR_NS::SdfPath path;  // the clay's Xform; its block meshes are children of it
  float detail = 0.002f; // metres per grain (voxel size)
  std::string cache;     // absolute path of the cache .vdb for exactly these steps, or "" (no cache)
  std::vector<StepNode> steps;
};

}  // namespace clay

// A `clay` item at `path`: the Xform (transform, material) in the scene's layer, and its node for the clay store.
clay::Node build_clay(Item& it, Reader& node, const PXR_NS::SdfPath& path);

}  // namespace r3d
