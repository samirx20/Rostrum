// A hidden OpenGL context and an offscreen float framebuffer. Hydra (Hgi) needs a current GL context
// for every renderer, and composites its colour result into the framebuffer that is bound.
#pragma once
#include <string>
#include <vector>

namespace r3d {

class GlContext {
 public:
  GlContext();   // hidden window + OpenGL 4.6 compatibility context, made current; throws r3d::Error
  // the context current on this thread, someone else's (the window's view, window_core.h): nothing made or destroyed
  struct Borrow {};
  explicit GlContext(Borrow) {}
  ~GlContext();
  GlContext(const GlContext&) = delete;
  GlContext& operator=(const GlContext&) = delete;
  std::string renderer() const;  // GL_RENDERER: which chip draws (the RTX, we hope)
  void finish() const;
  // borrowed: what is drawn next on this context (the window's own view post and Qt Quick) runs after it on the GPU
  // anyway, so the view waits for nothing (a GL finish here held a dab's frame ~2-5 ms for the GPU)
  bool borrowed() const { return rc_ == nullptr; }

 private:
  void* wnd_ = nullptr;
  void* dc_ = nullptr;
  void* rc_ = nullptr;
};

// RGBA32F colour + depth/stencil textures (the live viewport's passes read both: view_post.h), bound as the draw
// framebuffer by bind_and_clear().
class Framebuffer {
 public:
  Framebuffer(int width, int height);
  ~Framebuffer();
  Framebuffer(const Framebuffer&) = delete;
  Framebuffer& operator=(const Framebuffer&) = delete;
  int width() const { return w_; }
  int height() const { return h_; }
  void bind_and_clear() const;          // clear to transparent black, depth 1
  std::vector<float> read_rgba() const;  // top row first
  std::vector<float> read_depth() const;  // 0..1 window depth, GL rows bottom up
  unsigned color_texture() const { return color_; }
  unsigned depth_texture() const { return depth_; }

 private:
  unsigned texture(int inner, unsigned format, unsigned type) const;
  int w_, h_;
  unsigned fbo_ = 0, color_ = 0, depth_ = 0;
};

}  // namespace r3d
