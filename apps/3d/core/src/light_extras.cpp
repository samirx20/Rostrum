#include "light_extras.h"

#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usd/collectionAPI.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdLux/domeLight.h>
#include <pxr/usd/usdLux/domeLight_1.h>
#include <pxr/usd/usdLux/lightAPI.h>
#include <pxr/usd/usdLux/shapingAPI.h>
#include <pxr/usd/usdLux/sphereLight.h>

#include <sstream>

#include "error.h"
#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
const TfToken kCard("rostrum:card"), kLightsOnly("rostrum:lightsOnly"), kSeen("rostrum:seenByCamera");
constexpr int kMostSets = 63;  // Cycles' light sets are bits of a 64-bit mask; set 0 is "not linked"

LightExtras& table() {
  static LightExtras t;
  return t;
}

// a bool or string attribute of ours, when authored
template <class T>
bool read(const UsdPrim& p, const TfToken& name, T* out) {
  const UsdAttribute a = p.GetAttribute(name);
  return a && a.Get(out);
}

bool is_card(const UsdPrim& p) { return p.GetName().GetString().rfind(kCardName, 0) == 0; }

// the scene's items by id: prims our layer defines (not the materials, not the cards, not an import's insides)
std::map<std::string, SdfPath> items_of(const UsdStageRefPtr& stage) {
  std::map<std::string, SdfPath> out;
  const SdfLayerHandle layer = stage->GetRootLayer();
  for (const UsdPrim& p : stage->Traverse()) {
    const SdfPrimSpecHandle spec = layer->GetPrimAtPath(p.GetPath());
    if (!spec || spec->GetSpecifier() != SdfSpecifierDef || is_card(p)) continue;
    if (p.GetPath() == SdfPath("/World") || p.GetPath().HasPrefix(SdfPath("/World/Looks"))) continue;
    out[p.GetName().GetString()] = p.GetPath();
  }
  return out;
}

std::string id_of(const SdfPath& p) { return p.GetName(); }  // item ids are prim names
}  // namespace

int LightExtras::receiver_set(const SdfPath& prim) const {
  for (SdfPath p = prim; !p.IsEmpty() && p != SdfPath::AbsoluteRootPath(); p = p.GetParentPath())
    if (auto it = receivers.find(p); it != receivers.end()) return it->second;
  return 0;
}

void build_light_extras(Item& it, const UsdPrim& light, const std::string& kind) {
  const bool panel = kind == "rect" || kind == "disk" || kind == "strip";
  const double spread = it.props.num("spread");
  if (spread < 0 || spread > 180) fail(it.props.at("spread"), std::to_string(spread), "0 .. 180 degrees");
  if (panel && spread < 180)  // UsdLux: the cone's half angle; 180 (fully diffuse) authors nothing
    UsdLuxShapingAPI::Apply(light).CreateShapingConeAngleAttr().Set(float(spread / 2));
  if (it.props.flag("card") && panel) {
    light.CreateAttribute(kCard, SdfValueTypeNames->Bool, true).Set(true);
    build_card(it, light, kind);
  }
  const std::string only = it.props.str("lightsOnly");
  if (kind != "dome" && !only.empty()) light.CreateAttribute(kLightsOnly, SdfValueTypeNames->String, true).Set(only);
  const bool seen = it.props.flag("seenByCamera");
  if (kind == "dome") light.CreateAttribute(kSeen, SdfValueTypeNames->Bool, true).Set(seen);
}

void link_lights(const UsdStageRefPtr& built) {
  std::map<std::string, SdfPath> items;
  for (const UsdPrim& p : built->Traverse()) {
    std::string only;
    if (!read(p, kLightsOnly, &only) || only.empty()) continue;
    if (items.empty()) items = items_of(built);
    UsdCollectionAPI link = UsdLuxLightAPI(p).GetLightLinkCollectionAPI();
    link.CreateIncludeRootAttr().Set(false);  // lights only what it includes
    UsdRelationship includes = link.CreateIncludesRel();
    std::istringstream words(only);
    for (std::string id; words >> id;) {
      const auto found = items.find(id);
      if (found == items.end() || found->second == p.GetPath()) {
        std::string all;
        for (const auto& [name, path] : items)
          if (path != p.GetPath()) all += (all.empty() ? "" : ", ") + name;
        fail(id_of(p.GetPath()) + ".lightsOnly", "no item \"" + id + "\"", all.empty() ? "no other items" : all);
      }
      includes.AddTarget(found->second);
    }
  }
}

void publish_light_extras(const UsdStageRefPtr& stage) {
  LightExtras t;
  std::map<SdfPath, std::vector<SdfPath>> links;  // linked light -> the items it lights
  for (const UsdPrim& p : stage->Traverse()) {
    if (!p.HasAPI<UsdLuxLightAPI>()) continue;
    const SdfPath path = p.GetPath();
    bool on = false;
    if (read(p, kCard, &on) && on) t.cards.insert(path);
    float cone = 180;  // a panel's spread; a spot's own cone is read by both renderers as it is (lights_cameras.cpp)
    if (!p.IsA<UsdLuxSphereLight>() && p.HasAPI<UsdLuxShapingAPI>() &&
        UsdLuxShapingAPI(p).GetShapingConeAngleAttr().Get(&cone) && cone < 90) {
      t.coneDeg[path] = cone;
      t.stormNotes.push_back(id_of(path) + ": spread (the quick view throws the light all around; Cycles narrows it)");
    }
    if (p.IsA<UsdLuxDomeLight>() || p.IsA<UsdLuxDomeLight_1>()) {
      bool seen = true;
      read(p, kSeen, &seen);
      t.domeSeen[path] = seen;
      continue;
    }
    UsdCollectionAPI link = UsdLuxLightAPI(p).GetLightLinkCollectionAPI();
    bool root = true;
    SdfPathVector targets;
    link.GetIncludeRootAttr().Get(&root);
    if (link.GetIncludesRel().GetTargets(&targets) && !root && !targets.empty()) {
      links[path] = targets;
      t.stormNotes.push_back(id_of(path) + ": lightsOnly (the quick view lights every item; Cycles lights only the linked ones)");
    }
  }
  // one receiver set per distinct combination of lights linking an item (its own links and those of what holds it)
  std::map<SdfPath, std::set<SdfPath>> lit_by;
  for (const auto& [light, targets] : links)
    for (const SdfPath& item : targets) lit_by[item].insert(light);
  std::map<std::set<SdfPath>, int> sets;
  for (const auto& [item, _] : lit_by) {
    std::set<SdfPath> combo;
    for (const auto& [other, lights] : lit_by)
      if (item.HasPrefix(other)) combo.insert(lights.begin(), lights.end());
    auto [where, added] = sets.emplace(combo, int(sets.size()) + 1);
    if (added && where->second > kMostSets)
      throw Error("scene: light linking needs more than 63 different combinations of linked lights (Cycles' limit)");
    t.receivers[item] = where->second;
  }
  for (const auto& [light, _] : links) t.membership[light] = 0;
  for (const auto& [combo, index] : sets)
    for (const SdfPath& light : combo) t.membership[light] |= uint64_t(1) << index;
  table() = std::move(t);
}

const LightExtras& light_extras() { return table(); }

}  // namespace r3d
