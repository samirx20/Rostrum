#include "image_out.h"

#include <OpenImageIO/color.h>
#include <OpenImageIO/imagebuf.h>
#include <OpenImageIO/imagebufalgo.h>

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>

#include "error.h"

namespace r3d {

namespace fs = std::filesystem;

struct ColorOut::Impl {
  OIIO::ColorConfig config;
  explicit Impl(const std::string& name) : config(name) {}
};

ColorOut::ColorOut() {
  const char* env = std::getenv("OCIO");
  impl_ = std::make_unique<Impl>(env && *env ? std::string(env) : std::string("ocio://cg-config-latest"));
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
  buf.set_write_format(type);
  if (!buf.write(partial.string()))
    throw Error("render: could not write " + partial.string() + ": " + buf.geterror());
  std::error_code ec;
  fs::rename(partial, target, ec);
  if (ec) throw Error("render: could not rename " + partial.string() + " to " + file + ": " + ec.message());
  if (fs::file_size(target) == 0) throw Error("render: " + file + " came out empty");
}
}  // namespace

void ColorOut::write_exr(const Picture& p, const std::string& file) const {
  auto buf = to_buf(p);
  buf.specmod().attribute("compression", "zip");
  write_whole(buf, file, OIIO::TypeDesc::HALF);
}

namespace {
// exposure, the background laid in where the picture is transparent, then the OpenColorIO display view
OIIO::ImageBuf displayed(const Picture& p, OIIO::ColorConfig& config, const std::string& display,
                         const std::string& view, double exposure, const float background[3]) {
  Picture lit = p;
  const float gain = float(std::pow(2.0, exposure));
  for (size_t i = 0; i < lit.rgba.size(); i += 4) {
    float a = std::min(std::max(lit.rgba[i + 3], 0.0f), 1.0f);
    for (int c = 0; c < 3; ++c) lit.rgba[i + c] = lit.rgba[i + c] * gain + background[c] * gain * (1 - a);
    lit.rgba[i + 3] = 1.0f;
  }
  auto src = to_buf(lit);
  OIIO::ImageBuf shown;
  if (!OIIO::ImageBufAlgo::ociodisplay(shown, src, display, view, "scene_linear", "", false, false, "", "",
                                       &config))
    throw Error("render: the OpenColorIO view transform failed: " + shown.geterror());
  return shown;
}
}  // namespace

void ColorOut::write_png(const Picture& p, const std::string& file, const std::string& view, double exposure,
                         const float background[3]) const {
  auto shown = displayed(p, impl_->config, display_, check_view(view), exposure, background);
  write_whole(shown, file, OIIO::TypeDesc::UINT8);
}

void ColorOut::to_rgba8(const Picture& p, const std::string& view, double exposure, const float background[3],
                        unsigned char* dst) const {
  auto shown = displayed(p, impl_->config, display_, check_view(view), exposure, background);
  if (!shown.get_pixels(OIIO::ROI(0, p.width, 0, p.height, 0, 1, 0, 4), OIIO::TypeDesc::UINT8, dst))
    throw Error("view: could not read the displayed picture: " + shown.geterror());
}

std::string frame_path(const std::string& pattern, int frame) {
  auto at = pattern.find("{frame}");
  if (at == std::string::npos) return pattern;
  char num[16];
  std::snprintf(num, sizeof(num), "%04d", frame);
  return pattern.substr(0, at) + num + pattern.substr(at + 7);
}

}  // namespace r3d
