#include "ghosts.h"

#include <cmath>

#include "inspect.h"
#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

std::vector<Ghost> read_ghosts(const JsValue& v, const UsdStageRefPtr& stage,
                               const std::function<void(int, const std::string&)>& check_frame) {
  if (!v.IsArray())
    fail("view.ghosts", "is " + v.GetTypeName(),
         "a list of {\"frame\", \"items\": [item ids], \"tint\": [r, g, b], \"opacity\"}");
  const auto& list = v.GetJsArray();
  if (int(list.size()) > kMaxGhosts)
    fail("view.ghosts", std::to_string(list.size()) + " ghosts", "at most " + std::to_string(kMaxGhosts));
  std::vector<Ghost> out;
  for (size_t i = 0; i < list.size(); ++i) {
    const std::string where = "view.ghosts[" + std::to_string(i) + "]";
    if (!list[i].IsObject()) fail(where, "is " + list[i].GetTypeName(), "an object");
    Reader r(list[i].GetJsObject(), where);
    Ghost g;
    g.frame = r.count("frame", -1000000, 1000000);
    check_frame(g.frame, r.at("frame"));
    const auto& items = r.list("items");
    if (items.empty()) fail(r.at("items"), "is empty", "one or more item ids");
    for (const auto& id : items) {
      if (!id.IsString()) fail(r.at("items"), "holds " + id.GetTypeName(), "item ids (strings)");
      const SdfPath p = item_path(stage, id.GetString());
      if (p.IsEmpty()) fail(r.at("items"), "no item \"" + id.GetString() + "\" in the scene", "the scene's item ids");
      g.items.push_back(p);
    }
    if (r.has("tint")) {
      const GfVec3f t = Reader::vec3_of(r.get("tint", "[r, g, b]"), r.at("tint"));
      for (int k = 0; k < 3; ++k) {
        if (!(t[k] >= 0 && t[k] <= 1)) fail(r.at("tint"), "is out of range", "[r, g, b], each 0..1 (linear)");
        g.tint[k] = t[k];
      }
    }
    if (r.has("opacity")) {
      const double o = r.num("opacity");
      if (o < 0 || o > 1) fail(r.at("opacity"), std::to_string(o) + " is out of range", "a number 0..1");
      g.opacity = float(o);
    }
    r.finish();
    out.push_back(std::move(g));
  }
  return out;
}

}  // namespace r3d
