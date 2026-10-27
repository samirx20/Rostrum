#include "inspect.h"

#include <pxr/base/tf/errorMark.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/bboxCache.h>
#include <pxr/usd/usdGeom/metrics.h>
#include <pxr/usd/usdShade/materialBindingAPI.h>

#include <filesystem>

#include "convert.h"
#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
JsArray vec(const GfVec3d& v) { return JsArray{JsValue(v[0]), JsValue(v[1]), JsValue(v[2])}; }
constexpr size_t kMaxPrims = 2000;

// Whether the file says what its unit is: a converter marks the formats that don't (convert.h); a USD file
// without metersPerUnit authored doesn't either.
bool units_known(const UsdStageRefPtr& s) {
  const VtDictionary data = s->GetRootLayer()->GetCustomLayerData();
  const auto it = data.find("rostrum:unitsKnown");
  if (it != data.end() && it->second.IsHolding<bool>()) return it->second.UncheckedGet<bool>();
  return s->HasAuthoredMetadata(UsdGeomTokens->metersPerUnit);
}
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
  const Format* format = format_for(file);
  if (!is_usd(file) && !format) throw Error("inspect_usd.file: " + file + " is not " + accepted_files());
  TfErrorMark mark;
  UsdStageRefPtr s;
  if (format) {
    try {
      s = UsdStage::Open(converted_layer(file));
    } catch (const Error& e) {
      throw Error(std::string("inspect_usd.file: ") + e.what());
    }
  } else {
    s = UsdStage::Open(file);
  }
  if (!s || !mark.IsClean()) {
    std::string why;
    for (auto e = mark.GetBegin(); e != mark.GetEnd() && why.empty(); ++e) why = ": " + e->GetCommentary();
    throw Error("inspect_usd.file: USD could not open " + file + why);
  }
  // The earliest time: an animated file (Alembic) may have no values outside its samples.
  UsdGeomBBoxCache bbox(UsdTimeCode::EarliestTime(), {UsdGeomTokens->default_, UsdGeomTokens->render});
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
                  {"format", JsValue(format ? format->name : std::string("USD"))},
                  {"unitsKnown", JsValue(units_known(s))},
                  {"animated", JsValue(s->HasAuthoredTimeCodeRange())},
                  {"startFrame", JsValue(s->GetStartTimeCode())},
                  {"endFrame", JsValue(s->GetEndTimeCode())},
                  {"framesPerSecond", JsValue(s->GetTimeCodesPerSecond())},
                  {"prims", JsValue(prims)},
                  {"truncated", JsValue(truncated)}};
}

void save_stage(const UsdStageRefPtr& stage, const std::string& file, bool flatten) {
  TfErrorMark mark;
  const bool ok = flatten ? stage->Export(file) : stage->GetRootLayer()->Export(file);
  if (!ok || !mark.IsClean()) throw Error("save.file: could not write " + file);
}

}  // namespace r3d
