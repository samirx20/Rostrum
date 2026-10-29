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
#include <iterator>
#include <map>
#include <optional>
#include <string>
#include <vector>

#include "clay_preview.h"
#include "clay_slots.h"
#include "clay_whole.h"
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

VtVec3fArray extent_of(const VtVec3fArray& pts, const GfVec3f& at) {
  GfVec3f lo(FLT_MAX), hi(-FLT_MAX);
  for (const GfVec3f& p : pts)
    for (int c = 0; c < 3; ++c) lo[c] = std::min(lo[c], p[c]), hi[c] = std::max(hi[c], p[c]);
  if (pts.empty()) lo = hi = at;
  return VtVec3fArray{lo, hi};
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
  std::set<SdfPath> stale;  // CL6: clays whose Cycles whole no longer matches their blocks (clay_whole.h)
  std::map<SdfPath, Slot> slots;  // 3d-dab-viewer: each block prim's own surface and its slot (clay_slots.h)
  Slot* slot_of(const SdfPath& prim) {
    auto it = slots.find(prim);
    return it == slots.end() ? nullptr : &it->second;
  }
  const Slot* slot_of(const SdfPath& prim) const {
    auto it = slots.find(prim);
    return it == slots.end() ? nullptr : &it->second;
  }
  // the slot drawn with `pts`, `nrm` (one per vertex of its surface: at rest or posed): the corners, padded to the
  // slot's size (grown first if the surface no longer fits: then the face lists too), and the extent of the surface
  void draw(const SdfPath& prim, Slot& sl, VtVec3fArray pts, VtVec3fArray nrm) {
    const TfToken& dflt = SdfFieldKeys->Default;
    const auto attr = [&](const char* name) { return prim.AppendProperty(TfToken(name)); };
    const size_t nt = sl.triangles();
    if (!slots_on()) {  // as before: shared points, sized to the surface (an emptied block: one triangle of no area)
      const bool none = nt == 0;
      layer->SetField(attr("faceVertexCounts"), dflt, VtValue(VtIntArray(none ? 1 : nt, 3)));
      layer->SetField(attr("faceVertexIndices"), dflt, VtValue(none ? VtIntArray{0, 1, 2} : sl.indices));
      layer->SetField(attr("points"), dflt, VtValue(none ? VtVec3fArray(3, sl.at) : pts));
      layer->SetField(attr("normals"), dflt, VtValue(none ? VtVec3fArray(3, GfVec3f(0, 0, 1)) : nrm));
      layer->SetField(attr("extent"), dflt, VtValue(extent_of(pts, sl.at)));
      sl.cap = none ? 1 : nt;
      sl.shownPoints = std::move(pts);
      sl.shownNormals = std::move(nrm);
      return;
    }
    if (nt > sl.cap || sl.cap == 0) {
      sl.cap = slot_capacity(nt, is_preview_key(key_of(prim)));
      layer->SetField(attr("faceVertexCounts"), dflt, VtValue(slot_counts(sl.cap)));
      layer->SetField(attr("faceVertexIndices"), dflt, VtValue(slot_indices(sl.cap)));
    }
    if (nrm.size() != pts.size()) nrm = VtVec3fArray(pts.size(), GfVec3f(0, 0, 1));
    const GfVec3f pad = nt ? pts.cdata()[sl.indices.cdata()[0]] : sl.at;  // (cdata: no copy-on-write detach)
    layer->SetField(attr("points"), dflt, VtValue(slot_corners(pts, sl.indices, sl.cap, pad)));
    layer->SetField(attr("normals"), dflt, VtValue(slot_corners(nrm, sl.indices, sl.cap, GfVec3f(0, 0, 1))));
    layer->SetField(attr("extent"), dflt, VtValue(extent_of(pts, sl.at)));
    sl.shownPoints = std::move(pts);
    sl.shownNormals = std::move(nrm);
  }
  static BlockKey key_of(const SdfPath& prim) {
    BlockKey k{0, 0, 0};
    block_key_of(prim.GetName(), k);
    return k;
  }
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
  p_->stale.insert(clay);
  if (exists) drop_st(layer, path);
  Skinning* skin = p_->skin_of(clay);
  const SdfPath shadePath = attr(kShade), colorPath = attr(kDisplayColor);
  const auto drop_mask = [&] {
    if (!layer->HasSpec(shadePath)) return;
    SdfPrimSpecHandle prim = layer->GetPrimAtPath(path);
    for (const SdfPath& q : {shadePath, colorPath})
      if (SdfAttributeSpecHandle a = layer->GetAttributeAtPath(q)) prim->RemoveProperty(a);
  };
  if (m.empty()) {
    if (skin) skin->drop(key);
    // An emptied block keeps its prim (3d-v4): a prim removed or added makes Storm rebuild its draw batches
    // (rebuildBatches; 15-25 ms when a stroke's preview took 8 fine blocks down for each of its own), and the same
    // block is often filled again soon (the fine blocks come back at the stroke's end). It keeps its slot too, every
    // triangle on one point where the block was (no area: nothing draws; clay_slots.h), so bounds and framing don't
    // move and the refill goes where it was
    if (!exists) return;
    Slot& sl = p_->slots[path];
    if (!sl.points.empty()) sl.at = sl.points.cdata()[sl.indices.empty() ? 0 : size_t(sl.indices.cdata()[0])];
    sl.points = sl.normals = VtVec3fArray();
    sl.indices = VtIntArray();
    p_->draw(path, sl, VtVec3fArray(), VtVec3fArray());
    drop_mask();
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
    p_->slots.erase(path);  // (a clay removed and made again: a fresh prim, a fresh slot)
  }
  const size_t nv = m.points.size() / 3, nt = m.triangles();
  Slot& sl = p_->slots[path];
  sl.points = VtVec3fArray(nv);
  sl.normals = VtVec3fArray(nv, GfVec3f(0, 0, 1));
  std::memcpy(sl.points.data(), m.points.data(), nv * sizeof(GfVec3f));
  std::memcpy(sl.normals.data(), m.normals.data(), std::min(m.normals.size() / 3, nv) * sizeof(GfVec3f));
  sl.indices = VtIntArray(nt * 3);
  std::memcpy(sl.indices.data(), m.indices.data(), nt * 3 * sizeof(int32_t));
  VtVec3fArray pts = sl.points, nrm = sl.normals, extent;
  if (skin && skin->keep(key, sl.points, sl.normals, sl.indices))  // CL5: the rest surface kept, the posed one drawn
    skin->posed_surface(key, pts, nrm, extent);
  p_->draw(path, sl, std::move(pts), std::move(nrm));

  const TfToken& dflt = SdfFieldKeys->Default;
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
      const float sh = 1.0f - kMaskDarken * std::clamp(m.mask[i], 0.0f, 1.0f);
      shade[i] = sh;
      color[i] = GfVec3f(kNoMaterialGrey * sh);
    }
    // per corner, as the points (the padding unshaded)
    if (!slots_on()) {
      layer->SetField(shadePath, dflt, VtValue::Take(shade));
      layer->SetField(colorPath, dflt, VtValue::Take(color));
    } else {
      layer->SetField(shadePath, dflt, VtValue(slot_corners(shade, sl.indices, sl.cap, 1.0f)));
      layer->SetField(colorPath, dflt, VtValue(slot_corners(color, sl.indices, sl.cap, GfVec3f(kNoMaterialGrey))));
    }
  } else {  // the mask left this block: back to the plain clay
    drop_mask();
  }
  check(mark, "writing " + path.GetString());
}

void Blocks::hide(const SdfPath& clay, const BlockKey& key, bool hidden, const std::set<BlockKey>& have) {
  if (!have.count(key)) return;
  TfErrorMark mark;
  const SdfLayerHandle layer = p_->layer;
  const SdfPath path = clay.AppendChild(block_name(key));
  const SdfPath vis = path.AppendProperty(UsdGeomTokens->visibility);
  if (!layer->HasSpec(vis)) {
    if (!hidden) return;  // never hidden
    SdfAttributeSpec::New(layer->GetPrimAtPath(path), UsdGeomTokens->visibility.GetString(), SdfValueTypeNames->Token);
  }
  layer->SetField(vis, SdfFieldKeys->Default,
                  VtValue(hidden ? UsdGeomTokens->invisible : UsdGeomTokens->inherited));
  check(mark, (hidden ? "hiding " : "showing ") + path.GetString());
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
  for (auto it = p_->slots.begin(); it != p_->slots.end();)
    it = it->first.GetParentPath() == clay ? p_->slots.erase(it) : std::next(it);
  p_->stale.insert(clay);  // its wholes went with the clay's spec; none is made again until it has blocks
  if (Skinning* skin = p_->skin_of(clay)) skin->clear();
  check(mark, "removing the blocks of " + clay.GetString());
}

bool Blocks::get(const SdfPath& clay, const BlockKey& key, VtVec3fArray& points, VtVec3fArray& normals,
                 VtIntArray& indices) const {
  const Slot* sl = p_->slot_of(clay.AppendChild(block_name(key)));
  if (!sl) return false;
  points = sl->points;  // at rest (a skinned clay's slot keeps its rest surface)
  normals = sl->normals;
  indices = sl->indices;
  // a block kept ready (the store's ring): one triangle of no area, its 3 points the same
  if (indices.size() == 3 && points.size() == 3 && points[0] == points[1] && points[1] == points[2]) return false;
  return !indices.empty();
}

void Blocks::set_skin(const SdfPath& clay, std::shared_ptr<const SkinRig> rig, const std::set<BlockKey>& have) {
  TfErrorMark mark;
  const SdfLayerHandle layer = p_->layer;
  p_->stale.insert(clay);
  auto it = p_->skins.find(clay);
  std::unique_ptr<Skinning> old;
  if (it != p_->skins.end()) {
    if (rig && it->second->rig().same_weights(*rig)) {  // the same bones and pieces: only the pose table is new
      it->second->set_rig(std::move(rig));
      return;
    }
    old = std::move(it->second);
    p_->skins.erase(it);
  }
  if (!rig) {  // no bones any more: every block at rest again
    if (old && old->posed())
      for (const BlockKey& k : old->keys()) {
        const SdfPath path = clay.AppendChild(block_name(k));
        if (Slot* sl = p_->slot_of(path)) p_->draw(path, *sl, sl->points, sl->normals);
      }
    check(mark, "putting the blocks of " + clay.GetString() + " back at rest");
    return;
  }
  auto skin = std::make_unique<Skinning>(std::move(rig));  // every bone at rest
  for (const BlockKey& k : have) {
    const SdfPath path = clay.AppendChild(block_name(k));
    Slot* sl = p_->slot_of(path);
    if (!sl) continue;
    if (skin->keep(k, sl->points, sl->normals, sl->indices) && old && old->posed())
      p_->draw(path, *sl, sl->points, sl->normals);  // drawn posed by the old bones: at rest again (the new are)
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
  if (!moved.empty()) p_->stale.insert(clay);
  for (const BlockKey& k : moved) {  // the writes, one after another, in the caller's change block
    const SdfPath path = clay.AppendChild(block_name(k));
    Slot* sl = p_->slot_of(path);
    VtVec3fArray pts, nrm, extent;
    if (!sl || !skin->posed_surface(k, pts, nrm, extent)) continue;
    p_->draw(path, *sl, std::move(pts), std::move(nrm));
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
  const Slot* sl = p_->slot_of(path);
  layer->SetField(stPath, SdfFieldKeys->Default, slots_on() ? VtValue(slot_padded(st, sl ? sl->cap : st.size() / 3)) : VtValue(st));
  p_->stale.insert(clay);
  check(mark, "writing the unfolding of " + path.GetString());
}

void Blocks::clear_st(const SdfPath& clay, const BlockKey& key) {
  TfErrorMark mark;
  const SdfPath path = clay.AppendChild(block_name(key));
  drop_st(p_->layer, path);
  p_->stale.insert(clay);
  check(mark, "taking the unfolding off " + path.GetString());
}

bool Blocks::whole_stale(const SdfPath& clay) const { return p_->stale.count(clay) != 0; }

void Blocks::make_whole(const SdfPath& clay, const std::set<BlockKey>& have, const std::string& where) {
  TfErrorMark mark;
  const SdfLayerHandle layer = p_->layer;
  const TfToken& dflt = SdfFieldKeys->Default;
  std::vector<SurfaceBlock> plain, painted;
  std::vector<VtVec2fArray> st;
  for (const BlockKey& k : have) {  // the blocks as drawn: posed for a skinned clay, so the whole is posed too
    const SdfPath path = clay.AppendChild(block_name(k));
    const Slot* sl = p_->slot_of(path);
    if (!sl || sl->indices.empty() || sl->shownPoints.size() != sl->points.size()) continue;
    SurfaceBlock b{k, sl->shownPoints, sl->shownNormals, sl->indices};
    if (b.indices.size() == 3 && b.points.size() == 3 && b.points[0] == b.points[1] && b.points[1] == b.points[2])
      continue;  // a block kept ready (one triangle of no area)
    const VtValue s = layer->GetField(path.AppendProperty(TfToken(kSt)), dflt);
    if (s.IsHolding<VtVec2fArray>() && s.UncheckedGet<VtVec2fArray>().size() >= b.indices.size()) {
      const VtVec2fArray& all = s.UncheckedGet<VtVec2fArray>();  // padded to the slot: the surface's corners first
      st.emplace_back(all.cbegin(), all.cbegin() + b.indices.size());
      painted.push_back(std::move(b));
    } else {
      plain.push_back(std::move(b));
    }
  }
  write_whole(layer, clay, kWhole, plain, nullptr, where);
  write_whole(layer, clay, kWholePainted, painted, &st, where);
  p_->stale.erase(clay);
  check(mark, "welding the whole of " + clay.GetString());
}

}  // namespace r3d::clay
