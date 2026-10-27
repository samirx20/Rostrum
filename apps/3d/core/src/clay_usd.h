// Clay: the clay surfaces on the stage. One Mesh prim per 32^3 block, /World/…/<clay id>/clay_<x>_<y>_<z> (negative
// numbers written n5), authored in an anonymous layer of the clay store's own, a sublayer of the stage's session
// layer: build_stage replaces the root layer's content (TransferContent) and never touches these, and a dab re-sends
// only the blocks it changed. Written straight as Sdf specs inside one change block (the proof's fast path: one
// SetField per attribute, the arrays moved in). The clay's Xform (root layer) carries its transform and material;
// the blocks inherit both. Storm and Cycles read the same prims.
//
// CL5: a skinned clay (clay_skin.h) has its blocks written POSED: set() keeps each block's rest surface in the clay's
// Skinning and writes its posed points, normals and extent; pose() re-writes only the blocks whose bones moved. get()
// still gives the rest surface. Nothing of the skinning is in the stage: a stroke's worker may read it (skinning()).
#pragma once
#include <memory>
#include <set>
#include <string>
#include <vector>

#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/vt/array.h>
#include <pxr/base/vt/types.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include "clay_mesh.h"
#include "clay_skin.h"

namespace r3d::clay {

// a block prim's name ("clay_3_n1_0") -> its key; false for any other name
bool block_key_of(const std::string& name, BlockKey& key);

class Blocks {
 public:
  explicit Blocks(const PXR_NS::UsdStageRefPtr& stage);
  ~Blocks();
  // Create or update block `key` of the clay at `clay` (an empty mesh empties its prim, kept: 3d-v4); `have` is that clay's block list.
  // Call between begin() and end().
  void set(const PXR_NS::SdfPath& clay, const BlockKey& key, const BlockMesh& m, std::set<BlockKey>& have);
  void remove_all(const PXR_NS::SdfPath& clay, std::set<BlockKey>& have);
  // 3d-cl4, a painted clay's unfolded surface (clay_surface.h): `primvars:st` (faceVarying, one per triangle corner)
  // on a block. set() takes it off a block it re-writes (the block changed: no st until the next unfold). get() reads
  // a block's surface as written (false: no prim, or an emptied one).
  bool get(const PXR_NS::SdfPath& clay, const BlockKey& key, PXR_NS::VtVec3fArray& points,
           PXR_NS::VtVec3fArray& normals, PXR_NS::VtIntArray& indices) const;
  bool has_st(const PXR_NS::SdfPath& clay, const BlockKey& key) const;
  void set_st(const PXR_NS::SdfPath& clay, const BlockKey& key, PXR_NS::VtVec2fArray st);  // between begin() and end()
  void clear_st(const PXR_NS::SdfPath& clay, const BlockKey& key);                         // between begin() and end()
  void begin();
  void end();

  // CL5. The clay's bones (null: none, its blocks written at rest again). A rig of the same rest only takes the new
  // pose table; a new rest re-weighs every block of `have` (their rest surfaces from the old skinning, else the
  // layer). Call between begin() and end().
  void set_skin(const PXR_NS::SdfPath& clay, std::shared_ptr<const SkinRig> rig, const std::set<BlockKey>& have);
  // the clay's blocks posed with `moves` (one per bone): only those whose bones moved are written; how many. Between
  // begin() and end(). 0 for a clay with no skin.
  // `skinMs` / `usdMs` (optional): the bending (parallel) and the Sdf writes (serial)
  int pose(const PXR_NS::SdfPath& clay, const std::vector<BoneMove>& moves, double* skinMs = nullptr,
           double* usdMs = nullptr);
  const Skinning* skinning(const PXR_NS::SdfPath& clay) const;  // null: no skin

 private:
  struct Impl;
  Impl* p_;
};

}  // namespace r3d::clay
