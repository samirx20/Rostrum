// Pictures out: scene-linear half-float EXR for the Editor, and an 8-bit PNG through OpenColorIO for
// people and agents. Every file is written to <name>.partial and renamed only when whole.
#pragma once
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace r3d {

// the sun Storm took out of the scene's dome and drew as a light with a shadow (dome_sun.h)
struct SunSeen {
  double toward[3] = {0, 0, 0};  // world direction towards it
  double share = 0;              // its part of the dome's light
  double angleDeg = 0;           // its apparent size
};

struct Picture {
  int width = 0, height = 0;
  std::vector<float> rgba;  // scene-linear, straight from Hydra, top row first
  std::vector<unsigned char> mask;  // viewport only: 1 where a selected item is (empty = nothing selected)
  bool sceneDome = false;  // viewport only: the scene's own dome lit it (the studio light was not used)
  std::optional<SunSeen> sun;  // viewport only: Storm drew the dome's sun as a light
};

class ColorOut {
 public:
  ColorOut();  // the config named by $OCIO, else OpenColorIO's built-in CG config
  ~ColorOut();
  std::string config() const;
  std::string display() const { return display_; }
  std::map<std::string, std::vector<std::string>> views() const;
  // throws r3d::Error listing the accepted views when `view` is unknown ("" = the display's default)
  std::string check_view(const std::string& view) const;
  void write_exr(const Picture& p, const std::string& file) const;
  // exposure in stops; the picture is laid over `background` (linear RGB) where it is transparent
  void write_png(const Picture& p, const std::string& file, const std::string& view, double exposure,
                 const float background[3]) const;
  // the same picture as write_png, as straight 8-bit RGBA (top row first) into `dst` (width * height * 4 bytes)
  void to_rgba8(const Picture& p, const std::string& view, double exposure, const float background[3],
                unsigned char* dst) const;

 private:
  std::vector<float> displayed(const Picture& p, const std::string& view, double exposure,
                               const float background[3]) const;
  struct Impl;
  std::unique_ptr<Impl> impl_;
  std::string display_;
};

// "C:/out/f-{frame}.png", 12 -> "C:/out/f-0012.png"
std::string frame_path(const std::string& pattern, int frame);

}  // namespace r3d
