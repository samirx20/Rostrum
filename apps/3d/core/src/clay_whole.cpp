// Clay: the Cycles whole (clay_whole.h).
#include "clay_whole.h"

#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/imaging/hd/filteringSceneIndex.h>
#include <pxr/imaging/hd/overlayContainerDataSource.h>
#include <pxr/imaging/hd/retainedDataSource.h>
#include <pxr/imaging/hd/sceneIndexPluginRegistry.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hd/visibilitySchema.h>
#include <pxr/usd/sdf/attributeSpec.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/sdf/schema.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usdGeom/tokens.h>

#include <algorithm>
#include <cfloat>
#include <cstring>
#include <set>

#include "clay_usd.h"
#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::clay {

const char* const kWhole = "whole";
const char* const kWholePainted = "whole_painted";

bool is_whole(const std::string& name) { return name == kWhole || name == kWholePainted; }

void write_whole(const SdfLayerHandle& layer, const SdfPath& clay, const char* name,
                 const std::vector<SurfaceBlock>& blocks, const std::vector<VtVec2fArray>* st,
                 const std::string& where) {
  const SdfPath path = clay.AppendChild(TfToken(name));
  if (blocks.empty()) {
    if (SdfPrimSpecHandle spec = layer->GetPrimAtPath(path)) layer->GetPrimAtPath(clay)->RemoveNameChild(spec);
    return;
  }
  uint64_t tris = 0;
  for (const SurfaceBlock& b : blocks) tris += b.indices.size() / 3;
  const Welded w = weld(blocks, tris, where);
  const auto attr = [&](const char* a) { return path.AppendProperty(TfToken(a)); };
  if (!layer->GetPrimAtPath(path)) {  // as a block's specs (clay_usd.cpp Blocks::set), and invisible
    SdfPrimSpecHandle parent = SdfCreatePrimInLayer(layer, clay);
    SdfPrimSpecHandle prim = SdfPrimSpec::New(parent, name, SdfSpecifierDef, "Mesh");
    if (!prim) throw Error("clay: could not create " + path.GetString());
    SdfAttributeSpec::New(prim, "points", SdfValueTypeNames->Point3fArray);
    SdfAttributeSpec::New(prim, "normals", SdfValueTypeNames->Normal3fArray)
        ->SetInfo(UsdGeomTokens->interpolation, VtValue(UsdGeomTokens->vertex));
    SdfAttributeSpec::New(prim, "faceVertexCounts", SdfValueTypeNames->IntArray);
    SdfAttributeSpec::New(prim, "faceVertexIndices", SdfValueTypeNames->IntArray);
    SdfAttributeSpec::New(prim, "extent", SdfValueTypeNames->Float3Array);
    SdfAttributeSpec::New(prim, "subdivisionScheme", SdfValueTypeNames->Token, SdfVariabilityUniform)
        ->SetDefaultValue(VtValue(UsdGeomTokens->none));
    SdfAttributeSpec::New(prim, "doubleSided", SdfValueTypeNames->Bool, SdfVariabilityUniform)
        ->SetDefaultValue(VtValue(false));
    SdfAttributeSpec::New(prim, "visibility", SdfValueTypeNames->Token)
        ->SetDefaultValue(VtValue(UsdGeomTokens->invisible));
  }
  const size_t nv = w.points.size() / 3, nt = w.tris.size() / 3;
  VtVec3fArray pts(nv), nrm(nv);
  std::memcpy(pts.data(), w.points.data(), nv * sizeof(GfVec3f));
  std::memcpy(nrm.data(), w.normals.data(), nv * sizeof(GfVec3f));
  VtIntArray idx(w.tris.begin(), w.tris.end()), counts(nt, 3);
  GfVec3f lo(FLT_MAX), hi(-FLT_MAX);
  for (const GfVec3f& p : pts)
    for (int c = 0; c < 3; ++c) lo[c] = std::min(lo[c], p[c]), hi[c] = std::max(hi[c], p[c]);
  const TfToken& dflt = SdfFieldKeys->Default;
  layer->SetField(attr("points"), dflt, VtValue::Take(pts));
  layer->SetField(attr("normals"), dflt, VtValue::Take(nrm));
  layer->SetField(attr("faceVertexCounts"), dflt, VtValue::Take(counts));
  layer->SetField(attr("faceVertexIndices"), dflt, VtValue::Take(idx));
  layer->SetField(attr("extent"), dflt, VtValue(VtVec3fArray{lo, hi}));
  const SdfPath stPath = attr("primvars:st");
  if (st) {  // the blocks' st one after another: weld keeps the blocks' triangles in this order
    VtVec2fArray all(size_t(3 * tris));
    GfVec2f* to = all.data();
    for (const VtVec2fArray& s : *st) to = std::copy(s.cdata(), s.cdata() + s.size(), to);
    if (!layer->HasSpec(stPath))
      SdfAttributeSpec::New(layer->GetPrimAtPath(path), "primvars:st", SdfValueTypeNames->TexCoord2fArray)
          ->SetInfo(UsdGeomTokens->interpolation, VtValue(UsdGeomTokens->faceVarying));
    layer->SetField(stPath, dflt, VtValue::Take(all));
  } else if (SdfAttributeSpecHandle a = layer->GetAttributeAtPath(stPath)) {
    layer->GetPrimAtPath(path)->RemoveProperty(a);
  }
}

namespace {

using B = HdRetainedTypedSampledDataSource<bool>;

HdSceneIndexPrim with_visibility(HdSceneIndexPrim prim, bool visible) {
  prim.dataSource = HdOverlayContainerDataSource::New(
      HdRetainedContainerDataSource::New(HdVisibilitySchemaTokens->visibility,
                                         HdVisibilitySchema::BuildRetained(B::New(visible))),
      prim.dataSource);
  return prim;
}

class ClayWhole final : public HdSingleInputFilteringSceneIndexBase {
 public:
  static HdSceneIndexBaseRefPtr New(const HdSceneIndexBaseRefPtr& in) { return TfCreateRefPtr(new ClayWhole(in)); }

  HdSceneIndexPrim GetPrim(const SdfPath& path) const override {
    HdSceneIndexPrim prim = _GetInputSceneIndex()->GetPrim(path);
    if (!prim.dataSource || prim.primType != HdPrimTypeTokens->mesh) return prim;
    const std::string name = path.GetName();
    BlockKey k;
    if (is_whole(name)) return with_visibility(prim, visible(path.GetParentPath()));  // the clay's own visibility
    if (block_key_of(name, k) && has_whole(path.GetParentPath())) return with_visibility(prim, false);
    return prim;
  }
  SdfPathVector GetChildPrimPaths(const SdfPath& path) const override {
    return _GetInputSceneIndex()->GetChildPrimPaths(path);
  }

 protected:
  void _PrimsAdded(const HdSceneIndexBase&, const HdSceneIndexObserver::AddedPrimEntries& e) override {
    _SendPrimsAdded(e);
    std::set<SdfPath> clays;
    for (const auto& x : e)
      if (is_whole(x.primPath.GetName())) clays.insert(x.primPath.GetParentPath());
    blocks_changed(clays);
  }
  void _PrimsRemoved(const HdSceneIndexBase&, const HdSceneIndexObserver::RemovedPrimEntries& e) override {
    _SendPrimsRemoved(e);
    std::set<SdfPath> clays;
    for (const auto& x : e)
      if (is_whole(x.primPath.GetName())) clays.insert(x.primPath.GetParentPath());
    blocks_changed(clays);
  }
  void _PrimsDirtied(const HdSceneIndexBase&, const HdSceneIndexObserver::DirtiedPrimEntries& e) override {
    _SendPrimsDirtied(e);  // a hidden item: its flattened visibility dirties the whole too, read again from the clay
  }

 private:
  explicit ClayWhole(const HdSceneIndexBaseRefPtr& in) : HdSingleInputFilteringSceneIndexBase(in) {}

  bool has_whole(const SdfPath& clay) const {
    for (const char* n : {kWhole, kWholePainted})
      if (_GetInputSceneIndex()->GetPrim(clay.AppendChild(TfToken(n))).primType == HdPrimTypeTokens->mesh) return true;
    return false;
  }
  bool visible(const SdfPath& clay) const {
    const HdSceneIndexPrim p = _GetInputSceneIndex()->GetPrim(clay);
    if (!p.dataSource) return true;
    const HdBoolDataSourceHandle v = HdVisibilitySchema::GetFromParent(p.dataSource).GetVisibility();
    return !v || v->GetTypedValue(0.0f);
  }
  // a whole came or went: the clay's blocks show or hide in Cycles
  void blocks_changed(const std::set<SdfPath>& clays) {
    HdSceneIndexObserver::DirtiedPrimEntries dirty;
    BlockKey k;
    for (const SdfPath& clay : clays)
      for (const SdfPath& child : _GetInputSceneIndex()->GetChildPrimPaths(clay))
        if (block_key_of(child.GetName(), k))
          dirty.emplace_back(child, HdDataSourceLocatorSet{HdVisibilitySchema::GetDefaultLocator()});
    if (!dirty.empty()) _SendPrimsDirtied(dirty);
  }
};

}  // namespace

void register_cycles_clay_whole() {
  static const bool once = [] {
    HdSceneIndexPluginRegistry::GetInstance().RegisterSceneIndexForRenderer(
        "Cycles",
        [](const std::string&, const HdSceneIndexBaseRefPtr& in, const HdContainerDataSourceHandle&) {
          return ClayWhole::New(in);
        },
        nullptr, 0, HdSceneIndexPluginRegistry::InsertionOrderAtStart);
    return true;
  }();
  (void)once;
}

}  // namespace r3d::clay
