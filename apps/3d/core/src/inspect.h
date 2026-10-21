// Read-only facts: what a USD file holds (for imports), which item / material a prim belongs to,
// and saving the built stage as a hand-off file.
#pragma once
#include <pxr/base/js/value.h>
#include <pxr/usd/usd/stage.h>

#include <string>

namespace r3d {

PXR_NS::JsObject inspect_usd(const std::string& file);
// the document item a prim belongs to: the deepest prim on its path that our layer defines (an import's
// parts are only overridden, so they lead back to the import item)
std::string item_of(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& prim);
// the prim of a document item by id (ids are unique prim names our layer defines); empty when there is none
PXR_NS::SdfPath item_path(const PXR_NS::UsdStageRefPtr& stage, const std::string& id);
std::string material_of(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& prim);
void save_stage(const PXR_NS::UsdStageRefPtr& stage, const std::string& file, bool flatten);

}  // namespace r3d
