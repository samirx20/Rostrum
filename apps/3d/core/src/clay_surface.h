// Clay: a painted clay's unfolded surface (3d-cl4). A clay that holds paint (its scene node's `paint`) gets its
// full-detail surface laid flat once per shape: the blocks' meshes (clay_usd.h, exactly as drawn) welded into one
// surface (points at exactly the same place are one: the seams are bit-identical), unfolded by xatlas (unfold.h), and
// kept in a CLS1 file the Python side reads to lay strokes on it. The store writes the answer back on the blocks as
// `primvars:st` (faceVarying, one per triangle corner), so the paint pictures show in Quick (Storm) and Final (Cycles).
//
// CLS1 (little-endian): char[4] "CLS1", u32 version (1), u32 size, u32 nPoints, u32 nTris, u32 nBlocks,
// f32 points[3 nPoints] (clay space, welded), f32 normals[3 nPoints], i32 tris[3 nTris] (into points),
// f32 uv[6 nTris] (per triangle corner, 0..1, t up, as st), i32 blocks[4 nBlocks] (x, y, z, triangle count).
// The triangles are the blocks', in this block order (BlockKey order), each block's in its own order.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/vt/array.h>
#include <pxr/base/vt/types.h>

#include "clay_mesh.h"

namespace r3d::clay {

struct SurfaceBlock {  // a full-detail block as drawn (Blocks::get)
  BlockKey key;
  PXR_NS::VtVec3fArray points, normals;
  PXR_NS::VtIntArray indices;  // 3 per triangle
};

// the blocks' points joined where they sit at exactly the same place (a seam's two sides are bit-identical): the
// blocks in their order, each block's triangles in its own order (`tris`: their total, to reserve). Also the Cycles
// whole (clay_whole.h). Throws r3d::Error naming `where` when a block names a point it doesn't have.
struct Welded {
  std::vector<float> points, normals;  // xyz each
  std::vector<int32_t> tris;           // 3 per triangle, into points
};
Welded weld(const std::vector<SurfaceBlock>& blocks, uint64_t tris, const std::string& where);

struct SurfaceStats {
  bool made = false;  // false: read from the file
  size_t points = 0, triangles = 0;
  int charts = 0;
  double weldMs = 0, unfoldMs = 0, fileMs = 0;
};

// The st of each block (one per triangle corner, as `blocks`), read from `file` when it holds exactly these blocks
// (their keys and triangle counts) at `size`, else made (weld, unfold) and written there (`.partial` then renamed,
// its folder made). Blocks must be in BlockKey order. Throws r3d::Error naming `where` ("<item>.paint") and its
// `.file` / `.size` when the file can't be written or the surface can't be unfolded.
std::vector<PXR_NS::VtVec2fArray> clay_surface(const std::vector<SurfaceBlock>& blocks, int size,
                                               const std::string& file, const std::string& where,
                                               SurfaceStats* stats = nullptr);

}  // namespace r3d::clay
