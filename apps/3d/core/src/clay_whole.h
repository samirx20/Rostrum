// Clay: the Cycles whole (CL6). Cycles' light under the surface (random walk) only stays inside one closed mesh: a
// clay drawn as its 32³ block prims (clay_usd.h), each an open piece, let the walk out at every block's edge (the
// head looked see-through, the block borders a dark cross). So each clay also gets ONE welded closed mesh beside its
// blocks, made from the blocks exactly as drawn (posed too) with the paint weld (clay_surface.h `weld`):
//   <clay>/whole          the blocks with no paint unfolding (st), welded
//   <clay>/whole_painted  the blocks with one, welded, their st per triangle corner (faceVarying)
// Both are authored invisible, so Storm, the stylized look and pick see only the blocks, exactly as before. A Hydra
// filter in front of Cycles alone shows them (with the clay's own visibility) and hides the clay's block prims while
// a whole sits beside them. The store re-welds a clay only when a Cycles draw is next and its blocks changed since
// (Store::whole_for_cycles), so sculpting in the Quick view never pays for it.
#pragma once
#include <string>
#include <vector>

#include <pxr/base/vt/types.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/path.h>

#include "clay_surface.h"

namespace r3d::clay {

extern const char* const kWhole;
extern const char* const kWholePainted;
bool is_whole(const std::string& name);

// `<clay>/<name>` in `layer` made the welded `blocks` (removed when there are none); `st`: one array per block, one
// value per triangle corner (null: no st). Between Blocks::begin() and end(). Throws r3d::Error naming `where`.
void write_whole(const PXR_NS::SdfLayerHandle& layer, const PXR_NS::SdfPath& clay, const char* name,
                 const std::vector<SurfaceBlock>& blocks, const std::vector<PXR_NS::VtVec2fArray>* st,
                 const std::string& where);

// register the filter for Hydra's "Cycles" renderer; call once, before any Cycles engine is made
void register_cycles_clay_whole();

}  // namespace r3d::clay
