// Scene materials (ENGINE_CONTRACT.md § 2, Materials) -> /World/Looks/<id>: Cycles' principled_bsdf on
// outputs:cycles:surface (what Cycles' Hydra plug-in reads) and a UsdPreviewSurface on outputs:surface
// (Storm and other USD programs), and the Stylized look's rostrum_stylized shader on outputs:rostrum:surface
// (material_stylized.h); Light to colour rewires the Cycles surface after the lights (light_to_color.h).
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

// The live `material` request (material_request.cpp). rebuild_material: material `id` (props whole, as in a scene)
// built on a stage of its own (a problem throws and leaves `stage` as it was), its light-to-colour graph made from
// `stage`'s lights, then put in place of the held one in one change. restyle_material: only the Lines / Halftone
// inputs of its Stylized shader set (a line-width drag: no shader of Storm or Cycles changes).
void rebuild_material(const PXR_NS::UsdStageRefPtr& stage, const std::string& id, const PXR_NS::JsObject& props,
                      const PXR_NS::JsObject* anim, int start, int end);
void restyle_material(const PXR_NS::UsdStageRefPtr& stage, const std::string& id, const PXR_NS::JsObject& props);

// An image path from the scene: "" or an absolute path to a file that exists, else r3d::Error at `where`.
void check_file(const std::string& path, const std::string& where, const char* what);

// A material picture (v1.34): check_file, or a UDIM set (`<UDIM>` in the name, udim.h) with at least one tile there.
void check_picture(const std::string& path, const std::string& where);

}  // namespace r3d
