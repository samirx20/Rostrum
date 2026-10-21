#include "outline.h"

#include <algorithm>
#include <vector>

namespace r3d {

namespace {
constexpr unsigned char kAccent[3] = {0x4c, 0x8d, 0xff};  // shared/gui-kit Theme.accent
}

void draw_outline(const Picture& p, unsigned char* rgba8, int radius) {
  if (p.mask.empty()) return;
  const int w = p.width, h = p.height;
  // grow the mask by `radius` (separable: rows, then columns); the ring is grown and not the mask itself
  std::vector<unsigned char> row(p.mask.size()), grown(p.mask.size());
  for (int y = 0; y < h; ++y)
    for (int x = 0; x < w; ++x) {
      unsigned char v = 0;
      for (int dx = std::max(0, x - radius); dx <= std::min(w - 1, x + radius) && !v; ++dx) v = p.mask[size_t(y) * w + dx];
      row[size_t(y) * w + x] = v;
    }
  for (int y = 0; y < h; ++y)
    for (int x = 0; x < w; ++x) {
      unsigned char v = 0;
      for (int dy = std::max(0, y - radius); dy <= std::min(h - 1, y + radius) && !v; ++dy) v = row[size_t(dy) * w + x];
      grown[size_t(y) * w + x] = v;
    }
  for (size_t i = 0; i < grown.size(); ++i)
    if (grown[i] && !p.mask[i])
      for (int c = 0; c < 3; ++c) rgba8[i * 4 + c] = kAccent[c];
}

}  // namespace r3d
