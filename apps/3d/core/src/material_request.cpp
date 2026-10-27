// `material` (ENGINE_CONTRACT.md § 1): a material field's drag, live, without a new scene. The given props go over the
// material's last ones (the scene's, or what the last `material` left) and its shaders on the held stage are rewritten:
// only the Stylized shader's inputs when every changed field is a Lines / Halftone one (a line-width drag: Storm's
// and Cycles' shaders untouched), else the whole material, built and checked on a stage of its own first. It holds
// until the next `scene`, which the drop sends with the document's change (like `xform` and `copies`).
#include <chrono>
#include <cmath>

#include "args.h"
#include "error.h"
#include "material_stylized.h"
#include "materials.h"
#include "requests.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

JsObject Core::material(const JsObject& o) {
  const auto t0 = std::chrono::steady_clock::now();
  Args a(o, "material", {"id", "props"});
  need_scene("material");
  const std::string id = a.str("id");
  const JsValue& changes = a.need("props");
  if (!changes.IsObject()) throw Error("material.props: needs an object of the material's changed fields");

  // the material as the scene sent it
  const JsObject* sent = nullptr;
  const JsObject* anim = nullptr;
  std::string ids;
  const auto list = scene_.find("materials");
  if (list != scene_.end() && list->second.IsArray())
    for (const JsValue& m : list->second.GetJsArray()) {
      if (!m.IsObject()) continue;
      const JsObject& mo = m.GetJsObject();
      const auto mid = mo.find("id");
      if (mid == mo.end() || !mid->second.IsString()) continue;
      if (mid->second.GetString() != id) {
        ids += (ids.empty() ? "" : ", ") + mid->second.GetString();
        continue;
      }
      const auto props = mo.find("props");
      if (props != mo.end() && props->second.IsObject()) sent = &props->second.GetJsObject();
      const auto an = mo.find("anim");
      if (an != mo.end() && an->second.IsObject()) anim = &an->second.GetJsObject();
    }
  if (!sent) throw Error("material.id: no material \"" + id + "\" in the scene. Accepted: " + (ids.empty() ? "(none)" : ids));

  const auto last = material_props_.find(id);
  JsObject merged = last != material_props_.end() ? last->second : *sent;
  bool quick = true;
  for (const auto& [key, value] : changes.GetJsObject()) {
    if (!merged.count(key)) {
      std::string accepted;
      for (const auto& kv : merged) accepted += (accepted.empty() ? "" : ", ") + kv.first;
      throw Error("material.props." + key + ": unknown field. Accepted: " + accepted);
    }
    merged[key] = value;
    quick = quick && stylized_only_field(key);
  }
  if (quick) restyle_material(stage_, id, merged);
  else rebuild_material(stage_, id, merged, anim, built_.start, built_.end);
  material_props_[id] = std::move(merged);
  const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  return JsObject{{"ok", JsValue(true)}, {"ms", JsValue(std::round(ms * 10) / 10)}};
}

}  // namespace r3d
