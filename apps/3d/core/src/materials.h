// Scene materials (ENGINE_CONTRACT.md § 2, Materials) -> /World/Looks/<id>: Cycles' principled_bsdf on
// outputs:cycles:surface (what Cycles' Hydra plug-in reads) and a UsdPreviewSurface on outputs:surface
// (Storm and other USD programs).
#pragma once
#include <set>
#include <string>

#include <pxr/base/js/value.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

namespace r3d {

PXR_NS::SdfPath material_path(const std::string& id);

// Defines every material of scene["materials"]; returns their ids. Throws r3d::Error naming "<id>.<field>".
// start..end: the shot's frames (a material's `anim.emissionTexture` holds one image per frame).
std::set<std::string> build_materials(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::JsArray& materials,
                                      int start, int end);

// An image path from the scene: "" or an absolute path to a file that exists, else r3d::Error at `where`.
void check_file(const std::string& path, const std::string& where, const char* what);

}  // namespace r3d
