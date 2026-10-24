#include "view_post.h"

#include <epoxy/gl.h>

#include <cmath>

#include "error.h"
#include "view_post_glsl.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
constexpr float kAccent[3] = {0x4c / 255.f, 0x8d / 255.f, 0xff / 255.f};  // shared/gui-kit Theme.accent
constexpr int kRing = 2;                                                  // selection ring, pixels
constexpr float kMaxBlur = 32;                                            // depth of field, largest blur radius in pixels

unsigned compile(GLenum kind, const std::string& src) {
  const unsigned s = glCreateShader(kind);
  const char* text = src.c_str();
  glShaderSource(s, 1, &text, nullptr);
  glCompileShader(s);
  GLint ok = 0;
  glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
  if (!ok) {
    char log[2048];
    glGetShaderInfoLog(s, sizeof(log), nullptr, log);
    glDeleteShader(s);
    throw Error(std::string("view: a viewport shader did not compile: ") + log);
  }
  return s;
}

// a colour texture of `inner` format with a framebuffer drawing into it
struct Target {
  unsigned tex = 0, fbo = 0;
  Target(int w, int h, GLint inner, GLenum fmt, GLenum type) {
    glGenTextures(1, &tex);
    glBindTexture(GL_TEXTURE_2D, tex);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    glTexImage2D(GL_TEXTURE_2D, 0, inner, w, h, 0, fmt, type, nullptr);
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
      throw Error("view: a " + std::to_string(w) + "x" + std::to_string(h) + " viewport pass target is incomplete");
  }
  ~Target() {
    glDeleteFramebuffers(1, &fbo);
    glDeleteTextures(1, &tex);
  }
};

void use_textures(unsigned prog, std::initializer_list<std::pair<const char*, unsigned>> list) {
  int unit = 0;
  for (const auto& [name, tex] : list) {
    glActiveTexture(GL_TEXTURE0 + unit);
    glBindTexture(GL_TEXTURE_2D, tex);
    glUniform1i(glGetUniformLocation(prog, name), unit++);
  }
}

void set_common(unsigned prog, const ViewPostIn& in) {
  float inv[16];
  const GfMatrix4d m = in.projection.GetInverse();
  for (int i = 0; i < 16; ++i) inv[i] = float(m.data()[i]);  // row-major row vectors = GLSL column vectors
  glUniformMatrix4fv(glGetUniformLocation(prog, "invProj"), 1, GL_FALSE, inv);
  glUniform2i(glGetUniformLocation(prog, "isize"), in.width, in.height);
}

void draw_into(unsigned fbo, int w, int h) {
  glBindFramebuffer(GL_FRAMEBUFFER, fbo);
  glViewport(0, 0, w, h);
  glDrawArrays(GL_TRIANGLES, 0, 3);
}
}  // namespace

struct ViewPost::Targets {
  int w, h;
  Target ao, lit, out;
  std::unique_ptr<Target> spare;  // a second scene-linear target, made when onion-skin ghosts need to ping-pong
  Targets(int w_, int h_)
      : w(w_), h(h_), ao(w_, h_, GL_R16F, GL_RED, GL_FLOAT), lit(w_, h_, GL_RGBA32F, GL_RGBA, GL_FLOAT),
        out(w_, h_, GL_RGBA8, GL_RGBA, GL_UNSIGNED_BYTE) {}
};

// Onion skin: each ghost laid over the scene-linear picture in turn, tinted and see-through; returns the result
unsigned ViewPost::ghosts(const ViewPostIn& in, unsigned lit, const std::string& head) {
  const unsigned pg = program("ghost", head + glsl::kGhost);
  for (const GhostIn& g : in.ghosts) {
    Target* to = &t_->lit;
    if (lit == t_->lit.tex) {
      if (!t_->spare) t_->spare = std::make_unique<Target>(in.width, in.height, GL_RGBA32F, GL_RGBA, GL_FLOAT);
      to = t_->spare.get();
    }
    glUseProgram(pg);
    use_textures(pg, {{"litTex", lit}, {"ghostTex", g.tex}});
    glUniform3fv(glGetUniformLocation(pg, "tint"), 1, g.tint);
    glUniform1f(glGetUniformLocation(pg, "opacity"), g.opacity);
    draw_into(to->fbo, in.width, in.height);
    lit = to->tex;
  }
  return lit;
}

ViewPost::ViewPost() { glGenVertexArrays(1, &vao_); }

ViewPost::~ViewPost() {
  ocio_.clear();
  t_.reset();
  for (auto& [k, p] : programs_) glDeleteProgram(p);
  glDeleteVertexArrays(1, &vao_);
}

unsigned ViewPost::program(const std::string& key, const std::string& fragment) {
  auto it = programs_.find(key);
  if (it != programs_.end()) return it->second;
  const unsigned vs = compile(GL_VERTEX_SHADER, glsl::kVertex), fs = compile(GL_FRAGMENT_SHADER, fragment);
  const unsigned p = glCreateProgram();
  glAttachShader(p, vs);
  glAttachShader(p, fs);
  glLinkProgram(p);
  glDeleteShader(vs);
  glDeleteShader(fs);
  GLint ok = 0;
  glGetProgramiv(p, GL_LINK_STATUS, &ok);
  if (!ok) {
    char log[2048];
    glGetProgramInfoLog(p, sizeof(log), nullptr, log);
    glDeleteProgram(p);
    throw Error(std::string("view: a viewport shader did not link: ") + log);
  }
  return programs_[key] = p;
}

void ViewPost::run(const ViewPostIn& in, unsigned char* dst) {
  const int w = in.width, h = in.height;
  if (!t_ || t_->w != w || t_->h != h) {
    t_.reset();
    t_ = std::make_unique<Targets>(w, h);
  }
  auto& oc = ocio_[in.view];
  if (!oc) oc = std::make_unique<OcioGpu>(in.config, in.display, in.view);
  const std::string head = "#version 410 core\n";
  // Hydra leaves its own state behind: a full-picture pass needs none of it
  for (GLenum cap : {GL_DEPTH_TEST, GL_BLEND, GL_SCISSOR_TEST, GL_CULL_FACE, GL_STENCIL_TEST, GL_FRAMEBUFFER_SRGB})
    glDisable(cap);
  glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
  glBindVertexArray(vao_);
  while (glGetError() != GL_NO_ERROR) {}  // only errors from these passes count below

  unsigned lit = in.color;
  if (in.ao > 0) {
    const unsigned pa = program("ao", head + glsl::kViewPos + glsl::kAo);
    glUseProgram(pa);
    set_common(pa, in);
    use_textures(pa, {{"depthTex", in.depth}});
    glUniform1f(glGetUniformLocation(pa, "radius"), float(in.aoRadius));
    glUniform1f(glGetUniformLocation(pa, "pxPerUnit"), float(in.projection[0][0] * w / 2));
    draw_into(t_->ao.fbo, w, h);
    const unsigned pc = program("combine", head + glsl::kViewPos + glsl::kCombine);
    glUseProgram(pc);
    set_common(pc, in);
    use_textures(pc, {{"depthTex", in.depth}, {"colorTex", in.color}, {"aoTex", t_->ao.tex}});
    glUniform1f(glGetUniformLocation(pc, "strength"), float(in.ao));
    draw_into(t_->lit.fbo, w, h);
    lit = t_->lit.tex;
  }
  if (!in.ghosts.empty()) lit = ghosts(in, lit, head);

  const unsigned pf = program("final:" + in.view, head + glsl::kViewPos + glsl::kFinalHead + oc->glsl() + glsl::kFinalBody);
  glUseProgram(pf);
  set_common(pf, in);
  use_textures(pf, {{"depthTex", in.depth}, {"litTex", lit}, {"maskTex", in.mask ? in.mask : in.color}});
  oc->bind(pf, 3);
  const float gain = float(std::pow(2.0, in.exposure));
  glUniform1f(glGetUniformLocation(pf, "gain"), gain);
  glUniform3fv(glGetUniformLocation(pf, "bg"), 1, in.background);
  glUniform3fv(glGetUniformLocation(pf, "accent"), 1, kAccent);
  glUniform1i(glGetUniformLocation(pf, "hasMask"), in.mask ? 1 : 0);
  glUniform1i(glGetUniformLocation(pf, "ring"), kRing);
  const Lens* l = in.lens ? &*in.lens : nullptr;
  const double f = l ? l->focalLength : 0, S = l ? l->focusDistance : 0;
  const bool lens = l && l->fStop > 0 && S > f && l->sensorWidth > 0;
  glUniform1i(glGetUniformLocation(pf, "lens"), lens ? 1 : 0);
  // blur diameter on the sensor = f^2 / (N (S - f)) * |D - S| / D (thin lens), in pixels across the sensor width
  glUniform1f(glGetUniformLocation(pf, "cocScale"), lens ? float(f * f / (l->fStop * (S - f)) / l->sensorWidth * w) : 0.f);
  glUniform1f(glGetUniformLocation(pf, "focus"), float(S));
  glUniform1f(glGetUniformLocation(pf, "maxR"), kMaxBlur);
  draw_into(t_->out.fbo, w, h);

  glBindFramebuffer(GL_READ_FRAMEBUFFER, t_->out.fbo);
  glPixelStorei(GL_PACK_ALIGNMENT, 1);
  glReadPixels(0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, dst);
  glUseProgram(0);
  glBindVertexArray(0);
  glActiveTexture(GL_TEXTURE0);
  if (const GLenum e = glGetError(); e != GL_NO_ERROR)
    throw Error("view: the graphics card reported GL error " + std::to_string(e) + " finishing the viewport picture");
}

}  // namespace r3d
