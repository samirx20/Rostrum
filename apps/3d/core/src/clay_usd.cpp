// Clay: block Mesh prims in the clay layer (clay_usd.h). Moved from proofs/3d-clay (view.cpp View::set_block).
#include "clay_usd.h"

#include <pxr/base/gf/vec3f.h>
#include <pxr/base/tf/errorMark.h>
#include <pxr/base/vt/array.h>
#include <pxr/usd/sdf/attributeSpec.h>
#include <pxr/usd/sdf/changeBlock.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/sdf/schema.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usdGeom/tokens.h>

#include <algorithm>
#include <cfloat>
#include <cstring>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::clay {

namespace {
// The mask, shown (CL2b): masked clay drawn darker, by up to kMaskDarken at mask 1. Written per vertex as
// `primvars:rostrumMaskShade` (1 - kMaskDarken * mask), which every material's Storm network reads into its
// UsdPreviewSurface `occlusion` (materials.cpp; it scales all light, direct and indirect), and as
// `primvars:displayColor` (Storm's 0.5 grey times the same), what Storm draws a clay with no material with. Cycles'
// networks don't read the shade, so Final renders don't show the mask. A block with no mask near it has neither.
constexpr float kMaskDarken = 0.6f;
constexpr float kNoMaterialGrey = 0.5f;  // Storm's colour for a mesh with no material and no displayColor
const char* const kShade = "primvars:rostrumMaskShade";
const char* const kDisplayColor = "primvars:displayColor";
const char* const kSt = "primvars:st";  // 3d-cl4: a painted clay's unfolding (clay_surface.h)

std::string coord(int v) { return v < 0 ? "n" + std::to_string(-v) : std::to_string(v); }
TfToken block_name(const BlockKey& k) { return TfToken("clay_" + coord(k.x) + "_" + coord(k.y) + "_" + coord(k.z)); }

// a block's st taken off (it changed: its unfolding no longer fits it)
void drop_st(const SdfLayerHandle& layer, const SdfPath& prim) {
  if (SdfAttributeSpecHandle a = layer->GetAttributeAtPath(prim.AppendProperty(TfToken(kSt))))
    layer->GetPrimAtPath(prim)->RemoveProperty(a);
}

void check(const TfErrorMark& mark, const std::string& where) {
  if (mark.IsClean()) return;
  std::string msg;
  for (auto it = mark.GetBegin(); it != mark.GetEnd(); ++it) msg += (msg.empty() ? "" : "; ") + it->GetCommentary();
  throw Error("clay: " + where + ": USD reported: " + msg);
}
}  // namespace

struct Blocks::Impl {
  UsdStageRefPtr stage;
  SdfLayerRefPtr layer;  // held here: an anonymous layer lives as long as someone holds it
  std::optional<SdfChangeBlock> changes;
};


Blocks::Blocks(const UsdStageRefPtr& stage) : p_(new Impl) {
  p_->stage = stage;
  p_->layer = SdfLayer::CreateAnonymous("rostrum-clay");
  stage->GetSessionLayer()->InsertSubLayerPath(p_->layer->GetIdentifier());
}

Blocks::~Blocks() {
  p_->changes.reset();
  if (p_->stage) {
    SdfLayerHandle session = p_->stage->GetSessionLayer();
    const std::vector<std::string> paths = session->GetSubLayerPaths();
    for (size_t i = 0; i < paths.size(); ++i)
      if (paths[i] == p_->layer->GetIdentifier()) {
        session->RemoveSubLayerPath(int(i));
        break;
      }
  }
  delete p_;
}

void Blocks::begin() {
  if (!p_->changes) p_->changes.emplace();
}

void Blocks::end() { p_->changes.reset(); }

void Blocks::set(const SdfPath& clay, const BlockKey& key, const BlockMesh& m, std::set<BlockKey>& have) {
  TfErrorMark mark;
  const SdfLayerHandle layer = p_->layer;
  const SdfPath path = clay.AppendChild(block_name(key));
  const bool exists = have.count(key) != 0;
  const auto attr = [&](const char* name) { return path.AppendProperty(TfToken(name)); };
  if (exists) drop_st(layer, path);
  if (m.empty()) {
    // An emptied block keeps its prim (3d-v4): a prim removed or added makes Storm rebuild its draw batches
    // (rebuildBatches; 15-25 ms when a stroke's preview took 8 fine blocks down for each of its own), and the same
    // block is often filled again soon (the fine blocks come back at the stroke's end). It holds one triangle of no
    // area, which draws nothing: with no points at all Storm asked GL for buffers of size 0 (GL_INVALID_VALUE, and
    // the view was refused)
    if (!exists) return;
    const TfToken& dflt = SdfFieldKeys->Default;
    GfVec3f at(0.0f);  // where the block was (its old extent's corner), so bounds and framing don't move
    const VtValue was = layer->GetField(attr("extent"), dflt);
    if (was.IsHolding<VtVec3fArray>() && !was.UncheckedGet<VtVec3fArray>().empty())
      at = was.UncheckedGet<VtVec3fArray>()[0];
    layer->SetField(attr("points"), dflt, VtValue(VtVec3fArray{at, at, at}));
    layer->SetField(attr("normals"), dflt, VtValue(VtVec3fArray(3, GfVec3f(0, 0, 1))));
    layer->SetField(attr("faceVertexCounts"), dflt, VtValue(VtIntArray{3}));
    layer->SetField(attr("faceVertexIndices"), dflt, VtValue(VtIntArray{0, 1, 2}));
    layer->SetField(attr("extent"), dflt, VtValue(VtVec3fArray{at, at}));
    if (layer->HasSpec(attr(kShade))) {
      SdfPrimSpecHandle prim = layer->GetPrimAtPath(path);
      for (const SdfPath& q : {attr(kShade), attr(kDisplayColor)})
        if (SdfAttributeSpecHandle a = layer->GetAttributeAtPath(q)) prim->RemoveProperty(a);
    }
    check(mark, "emptying " + path.GetString());
    return;
  }
  if (!exists) {  // a new prim: its specs, the uniform values once
    SdfPrimSpecHandle parent = SdfCreatePrimInLayer(layer, clay);  // `over` specs down to the clay's Xform
    SdfPrimSpecHandle prim = SdfPrimSpec::New(parent, path.GetName(), SdfSpecifierDef, "Mesh");
    if (!prim) throw Error("clay: could not create " + path.GetString());
    SdfAttributeSpec::New(prim, "points", SdfValueTypeNames->Point3fArray);
    SdfAttributeSpecHandle normals = SdfAttributeSpec::New(prim, "normals", SdfValueTypeNames->Normal3fArray);
    normals->SetInfo(UsdGeomTokens->interpolation, VtValue(UsdGeomTokens->vertex));
    SdfAttributeSpec::New(prim, "faceVertexCounts", SdfValueTypeNames->IntArray);
    SdfAttributeSpec::New(prim, "faceVertexIndices", SdfValueTypeNames->IntArray);
    SdfAttributeSpec::New(prim, "extent", SdfValueTypeNames->Float3Array);
    SdfAttributeSpec::New(prim, "subdivisionScheme", SdfValueTypeNames->Token, SdfVariabilityUniform)
        ->SetDefaultValue(VtValue(UsdGeomTokens->none));
    SdfAttributeSpec::New(prim, "doubleSided", SdfValueTypeNames->Bool, SdfVariabilityUniform)
        ->SetDefaultValue(VtValue(false));
    have.insert(key);
  }
  const size_t nv = m.points.size() / 3, nt = m.triangles();
  VtVec3fArray pts(nv), nrm(nv);
  std::memcpy(pts.data(), m.points.data(), nv * sizeof(GfVec3f));
  std::memcpy(nrm.data(), m.normals.data(), std::min(m.normals.size() / 3, nv) * sizeof(GfVec3f));
  VtIntArray idx(nt * 3), counts(nt, 3);
  std::memcpy(idx.data(), m.indices.data(), nt * 3 * sizeof(int32_t));
  GfVec3f lo(FLT_MAX), hi(-FLT_MAX);
  for (size_t i = 0; i < nv; ++i)
    for (int c = 0; c < 3; ++c) lo[c] = std::min(lo[c], pts[i][c]), hi[c] = std::max(hi[c], pts[i][c]);
  VtVec3fArray extent{lo, hi};
  const TfToken& dflt = SdfFieldKeys->Default;
  layer->SetField(attr("points"), dflt, VtValue::Take(pts));
  layer->SetField(attr("normals"), dflt, VtValue::Take(nrm));
  layer->SetField(attr("faceVertexCounts"), dflt, VtValue::Take(counts));
  layer->SetField(attr("faceVertexIndices"), dflt, VtValue::Take(idx));
  layer->SetField(attr("extent"), dflt, VtValue::Take(extent));

  const SdfPath shadePath = attr(kShade), colorPath = attr(kDisplayColor);
  if (m.mask.size() == nv) {
    if (!layer->HasSpec(shadePath)) {
      SdfPrimSpecHandle prim = layer->GetPrimAtPath(path);
      SdfAttributeSpec::New(prim, kShade, SdfValueTypeNames->FloatArray)
          ->SetInfo(UsdGeomTokens->interpolation, VtValue(UsdGeomTokens->vertex));
      SdfAttributeSpec::New(prim, kDisplayColor, SdfValueTypeNames->Color3fArray)
          ->SetInfo(UsdGeomTokens->interpolation, VtValue(UsdGeomTokens->vertex));
    }
    VtFloatArray shade(nv);
    VtVec3fArray color(nv);
    for (size_t i = 0; i < nv; ++i) {
      const float s = 1.0f - kMaskDarken * std::clamp(m.mask[i], 0.0f, 1.0f);
      shade[i] = s;
      color[i] = GfVec3f(kNoMaterialGrey * s);
    }
    layer->SetField(shadePath, dflt, VtValue::Take(shade));
    layer->SetField(colorPath, dflt, VtValue::Take(color));
  } else if (layer->HasSpec(shadePath)) {  // the mask left this block: back to the plain clay
    SdfPrimSpecHandle prim = layer->GetPrimAtPath(path);
    for (const SdfPath& q : {shadePath, colorPath})
      if (SdfAttributeSpecHandle a = layer->GetAttributeAtPath(q)) prim->RemoveProperty(a);
  }
  check(mark, "writing " + path.GetString());
}

void Blocks::remove_all(const SdfPath& clay, std::set<BlockKey>& have) {
  TfErrorMark mark;
  const SdfLayerHandle layer = p_->layer;
  if (SdfPrimSpecHandle spec = layer->GetPrimAtPath(clay)) {
    const SdfPath parentPath = clay.GetParentPath();
    if (SdfPrimSpecHandle parent = layer->GetPrimAtPath(parentPath)) parent->RemoveNameChild(spec);
    else layer->RemoveRootPrim(spec);
  }
  have.clear();
  check(mark, "removing the blocks of " + clay.GetString());
}

bool Blocks::get(const SdfPath& clay, const BlockKey& key, VtVec3fArray& points, VtVec3fArray& normals,
                 VtIntArray& indices) const {
  const SdfLayerHandle layer = p_->layer;
  const SdfPath path = clay.AppendChild(block_name(key));
  const TfToken& dflt = SdfFieldKeys->Default;
  const VtValue p = layer->GetField(path.AppendProperty(TfToken("points")), dflt);
  const VtValue n = layer->GetField(path.AppendProperty(TfToken("normals")), dflt);
  const VtValue i = layer->GetField(path.AppendProperty(TfToken("faceVertexIndices")), dflt);
  if (!p.IsHolding<VtVec3fArray>() || !n.IsHolding<VtVec3fArray>() || !i.IsHolding<VtIntArray>()) return false;
  points = p.UncheckedGet<VtVec3fArray>();
  normals = n.UncheckedGet<VtVec3fArray>();
  indices = i.UncheckedGet<VtIntArray>();
  // an emptied block (set): one triangle of no area, its 3 points the same
  if (indices.size() == 3 && points.size() == 3 && points[0] == points[1] && points[1] == points[2]) return false;
  return !indices.empty();
}

bool Blocks::has_st(const SdfPath& clay, const BlockKey& key) const {
  return p_->layer->HasSpec(clay.AppendChild(block_name(key)).AppendProperty(TfToken(kSt)));
}

void Blocks::set_st(const SdfPath& clay, const BlockKey& key, VtVec2fArray st) {
  TfErrorMark mark;
  const SdfLayerHandle layer = p_->layer;
  const SdfPath path = clay.AppendChild(block_name(key));
  const SdfPath stPath = path.AppendProperty(TfToken(kSt));
  if (!layer->HasSpec(stPath)) {
    SdfPrimSpecHandle prim = layer->GetPrimAtPath(path);
    if (!prim) throw Error("clay: no block " + path.GetString() + " to unfold");
    SdfAttributeSpec::New(prim, kSt, SdfValueTypeNames->TexCoord2fArray)
        ->SetInfo(UsdGeomTokens->interpolation, VtValue(UsdGeomTokens->faceVarying));
  }
  layer->SetField(stPath, SdfFieldKeys->Default, VtValue::Take(st));
  check(mark, "writing the unfolding of " + path.GetString());
}

void Blocks::clear_st(const SdfPath& clay, const BlockKey& key) {
  TfErrorMark mark;
  const SdfPath path = clay.AppendChild(block_name(key));
  drop_st(p_->layer, path);
  check(mark, "taking the unfolding off " + path.GetString());
}

}  // namespace r3d::clay
