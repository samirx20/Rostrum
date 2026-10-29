#include "aovs.h"

#include <pxr/imaging/hd/renderBuffer.h>
#include <pxr/imaging/hd/tokens.h>

#include <cstring>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

const std::vector<float>& Aovs::plane(const std::string& name) const {
  auto it = planes.find(name);
  if (it == planes.end()) throw Error("render.passes: the renderer made no \"" + name + "\" output");
  return it->second;
}

namespace {
// Hydra's render buffers hold the bottom row first (as OpenGL does); pictures here are top row first.
template <typename T>
void copy_flipped(const T* src, T* dst, int w, int h, int n) {
  const size_t row = size_t(w) * n;
  for (int y = 0; y < h; ++y) std::memcpy(dst + size_t(h - 1 - y) * row, src + size_t(y) * row, row * sizeof(T));
}
}  // namespace

Aovs read_aovs(UsdImagingGLEngine& e, const std::vector<std::string>& names, int w, int h,
               const std::function<SdfPath(int)>& prim_of) {
  Aovs out;
  out.width = w;
  out.height = h;
  for (const auto& name : names) {
    HdRenderBuffer* rb = e.GetAovRenderBuffer(TfToken(name));
    if (!rb) throw Error("render.passes: the renderer has no \"" + name + "\" output (light groups, Cryptomatte and motion need the library folder -r5)");
    rb->Resolve();
    if (int(rb->GetWidth()) != w || int(rb->GetHeight()) != h)
      throw Error("render.passes: \"" + name + "\" came out " + std::to_string(rb->GetWidth()) + " x " +
                  std::to_string(rb->GetHeight()) + ", not " + std::to_string(w) + " x " + std::to_string(h));
    const HdFormat f = rb->GetFormat();
    const void* data = rb->Map();
    if (!data) throw Error("render.passes: could not read \"" + name + "\"");
    if (name == HdAovTokens->primId.GetString()) {
      if (f != HdFormatInt32) { rb->Unmap(); throw Error("render.passes: primId is not whole numbers"); }
      out.primIds.resize(size_t(w) * h);
      copy_flipped(static_cast<const int*>(data), out.primIds.data(), w, h, 1);
    } else {
      const int n = int(HdGetComponentCount(f));
      if (HdGetComponentFormat(f) != HdFormatFloat32) {
        rb->Unmap();
        throw Error("render.passes: \"" + name + "\" is not 32-bit floats (format " + std::to_string(int(f)) + ")");
      }
      auto& px = out.planes[name];
      px.resize(size_t(w) * h * n);
      copy_flipped(static_cast<const float*>(data), px.data(), w, h, n);
      out.channels[name] = n;
    }
    rb->Unmap();
  }
  for (int id : out.primIds)
    if (id >= 0 && !out.prims.count(id)) out.prims[id] = prim_of(id);
  return out;
}

}  // namespace r3d
