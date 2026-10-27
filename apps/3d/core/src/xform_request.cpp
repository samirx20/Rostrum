// `xform` (ENGINE_CONTRACT.md § 1): a gizmo drag's move on the live stage, without a new scene. The item's translate,
// rotateXYZ and scale ops (stage_items.cpp author_transform) take the given values (resolved, as the scene's props:
// the pivot already in x y z) as plain values, their per-frame samples dropped; children follow through the
// hierarchy. It holds until the next `scene`, which the drop sends with the document's change.
#include <pxr/base/gf/vec3d.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/usd/sdf/changeBlock.h>
#include <pxr/usd/usd/attribute.h>

#include <array>

#include "args.h"
#include "error.h"
#include "inspect.h"
#include "requests.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

JsObject Core::xform(const JsObject& o) {
  Args a(o, "xform", {"item", "x", "y", "z", "rx", "ry", "rz", "sx", "sy", "sz"});
  need_scene("xform");
  const std::string id = a.str("item");
  if (id != xform_id_ || !stage_->GetPrimAtPath(xform_path_)) {  // a drag sends many: look the item up once
    xform_path_ = item_path(stage_, id);
    xform_id_ = id;
  }
  if (xform_path_.IsEmpty()) {
    xform_id_.clear();
    throw Error("xform.item: no item \"" + id + "\" in the scene");
  }
  const UsdPrim prim = stage_->GetPrimAtPath(xform_path_);
  struct Op { const char* attr; std::array<const char*, 3> keys; bool dbl; };
  static const Op ops[] = {{"xformOp:translate", {"x", "y", "z"}, true},
                           {"xformOp:rotateXYZ", {"rx", "ry", "rz"}, false},
                           {"xformOp:scale", {"sx", "sy", "sz"}, false}};
  const SdfChangeBlock block;  // one change for Hydra
  for (const Op& op : ops) {
    if (!a.has(op.keys[0]) && !a.has(op.keys[1]) && !a.has(op.keys[2])) continue;
    UsdAttribute attr = prim.GetAttribute(TfToken(op.attr));
    if (!attr) throw Error("xform.item: \"" + id + "\" has no " + op.attr + " (it can't be moved this way)");
    GfVec3d v(0.0);
    if (op.dbl) {
      GfVec3d have;
      attr.Get(&have, UsdTimeCode::EarliestTime());
      v = have;
    } else {
      GfVec3f have;
      attr.Get(&have, UsdTimeCode::EarliestTime());
      v = GfVec3d(have);
    }
    for (int i = 0; i < 3; ++i)
      if (a.has(op.keys[i])) v[i] = a.num(op.keys[i]);
    attr.Clear();  // the per-frame samples go: the live view shows this value at every frame until the next scene
    if (op.dbl) attr.Set(v);
    else attr.Set(GfVec3f(v));
  }
  return JsObject{{"ok", JsValue(true)}};
}

}  // namespace r3d
