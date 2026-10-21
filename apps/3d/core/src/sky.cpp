#include "sky.h"

#include <OpenImageIO/imagebuf.h>
#include <OpenImageIO/imagebufalgo.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/xformable.h>
#include <pxr/usd/usdLux/domeLight.h>
#include <pxr/usd/usdLux/domeLight_1.h>
#include <pxr/usd/usdLux/lightAPI.h>
#include <pxr/usd/usdLux/tokens.h>

#include <cmath>
#include <cstdio>
#include <filesystem>
#include <functional>

#include "error.h"
#include "studio.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
namespace fs = std::filesystem;
constexpr float kPi = 3.14159265358979323846f;

// `source` (a lat-long picture; "" = a flat white one) × `gain`, as an EXR in the cache, named by what made it
std::string sky_picture(const std::string& source, const GfVec3f& gain) {
  std::string stamp = "flat";
  if (!source.empty()) {
    std::error_code ec;
    const auto when = fs::last_write_time(source, ec);
    if (ec) throw Error("view.sky: the dome's picture can't be read: " + source + " (" + ec.message() + ")");
    stamp = std::to_string(std::hash<std::string>{}(source)) + "-" + std::to_string(when.time_since_epoch().count());
  }
  char name[160];
  std::snprintf(name, sizeof name, "sky-v2-%s-%.5f-%.5f-%.5f.exr", stamp.c_str(), gain[0], gain[1], gain[2]);
  const fs::path file = cache_dir() / name;
  if (fs::exists(file)) return file.string();
  fs::create_directories(file.parent_path());
  OIIO::ImageBuf buf;
  if (source.empty()) {
    buf.reset(OIIO::ImageSpec(8, 4, 3, OIIO::TypeDesc::FLOAT));
    OIIO::ImageBufAlgo::fill(buf, {1.0f, 1.0f, 1.0f});
  } else {
    OIIO::ImageBuf in(source);
    if (!in.read(0, 0, 0, 3, true, OIIO::TypeDesc::FLOAT))
      throw Error("view.sky: could not read the dome's picture " + source + ": " + in.geterror());
    buf = std::move(in);
  }
  const float g[3] = {gain[0], gain[1], gain[2]};
  OIIO::ImageBuf out = OIIO::ImageBufAlgo::mul(buf, g);
  if (out.has_error()) throw Error("view.sky: could not scale " + source + ": " + out.geterror());
  const fs::path partial = file.parent_path() / (file.stem().string() + ".partial.exr");
  if (!out.write(partial.string())) throw Error("view.sky: could not write " + partial.string() + ": " + out.geterror());
  std::error_code ec;
  fs::rename(partial, file, ec);
  if (ec) throw Error("view.sky: could not rename " + partial.string() + ": " + ec.message());
  return file.string();
}
}  // namespace

std::optional<GlfSimpleLight> scene_sky(const UsdStageRefPtr& stage, int frame) {
  for (const UsdPrim& p : stage->Traverse()) {
    if (!p.IsA<UsdLuxDomeLight>() && !p.IsA<UsdLuxDomeLight_1>()) continue;
    const UsdTimeCode t(frame);
    SdfAssetPath tex;
    p.GetAttribute(UsdLuxTokens->inputsTextureFile).Get(&tex, t);
    const std::string source = tex.GetResolvedPath().empty() ? tex.GetAssetPath() : tex.GetResolvedPath();
    UsdLuxLightAPI l(p);
    GfVec3f colour(1);
    float intensity = 1, exposure = 0;
    l.GetColorAttr().Get(&colour, t);
    l.GetIntensityAttr().Get(&intensity, t);
    l.GetExposureAttr().Get(&exposure, t);
    GlfSimpleLight sky = dome_light(sky_picture(source, colour * intensity * std::exp2(exposure) * kPi), "/RostrumViewport/sky");
    sky.SetTransform(UsdGeomXformable(p).ComputeLocalToWorldTransform(t));
    return sky;
  }
  return std::nullopt;
}

}  // namespace r3d
