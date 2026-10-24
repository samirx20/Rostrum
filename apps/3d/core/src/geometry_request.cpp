// The `geometry` request: the built mesh of one `mesh` or `combine` item, in the item's own space (no
// transform), at the shot's first frame. One point per face corner is fine: the Python side welds.
#include <pxr/usd/usdGeom/mesh.h>

#include "args.h"
#include "error.h"
#include "inspect.h"
#include "requests.h"

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
    if (owner.empty() && (type == "mesh" || type == "combine")) accepted += (accepted.empty() ? "" : ", ") + iid;
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

JsObject Core::geometry(const JsObject& o) {
  Args a(o, "geometry", {"item"});
  need_scene("geometry");
  const std::string id = a.str("item");
  Found f;
  std::string accepted;
  auto items = scene_.find("items");
  if (items != scene_.end() && items->second.IsArray()) find(items->second.GetJsArray(), id, "", f, accepted);
  if (accepted.empty()) accepted = "(no mesh or combine items)";
  if (!f.found) throw Error("geometry.item: no item \"" + id + "\". Accepted: " + accepted);
  if (!f.owner.empty())
    throw Error("geometry.item: \"" + id + "\" is an input of combine \"" + f.owner +
                "\"; convert the combine. Accepted: " + accepted);
  if (f.type != "mesh" && f.type != "combine")
    throw Error("geometry.item: \"" + id + "\" is a " + f.type + ", not a mesh or combine. Accepted: " + accepted);
  const UsdGeomMesh m(stage_->GetPrimAtPath(item_path(stage_, id)));
  if (!m) throw Error("geometry.item: \"" + id + "\" has no built mesh");
  const UsdTimeCode t(built_.start);
  VtVec3fArray pts;
  VtIntArray counts, indices;
  m.GetPointsAttr().Get(&pts, t);
  m.GetFaceVertexCountsAttr().Get(&counts, t);
  m.GetFaceVertexIndicesAttr().Get(&indices, t);
  JsArray jp;
  jp.reserve(pts.size());
  for (const GfVec3f& p : pts)
    jp.push_back(JsValue(JsArray{JsValue(double(p[0])), JsValue(double(p[1])), JsValue(double(p[2]))}));
  return JsObject{{"ok", JsValue(true)}, {"item", JsValue(id)}, {"points", JsValue(jp)},
                  {"faceCounts", JsValue(ints(counts))}, {"faceIndices", JsValue(ints(indices))}};
}

}  // namespace r3d
