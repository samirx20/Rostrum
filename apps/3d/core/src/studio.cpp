#include "studio.h"

#include <OpenImageIO/imagebuf.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
namespace fs = std::filesystem;
constexpr int kW = 512, kH = 256;
constexpr double kPi = 3.14159265358979323846;

double smooth(double e0, double e1, double x) {
  const double t = std::clamp((x - e0) / (e1 - e0), 0.0, 1.0);
  return t * t * (3 - 2 * t);
}

// a soft rectangle on the sphere: centre azimuth/elevation, half sizes, all in degrees
double box(double az, double el, double caz, double cel, double haz, double hel) {
  double d = std::fmod(az - caz + 540.0, 360.0) - 180.0;
  const double fx = 1 - smooth(haz * 0.7, haz, std::abs(d)), fy = 1 - smooth(hel * 0.7, hel, std::abs(el - cel));
  return fx * fy;
}

// linear radiance of the studio in the direction (azimuth, elevation), degrees
float studio(double az, double el) {
  double v = el > 0 ? 0.16 + 0.10 * (el / 90.0) : 0.05 + 0.08 * smooth(-25, 0, el);  // grey sweep, darker floor
  v += 5.0 * box(az, el, -35, 50, 32, 18);   // big soft box, overhead left
  v += 3.5 * box(az, el, 95, 12, 6, 34);     // tall strip right
  v += 2.5 * box(az, el, -125, 12, 6, 34);   // tall strip back left
  v += 1.2 * box(az, el, 150, 70, 40, 12);   // a soft top bounce behind
  return float(v);
}

}  // namespace

fs::path cache_dir() {
  const char* home = std::getenv("USERPROFILE");
  return fs::path(home && *home ? home : ".") / ".rostrum" / "cache" / "3d";
}

std::string studio_texture(double strength) {
  const int tenth = int(std::lround(std::clamp(strength, 0.0, 4.0) * 10));
  const fs::path file = cache_dir() / ("studio-v1-" + std::to_string(tenth) + ".exr");
  if (fs::exists(file)) return file.string();
  fs::create_directories(file.parent_path());
  OIIO::ImageBuf buf(OIIO::ImageSpec(kW, kH, 3, OIIO::TypeDesc::FLOAT));
  std::vector<float> px(size_t(kW) * kH * 3);
  for (int y = 0; y < kH; ++y)
    for (int x = 0; x < kW; ++x) {
      const double az = (x + 0.5) / kW * 360.0 - 180.0, el = 90.0 - (y + 0.5) / kH * 180.0;
      const float v = studio(az, el) * float(tenth) / 10.0f;
      for (int c = 0; c < 3; ++c) px[(size_t(y) * kW + x) * 3 + c] = v;
    }
  buf.set_pixels(OIIO::ROI::All(), OIIO::TypeDesc::FLOAT, px.data());
  buf.set_write_format(OIIO::TypeDesc::HALF);
  const fs::path partial = file.parent_path() / (file.stem().string() + ".partial.exr");
  if (!buf.write(partial.string())) throw Error("view.studio: could not write " + partial.string() + ": " + buf.geterror());
  std::error_code ec;
  fs::rename(partial, file, ec);
  if (ec) throw Error("view.studio: could not rename " + partial.string() + ": " + ec.message());
  return file.string();
}

GlfSimpleLight dome_light(const std::string& texture, const char* id) {
  GlfSimpleLight dome;
  dome.SetIsDomeLight(true);
  dome.SetID(SdfPath(id));
  dome.SetDomeLightTextureFile(SdfAssetPath(texture, texture));
  dome.SetDiffuse(GfVec4f(1));
  dome.SetSpecular(GfVec4f(1));
  dome.SetAmbient(GfVec4f(0));
  dome.SetTransform(GfMatrix4d(1));
  return dome;
}

GlfSimpleLightVector studio_lights(double strength) {
  if (strength <= 0) return {};
  return {dome_light(studio_texture(strength), "/RostrumViewport/studio")};
}

}  // namespace r3d
