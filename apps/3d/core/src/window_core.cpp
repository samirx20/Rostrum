#include "window_core.h"

#include <epoxy/gl.h>
#include <stdlib.h>
#include <pxr/base/js/json.h>

#include "requests.h"
#include "serve.h"

namespace r3d {

namespace {
// Storm keeps the clay's blocks in shared vertex buffers of up to HD_MAX_VBO_SIZE bytes (1 GB by default). When a dab
// resizes blocks, the next frame's garbage collection compacts the buffers they were in, copying each one whole on the
// GPU: with the defaults one buffer held every block, and the copy put 20-30 ms on a stroke's first dabs (Storm's
// counters: garbageCollected, vboRelocated; 3d-v4). Smaller buffers make that copy small. Before Hydra starts (the
// setting is read once); a value set by hand wins.
bool storm_buffers() {
  if (!std::getenv("HD_MAX_VBO_SIZE")) _putenv_s("HD_MAX_VBO_SIZE", "4194304");
  return true;
}
}  // namespace

WindowCore::WindowCore() : core_((storm_buffers(), std::make_unique<Core>(GlContext::Borrow{}))) {}

WindowCore::~WindowCore() {
  core_.reset();  // Hydra and the view post release their GL objects while the context is still current
  if (fbo_) glDeleteFramebuffers(1, &fbo_);
}

int WindowCore::views_drawn() const { return core_->views_drawn(); }

bool WindowCore::set_texture(unsigned tex, int width, int height) {
  if (tex == tex_ && width == w_ && height == h_ && fbo_) return false;
  if (!fbo_) glGenFramebuffers(1, &fbo_);
  GLint prev = 0;
  glGetIntegerv(GL_FRAMEBUFFER_BINDING, &prev);
  glBindFramebuffer(GL_FRAMEBUFFER, fbo_);
  glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex, 0);
  glBindFramebuffer(GL_FRAMEBUFFER, GLuint(prev));
  tex_ = tex;
  w_ = width;
  h_ = height;
  core_->set_target({fbo_, w_, h_});
  return true;
}

void WindowCore::reset_gl_state() {
  // Qt Quick's own state, as its last draw left it: Hydra (Storm) and the view post assume GL's defaults
  glDisable(GL_SCISSOR_TEST);
  glDisable(GL_STENCIL_TEST);
  glDisable(GL_BLEND);
  glDisable(GL_CULL_FACE);
  glDisable(GL_FRAMEBUFFER_SRGB);
  glDisable(GL_PRIMITIVE_RESTART);
  glEnable(GL_DEPTH_TEST);
  glDepthFunc(GL_LESS);
  glDepthMask(GL_TRUE);
  glDepthRange(0, 1);
  glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
  glFrontFace(GL_CCW);
  glBindVertexArray(0);
  glUseProgram(0);
  glBindBuffer(GL_ARRAY_BUFFER, 0);
  glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0);
  glActiveTexture(GL_TEXTURE0);
  glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
  glPixelStorei(GL_PACK_ALIGNMENT, 4);
}

std::string WindowCore::answer(const std::string& line) {
  GLint prev = 0;
  glGetIntegerv(GL_FRAMEBUFFER_BINDING, &prev);
  reset_gl_state();
  core_->join_ahead();  // a dab started early: done before anything else touches the core
  std::string reply = r3d::answer(*core_, line, nullptr);
  glBindFramebuffer(GL_FRAMEBUFFER, GLuint(prev));
  return reply;
}

std::string WindowCore::answer_without_gl(const std::string& line) {
  core_->join_ahead();
  return r3d::answer(*core_, line, nullptr);
}

bool WindowCore::is_stroke_dab(const std::string& line) {
  return line.rfind("{\"sculpt\"", 0) == 0 &&
         (line.find("\"phase\": \"dab\"") != std::string::npos || line.find("\"phase\":\"dab\"") != std::string::npos);
}

bool WindowCore::ahead(const std::string& line) {
  if (!is_stroke_dab(line)) return false;
  PXR_NS::JsParseError err;
  const PXR_NS::JsValue v = PXR_NS::JsParseString(line, &err);
  if (!v.IsObject()) return false;
  const PXR_NS::JsObject& o = v.GetJsObject();
  auto it = o.find("sculpt");
  if (it == o.end() || !it->second.IsObject()) return false;
  return core_->sculpt_ahead(it->second.GetJsObject());
}

bool WindowCore::is_stroke_end(const std::string& line) {
  // {"sculpt": {... "phase": "end" ...}} as Python's json.dumps writes it (with or without the space)
  return line.rfind("{\"sculpt\"", 0) == 0 &&
         (line.find("\"phase\": \"end\"") != std::string::npos || line.find("\"phase\":\"end\"") != std::string::npos);
}

void WindowCore::clear() {
  if (!fbo_) return;
  GLint prev = 0;
  glGetIntegerv(GL_FRAMEBUFFER_BINDING, &prev);
  reset_gl_state();
  glBindFramebuffer(GL_FRAMEBUFFER, fbo_);
  glViewport(0, 0, w_, h_);
  glClearColor(0, 0, 0, 0);
  glClear(GL_COLOR_BUFFER_BIT);
  glBindFramebuffer(GL_FRAMEBUFFER, GLuint(prev));
}

std::string WindowCore::gl_renderer() const {
  auto s = reinterpret_cast<const char*>(glGetString(GL_RENDERER));
  return s ? s : "unknown";
}

}  // namespace r3d
