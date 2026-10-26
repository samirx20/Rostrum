// Scene items (ENGINE_CONTRACT.md § 2, Item types) -> prims at /World/<id>/<child id>… Every item is a
// `def` prim; changes to the parts of an import are `over` prims (pick relies on that to name the item).
#pragma once
#include <set>
#include <string>

#include <pxr/base/js/value.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>
#include <vector>

#include "clay_scene.h"

namespace r3d {

struct ItemsContext {
  PXR_NS::UsdStageRefPtr stage;
  int start = 0, end = 0;               // the shot's frames, inclusive: anim lists hold end - start + 1 values
  double shutter = 0;                   // frames the shutter is open, centred on each frame; 0 = no motion blur
  std::set<std::string> materials;      // material ids that exist
  std::set<std::string> ids;            // item ids seen so far (unique across the scene)
  int items = 0;
  std::vector<clay::Node> clays;        // clay items, for the clay store (clay_store.h)
};

// Ids are prim names: [A-Za-z_][A-Za-z0-9_]*, and "Looks" is taken by /World/Looks.
void check_id(const std::string& id, const std::string& where);

// Builds every item of `items` under `parent`; `where` names the list in errors ("items", "body.children").
void build_items(ItemsContext& ctx, const PXR_NS::JsArray& items, const PXR_NS::SdfPath& parent,
                 const std::string& where);

}  // namespace r3d
