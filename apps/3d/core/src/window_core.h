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
  // The same with no GL at all, for a request that needs none and is slow (runs_aside): a clay stroke's end (the stroke
  // applied again as one unit, 50-600 ms), a scene's clays brought to their steps. Any thread, as long as nothing else
  // uses this core meanwhile (the view item holds its other requests and draws nothing until it is answered).
  std::string answer_without_gl(const std::string& line);
  static bool is_stroke_end(const std::string& line);
  // A request the window answers on a worker (answer_without_gl), drawing its other things meanwhile with the view's
  // last picture held: a stroke's end, and a scene holding a clay (its clays brought to their steps: an undo of a
  // stroke, a redo, a document opened; up to ~1.5 s that held the whole window's drawing). Not a scene whose copies
  // are seen-tested by a camera: that test draws with Hydra (GL), so that scene is answered on the drawing step.
  static bool runs_aside(const std::string& line);
  // Any one thread (the GUI's), only while no request of this core is waiting for its answer: a `sculpt` dab line's
  // clay work started now on a worker (Core::sculpt_ahead), so that when answer() gets the same line only its blocks
  // are written and the picture drawn. False when it can't start (no live stroke, another camera): answer() does all.
  bool ahead(const std::string& line);
  static bool is_stroke_dab(const std::string& line);
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
