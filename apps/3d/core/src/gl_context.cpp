#include "gl_context.h"

#include <windows.h>
#include <epoxy/gl.h>
#include <epoxy/wgl.h>

#include <cstring>

#include "error.h"

namespace r3d {

namespace {
const wchar_t* kClass = L"Rostrum3DHiddenGL";

HWND make_window() {
  WNDCLASSW wc{};
  wc.style = CS_OWNDC;
  wc.lpfnWndProc = DefWindowProcW;
  wc.hInstance = GetModuleHandleW(nullptr);
  wc.lpszClassName = kClass;
  RegisterClassW(&wc);  // a second registration fails harmlessly
  HWND w = CreateWindowExW(0, kClass, L"rostrum3d", WS_OVERLAPPEDWINDOW, 0, 0, 64, 64, nullptr, nullptr,
                           wc.hInstance, nullptr);
  if (!w) throw Error("gl: could not create the hidden window (" + std::to_string(GetLastError()) + ")");
  return w;
}

void set_pixel_format(HDC dc) {
  PIXELFORMATDESCRIPTOR pfd{};
  pfd.nSize = sizeof(pfd);
  pfd.nVersion = 1;
  pfd.dwFlags = PFD_DRAW_TO_WINDOW | PFD_SUPPORT_OPENGL | PFD_DOUBLEBUFFER;
  pfd.iPixelType = PFD_TYPE_RGBA;
  pfd.cColorBits = 32;
  pfd.cDepthBits = 24;
  pfd.cStencilBits = 8;
  int pf = ChoosePixelFormat(dc, &pfd);
  if (!pf || !SetPixelFormat(dc, pf, &pfd)) throw Error("gl: no usable pixel format");
}
}  // namespace

GlContext::GlContext() {
  HWND w = make_window();
  HDC dc = GetDC(w);
  set_pixel_format(dc);
  HGLRC legacy = wglCreateContext(dc);  // needed to reach wglCreateContextAttribsARB
  if (!legacy || !wglMakeCurrent(dc, legacy)) throw Error("gl: could not create an OpenGL context");
  const int attrs[] = {WGL_CONTEXT_MAJOR_VERSION_ARB, 4, WGL_CONTEXT_MINOR_VERSION_ARB, 6,
                       WGL_CONTEXT_PROFILE_MASK_ARB, WGL_CONTEXT_COMPATIBILITY_PROFILE_BIT_ARB, 0};
  HGLRC rc = epoxy_has_wgl_extension(dc, "WGL_ARB_create_context")
                 ? wglCreateContextAttribsARB(dc, nullptr, attrs) : nullptr;
  wglMakeCurrent(nullptr, nullptr);
  wglDeleteContext(legacy);
  if (!rc || !wglMakeCurrent(dc, rc))
    throw Error("gl: OpenGL 4.6 is not available on this machine (Hydra needs it)");
  wnd_ = w;
  dc_ = dc;
  rc_ = rc;
}

GlContext::~GlContext() {
  wglMakeCurrent(nullptr, nullptr);
  if (rc_) wglDeleteContext(static_cast<HGLRC>(rc_));
  if (dc_) ReleaseDC(static_cast<HWND>(wnd_), static_cast<HDC>(dc_));
  if (wnd_) DestroyWindow(static_cast<HWND>(wnd_));
}

std::string GlContext::renderer() const {
  auto s = reinterpret_cast<const char*>(glGetString(GL_RENDERER));
  return s ? s : "unknown";
}

void GlContext::finish() const { glFinish(); }

unsigned Framebuffer::texture(int inner, unsigned format, unsigned type) const {
  unsigned t = 0;
  glGenTextures(1, &t);
  glBindTexture(GL_TEXTURE_2D, t);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
  glTexImage2D(GL_TEXTURE_2D, 0, inner, w_, h_, 0, format, type, nullptr);
  glBindTexture(GL_TEXTURE_2D, 0);
  return t;
}

Framebuffer::Framebuffer(int width, int height) : w_(width), h_(height) {
  glGenFramebuffers(1, &fbo_);
  glBindFramebuffer(GL_FRAMEBUFFER, fbo_);
  color_ = texture(GL_RGBA32F, GL_RGBA, GL_FLOAT);
  glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color_, 0);
  depth_ = texture(GL_DEPTH24_STENCIL8, GL_DEPTH_STENCIL, GL_UNSIGNED_INT_24_8);
  glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_TEXTURE_2D, depth_, 0);
  if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
    throw Error("gl: the " + std::to_string(w_) + "x" + std::to_string(h_) + " float framebuffer is incomplete");
}

Framebuffer::~Framebuffer() {
  glBindFramebuffer(GL_FRAMEBUFFER, 0);
  glDeleteTextures(1, &depth_);
  glDeleteTextures(1, &color_);
  glDeleteFramebuffers(1, &fbo_);
}

void Framebuffer::bind_and_clear() const {
  glBindFramebuffer(GL_FRAMEBUFFER, fbo_);
  glViewport(0, 0, w_, h_);
  glClearColor(0, 0, 0, 0);
  glClearDepth(1.0);
  glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT | GL_STENCIL_BUFFER_BIT);
}

std::vector<float> Framebuffer::read_rgba() const {
  std::vector<float> px(size_t(w_) * h_ * 4), out(px.size());
  glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo_);
  glPixelStorei(GL_PACK_ALIGNMENT, 1);
  glReadPixels(0, 0, w_, h_, GL_RGBA, GL_FLOAT, px.data());
  const size_t row = size_t(w_) * 4;
  for (int y = 0; y < h_; ++y)  // GL rows go bottom-up
    std::memcpy(&out[size_t(y) * row], &px[size_t(h_ - 1 - y) * row], row * sizeof(float));
  return out;
}

}  // namespace r3d
