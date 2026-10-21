// A hidden OpenGL context and an offscreen float framebuffer. Hydra (Hgi) needs a current GL context
// for every renderer, and composites its colour result into the framebuffer that is bound.
#pragma once
#include <string>
#include <vector>

namespace r3d {

class GlContext {
 public:
  GlContext();   // hidden window + OpenGL 4.6 compatibility context, made current; throws r3d::Error
  ~GlContext();
  GlContext(const GlContext&) = delete;
  GlContext& operator=(const GlContext&) = delete;
  std::string renderer() const;  // GL_RENDERER: which chip draws (the RTX, we hope)
  void finish() const;

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
  unsigned color_texture() const { return color_; }
  unsigned depth_texture() const { return depth_; }

 private:
  unsigned texture(int inner, unsigned format, unsigned type) const;
  int w_, h_;
  unsigned fbo_ = 0, color_ = 0, depth_ = 0;
};

}  // namespace r3d
