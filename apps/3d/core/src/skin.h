// Simple bone chains (SPEC §9, brief 19): a mesh bent by its bones, the same in Quick and Final because the
// bent points are written onto the mesh as time samples, which every renderer reads. Weights are automatic
// (from each point's distance to each bone at rest); the bending is USD skel's linear blend skinning.
// CL5: a clay's blocks bend by the same weights (clay_skin.h), so the rule and the `skin` reader live here.
#pragma once
#include <array>
#include <cstddef>
#include <memory>
#include <string>
#include <vector>

#include <pxr/base/js/value.h>
#include <pxr/usd/usdGeom/mesh.h>

#include "primitives.h"

namespace r3d {

// One bone's move from rest: [m00, m01, m02, m10, m11, m12, m20, m21, m22, tx, ty, tz], M row by row,
// p_now = M·p_rest + t.
using BoneMove = std::array<double, 12>;

// CL7, a clay's `skin.parts` (ENGINE_CONTRACT.md § Clay with bones, Parts; Python: rostrum3d/skin_parts.py): which
// piece (0 = the body, n = a limb) each cell of the clay's rest grid belongs to, each bone's piece, and per piece the
// bone it hangs from, its first bone and how far round that joint the bend is shared. A point leans only on its own
// piece's bones, and on the neighbour piece's bone at a joint within 2 × blend of it, so a raised arm never pulls
// the body's side or hip (the bones near it through the air are another piece's).
struct SkinParts {
  std::array<double, 3> origin{};  // the grid's low corner; cell (i, j, k)'s centre is origin + (i + 0.5) × cell
  double cell = 1;
  std::array<int, 3> dims{};
  std::vector<unsigned char> cells;  // x fastest, then y, then z; 255 outside
  std::vector<int> bone;             // the piece of each bone
  struct Piece {
    int from = -1, first = -1;
    double blend = 0;
    bool operator==(const Piece& o) const { return from == o.from && first == o.first && blend == o.blend; }
  };
  std::vector<Piece> pieces;
  bool operator==(const SkinParts& o) const {
    return origin == o.origin && cell == o.cell && dims == o.dims && cells == o.cells && bone == o.bone &&
           pieces == o.pieces;
  }
  int piece_at(const double p[3]) const;  // the cell's piece, else the nearest inside one of the 26 round; -1: none
  // how much bone b may lean on a point of `piece` at p (0..1); rest = the bones' rest segments
  double gate(int piece, int b, const double p[3], const std::vector<std::array<double, 6>>& rest) const;
};

// `skin` (ENGINE_CONTRACT.md § 2, mesh and clay `skin`): {"rest": [[hx,hy,hz, tx,ty,tz] per bone],
// "pose": [[move per bone] per frame], "parts" (clay, optional)}, all in the item's own space.
struct SkinRig {
  std::vector<std::array<double, 6>> rest;   // each bone's head and tail at rest
  std::vector<std::vector<BoneMove>> pose;   // per frame of the shot (from its start), one move per bone
  std::shared_ptr<const SkinParts> parts;    // null: every point may lean on every bone (the mesh's rule)
  bool same_weights(const SkinRig& o) const {  // the same rest and pieces: the weights stay
    return rest == o.rest && (parts == o.parts || (parts && o.parts && *parts == *o.parts));
  }
};

// Read loudly: an empty `rest` or `pose`, a frame without one move per bone, a list that isn't 6 / 12 numbers.
SkinRig read_skin(const PXR_NS::JsObject& skin, const std::string& where);
// one [12 numbers] move; `where` names it in errors
BoneMove read_bone_move(const PXR_NS::JsValue& v, const std::string& where);

// Automatic weights: each point leans on its nearest kSkinMost bones by 1 / distance⁴ to their rest segments,
// normalised. `xyz`: n points, 3 floats each; `idx` / `w`: n × skin_influences(bones) each, filled.
// `behind` (CL5c, clay only; 0 = the mesh's rule exactly): a point behind a bone's head (its projection on the bone's
// axis before the head) counts as farther from that bone by `behind` × that distance along the axis, so a limb whose
// head sits on a body's surface doesn't pull the body behind it along.
constexpr int kSkinMost = 4;
inline int skin_influences(size_t bones) { return int(bones < size_t(kSkinMost) ? bones : size_t(kSkinMost)); }
// `parts` (CL7, clay only; null = none): each bone's 1 / distance⁴ is times SkinParts::gate for the point's piece.
void skin_weights(const float* xyz, size_t n, const std::vector<std::array<double, 6>>& rest, int* idx, float* w,
                  double behind = 0.0, const SkinParts* parts = nullptr);

// Writes points, normals and extent per frame from `start`. `where` names the field in errors.
void skin_mesh(PXR_NS::UsdGeomMesh m, const MeshData& d, const PXR_NS::JsObject& skin, int start,
               const std::string& where);

}  // namespace r3d
