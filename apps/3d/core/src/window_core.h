// The engine's Core inside the app's window (view/viewport_item.h): the same requests and replies as the engine
// program (serve.h `answer`), on the window's own GL context, with `view` pictures drawn straight into the view item's
// texture instead of shared memory. No pxr, Qt or GL headers here, so the Qt side includes it without their clashes.
// Everything in it belongs to the thread that made it (Qt Quick's render thread), with the window's context current.
#pragma once
#include <memory>
#include <string>

namespace r3d {

class Core;

class WindowCore {
 public:
  WindowCore();  // the window's GL context must be current
  ~WindowCore();
  WindowCore(const WindowCore&) = delete;
  WindowCore& operator=(const WindowCore&) = delete;
  // the view item's colour texture (GL name) and its size: `view` pictures land there, scaled to fit
  // (true when it changed: what was drawn there is gone)
  bool set_texture(unsigned tex, int width, int height);
  int views_drawn() const;  // `view` pictures drawn so far (a sculpt request may draw one too)
  // one ENGINE_CONTRACT request line -> its reply line (never throws). Puts GL's state the way Hydra expects first
  // (Qt Quick leaves its own behind) and keeps no framebuffer of its own bound after.
  std::string answer(const std::string& line);
  // clear the texture (no scene drawn yet)
  void clear();
  std::string gl_renderer() const;

 private:
  void reset_gl_state();
  std::unique_ptr<Core> core_;
  unsigned fbo_ = 0, tex_ = 0;
  int w_ = 0, h_ = 0;
};

}  // namespace r3d
