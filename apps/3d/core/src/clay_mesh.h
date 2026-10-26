// Clay: the surface read out in blocks (surface nets). Moved from proofs/3d-clay (mesh.h).
//
// The clay is a signed distance field sampled on a voxel lattice (negative inside). Space is cut into blocks of
// kBlock^3 voxels; block (bx,by,bz) covers voxel indices [b*kBlock, b*kBlock + kBlock) on each axis.
//
// Ownership (so blocks join without cracks or double faces): a block owns every lattice edge whose START voxel p
// lies inside the block. An edge p -> p+axis that crosses the surface makes one quad joining the 4 cells around the
// edge. Cell c has corners c .. c+1. So a block needs cells [-1, kBlock) relative to its min, i.e. voxel values on
// [-1, kBlock] relative to its min: kDense = kBlock + 2 samples per axis, starting at (blockMin - 1).
// A cell's vertex is placed and shaded only from its own 8 corners, so the same cell in two blocks gives the same
// vertex bit for bit; seams match exactly.
#pragma once
#include <cstdint>
#include <vector>

namespace r3d::clay {

constexpr int kBlock = 32;
constexpr int kDense = kBlock + 2;
constexpr int kWide = kBlock + 4;  // the same, one more voxel all round (origin blockMin - 2): smooth normals

struct BlockKey {
  int x = 0, y = 0, z = 0;
  bool operator==(const BlockKey& o) const { return x == o.x && y == o.y && z == o.z; }
  bool operator<(const BlockKey& o) const {
    return x != o.x ? x < o.x : y != o.y ? y < o.y : z < o.z;
  }
};

struct BlockMesh {
  std::vector<float> points;     // xyz per vertex, clay space (metres)
  std::vector<float> normals;    // xyz per vertex, unit, pointing out of the clay
  std::vector<int32_t> indices;  // 3 per triangle, counter-clockwise seen from outside
  bool empty() const { return indices.empty(); }
  size_t triangles() const { return indices.size() / 3; }
};

// `dense`: kDense^3 values, x fastest (index = x + kDense*(y + kDense*z)), sample (0,0,0) is voxel blockMin - 1.
// `voxel`: size of one voxel (metres); voxel index i sits at i * voxel in clay space (no offset).
// `wide`: kWide^3 values, origin blockMin - 2 (null: normals from the cell's own corners only). With it, a vertex's
// normal is the trilinear blend of central-difference gradients at its cell's 8 corners, so shading is continuous
// across cells (no voxel-scale rings), and still the same in both blocks of a seam.
// Clears `out` and fills it with the block's part of the surface (iso level 0).
void mesh_block(const float* dense, const float* wide, const BlockKey& key, float voxel, BlockMesh& out);

// Appends `b` to `whole` (indices offset).
void append(BlockMesh& whole, const BlockMesh& b);

}  // namespace r3d::clay
