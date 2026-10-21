#include "inspect.h"

#include <pxr/base/tf/errorMark.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/bboxCache.h>
#include <pxr/usd/usdGeom/metrics.h>
#include <pxr/usd/usdShade/materialBindingAPI.h>

#include <filesystem>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
JsArray vec(const GfVec3d& v) { return JsArray{JsValue(v[0]), JsValue(v[1]), JsValue(v[2])}; }
constexpr size_t kMaxPrims = 2000;
}  // namespace

std::string material_of(const UsdStageRefPtr& stage, const SdfPath& path) {
  UsdPrim prim = stage->GetPrimAtPath(path);
  if (!prim) return "";
  UsdShadeMaterial m = UsdShadeMaterialBindingAPI(prim).ComputeBoundMaterial();
  return m ? m.GetPrim().GetName().GetString() : "";
}

std::string item_of(const UsdStageRefPtr& stage, const SdfPath& path) {
  const auto& layer = stage->GetRootLayer();
  for (SdfPath p = path; p.GetPathElementCount() > 1; p = p.GetParentPath()) {  // /World itself is no item
    SdfPrimSpecHandle spec = layer->GetPrimAtPath(p);
    if (spec && spec->GetSpecifier() == SdfSpecifierDef) return p.GetName();
  }
  return "";
}

SdfPath item_path(const UsdStageRefPtr& stage, const std::string& id) {
  const auto& layer = stage->GetRootLayer();
  for (UsdPrim p : stage->Traverse()) {
    if (p.GetName() != id) continue;
    SdfPrimSpecHandle spec = layer->GetPrimAtPath(p.GetPath());
    if (spec && spec->GetSpecifier() == SdfSpecifierDef && p.GetPath().GetPathElementCount() > 1) return p.GetPath();
  }
  return SdfPath();
}

JsObject inspect_usd(const std::string& file) {
  if (!std::filesystem::exists(file)) throw Error("inspect_usd.file: no file " + file);
  TfErrorMark mark;
  UsdStageRefPtr s = UsdStage::Open(file);
  if (!s || !mark.IsClean()) throw Error("inspect_usd.file: USD could not open " + file);
  UsdGeomBBoxCache bbox(UsdTimeCode::Default(), {UsdGeomTokens->default_, UsdGeomTokens->render});
  JsArray prims;
  bool truncated = false;
  for (UsdPrim p : s->Traverse()) {
    if (prims.size() >= kMaxPrims) { truncated = true; break; }
    JsObject o{{"path", JsValue(p.GetPath().GetString())}, {"type", JsValue(p.GetTypeName().GetString())},
               {"material", JsValue(material_of(s, p.GetPath()))}};
    if (p.IsA<UsdGeomImageable>()) {
      GfRange3d r = bbox.ComputeWorldBound(p).ComputeAlignedRange();
      if (!r.IsEmpty()) o["bounds"] = JsArray{JsValue(vec(r.GetMin())), JsValue(vec(r.GetMax()))};
    }
    prims.push_back(JsValue(o));
  }
  UsdPrim def = s->GetDefaultPrim();
  return JsObject{{"ok", JsValue(true)},
                  {"defaultPrim", JsValue(def ? def.GetPath().GetString() : std::string())},
                  {"upAxis", JsValue(UsdGeomGetStageUpAxis(s).GetString())},
                  {"metersPerUnit", JsValue(UsdGeomGetStageMetersPerUnit(s))},
                  {"prims", JsValue(prims)},
                  {"truncated", JsValue(truncated)}};
}

void save_stage(const UsdStageRefPtr& stage, const std::string& file, bool flatten) {
  TfErrorMark mark;
  const bool ok = flatten ? stage->Export(file) : stage->GetRootLayer()->Export(file);
  if (!ok || !mark.IsClean()) throw Error("save.file: could not write " + file);
}

}  // namespace r3d
