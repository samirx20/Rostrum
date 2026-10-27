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
#include <chrono>
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

VtVec3fArray extent_of(const VtVec3fArray& pts) {
  GfVec3f lo(FLT_MAX), hi(-FLT_MAX);
  for (const GfVec3f& p : pts)
    for (int c = 0; c < 3; ++c) lo[c] = std::min(lo[c], p[c]), hi[c] = std::max(hi[c], p[c]);
  if (pts.empty()) lo = hi = GfVec3f(0.0f);
  return VtVec3fArray{lo, hi};
}

// CL5: a skinned block's surface as drawn (its points, normals, extent)
void write_surface(const SdfLayerHandle& layer, const SdfPath& prim, VtVec3fArray pts, VtVec3fArray nrm,
                   VtVec3fArray extent) {
  const TfToken& dflt = SdfFieldKeys->Default;
  layer->SetField(prim.AppendProperty(TfToken("points")), dflt, VtValue::Take(pts));
  if (!nrm.empty()) layer->SetField(prim.AppendProperty(TfToken("normals")), dflt, VtValue::Take(nrm));
  layer->SetField(prim.AppendProperty(TfToken("extent")), dflt, VtValue::Take(extent));
}

void check(const TfErrorMark& mark, const std::string& where) {
  if (mark.IsClean()) return;
  std::string msg;
  for (auto it = mark.GetBegin(); it != mark.GetEnd(); ++it) msg += (msg.empty() ? "" : "; ") + it->GetCommentary();
  throw Error("clay: " + where + ": USD reported: " + msg);
}
}  // namespace

bool block_key_of(const std::string& name, BlockKey& key) {
  if (name.rfind("clay_", 0) != 0) return false;
  int v[3];
  size_t at = 5;
  for (int i = 0; i < 3; ++i) {
    const size_t end = name.find('_', at);
    if ((i < 2) != (end != std::string::npos)) return false;
    std::string part = name.substr(at, end == std::string::npos ? std::string::npos : end - at);
    const bool neg = !part.empty() && part[0] == 'n';
    if (neg) part.erase(0, 1);
    if (part.empty() || part.size() > 9 || part.find_first_not_of("0123456789") != std::string::npos) return false;
    v[i] = neg ? -std::stoi(part) : std::stoi(part);
    at = end + 1;
  }
  key = BlockKey{v[0], v[1], v[2]};
  return true;
}

struct Blocks::Impl {
  UsdStageRefPtr stage;
  SdfLayerRefPtr layer;  // held here: an anonymous layer lives as long as someone holds it
  std::optional<SdfChangeBlock> changes;
  std::map<SdfPath, std::unique_ptr<Skinning>> skins;  // CL5: the skinned clays' rest surfaces and weights
  Skinning* skin_of(const SdfPath& clay) const {
    auto it = skins.find(clay);
    return it == skins.end() ? nullptr : it->second.get();
  }
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
  Skinning* skin = p_->skin_of(clay);
  if (m.empty()) {
    if (skin) skin->drop(key);
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
  if (skin && skin->keep(key, pts, nrm, idx))  // CL5: the rest surface kept, the posed one written
    skin->posed_surface(key, pts, nrm, extent);
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
  if (Skinning* skin = p_->skin_of(clay)) skin->clear();
  check(mark, "removing the blocks of " + clay.GetString());
}

bool Blocks::get(const SdfPath& clay, const BlockKey& key, VtVec3fArray& points, VtVec3fArray& normals,
                 VtIntArray& indices) const {
  const SdfLayerHandle layer = p_->layer;
  const SdfPath path = clay.AppendChild(block_name(key));
  if (const Skinning* skin = p_->skin_of(clay); skin && skin->rest(key, points, normals, indices)) {  // CL5: at rest
    if (indices.size() == 3 && points.size() == 3 && points[0] == points[1] && points[1] == points[2]) return false;
    return !indices.empty();
  }
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

void Blocks::set_skin(const SdfPath& clay, std::shared_ptr<const SkinRig> rig, const std::set<BlockKey>& have) {
  TfErrorMark mark;
  const SdfLayerHandle layer = p_->layer;
  auto it = p_->skins.find(clay);
  std::unique_ptr<Skinning> old;
  if (it != p_->skins.end()) {
    if (rig && it->second->rig().rest == rig->rest) {  // the same bones: only the pose table is new
      it->second->set_rig(std::move(rig));
      return;
    }
    old = std::move(it->second);
    p_->skins.erase(it);
  }
  if (!rig) {  // no bones any more: every block at rest again
    if (old && old->posed())
      for (const BlockKey& k : old->keys()) {
        VtVec3fArray pts, nrm;
        VtIntArray idx;
        old->rest(k, pts, nrm, idx);
        VtVec3fArray extent = extent_of(pts);
        write_surface(layer, clay.AppendChild(block_name(k)), std::move(pts), std::move(nrm), std::move(extent));
      }
    check(mark, "putting the blocks of " + clay.GetString() + " back at rest");
    return;
  }
  auto skin = std::make_unique<Skinning>(std::move(rig));  // every bone at rest
  const TfToken& dflt = SdfFieldKeys->Default;
  for (const BlockKey& k : have) {
    VtVec3fArray pts, nrm;
    VtIntArray idx;
    if (!old || !old->rest(k, pts, nrm, idx)) {  // as written (no skin: at rest)
      const SdfPath path = clay.AppendChild(block_name(k));
      const VtValue p = layer->GetField(path.AppendProperty(TfToken("points")), dflt);
      const VtValue n = layer->GetField(path.AppendProperty(TfToken("normals")), dflt);
      const VtValue i = layer->GetField(path.AppendProperty(TfToken("faceVertexIndices")), dflt);
      if (!p.IsHolding<VtVec3fArray>() || !i.IsHolding<VtIntArray>()) continue;
      pts = p.UncheckedGet<VtVec3fArray>();
      idx = i.UncheckedGet<VtIntArray>();
      if (n.IsHolding<VtVec3fArray>()) nrm = n.UncheckedGet<VtVec3fArray>();
    }
    if (skin->keep(k, pts, nrm, idx) && old && old->posed()) {
      VtVec3fArray extent;
      skin->posed_surface(k, pts, nrm, extent);
      write_surface(layer, clay.AppendChild(block_name(k)), std::move(pts), std::move(nrm), std::move(extent));
    }
  }
  p_->skins[clay] = std::move(skin);
  check(mark, "giving the blocks of " + clay.GetString() + " their bones");
}

int Blocks::pose(const SdfPath& clay, const std::vector<BoneMove>& moves, double* skinMs, double* usdMs) {
  Skinning* skin = p_->skin_of(clay);
  if (!skin) return 0;
  using Clock = std::chrono::steady_clock;
  const auto ms = [](Clock::time_point t) { return std::chrono::duration<double, std::milli>(Clock::now() - t).count(); };
  TfErrorMark mark;
  const auto t0 = Clock::now();
  const std::vector<BlockKey> moved = skin->pose(moves);  // the bending, in parallel
  if (skinMs) *skinMs += ms(t0);
  const auto t1 = Clock::now();
  for (const BlockKey& k : moved) {  // the writes, one after another, in the caller's change block
    VtVec3fArray pts, nrm, extent;
    skin->posed_surface(k, pts, nrm, extent);
    write_surface(p_->layer, clay.AppendChild(block_name(k)), std::move(pts), std::move(nrm), std::move(extent));
  }
  check(mark, "posing the blocks of " + clay.GetString());
  if (usdMs) *usdMs += ms(t1);
  return int(moved.size());
}

const Skinning* Blocks::skinning(const SdfPath& clay) const { return p_->skin_of(clay); }

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
