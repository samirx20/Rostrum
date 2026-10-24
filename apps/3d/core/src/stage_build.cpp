#include "stage_build.h"

#include <pxr/base/gf/vec3f.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usdGeom/metrics.h>
#include <pxr/usd/usdGeom/scope.h>
#include <pxr/usd/usdGeom/tokens.h>
#include <pxr/usd/usdGeom/xform.h>

#include "json_read.h"
#include "light_extras.h"
#include "materials.h"
#include "stage_items.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

BuildResult build_stage(const JsObject& scene, const UsdStageRefPtr& stage) {
  Reader s(scene, "scene");
  const std::string format = s.str("format");
  if (format != "rostrum-3d-scene") fail(s.at("format"), "\"" + format + "\" is not a scene", "\"rostrum-3d-scene\"");
  const double version = s.num("version");
  if (version != 1) fail(s.at("version"), std::to_string(version) + " is not known to this core", "1");

  Reader shot(s.object("shot"), "shot");
  const std::string shot_id = shot.str("id");
  const double fps = shot.num_min("fps", 0.0, false);
  const int start = shot.count("start", -1000000, 1000000);
  const int end = shot.count("end", start, 1000000);
  const double shutter = shot.num("shutter");  // frames; 0 = no motion blur (ENGINE_CONTRACT.md § 2)
  if (shutter < 0 || shutter > 1) fail(shot.at("shutter"), std::to_string(shutter), "0 (off) to 1 frame");
  shot.finish();

  Reader world(s.object("world"), "world");
  const GfVec3f background = world.vec3("background");
  const JsValue& environment = world.get("environment", "null");
  if (!environment.IsNull())
    fail(world.at("environment"), "is " + environment.GetTypeName(), "null (version 1 lights the world with a dome light)");
  world.finish();

  // Built on a stage of its own, so a scene that fails halfway leaves the held stage as it was.
  UsdStageRefPtr built = UsdStage::CreateInMemory();
  UsdGeomSetStageUpAxis(built, UsdGeomTokens->y);
  UsdGeomSetStageMetersPerUnit(built, 1.0);
  const SdfLayerHandle layer = built->GetRootLayer();
  layer->SetDefaultPrim(TfToken("World"));
  layer->SetStartTimeCode(start);
  layer->SetEndTimeCode(end);
  layer->SetTimeCodesPerSecond(fps);  // frame n is time code n
  layer->SetFramesPerSecond(fps);

  UsdPrim root = UsdGeomXform::Define(built, SdfPath("/World")).GetPrim();
  // The renderer side reads the background colour (linear RGB) from here.
  root.CreateAttribute(TfToken("rostrum:background"), SdfValueTypeNames->Color3f, true).Set(background);
  root.CreateAttribute(TfToken("rostrum:shot"), SdfValueTypeNames->String, true).Set(shot_id);
  UsdGeomScope::Define(built, SdfPath("/World/Looks"));

  ItemsContext ctx;
  ctx.stage = built;
  ctx.start = start;
  ctx.end = end;
  ctx.shutter = shutter;
  ctx.materials = build_materials(built, s.list("materials"), start, end);
  build_items(ctx, s.list("items"), SdfPath("/World"), "items");
  link_lights(built);  // lightsOnly ids -> UsdLux lightLink collections, once every item exists
  s.finish();

  BuildResult result;
  result.items = ctx.items;
  layer->Traverse(SdfPath::AbsoluteRootPath(), [&](const SdfPath& p) {
    if (p.IsPrimPath()) ++result.prims;
  });
  result.start = start;
  result.end = end;
  result.fps = fps;
  publish_light_extras(built);  // what the Hydra filters hand the renderers (light_extras.h); same paths once moved
  stage->GetRootLayer()->TransferContent(layer);
  return result;
}

}  // namespace r3d
