#include "passes.h"

#include <pxr/imaging/hd/tokens.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/camera.h>
#include <pxr/usd/usdLux/lightAPI.h>

#include <algorithm>
#include <map>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
const std::vector<std::string> kPasses = {"light", "shadow", "reflections", "masks", "depth", "normal"};
const std::vector<std::string> kRest = {"transmission", "emission", "background", "volume"};  // add up to "rest"

bool has(const std::vector<std::string>& v, const std::string& x) { return std::find(v.begin(), v.end(), x) != v.end(); }

std::string join(const std::vector<std::string>& v) {
  std::string s;
  for (const auto& x : v) s += (s.empty() ? "" : ", ") + x;
  return s;
}

ExrLayer colour(const std::string& layer, std::vector<float> px) {
  return ExrLayer{{layer + ".R", layer + ".G", layer + ".B"}, std::move(px), false};
}

float luminance(const float* c) { return 0.2126f * c[0] + 0.7152f * c[1] + 0.0722f * c[2]; }

// 0 lit .. 1 in full shadow, from the matte surfaces' direct light with and without shadows
std::vector<float> shadow(const Aovs& lit, const Aovs& unshadowed) {
  const auto &a = lit.plane("diffuseDirect"), &b = unshadowed.plane("diffuseDirect");
  std::vector<float> out(a.size() / 3, 0.0f);
  for (size_t i = 0; i < out.size(); ++i) {
    const float with = luminance(&a[i * 3]), without = luminance(&b[i * 3]);
    if (without > 1e-6f) out[i] = std::clamp(1.0f - with / without, 0.0f, 1.0f);
  }
  return out;
}

// every item of the scene (a `def` prim of the document under /World; not its materials, cameras or lights)
std::vector<SdfPath> items(const UsdStageRefPtr& stage) {
  std::vector<SdfPath> out;
  const auto& layer = stage->GetRootLayer();
  for (UsdPrim p : stage->Traverse()) {
    const SdfPath path = p.GetPath();
    if (path.GetPathElementCount() < 2 || path.HasPrefix(SdfPath("/World/Looks"))) continue;
    const SdfPrimSpecHandle spec = layer->GetPrimAtPath(path);
    if (!spec || spec->GetSpecifier() != SdfSpecifierDef) continue;
    if (p.IsA<UsdGeomCamera>() || p.HasAPI<UsdLuxLightAPI>()) continue;
    out.push_back(path);
  }
  return out;
}

// one channel per item: 1 where a pixel shows the item or anything it holds
std::vector<ExrLayer> masks(const Aovs& lit, const UsdStageRefPtr& stage) {
  const auto list = items(stage);
  std::map<int, std::vector<size_t>> of_id;  // prim id -> the items it is part of
  for (const auto& [id, prim] : lit.prims)
    for (size_t k = 0; k < list.size(); ++k)
      if (prim.HasPrefix(list[k])) of_id[id].push_back(k);
  std::vector<std::vector<float>> px(list.size(), std::vector<float>(lit.primIds.size(), 0.0f));
  for (size_t i = 0; i < lit.primIds.size(); ++i) {
    auto it = of_id.find(lit.primIds[i]);
    if (it != of_id.end())
      for (size_t k : it->second) px[k][i] = 1.0f;
  }
  std::vector<ExrLayer> out;
  for (size_t k = 0; k < list.size(); ++k)
    out.push_back(ExrLayer{{"masks." + list[k].GetName()}, std::move(px[k]), false});
  return out;
}
}  // namespace

std::vector<std::string> read_passes(const JsValue& v, const std::string& where) {
  if (!v.IsArray()) throw Error(where + ": needs a list of pass names. Accepted: " + join(kPasses));
  std::vector<std::string> out;
  for (const auto& x : v.GetJsArray()) {
    if (!x.IsString() || !has(kPasses, x.GetString()))
      throw Error(where + ": no pass " + (x.IsString() ? "\"" + x.GetString() + "\"" : std::string("(not a name)")) +
                  ". Accepted: " + join(kPasses));
    if (has(out, x.GetString())) throw Error(where + ": \"" + x.GetString() + "\" is asked twice");
    out.push_back(x.GetString());
  }
  return out;
}

std::vector<std::string> aovs_for(const std::vector<std::string>& passes) {
  std::vector<std::string> out;
  if (has(passes, "light")) out.push_back("diffuse");
  if (has(passes, "reflections")) out.push_back("glossy");
  if (has(passes, "light") || has(passes, "reflections")) out.insert(out.end(), kRest.begin(), kRest.end());
  if (has(passes, "shadow")) out.push_back("diffuseDirect");
  if (has(passes, "masks")) out.push_back(HdAovTokens->primId.GetString());
  if (has(passes, "depth")) out.push_back(HdAovTokens->depth.GetString());
  if (has(passes, "normal")) out.push_back(HdAovTokens->normal.GetString());
  return out;
}

bool needs_unshadowed(const std::vector<std::string>& passes) { return has(passes, "shadow"); }

std::vector<ExrLayer> pass_layers(const std::vector<std::string>& passes, const Aovs& lit, const Aovs& unshadowed,
                                  const UsdStageRefPtr& stage) {
  std::vector<ExrLayer> out;
  if (has(passes, "light")) out.push_back(colour("light", lit.plane("diffuse")));
  if (has(passes, "reflections")) out.push_back(colour("reflections", lit.plane("glossy")));
  if (has(passes, "light") || has(passes, "reflections")) {
    std::vector<float> rest(lit.plane("background").size(), 0.0f);
    for (const auto& name : kRest) {
      const auto& p = lit.plane(name);
      for (size_t i = 0; i < rest.size(); ++i) rest[i] += p[i];
    }
    out.push_back(colour("rest", std::move(rest)));
  }
  if (has(passes, "shadow")) out.push_back(ExrLayer{{"shadow.A"}, shadow(lit, unshadowed), false});
  if (has(passes, "masks"))
    for (auto& m : masks(lit, stage)) out.push_back(std::move(m));
  if (has(passes, "depth")) {  // Cycles says 1e10 where its ray met nothing; the layer says 0 there (passes.h)
    std::vector<float> z = lit.plane("depth");
    for (float& d : z)
      if (!(d < 1e9f)) d = 0.0f;
    out.push_back(ExrLayer{{"depth.Z"}, std::move(z), true});
  }
  if (has(passes, "normal")) out.push_back(ExrLayer{{"normal.X", "normal.Y", "normal.Z"}, lit.plane("normal"), false});
  return out;
}

void check_beauty(const Picture& beauty, const std::vector<ExrLayer>& layers, int frame) {
  const auto any = [](const std::vector<float>& v) { return std::any_of(v.begin(), v.end(), [](float x) { return x != 0.0f; }); };
  if (any(beauty.rgba)) return;
  for (const auto& l : layers)
    if (l.channels.front().rfind("masks.", 0) != 0 && any(l.pixels))
      throw Error("render: frame " + std::to_string(frame) + ": the picture came out empty while its " +
                  l.channels.front() + " layer is not; no file written");
}

}  // namespace r3d
