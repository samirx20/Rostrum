// A material's blocks (ENGINE_CONTRACT.md § Materials, Blocks): its MaterialX document, read with USD's MaterialX
// reader (usdMtlx), drawn by both renderers. Storm: the document's NG_blocks referenced under <material>/Blocks and an
// ND_UsdPreviewSurface_surfaceshader on outputs:mtlx:surface (Storm's MaterialX code draws the Rostrum blocks from their
// nodedefs' nodegraphs, apps/3d/core/mtlx/rostrum_blocks.mtlx). Cycles: each block as its own Cycles node, linked into
// the principled BSDF where the document's nodegraph outputs say.
#pragma once
#include <string>

#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdShade/shader.h>

namespace r3d {

// `file`: the absolute path of the material's document (props.blocks); `where`: "<id>.blocks" for errors.
// `preview`: the material's UsdPreviewSurface (its values are copied onto the MaterialX surface). Throws r3d::Error
// naming the block and what is wrong (an unreadable document, an unknown block, a wire to an input that isn't there).
void author_blocks(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& mat, const std::string& id,
                   const std::string& file, const std::string& where, PXR_NS::UsdShadeShader& bsdf,
                   PXR_NS::UsdShadeShader& preview);

}  // namespace r3d
