#include "dome_sun.h"

#include <OpenImageIO/imagebuf.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <vector>

#include "error.h"
#include "studio.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
namespace fs = std::filesystem;
constexpr double kPi = 3.14159265358979323846;
constexpr const char* kVersion = "domesun-v1";  // bump when the analysis changes: old cache files are then ignored
constexpr double kPeakPart = 0.05;      // the patch: pixels at least this part of the brightest one ...
constexpr double kOverMean = 20;        // ... and this many times the dome's mean brightness
constexpr double kMaxSolidAngle = 0.05; // larger than this (a cone of ~14°) is a bright sky, not a sun
constexpr double kMinShare = 0.10;      // a patch with less of the light is left in the dome

double luma(const float* c) { return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; }

// the analysis itself: finds the patch, paints it over with the sky around it (in `px`) and measures what it took out
std::optional<DomeSun> take_out_sun(std::vector<float>& px, int w, int h) {
  const double du = 2 * kPi / w, dv = kPi / h;
  auto omega = [&](int y) { return du * dv * std::sin((y + 0.5) * dv); };
  double total = 0, peak = 0;
  size_t peak_at = 0;
  for (int y = 0; y < h; ++y)
    for (int x = 0; x < w; ++x) {
      const size_t i = size_t(y) * w + x;
      const double l = luma(&px[i * 3]);
      total += l * omega(y);
      if (l > peak) peak = l, peak_at = i;
    }
  const double mean = total / (4 * kPi);
  if (total <= 0 || peak < kOverMean * mean) return std::nullopt;
  const double threshold = std::max(kPeakPart * peak, kOverMean * mean);

  // the connected patch around the brightest pixel (8 neighbours, wrapping left-right)
  std::vector<char> in(size_t(w) * h, 0);
  std::vector<size_t> patch, todo{peak_at};
  in[peak_at] = 1;
  double solid = 0;
  auto neighbours = [&](size_t i, const std::function<void(size_t)>& f) {
    const int x = int(i % w), y = int(i / w);
    for (int dy = -1; dy <= 1; ++dy)
      for (int dx = -1; dx <= 1; ++dx) {
        const int ny = y + dy;
        if ((dx || dy) && ny >= 0 && ny < h) f(size_t(ny) * w + (x + dx + w) % w);
      }
  };
  while (!todo.empty()) {
    const size_t i = todo.back();
    todo.pop_back();
    patch.push_back(i);
    solid += omega(int(i / w));
    if (solid > kMaxSolidAngle) return std::nullopt;
    neighbours(i, [&](size_t n) {
      if (!in[n] && luma(&px[n * 3]) >= threshold) in[n] = 1, todo.push_back(n);
    });
  }
  // the sky just around the patch: what the patch is painted with
  double fill[3] = {0, 0, 0};
  int ring = 0;
  std::vector<char> seen(in);
  for (size_t i : patch)
    neighbours(i, [&](size_t n) {
      if (seen[n]) return;
      seen[n] = 1, ++ring;
      for (int c = 0; c < 3; ++c) fill[c] += px[n * 3 + c];
    });
  for (double& f : fill) f = ring ? f / ring : 0.0;

  DomeSun sun;
  GfVec3d e(0), dir(0);
  for (size_t i : patch) {
    const int x = int(i % w), y = int(i / w);
    const double th = (y + 0.5) * dv, ph = (x + 0.5) * du - kPi / 2;  // inverse of u, v (dome_sun.h)
    const GfVec3d d(std::sin(th) * std::cos(ph), std::cos(th), std::sin(th) * std::sin(ph));
    float excess[3];
    for (int c = 0; c < 3; ++c) {
      excess[c] = float(std::max(0.0, px[i * 3 + c] - fill[c]));
      e[c] += excess[c] * omega(y);
      px[i * 3 + c] = float(fill[c]);
    }
    dir += d * (luma(excess) * omega(y));
  }
  if (dir.GetLength() <= 0) return std::nullopt;
  sun.toward = dir.GetNormalized();
  sun.irradiance = GfVec3f(float(e[0]), float(e[1]), float(e[2]));
  sun.solidAngle = solid;
  sun.share = (0.2126 * e[0] + 0.7152 * e[1] + 0.0722 * e[2]) / total;
  if (sun.share < kMinShare) return std::nullopt;
  return sun;
}

void write_exr(const OIIO::ImageSpec& spec, const std::vector<float>& px, const fs::path& file) {
  OIIO::ImageBuf out(spec);
  out.set_pixels(OIIO::ROI::All(), OIIO::TypeDesc::FLOAT, px.data());
  const fs::path partial = file.parent_path() / (file.stem().string() + ".partial.exr");
  if (!out.write(partial.string())) throw Error("view.sky: could not write " + partial.string() + ": " + out.geterror());
  std::error_code ec;
  fs::rename(partial, file, ec);
  if (ec) throw Error("view.sky: could not rename " + partial.string() + ": " + ec.message());
}

std::optional<DomeSplit> read_record(const fs::path& record, const fs::path& picture, const std::string& source) {
  std::ifstream in(record);
  std::string head;
  if (!(in >> head) || head != kVersion) return std::nullopt;
  std::string what;
  in >> what;
  if (what == "none") return DomeSplit{source, std::nullopt};
  DomeSun s;
  if (what != "sun" || !(in >> s.toward[0] >> s.toward[1] >> s.toward[2] >> s.irradiance[0] >> s.irradiance[1] >>
                         s.irradiance[2] >> s.solidAngle >> s.share) || !fs::exists(picture))
    return std::nullopt;
  return DomeSplit{picture.string(), s};
}

DomeSplit analyse(const std::string& source, const fs::path& record, const fs::path& picture) {
  OIIO::ImageBuf in(source);
  if (!in.read(0, 0, 0, 3, true, OIIO::TypeDesc::FLOAT))
    throw Error("view.sky: could not read the dome's picture " + source + ": " + in.geterror());
  const OIIO::ImageSpec& s = in.spec();
  DomeSplit split{source, std::nullopt};
  if (s.nchannels >= 3) {
    std::vector<float> px(size_t(s.width) * s.height * 3);
    if (!in.get_pixels(OIIO::ROI(0, s.width, 0, s.height, 0, 1, 0, 3), OIIO::TypeDesc::FLOAT, px.data()))
      throw Error("view.sky: could not read the pixels of " + source + ": " + in.geterror());
    split.sun = take_out_sun(px, s.width, s.height);
    if (split.sun) {
      write_exr(OIIO::ImageSpec(s.width, s.height, 3, OIIO::TypeDesc::FLOAT), px, picture);
      split.picture = picture.string();
    }
  }
  std::ofstream out(record, std::ios::trunc);
  out.precision(9);
  out << kVersion << "\n";
  if (split.sun)
    out << "sun " << split.sun->toward[0] << " " << split.sun->toward[1] << " " << split.sun->toward[2] << " "
        << split.sun->irradiance[0] << " " << split.sun->irradiance[1] << " " << split.sun->irradiance[2] << " "
        << split.sun->solidAngle << " " << split.sun->share << "\n";
  else
    out << "none\n";
  if (!out) throw Error("view.sky: could not write " + record.string());
  return split;
}
}  // namespace

std::string picture_stamp(const std::string& source) {
  std::error_code ec;
  const auto when = fs::last_write_time(source, ec);
  const auto size = ec ? 0 : fs::file_size(source, ec);
  if (ec) throw Error("view.sky: the dome's picture can't be read: " + source + " (" + ec.message() + ")");
  return std::to_string(std::hash<std::string>{}(source)) + "-" + std::to_string(when.time_since_epoch().count()) +
         "-" + std::to_string(size);
}

DomeSplit split_dome_sun(const std::string& source) {
  static std::map<std::string, DomeSplit> known;  // stamp -> split: the cache files are read once per run
  const std::string stamp = picture_stamp(source);
  if (auto it = known.find(stamp); it != known.end()) return it->second;
  const fs::path dir = cache_dir();
  fs::create_directories(dir);
  const fs::path record = dir / (std::string(kVersion) + "-" + stamp + ".txt");
  const fs::path picture = dir / (std::string(kVersion) + "-" + stamp + ".exr");
  auto split = read_record(record, picture, source);
  if (!split) split = analyse(source, record, picture);
  return known[stamp] = *split;
}

}  // namespace r3d
