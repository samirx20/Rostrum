// Clay: the clay surfaces on the stage. One Mesh prim per 32^3 block, /World/…/<clay id>/clay_<x>_<y>_<z> (negative
// numbers written n5), authored in an anonymous layer of the clay store's own, a sublayer of the stage's session
// layer: build_stage replaces the root layer's content (TransferContent) and never touches these, and a dab re-sends
// only the blocks it changed. Written straight as Sdf specs inside one change block (the proof's fast path: one
// SetField per attribute, the arrays moved in). The clay's Xform (root layer) carries its transform and material;
// the blocks inherit both. Storm and Cycles read the same prims.
#pragma once
#include <set>

#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include "clay_mesh.h"

namespace r3d::clay {

class Blocks {
 public:
  explicit Blocks(const PXR_NS::UsdStageRefPtr& stage);
  ~Blocks();
  // Create or update block `key` of the clay at `clay` (an empty mesh removes it); `have` is that clay's block list.
  // Call between begin() and end().
  void set(const PXR_NS::SdfPath& clay, const BlockKey& key, const BlockMesh& m, std::set<BlockKey>& have);
  void remove_all(const PXR_NS::SdfPath& clay, std::set<BlockKey>& have);
  void begin();
  void end();

 private:
  struct Impl;
  Impl* p_;
};

}  // namespace r3d::clay
