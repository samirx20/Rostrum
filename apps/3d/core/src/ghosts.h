// Onion skin (brief 17): the view request's `ghosts`, read loudly. Each ghost is some items drawn as they are at
// another frame of the shot, tinted and see-through over the live picture (Hydra::view draws them, view_post.h
// lays them in). Viewport only: renders and the Final look never draw ghosts.
#pragma once
#include <pxr/base/js/value.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include <functional>
#include <string>
#include <vector>

namespace r3d {

struct Ghost {
  int frame = 0;
  PXR_NS::SdfPathVector items;   // the items' prims, drawn alone at `frame`
  float tint[3] = {1, 1, 1};     // linear RGB, 0..1
  float opacity = 0.35f;         // 0..1
};

constexpr int kMaxGhosts = 8;

// `check_frame(frame, where)` throws when a frame is outside the shot
std::vector<Ghost> read_ghosts(const PXR_NS::JsValue& v, const PXR_NS::UsdStageRefPtr& stage,
                               const std::function<void(int, const std::string&)>& check_frame);

}  // namespace r3d
