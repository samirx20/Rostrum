// Clay: a clay bent by its bones (CL5, ENGINE_CONTRACT.md § 2 clay `skin`). Each block's REST surface is kept here
// with its automatic weights (skin.h, the mesh's rule: the 4 nearest bones by 1 / distance⁴), and its points and
// normals posed by the clay's current bone moves (dual-quaternion blend, dual_quat.h; linear when a move isn't a
// pure turn and shift, or with ROSTRUM3D_CLAY_SKIN_LINEAR=1). The block prims (clay_usd.h) are written with the
// posed surface; Blocks::get still gives the rest one, so a painted clay's unfolding never depends on the pose.
// A new pose re-poses only the blocks one of whose bones moved, never re-meshes. The posed triangles answer rays
// (a stroke on a posed clay, cast()) from memory: nothing here reads or writes the stage.
//
// Weights are made when a block is kept (CL5b; in parallel over its points), so the first move of a drag weighs
// nothing. A clay's weights are pruned (clay_skin.cpp prune_share: influences under 2 % dropped, renormalised), so a
// move re-writes only the blocks near the bones that moved. Zero-area placeholder blocks are never kept.
#pragma once
#include <array>
#include <map>
#include <memory>
#include <optional>
#include <vector>

#include <pxr/base/gf/vec3d.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/vt/types.h>

#include "clay_mesh.h"
#include "dual_quat.h"
#include "skin.h"

namespace r3d::clay {

// p' = m·p + t, m row by row (a bone move, or a blend of them)
struct Affine {
  double m[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};
  double t[3] = {0, 0, 0};
  static Affine of(const BoneMove& b);
  PXR_NS::GfVec3d point(const PXR_NS::GfVec3d& p) const;
  PXR_NS::GfVec3d dir(const PXR_NS::GfVec3d& d) const;     // m·d
  PXR_NS::GfVec3d normal(const PXR_NS::GfVec3d& n) const;  // m⁻ᵀ·n, unit
  bool inverse(Affine& out) const;                         // false: m can't be inverted
};

// where a ray met the posed surface
struct PosedHit {
  BlockKey key;
  int tri = -1;
  double t = 0;              // along the ray (its own units)
  double bary[3] = {0, 0, 0};
  PXR_NS::GfVec3d point;     // posed, clay space
  Affine blend;              // the blended bone move there (as drawn: weights barycentric over the corners)
};

class Skinning {
 public:
  explicit Skinning(std::shared_ptr<const SkinRig> rig);
  const SkinRig& rig() const { return *rig_; }
  void set_rig(std::shared_ptr<const SkinRig> rig);  // the same rest (bones and their places); a new pose table
  size_t bones() const { return rig_->rest.size(); }
  bool posed() const { return posed_; }  // some bone is not at rest

  // a block's rest surface kept (the arrays shared, not copied) and weighed; its posed points and normals made with
  // the moves. A zero-area placeholder (one triangle, its points the same) is not kept: false, drawn as it is
  bool keep(const BlockKey& k, const PXR_NS::VtVec3fArray& points, const PXR_NS::VtVec3fArray& normals,
            const PXR_NS::VtIntArray& indices);
  void drop(const BlockKey& k);
  void clear() { blocks_.clear(); }
  bool has(const BlockKey& k) const { return blocks_.count(k) != 0; }
  std::vector<BlockKey> keys() const;
  bool rest(const BlockKey& k, PXR_NS::VtVec3fArray& points, PXR_NS::VtVec3fArray& normals,
            PXR_NS::VtIntArray& indices) const;
  // the block as drawn (false: not kept); extent = [lo, hi] of the posed points
  bool posed_surface(const BlockKey& k, PXR_NS::VtVec3fArray& points, PXR_NS::VtVec3fArray& normals,
                     PXR_NS::VtVec3fArray& extent) const;

  // new moves (one per bone; the caller checked the count): the blocks re-posed (in parallel), which the caller
  // writes out
  std::vector<BlockKey> pose(const std::vector<BoneMove>& moves);

  // the nearest posed triangle a ray (clay space, `dir` unit) meets within maxDist, either side; blocks culled by
  // their posed bounds
  bool cast(const PXR_NS::GfVec3d& origin, const PXR_NS::GfVec3d& dir, double maxDist, PosedHit& hit) const;
  // a drawn spot on triangle `tri` of block `k` (posed, clay space) -> the same spot on the rest surface
  std::optional<PXR_NS::GfVec3d> rest_spot(const BlockKey& k, int tri, const PXR_NS::GfVec3d& posedPoint) const;

 private:
  struct Block {
    PXR_NS::VtVec3fArray rest, restN, posed, posedN;
    PXR_NS::VtIntArray indices;
    std::vector<int> idx;      // k per point
    std::vector<float> w;
    std::vector<int> bones;    // every bone some point leans on (sorted)
    bool weighted = false;
    PXR_NS::GfVec3f lo, hi;    // posed bounds
  };
  void weigh(Block& b) const;
  void pose_block(Block& b) const;
  Affine blend_at(const Block& b, int tri, const double bary[3]) const;

  std::shared_ptr<const SkinRig> rig_;
  std::vector<BoneMove> moves_;   // what the blocks are posed with
  std::vector<Affine> aff_;       // the same, as Affine
  std::vector<std::array<double, 9>> nmat_;  // and each move's normal matrix (m⁻ᵀ, row by row)
  std::vector<DualQuat> dq_;      // and as dual quaternions (CL6), when every move is rigid
  bool dual_ = false;             // blend the moves as dual quaternions (every move rigid, not switched off)
  bool posed_ = false;
  std::map<BlockKey, Block> blocks_;
};

}  // namespace r3d::clay
