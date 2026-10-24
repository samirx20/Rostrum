#include "image_out.h"

#include <OpenImageIO/color.h>
#include <OpenImageIO/imagebuf.h>
#include <OpenImageIO/imagebufalgo.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <mutex>
#include <thread>

#include "error.h"

namespace r3d {

namespace fs = std::filesystem;

struct ColorOut::Impl {
  OIIO::ColorConfig config;
  std::map<std::string, OIIO::ColorProcessorHandle> views;  // display transforms, made once per view
  std::mutex lock;
  explicit Impl(const std::string& name) : config(name) {}
  const OIIO::ColorProcessor& processor(const std::string& display, const std::string& view) {
    std::lock_guard<std::mutex> g(lock);
    auto& h = views[view];
    if (!h) h = config.createDisplayTransform(display, view, "scene_linear");
    if (!h) throw Error("render: OpenColorIO could not make the view transform for \"" + view + "\": " + config.geterror());
    return *h;
  }
};

ColorOut::ColorOut() {
  const char* env = std::getenv("OCIO");
  name_ = env && *env ? std::string(env) : std::string("ocio://cg-config-latest");
  impl_ = std::make_unique<Impl>(name_);
  if (impl_->config.has_error() || impl_->config.getNumDisplays() == 0)
    throw Error("colour: could not load the OpenColorIO config '" + impl_->config.configname() +
                "': " + impl_->config.geterror());
  display_ = impl_->config.getDefaultDisplayName();
  for (const auto& d : impl_->config.getDisplayNames())  // prefer a plain sRGB monitor
    if (d.rfind("sRGB", 0) == 0) { display_ = d; break; }
}

ColorOut::~ColorOut() = default;

std::string ColorOut::config() const { return impl_->config.configname(); }

std::map<std::string, std::vector<std::string>> ColorOut::views() const {
  std::map<std::string, std::vector<std::string>> out;
  for (const auto& d : impl_->config.getDisplayNames()) out[d] = impl_->config.getViewNames(d);
  return out;
}

std::string ColorOut::check_view(const std::string& view) const {
  if (view.empty()) return impl_->config.getDefaultViewName(display_);
  auto names = impl_->config.getViewNames(display_);
  for (const auto& n : names)
    if (n == view) return n;
  std::string list;
  for (const auto& n : names) list += (list.empty() ? "" : ", ") + n;
  throw Error("render.view: \"" + view + "\" is not a view of display \"" + display_ + "\". Accepted: " + list);
}

namespace {
OIIO::ImageBuf to_buf(const Picture& p) {
  OIIO::ImageSpec spec(p.width, p.height, 4, OIIO::TypeDesc::FLOAT);
  spec.alpha_channel = 3;
  OIIO::ImageBuf buf(spec);
  buf.set_pixels(OIIO::ROI::All(), OIIO::TypeDesc::FLOAT, p.rgba.data());
  return buf;
}

void write_whole(OIIO::ImageBuf& buf, const std::string& file, OIIO::TypeDesc type) {
  fs::path target(file);
  if (target.has_parent_path()) fs::create_directories(target.parent_path());
  // keep the real extension last so OpenImageIO picks the right writer
  fs::path partial = target.parent_path() / (target.stem().string() + ".partial" + target.extension().string());
  if (type != OIIO::TypeDesc::UNKNOWN) buf.set_write_format(type);  // UNKNOWN: the caller set each channel's type
  if (!buf.write(partial.string()))
    throw Error("render: could not write " + partial.string() + ": " + buf.geterror());
  std::error_code ec;
  fs::rename(partial, target, ec);
  if (ec) throw Error("render: could not rename " + partial.string() + " to " + file + ": " + ec.message());
  if (fs::file_size(target) == 0) throw Error("render: " + file + " came out empty");
}
}  // namespace

void ColorOut::write_exr(const Picture& p, const std::string& file, const std::vector<ExrLayer>& layers) const {
  if (layers.empty()) {
    auto buf = to_buf(p);
    buf.specmod().attribute("compression", "zip");
    write_whole(buf, file, OIIO::TypeDesc::HALF);
    return;
  }
  // R G B A first, then every layer's channels, interleaved into one picture; each channel keeps its own type
  std::vector<std::string> names{"R", "G", "B", "A"};
  std::vector<OIIO::TypeDesc> types(4, OIIO::TypeDesc::HALF);
  for (const auto& l : layers) {
    if (l.pixels.size() != size_t(p.width) * p.height * l.channels.size())
      throw Error("render: the " + l.channels.front() + " layer has the wrong number of pixels");
    for (const auto& c : l.channels) names.push_back(c), types.push_back(l.full ? OIIO::TypeDesc::FLOAT : OIIO::TypeDesc::HALF);
  }
  const size_t n = names.size(), count = size_t(p.width) * p.height;
  std::vector<float> all(count * n);
  for (size_t i = 0; i < count; ++i) std::copy_n(&p.rgba[i * 4], 4, &all[i * n]);
  size_t at = 4;
  for (const auto& l : layers) {
    const size_t k = l.channels.size();
    for (size_t i = 0; i < count; ++i) std::copy_n(&l.pixels[i * k], k, &all[i * n + at]);
    at += k;
  }
  OIIO::ImageSpec spec(p.width, p.height, int(n), OIIO::TypeDesc::FLOAT);
  spec.channelnames = names;
  spec.alpha_channel = 3;
  spec.attribute("compression", "zip");
  OIIO::ImageBuf buf(spec);
  buf.set_pixels(OIIO::ROI::All(), OIIO::TypeDesc::FLOAT, all.data());
  buf.set_write_format(types);
  write_whole(buf, file, OIIO::TypeDesc::UNKNOWN);
}

// The picture path for files (the live viewport does the same on the graphics card: view_post.h): exposure, the background laid in where the picture is
// transparent, then the OpenColorIO display view (made once per view, applied in bands on all cores).
std::vector<float> ColorOut::displayed(const Picture& p, const std::string& view, double exposure,
                                       const float background[3]) const {
  const auto& proc = impl_->processor(display_, check_view(view));
  std::vector<float> lit(p.rgba);
  const float gain = float(std::pow(2.0, exposure));
  for (size_t i = 0; i < lit.size(); i += 4) {
    float a = std::min(std::max(lit[i + 3], 0.0f), 1.0f);
    for (int c = 0; c < 3; ++c) lit[i + c] = lit[i + c] * gain + background[c] * gain * (1 - a);
    lit[i + 3] = 1.0f;
  }
  const int bands = std::max(1, std::min(int(std::thread::hardware_concurrency()), 8));
  const int rows = (p.height + bands - 1) / bands;
  std::vector<std::thread> workers;
  for (int b = 0; b < bands; ++b) {
    const int y0 = b * rows, n = std::min(rows, p.height - y0);
    if (n <= 0) break;
    workers.emplace_back([&, y0, n] {
      proc.apply(lit.data() + size_t(y0) * p.width * 4, p.width, n, 4, sizeof(float), 4 * sizeof(float),
                 OIIO::stride_t(p.width) * 4 * sizeof(float));
    });
  }
  for (auto& w : workers) w.join();
  return lit;
}

void ColorOut::write_png(const Picture& p, const std::string& file, const std::string& view, double exposure,
                         const float background[3]) const {
  Picture shown{p.width, p.height, displayed(p, view, exposure, background)};
  auto buf = to_buf(shown);
  write_whole(buf, file, OIIO::TypeDesc::UINT8);
}

std::string frame_path(const std::string& pattern, int frame) {
  auto at = pattern.find("{frame}");
  if (at == std::string::npos) return pattern;
  char num[16];
  std::snprintf(num, sizeof(num), "%04d", frame);
  return pattern.substr(0, at) + num + pattern.substr(at + 7);
}

}  // namespace r3d
