// UDIM sets inside a USD file brought in by reference (contract v1.34): Storm finds a `<UDIM>` texture's tiles by
// itself, Cycles loads only the tiles its texture node lists. So after an import is referenced, each `UsdUVTexture`
// under it whose `inputs:file` is a `<UDIM>` set and which lists no `inputs:tiles` gets them as an override in our
// layer (the file itself is never rewritten): the tiles found next to the path, resolved against the layer that
// wrote it.
#pragma once
#include <pxr/usd/usd/prim.h>

namespace r3d::udim {

// How many texture nodes under `root` were given their tiles.
int list_tiles_under(const PXR_NS::UsdPrim& root);

}  // namespace r3d::udim
