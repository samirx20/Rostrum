#include "clay_slots.h"

#include <pxr/base/gf/vec2f.h>

#include <algorithm>
#include <cstdlib>
#include <map>
#include <mutex>
#include <string>
#include <utility>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::clay {

bool slots_on() {
  static const bool on = [] {
    const char* v = std::getenv("ROSTRUM3D_CLAY_SLOTS");
    return !(v && std::string(v) == "0");
  }();
  return on;
}

size_t slot_capacity(size_t n, bool preview) {
  const size_t want = std::max(n + n / 4, preview ? kPreviewSlot : kBlockSlot);
  size_t c = 64;  // 64, 96, 128, 192, 256, 384, ...
  while (c < want) c = (c & (c - 1)) == 0 ? c + c / 2 : (c / 3) * 4;
  return c;
}

namespace {
std::mutex listsM;
std::map<size_t, std::pair<VtIntArray, VtIntArray>> lists;  // by size: counts, indices (Storm's topology is shared)

const std::pair<VtIntArray, VtIntArray>& lists_of(size_t cap) {
  std::lock_guard<std::mutex> lock(listsM);
  auto it = lists.find(cap);
  if (it == lists.end()) {
    VtIntArray counts(cap, 3), idx(3 * cap);
    for (size_t i = 0; i < 3 * cap; ++i) idx[i] = int(i);
    it = lists.emplace(cap, std::make_pair(std::move(counts), std::move(idx))).first;
  }
  return it->second;
}

template <class T>
VtArray<T> corners(const VtArray<T>& v, const VtIntArray& indices, size_t cap, const T& pad) {
  VtArray<T> out(3 * cap);
  T* o = out.data();
  const T* in = v.cdata();
  const size_t n = std::min(indices.size(), 3 * cap);
  const int* ix = indices.cdata();
  for (size_t i = 0; i < n; ++i) o[i] = in[ix[i]];
  std::fill(o + n, o + 3 * cap, pad);
  return out;
}
}  // namespace

VtIntArray slot_counts(size_t cap) { return lists_of(cap).first; }
VtIntArray slot_indices(size_t cap) { return lists_of(cap).second; }

VtVec3fArray slot_corners(const VtVec3fArray& v, const VtIntArray& indices, size_t cap, const GfVec3f& pad) {
  return corners(v, indices, cap, pad);
}
VtFloatArray slot_corners(const VtFloatArray& v, const VtIntArray& indices, size_t cap, float pad) {
  return corners(v, indices, cap, pad);
}

VtVec2fArray slot_padded(const VtVec2fArray& st, size_t cap) {
  VtVec2fArray out(3 * cap, GfVec2f(0.0f));
  std::copy_n(st.cdata(), std::min(st.size(), out.size()), out.data());
  return out;
}

}  // namespace r3d::clay
