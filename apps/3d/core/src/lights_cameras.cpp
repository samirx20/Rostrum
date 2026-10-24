// Light and camera items (ENGINE_CONTRACT.md § 2). Attribute names checked against UsdLux / UsdGeomCamera
// and against how Cycles' Hydra plug-in reads them (hydra/light.cpp, hydra/camera.cpp).
#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/usdGeom/camera.h>
#include <pxr/usd/usdLux/diskLight.h>
#include <pxr/usd/usdLux/distantLight.h>
#include <pxr/usd/usdLux/domeLight.h>
#include <pxr/usd/usdLux/lightAPI.h>
#include <pxr/usd/usdLux/rectLight.h>
#include <pxr/usd/usdLux/shadowAPI.h>
#include <pxr/usd/usdLux/shapingAPI.h>
#include <pxr/usd/usdLux/sphereLight.h>

#include "item_track.h"
#include "light_extras.h"
#include "materials.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

// A float attribute from one field, times `scale` (e.g. mm -> tenths of a metre).
void write_float(Item& it, const UsdAttribute& attr, const std::string& key, double scale = 1.0) {
  const auto v = it.nums(key);
  it.write<float>(attr, v.size(), [&](size_t i) { return float(pick(v, i) * scale); });
}

UsdPrim define_light(Item& it, const SdfPath& path, const std::string& kind) {
  const UsdStageRefPtr& stage = it.ctx.stage;
  if (kind == "strip") {  // a long thin rect: its length along X, its width along Y
    UsdLuxRectLight l = UsdLuxRectLight::Define(stage, path);
    write_float(it, l.CreateWidthAttr(), "length");
    write_float(it, l.CreateHeightAttr(), "width");
    return l.GetPrim();
  }
  if (kind == "rect") {
    UsdLuxRectLight l = UsdLuxRectLight::Define(stage, path);
    write_float(it, l.CreateWidthAttr(), "width");
    write_float(it, l.CreateHeightAttr(), "height");
    return l.GetPrim();
  }
  if (kind == "disk") {
    UsdLuxDiskLight l = UsdLuxDiskLight::Define(stage, path);
    write_float(it, l.CreateRadiusAttr(), "radius");
    return l.GetPrim();
  }
  if (kind == "sphere") {
    UsdLuxSphereLight l = UsdLuxSphereLight::Define(stage, path);
    write_float(it, l.CreateRadiusAttr(), "radius");
    return l.GetPrim();
  }
  if (kind == "spot") {  // a bulb in a cone (UsdLux: the shaping cone's half angle; Cycles: a spot light)
    UsdLuxSphereLight l = UsdLuxSphereLight::Define(stage, path);
    write_float(it, l.CreateRadiusAttr(), "radius");
    UsdLuxShapingAPI shaping = UsdLuxShapingAPI::Apply(l.GetPrim());
    write_float(it, shaping.CreateShapingConeAngleAttr(), "cone", 0.5);
    write_float(it, shaping.CreateShapingConeSoftnessAttr(), "softness");
    return l.GetPrim();
  }
  if (kind == "distant") {
    UsdLuxDistantLight l = UsdLuxDistantLight::Define(stage, path);
    write_float(it, l.CreateAngleAttr(), "angle");
    return l.GetPrim();
  }
  UsdLuxDomeLight l = UsdLuxDomeLight::Define(stage, path);
  const std::string texture = it.props.str("texture");
  check_file(texture, it.props.at("texture"), "an HDR or EXR image");
  if (!texture.empty()) l.CreateTextureFileAttr().Set(SdfAssetPath(texture));
  return l.GetPrim();
}

}  // namespace

void build_light(Item& it, const SdfPath& path) {
  const std::string kind = it.props.one_of("kind", {"rect", "disk", "strip", "sphere", "spot", "distant", "dome"});
  const UsdPrim prim = define_light(it, path, kind);
  author_transform(it, prim);
  UsdLuxLightAPI light(prim);
  const auto colour = it.colours("color");
  it.write<GfVec3f>(light.CreateColorAttr(), colour.size(), [&](size_t i) { return pick(colour, i); });
  write_float(it, light.CreateIntensityAttr(), "intensity");
  write_float(it, light.CreateExposureAttr(), "exposure");
  // temperature 0 = off: the switch is a track of its own so a light can warm up from "off"
  const auto kelvin = it.nums("temperature");
  it.write<bool>(light.CreateEnableColorTemperatureAttr(), kelvin.size(), [&](size_t i) { return pick(kelvin, i) > 0; });
  it.write<float>(light.CreateColorTemperatureAttr(), kelvin.size(), [&](size_t i) {
    return pick(kelvin, i) > 0 ? float(pick(kelvin, i)) : 6500.0f;  // USD's fallback while switched off
  });
  light.CreateNormalizeAttr().Set(it.props.flag("normalize"));
  UsdLuxShadowAPI::Apply(prim).CreateShadowEnableAttr().Set(it.props.flag("shadows"));
  build_light_extras(it, prim, kind);  // spread, card, links, a dome's camera visibility (light_extras.h)
}

// USD measures focal length and apertures in tenths of a scene unit (usdGeom/camera.h, "Units of
// Measure"); HdCycles multiplies them by GfCamera's 0.1 unit and the stage's metersPerUnit. The scene is
// in metres, so a tenth of a unit is 100 mm: mm / 100.
void build_camera(Item& it, const SdfPath& path) {
  constexpr double kMmToTenthsOfAMetre = 0.01;
  UsdGeomCamera cam = UsdGeomCamera::Define(it.ctx.stage, path);
  author_transform(it, cam.GetPrim());
  write_float(it, cam.CreateFocalLengthAttr(), "focalLength", kMmToTenthsOfAMetre);
  const auto sensor = it.nums("sensorWidth");
  it.write<float>(cam.CreateHorizontalApertureAttr(), sensor.size(),
                  [&](size_t i) { return float(pick(sensor, i) * kMmToTenthsOfAMetre); });
  // The render sets the height from its aspect; 16:9 until then (and in a saved .usda).
  it.write<float>(cam.CreateVerticalApertureAttr(), sensor.size(),
                  [&](size_t i) { return float(pick(sensor, i) * 9.0 / 16.0 * kMmToTenthsOfAMetre); });
  const bool dof = it.props.flag("dof");
  const auto fstop = it.nums("fStop");
  it.write<float>(cam.CreateFStopAttr(), dof ? fstop.size() : 1,
                  [&](size_t i) { return dof ? float(pick(fstop, i)) : 0.0f; });  // f-stop 0 = no depth of field
  write_float(it, cam.CreateFocusDistanceAttr(), "focusDistance");
  // Motion blur: the shot's shutter, frame-relative and centred (USD's shutter:open / close; Cycles' Hydra plug-in
  // samples the camera's moves inside it, and the engine switches Cycles' motion blur on when it is open, hydra.cpp).
  cam.CreateShutterOpenAttr().Set(-it.ctx.shutter / 2);
  cam.CreateShutterCloseAttr().Set(it.ctx.shutter / 2);
  const auto near_ = it.nums("near"), far_ = it.nums("far");
  for (size_t i = 0; i < std::max(near_.size(), far_.size()); ++i)
    if (pick(near_, i) <= 0 || pick(far_, i) <= pick(near_, i))
      fail(it.id + (near_.size() > 1 || far_.size() > 1 ? ".anim" : "") + ".near",
           "near " + std::to_string(pick(near_, i)) + " / far " + std::to_string(pick(far_, i)),
           "0 < near < far (metres)");
  it.write<GfVec2f>(cam.CreateClippingRangeAttr(), frames({near_.size(), far_.size()}),
                    [&](size_t i) { return GfVec2f(float(pick(near_, i)), float(pick(far_, i))); });
}

}  // namespace r3d
