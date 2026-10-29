// Clay: a block prim as Storm draws it, a slot of fixed size (3d-dab-viewer). A dab re-sent ~35-50 prims whose
// point and triangle counts changed every time; Storm then gave each a new place in its shared graphics buffers,
// moved the buffers' other contents along (~130 copies on the card a dab), made a new index list per block (each
// block's own triangles) and rebuilt its draw batches: ~7.5 ms of a dab's drawing, 40-60 ms on a stroke's first.
// So a block prim holds its triangles one after another, each with its own 3 corners ("triangle soup"):
//  - its face lists are the same for every prim of a size (0 1 2 3 4 5 ...: one shared index list in Storm, written
//    only when the slot grows), and its points and normals keep their count while the block's surface changes, so
//    Storm copies the new values into the same place (no move, no new list, no rebuilt batch);
//  - a slot holds `cap` triangles; those past the surface's own sit on one point (no area, nothing drawn); it grows
//    with room to spare (slot_capacity) and never shrinks, so an emptied block keeps its place for when it fills;
//  - triangle i of the prim is triangle i of the surface (a picked face is the block's own), and a faceVarying st
//    lines up with the corners.
// The block's own surface (shared points, 3 indices per triangle) stays with the Blocks (Slot), for get(), the
// skinning and the Cycles whole; the stage holds only what Storm draws (Cycles draws the whole, clay_whole.h).
// ROSTRUM3D_CLAY_SLOTS=0 draws the blocks as before (shared points, sized to the surface): an A/B on one build.
#pragma once
#include <cstddef>

#include <pxr/base/gf/vec3f.h>
#include <pxr/base/vt/array.h>
#include <pxr/base/vt/types.h>

namespace r3d::clay {

bool slots_on();

struct Slot {
  PXR_NS::VtVec3fArray points, normals;  // the block's surface at rest, one per vertex
  PXR_NS::VtIntArray indices;            // 3 per triangle
  PXR_NS::VtVec3fArray shownPoints, shownNormals;  // as last drawn (posed, for a skinned clay)
  size_t cap = 0;                        // triangles the prim holds (0: not drawn yet)
  PXR_NS::GfVec3f at{0.0f};              // where an empty block's triangles sit (so bounds and framing don't move)
  size_t triangles() const { return indices.size() / 3; }
};

// the slot's size for `n` triangles: the next of 64, 96, 128, 192, 256, ... with a quarter to spare, at least
// kPreviewSlot for a live stroke's preview part (made ahead, empty, by the store's ring: its first fill mid-stroke
// must not grow it) and kBlockSlot for a block
constexpr size_t kPreviewSlot = 1024, kBlockSlot = 128;
size_t slot_capacity(size_t n, bool preview);
// the face lists of a slot of `cap` triangles (shared arrays: one per size)
PXR_NS::VtIntArray slot_counts(size_t cap);
PXR_NS::VtIntArray slot_indices(size_t cap);
// per-vertex values `v` spread to the corners of `indices`' triangles, then `pad` to 3 * cap
PXR_NS::VtVec3fArray slot_corners(const PXR_NS::VtVec3fArray& v, const PXR_NS::VtIntArray& indices, size_t cap,
                                  const PXR_NS::GfVec3f& pad);
PXR_NS::VtFloatArray slot_corners(const PXR_NS::VtFloatArray& v, const PXR_NS::VtIntArray& indices, size_t cap,
                                  float pad);
// per-corner values (faceVarying) padded to 3 * cap
PXR_NS::VtVec2fArray slot_padded(const PXR_NS::VtVec2fArray& st, size_t cap);

}  // namespace r3d::clay
