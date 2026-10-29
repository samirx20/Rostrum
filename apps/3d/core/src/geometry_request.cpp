// The `geometry` request: the built mesh of one `mesh` or `combine` item, in the item's own space (no
// transform), at the shot's first frame. One point per face corner is fine: the Python side welds.
// v1.33: also a `clay`'s surface as drawn now (posed, its layers in), welded into one closed triangle mesh in the
// clay's own space: the Cycles whole (clay_whole.h), made first when its blocks changed since. "Make a clean mesh"
// (rostrum3d/remesh.py) starts from it. Loud while a stroke is being drawn (its blocks are down for the preview).
// The `unfold` request: the same built mesh laid flat (unfold.h), one (s, t) per face corner.
#include <pxr/usd/usdGeom/mesh.h>

#include <chrono>
#include <cmath>

#include "args.h"
#include "clay_whole.h"
#include "error.h"
#include "inspect.h"
#include "requests.h"
#include "unfold.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

struct Found {
  std::string type, owner;  // owner: the combine this item is an input of ("" = none)
  bool found = false;
};

// Walks the scene's items for `id`; `accepted` gets the ids that geometry can answer for.
void find(const JsArray& items, const std::string& id, const std::string& owner, Found& out,
          std::string& accepted) {
  for (const JsValue& v : items) {
    if (!v.IsObject()) continue;
    const JsObject& o = v.GetJsObject();
    auto get = [&](const char* k) {
      auto it = o.find(k);
      return it != o.end() && it->second.IsString() ? it->second.GetString() : std::string();
    };
    const std::string iid = get("id"), type = get("type");
    if (owner.empty() && (type == "mesh" || type == "combine" || type == "clay")) accepted += (accepted.empty() ? "" : ", ") + iid;
    if (iid == id && !out.found) out = Found{type, owner, true};
    auto ch = o.find("children");
    if (ch != o.end() && ch->second.IsArray())
      find(ch->second.GetJsArray(), id, type == "combine" ? (owner.empty() ? iid : owner) : owner, out, accepted);
  }
}

JsArray ints(const VtIntArray& a) {
  JsArray out;
  out.reserve(a.size());
  for (int i : a) out.push_back(JsValue(i));
  return out;
}

}  // namespace

UsdGeomMesh Core::built_mesh(const std::string& id, const char* request) const {
  const std::string at = std::string(request) + ".item";
  Found f;
  std::string accepted;
  auto items = scene_.find("items");
  if (items != scene_.end() && items->second.IsArray()) find(items->second.GetJsArray(), id, "", f, accepted);
  if (accepted.empty()) accepted = "(no mesh, combine or clay items)";
  if (!f.found) throw Error(at + ": no item \"" + id + "\". Accepted: " + accepted);
  if (!f.owner.empty())
    throw Error(at + ": \"" + id + "\" is an input of combine \"" + f.owner + "\"; use the combine. Accepted: " + accepted);
  if (f.type != "mesh" && f.type != "combine")
    throw Error(at + ": \"" + id + "\" is a " + f.type + ", not a mesh or combine. Accepted: " + accepted);
  const UsdGeomMesh m(stage_->GetPrimAtPath(item_path(stage_, id)));
  if (!m) throw Error(at + ": \"" + id + "\" has no built mesh");
  return m;
}

SdfPath Core::clay_path(const std::string& id) const {
  Found f;
  std::string accepted;
  auto items = scene_.find("items");
  if (items != scene_.end() && items->second.IsArray()) find(items->second.GetJsArray(), id, "", f, accepted);
  return f.found && f.type == "clay" && f.owner.empty() ? item_path(stage_, id) : SdfPath();
}

void Core::clay_whole(const std::string& id, const SdfPath& clay, VtVec3fArray& pts, VtIntArray& counts,
                      VtIntArray& indices) {
  if (!clay_) throw Error("geometry.item: \"" + id + "\" is a clay, but this scene has no clays built");
  if (clay_->previewing())
    throw Error("geometry.item: \"" + id + "\" is being sculpted (a stroke is still on its preview); ask again "
                "after the stroke ends");
  clay_->whole_for_cycles();  // welds every clay whose blocks changed since; the rest are kept as they were
  for (const char* name : {clay::kWhole, clay::kWholePainted}) {  // a clay's blocks sit in one or the other
    const UsdGeomMesh m(stage_->GetPrimAtPath(clay.AppendChild(TfToken(name))));
    if (!m) continue;
    VtVec3fArray p;
    VtIntArray c, i;
    m.GetPointsAttr().Get(&p);
    m.GetFaceVertexCountsAttr().Get(&c);
    m.GetFaceVertexIndicesAttr().Get(&i);
    const int base = int(pts.size());
    pts.insert(pts.end(), p.begin(), p.end());
    counts.insert(counts.end(), c.begin(), c.end());
    for (int v : i) indices.push_back(v + base);
  }
  if (pts.empty())
    throw Error("geometry.item: clay \"" + id + "\" has no surface (no pieces, or every piece is cut away)");
}

JsObject Core::geometry(const JsObject& o) {
  Args a(o, "geometry", {"item"});
  need_scene("geometry");
  const std::string id = a.str("item");
  VtVec3fArray pts;
  VtIntArray counts, indices;
  const SdfPath clay = clay_path(id);
  if (!clay.IsEmpty()) {
    clay_whole(id, clay, pts, counts, indices);
  } else {
    const UsdGeomMesh m = built_mesh(id, "geometry");
    const UsdTimeCode t(built_.start);
    m.GetPointsAttr().Get(&pts, t);
    m.GetFaceVertexCountsAttr().Get(&counts, t);
    m.GetFaceVertexIndicesAttr().Get(&indices, t);
  }
  JsArray jp;
  jp.reserve(pts.size());
  for (const GfVec3f& p : pts)
    jp.push_back(JsValue(JsArray{JsValue(double(p[0])), JsValue(double(p[1])), JsValue(double(p[2]))}));
  return JsObject{{"ok", JsValue(true)}, {"item", JsValue(id)}, {"points", JsValue(jp)},
                  {"faceCounts", JsValue(ints(counts))}, {"faceIndices", JsValue(ints(indices))}};
}

JsObject Core::unfold(const JsObject& o) {
  Args a(o, "unfold", {"item", "size"});
  need_scene("unfold");
  const std::string id = a.str("item");
  const UsdGeomMesh m = built_mesh(id, "unfold");
  const UsdTimeCode t(built_.start);
  VtVec3fArray pts;
  VtIntArray counts, indices;
  m.GetPointsAttr().Get(&pts, t);
  m.GetFaceVertexCountsAttr().Get(&counts, t);
  m.GetFaceVertexIndicesAttr().Get(&indices, t);
  const auto t0 = std::chrono::steady_clock::now();
  const Unfolded u = unfold_mesh(pts, counts, indices, a.whole("size", 2048), "unfold");
  JsArray st;
  st.reserve(u.st.size() * 2);
  for (const GfVec2f& c : u.st)
    for (int i = 0; i < 2; ++i) st.push_back(JsValue(std::round(double(c[i]) * 1e6) / 1e6));
  const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  return JsObject{{"ok", JsValue(true)}, {"item", JsValue(id)}, {"uvs", JsValue(st)},
                  {"corners", JsValue(int(u.st.size()))}, {"charts", JsValue(u.charts)}, {"split", JsValue(u.split)},
                  {"used", JsValue(std::round(double(u.used) * 1000) / 1000)}, {"ms", JsValue(std::round(ms))}};
}

}  // namespace r3d
