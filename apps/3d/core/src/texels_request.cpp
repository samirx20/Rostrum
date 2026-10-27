// The `texels` request (ENGINE_CONTRACT.md › texels): which texel of which item each pixel of a camera's picture sees.
// One Storm id + depth picture (Hydra::ids, the one `sees` draws too), then each seen mesh's st along the pixels'
// rays (texels.h). The single source of truth for painting from the view, projecting a picture and coverage.
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <limits>
#include <map>

#include "args.h"
#include "error.h"
#include "inspect.h"
#include "requests.h"
#include "texels.h"
#include "view_camera.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
using Clock = std::chrono::steady_clock;
double ms_since(Clock::time_point t) { return std::chrono::duration<double, std::milli>(Clock::now() - t).count(); }
double r1(double v) { return std::round(v * 10) / 10; }
}  // namespace

JsObject Core::texels(const JsObject& o) {
  Args a(o, "texels", {"camera", "eye", "target", "fov", "frame", "width", "height", "file"});
  need_scene("texels");
  const auto t0 = Clock::now();
  const ViewCamera vc = read_view_camera(a, [&](const std::string& id) { return camera(id, "texels"); });
  const int f = a.whole("frame"), w = a.whole("width"), h = a.whole("height");
  check_frame(f, "texels.frame");
  if (w < 16 || h < 16 || w > 4096 || h > 4096) throw Error("texels.width/height: each must be 16..4096");
  const std::string file = a.str("file");
  clay_->pose_frame(f);  // a skinned clay is seen as drawn at this frame
  const GfFrustum fr = frustum_of(stage_, vc, f, w, h);
  const IdPicture pic = hydra().ids(fr, f, w, h, {}, true);
  const PixelRays rays(fr, w, h);

  // each prim id seen -> its item (anything a copies item draws is that item: no st) and its pixels
  struct Seen {
    std::string item;
    bool copy = false;
    std::vector<int> pixels;
  };
  std::map<int, Seen> seen;
  for (const auto& [id, path] : pic.prims) {
    Seen s;
    if (path.IsEmpty()) { seen[id] = s; continue; }
    for (const auto& [cid, c] : copies_)
      if (path.HasPrefix(c.path)) {
        s.item = cid;
        s.copy = true;
      }
    if (!s.copy) s.item = item_of(stage_, path);
    seen[id] = std::move(s);
  }
  const size_t n = size_t(w) * h;
  for (size_t i = 0; i < n; ++i)
    if (pic.primIds[i] >= 0) seen[pic.primIds[i]].pixels.push_back(int(i));
  std::map<std::string, int> index;  // item id -> its place in `items` (by name)
  for (const auto& [id, s] : seen)
    if (!s.item.empty()) index[s.item] = 0;
  JsArray items;
  for (auto& [item, at] : index) {
    at = int(items.size());
    items.push_back(JsValue(item));
  }

  // u, v, item, distance a pixel, rows top first; the distance Storm drew, then the surface's own where it has st
  const float nan = std::numeric_limits<float>::quiet_NaN();
  std::vector<float> out(n * 4);
  std::vector<double> drawn(n, -1);
  for (size_t i = 0; i < n; ++i) {
    const int id = pic.primIds[i];
    if (pic.depth[i] < 1.f) drawn[i] = rays.distance(int(i % w), int(i / w), pic.depth[i]);
    const auto s = id >= 0 ? seen.find(id) : seen.end();
    out[4 * i] = nan;
    out[4 * i + 1] = nan;
    out[4 * i + 2] = s != seen.end() && !s->second.item.empty() ? float(index[s->second.item]) : -1.f;
    out[4 * i + 3] = float(drawn[i]);
  }
  const auto tu = Clock::now();
  for (const auto& [id, s] : seen)
    if (!s.copy && !s.item.empty()) mesh_texels(stage_, pic.prims.at(id), f, rays, pic.primIds, id, s.pixels, drawn, &out);
  const double uv_ms = ms_since(tu);

  std::ofstream fh(std::filesystem::u8path(file), std::ios::binary | std::ios::trunc);
  if (!fh) throw Error("texels.file: could not write " + file);
  fh.write(reinterpret_cast<const char*>(out.data()), std::streamsize(out.size() * sizeof(float)));
  fh.close();
  if (!fh) throw Error("texels.file: writing " + file + " failed");
  return JsObject{{"ok", JsValue(true)},  {"width", JsValue(w)},           {"height", JsValue(h)},
                  {"file", JsValue(file)}, {"items", JsValue(items)},      {"ms", JsValue(r1(ms_since(t0)))},
                  {"uvMs", JsValue(r1(uv_ms))}};
}

}  // namespace r3d
