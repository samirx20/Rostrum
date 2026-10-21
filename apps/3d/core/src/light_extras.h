// Product lighting (H21, ENGINE_CONTRACT.md § 2 light row): a panel's spread, its visible card, light linking and a
// dome's camera visibility. The stage holds the truth in UsdLux terms (ShapingAPI cone angle = spread / 2, the light's
// lightLink collection) plus three attributes of ours (rostrum:card, rostrum:lightsOnly, rostrum:seenByCamera);
// LightExtras is what the renderer side derives from it, once per scene, for the Hydra filters:
//  - Cycles (cycles_lights.cpp + our patch on its Hydra plug-in, apps/3d/libs/cycles-rostrum-lights.patch): the card is
//    the light's own camera visibility (visibleInPrimaryRay; Cycles shows area lights in reflections anyway), the cone
//    angle becomes the area light's spread, links become Cycles light sets (a receiver set per distinct combination of
//    lights linking an item, at most 63; each linked light's membership is the sets it lights), a dome's camera
//    visibility becomes the background's.
//  - Storm: the card is an emissive mesh the core makes under the light (RostrumCard), hidden from Cycles. Storm has no
//    spread and no light linking: notes_for_storm() names what the quick view can't show.
#pragma once
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "item_track.h"

namespace r3d {

inline const char* kCardName = "RostrumCard";

struct LightExtras {
  std::set<PXR_NS::SdfPath> cards;                  // lights whose panel the camera sees (their RostrumCard child)
  std::map<PXR_NS::SdfPath, float> coneDeg;         // panels with a spread < 180: UsdLux cone angle (spread / 2)
  std::map<PXR_NS::SdfPath, bool> domeSeen;         // domes: seen by the camera
  std::map<PXR_NS::SdfPath, uint64_t> membership;   // linked lights: the Cycles light sets they light
  std::map<PXR_NS::SdfPath, int> receivers;         // linked items: their Cycles receiver light set (1..63)
  std::vector<std::string> stormNotes;              // what the quick view (Storm) can't show, per light

  int receiver_set(const PXR_NS::SdfPath& prim) const;  // the deepest linked item holding `prim`; 0 = none
};

// lights_cameras.cpp, per light: spread, card (and its mesh), the links and the dome's camera visibility, as authored
void build_light_extras(Item& it, const PXR_NS::UsdPrim& light, const std::string& kind);
// light_card.cpp: the panel as an emissive mesh under the light, glowing at the light's own brightness (for Storm)
void build_card(Item& it, const PXR_NS::UsdPrim& light, const std::string& kind);
// stage_build.cpp, after every item is built: lightsOnly ids -> the lightLink collections; an unknown id fails loudly
void link_lights(const PXR_NS::UsdStageRefPtr& built);
// stage_build.cpp, on the built stage just before it replaces the held one: derive the table the filters read
void publish_light_extras(const PXR_NS::UsdStageRefPtr& stage);
const LightExtras& light_extras();

}  // namespace r3d
