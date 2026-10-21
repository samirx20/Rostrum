// Pictures out: scene-linear half-float EXR for the Editor, and an 8-bit PNG through OpenColorIO for
// people and agents. Every file is written to <name>.partial and renamed only when whole.
#pragma once
#include <map>
#include <memory>
#include <string>
#include <vector>

namespace r3d {

struct Picture {
  int width = 0, height = 0;
  std::vector<float> rgba;  // scene-linear, straight from Hydra, top row first
};

class ColorOut {
 public:
  ColorOut();  // the config named by $OCIO, else OpenColorIO's built-in CG config
  ~ColorOut();
  std::string config() const;
  const std::string& config_name() const { return name_; }  // as given ($OCIO or the built-in's ocio:// name)
  std::string display() const { return display_; }
  std::map<std::string, std::vector<std::string>> views() const;
  // throws r3d::Error listing the accepted views when `view` is unknown ("" = the display's default)
  std::string check_view(const std::string& view) const;
  void write_exr(const Picture& p, const std::string& file) const;
  // exposure in stops; the picture is laid over `background` (linear RGB) where it is transparent
  void write_png(const Picture& p, const std::string& file, const std::string& view, double exposure,
                 const float background[3]) const;

 private:
  std::vector<float> displayed(const Picture& p, const std::string& view, double exposure,
                               const float background[3]) const;
  struct Impl;
  std::unique_ptr<Impl> impl_;
  std::string display_, name_;
};

// "C:/out/f-{frame}.png", 12 -> "C:/out/f-0012.png"
std::string frame_path(const std::string& pattern, int frame);

}  // namespace r3d
