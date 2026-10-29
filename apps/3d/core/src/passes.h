// The render passes (SPEC §11.2 "Passes", EXR only): the names people and agents choose, the Hydra outputs each
// needs from Cycles, and the EXR layers made from them (written beside the beauty by image_out.*).
//
//   light        light.R G B        light on matte surfaces (Cycles' diffuse, direct + bounced, colour included)
//   reflections  reflections.R G B  reflections and highlights (Cycles' glossy)
//   (with either) rest.R G B        everything else: glass, glow, sky and haze (transmission + emission +
//                                   background + volume), so  light + reflections + rest = beauty before noise clean-up
//   shadow       shadow.A           0 lit .. 1 in full shadow: how much of the lights' direct light a matte surface
//                                   loses to shadows (a second render with no shadows, so it doubles the time)
//   masks        masks.<item id>    1 where the item (a top-level item, with all it holds) is, else 0; hard-edged
//   depth        depth.Z            distance from the camera plane in metres (32-bit); 0 where nothing is
//   normal       normal.X Y Z       surface direction, world space (Y up), -1..1; 0 where nothing is
//   lightGroups  lightgroup_<light>.R G B  each light's own share of the picture (a dome's sky too), as seen; they
//                                   add up to the picture before noise clean-up, less what glows on its own
//                                   (emissive surfaces): re-balance lights in the Editor. Not cleaned of noise
//   cryptomatte  CryptoObject00..02.R G B A  soft-edged masks per item in the Cryptomatte form (cryptomatte.h)
//   motion       motion.X Y Z W     motion vectors in pixels, x right, y up: X Y = where the point was a frame
//                                   before minus where it is, Z W = where it is minus where it will be a frame
//                                   after (Blender's "Vector"). Cycles makes them only with its motion blur off, so
//                                   with this pass the picture renders sharp and the Editor adds the blur
#pragma once
#include <pxr/base/js/value.h>
#include <pxr/usd/usd/stage.h>

#include <string>
#include <vector>

#include "aovs.h"
#include "image_out.h"

namespace r3d {

// "render.passes" as asked (a list of the names above, each once); throws listing the accepted names
std::vector<std::string> read_passes(const PXR_NS::JsValue& v, const std::string& where);

// the Hydra outputs Cycles must make for `passes` (empty for none); the light groups are the stage's lights
std::vector<std::string> aovs_for(const std::vector<std::string>& passes, const PXR_NS::UsdStageRefPtr& stage);

// the Shadow pass needs the frame again with no shadows (Hydra's rostrum:castShadows off)
bool needs_unshadowed(const std::vector<std::string>& passes);

// the Motion pass needs Cycles' motion blur off and every move sampled a frame either side (hydra.cpp)
bool needs_motion(const std::vector<std::string>& passes);

// the layers for `passes` from a render's outputs (`unshadowed`: the second render, only read for shadow)
std::vector<ExrLayer> pass_layers(const std::vector<std::string>& passes, const Aovs& lit, const Aovs& unshadowed,
                                  const PXR_NS::UsdStageRefPtr& stage);

// loud when the picture came out empty while a layer is not (the colour output went missing: brief 15)
void check_beauty(const Picture& beauty, const std::vector<ExrLayer>& layers, int frame);

}  // namespace r3d
