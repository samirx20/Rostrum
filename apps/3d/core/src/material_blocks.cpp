// A material's blocks: its MaterialX document drawn by Storm and Cycles (material_blocks.h).
#include "material_blocks.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <map>
#include <vector>

#include <pxr/base/gf/vec3f.h>
#include <pxr/base/vt/array.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usd/references.h>
#include <pxr/usd/usdShade/connectableAPI.h>
#include <pxr/usd/usdShade/material.h>
#include <pxr/usd/usdShade/nodeGraph.h>

#include "error.h"
#include "json_read.h"
#include "material_nodes.h"
#include "materials.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

const SdfValueTypeName& kFloat = SdfValueTypeNames->Float;
const SdfValueTypeName& kColor = SdfValueTypeNames->Color3f;
const SdfValueTypeName& kNormal = SdfValueTypeNames->Normal3f;

// "ND_rostrum_colour_adjust_color3" -> "colouradjust": the id without "ND_rostrum_", underscores or case.
std::string squash(const std::string& s) {
  std::string out;
  for (char c : s)
    if (c != '_') out += char(std::tolower(static_cast<unsigned char>(c)));
  return out;
}

const char* kTypes[] = {"colouradjust", "occlusion", "bevel", "image", "noise", "mix", "ramp", "curve"};

std::string block_type(const std::string& shader_id) {
  const std::string s = squash(shader_id);
  const std::string head = "ndrostrum";
  if (s.rfind(head, 0) != 0) return "";
  for (const char* t : kTypes)
    if (s.compare(head.size(), std::string(t).size(), t) == 0) return t;
  return "";
}

// One block's values as written in the document (usdMtlx authors what the document gives).
struct Values {
  UsdShadeShader s;
  float num(const char* name, float fallback) const {
    VtValue v;
    if (UsdShadeInput in = s.GetInput(TfToken(name)); in && in.Get(&v)) {
      if (v.IsHolding<float>()) return v.UncheckedGet<float>();
      if (v.IsHolding<double>()) return float(v.UncheckedGet<double>());
      if (v.IsHolding<int>()) return float(v.UncheckedGet<int>());
    }
    return fallback;
  }
  GfVec3f colour(const char* name, const GfVec3f& fallback) const {
    VtValue v;
    if (UsdShadeInput in = s.GetInput(TfToken(name)); in && in.Get(&v)) {
      if (v.IsHolding<GfVec3f>()) return v.UncheckedGet<GfVec3f>();
      if (v.IsHolding<float>()) return GfVec3f(v.UncheckedGet<float>());
    }
    return fallback;
  }
  std::string text(const char* name, const std::string& fallback) const {
    VtValue v;
    if (UsdShadeInput in = s.GetInput(TfToken(name)); in && in.Get(&v)) {
      if (v.IsHolding<std::string>()) return v.UncheckedGet<std::string>();
      if (v.IsHolding<TfToken>()) return v.UncheckedGet<TfToken>().GetString();
      if (v.IsHolding<SdfAssetPath>()) {
        const SdfAssetPath& a = v.UncheckedGet<SdfAssetPath>();
        return a.GetResolvedPath().empty() ? a.GetAssetPath() : a.GetResolvedPath();
      }
    }
    return fallback;
  }
};

// Where a block's input or output is on the Cycles side.
struct Socket {
  UsdShadeShader node;
  std::string name;
  SdfValueTypeName type;
};

struct Block {
  std::string id, type;
  std::map<std::string, Socket> ins, outs;   // the document's names -> Cycles sockets
};

// A ramp's / curve's stops (pos1..posN with col1..colN or val1..valN, `count`), sorted by position.
template <class V>
std::vector<std::pair<float, V>> stops(const Values& b, const char* value_prefix, V (*read)(const Values&, const std::string&)) {
  const int n = std::clamp(int(b.num("count", 2)), 1, 8);
  std::vector<std::pair<float, V>> out;
  for (int i = 1; i <= n; ++i) {
    const std::string pos = "pos" + std::to_string(i);
    out.emplace_back(b.num(pos.c_str(), i == 1 ? 0.0f : 1.0f), read(b, value_prefix + std::to_string(i)));
  }
  std::stable_sort(out.begin(), out.end(), [](const auto& a, const auto& c) { return a.first < c.first; });
  return out;
}

template <class V>
V sample(const std::vector<std::pair<float, V>>& st, float t, const std::string& how) {
  if (t <= st.front().first) return st.front().second;
  if (t >= st.back().first) return st.back().second;
  for (size_t i = 1; i < st.size(); ++i) {
    if (t > st[i].first) continue;
    const auto& [p0, v0] = st[i - 1];
    const auto& [p1, v1] = st[i];
    if (how == "constant") return v0;
    float f = p1 > p0 ? (t - p0) / (p1 - p0) : 1.0f;
    if (how == "smooth") f = f * f * (3.0f - 2.0f * f);
    return v0 * (1.0f - f) + v1 * f;
  }
  return st.back().second;
}

GfVec3f read_col(const Values& b, const std::string& n) { return b.colour(n.c_str(), GfVec3f(0.5f)); }
float read_val(const Values& b, const std::string& n) { return b.num(n.c_str(), 0.5f); }

constexpr int kTable = 256;  // Cycles' own ramp / curve table size

Block cycles_block(const UsdStageRefPtr& stage, const SdfPath& mat, const std::string& id, const std::string& type,
                   const Values& b, const std::string& where) {
  Block k{id, type, {}, {}};
  const std::string pre = "Block_" + id;
  auto node = [&](const char* suffix, const char* cid) {
    return shader(stage, mat, (pre + suffix).c_str(), cid);
  };
  if (type == "noise") {
    UsdShadeShader coords = node("Coords", "cycles_texture_coordinate");
    UsdShadeShader n = node("", "cycles_noise_texture");
    set(n, "dimensions", SdfValueTypeNames->Int, 3);
    set(n, "scale", kFloat, b.num("scale", 5));
    set(n, "detail", kFloat, b.num("detail", 2));
    set(n, "roughness", kFloat, b.num("roughness", 0.5f));
    set(n, "distortion", kFloat, b.num("distortion", 0));
    link(n, "vector", SdfValueTypeNames->Vector3f, coords, "object", SdfValueTypeNames->Vector3f);
    for (const char* in : {"scale", "detail", "roughness", "distortion"}) k.ins[in] = {n, in, kFloat};
    k.outs["value"] = k.outs["out"] = {n, "fac", kFloat};
    k.outs["colour"] = {n, "color", kColor};
  } else if (type == "image") {
    const std::string file = b.text("file", "");
    check_file(file, where + "." + id + ".file", "an image");
    if (file.empty()) fail(where + "." + id + ".file", "is empty", "the absolute path of an image");
    const bool colour = b.text("colourData", "colour") != "data";
    UsdShadeShader t = cycles_image(stage, mat, pre.c_str(), Picture{{file}, 0}, colour);
    k.outs["colour"] = k.outs["out"] = {t, "color", kColor};
    k.outs["value"] = {t, "color", kColor};    // a colour into a number: Cycles takes its brightness
  } else if (type == "mix") {
    UsdShadeShader m = node("", "cycles_mix_color");
    set(m, "blend_type", SdfValueTypeNames->String, b.text("blend", "mix"));
    set(m, "fac", kFloat, b.num("factor", 0.5f));
    set(m, "a", kColor, b.colour("a", GfVec3f(0)));
    set(m, "b", kColor, b.colour("b", GfVec3f(1)));
    k.ins["factor"] = {m, "fac", kFloat};
    k.ins["a"] = {m, "a", kColor};
    k.ins["b"] = {m, "b", kColor};
    k.outs["colour"] = k.outs["out"] = k.outs["value"] = {m, "result", kColor};
  } else if (type == "ramp") {
    const std::string how = b.text("interpolate", "linear");
    const auto st = stops<GfVec3f>(b, "col", read_col);
    VtVec3fArray ramp(kTable);
    VtFloatArray alpha(kTable, 1.0f);
    for (int i = 0; i < kTable; ++i) ramp[i] = sample(st, float(i) / (kTable - 1), how);
    UsdShadeShader r = node("", "cycles_rgb_ramp");
    r.CreateInput(TfToken("ramp"), SdfValueTypeNames->Color3fArray).Set(ramp);
    r.CreateInput(TfToken("ramp_alpha"), SdfValueTypeNames->FloatArray).Set(alpha);
    set(r, "interpolate", SdfValueTypeNames->Bool, how != "constant");
    set(r, "fac", kFloat, b.num("factor", 0.5f));
    k.ins["factor"] = {r, "fac", kFloat};
    k.outs["colour"] = k.outs["out"] = k.outs["value"] = {r, "color", kColor};
  } else if (type == "curve") {
    const auto st = stops<float>(b, "val", read_val);
    VtFloatArray curve(kTable);
    for (int i = 0; i < kTable; ++i) curve[i] = sample(st, float(i) / (kTable - 1), "linear");
    UsdShadeShader c = node("", "cycles_float_curve");
    c.CreateInput(TfToken("curve"), SdfValueTypeNames->FloatArray).Set(curve);
    set(c, "min_x", kFloat, 0.0f);
    set(c, "max_x", kFloat, 1.0f);
    set(c, "fac", kFloat, 1.0f);
    set(c, "value", kFloat, b.num("value", 0.5f));
    k.ins["value"] = {c, "value", kFloat};
    k.outs["value"] = k.outs["out"] = {c, "value", kFloat};
  } else if (type == "colouradjust") {
    UsdShadeShader h = node("", "cycles_hsv");
    set(h, "hue", kFloat, 0.5f + b.num("hue", 0));
    set(h, "saturation", kFloat, b.num("saturation", 1));
    set(h, "value", kFloat, b.num("brightness", 1));
    set(h, "fac", kFloat, 1.0f);
    set(h, "color", kColor, b.colour("colour", GfVec3f(0.5f)));
    UsdShadeShader c = node("Contrast", "cycles_brightness_contrast");
    set(c, "bright", kFloat, 0.0f);
    set(c, "contrast", kFloat, b.num("contrast", 0));
    link(c, "color", kColor, h, "color", kColor);
    k.ins["colour"] = {h, "color", kColor};
    k.ins["saturation"] = {h, "saturation", kFloat};
    k.ins["brightness"] = {h, "value", kFloat};
    k.ins["contrast"] = {c, "contrast", kFloat};
    k.outs["colour"] = k.outs["out"] = k.outs["value"] = {c, "color", kColor};
  } else if (type == "bevel") {
    UsdShadeShader v = node("", "cycles_bevel");
    set(v, "radius", kFloat, b.num("radius", 0.005f));
    set(v, "samples", SdfValueTypeNames->Int, std::clamp(int(b.num("samples", 8)), 1, 64));
    k.ins["radius"] = {v, "radius", kFloat};
    k.outs["normal"] = k.outs["out"] = {v, "normal", kNormal};
  } else if (type == "occlusion") {
    UsdShadeShader a = node("", "cycles_ambient_occlusion");
    set(a, "distance", kFloat, b.num("distance", 0.2f));
    set(a, "color", kColor, b.colour("colour", GfVec3f(1)));
    set(a, "samples", SdfValueTypeNames->Int, 16);
    k.ins["distance"] = {a, "distance", kFloat};
    k.ins["colour"] = {a, "color", kColor};
    k.outs["value"] = k.outs["out"] = {a, "ao", kFloat};
    k.outs["colour"] = {a, "color", kColor};
  }
  return k;
}

// The material's surface inputs a block can feed: Cycles' principled input, Storm's UsdPreviewSurface input.
struct Feed {
  const char* cycles;
  SdfValueTypeName ctype;
  const char* storm;  // nullptr: Final only (Storm's normal input is a normal map's, not a direction)
  SdfValueTypeName stype;
};
const std::map<std::string, Feed>& feeds() {
  static const std::map<std::string, Feed> f = {
      {"baseColor", {"base_color", SdfValueTypeNames->Color3f, "diffuseColor", SdfValueTypeNames->Color3f}},
      {"roughness", {"roughness", SdfValueTypeNames->Float, "roughness", SdfValueTypeNames->Float}},
      {"metallic", {"metallic", SdfValueTypeNames->Float, "metallic", SdfValueTypeNames->Float}},
      {"emissionColor", {"emission_color", SdfValueTypeNames->Color3f, "emissiveColor", SdfValueTypeNames->Color3f}},
      {"normal", {"normal", SdfValueTypeNames->Normal3f, nullptr, SdfValueTypeNames->Float}},
  };
  return f;
}

// The NodeGraph "NG_blocks" of the document's material, or an invalid one.
UsdShadeNodeGraph find_graph(const UsdStageRefPtr& doc, SdfPath* path) {
  for (const UsdPrim& p : doc->Traverse()) {
    if (p.GetName() != "NG_blocks" || !p.IsA<UsdShadeNodeGraph>()) continue;
    if (!p.GetParent().IsA<UsdShadeMaterial>()) continue;   // the material's copy, not /MaterialX/NodeGraphs'
    *path = p.GetPath();
    return UsdShadeNodeGraph(p);
  }
  return UsdShadeNodeGraph();
}

// The Storm surface: the UsdPreviewSurface as a MaterialX node, with the Preview's values; its pictures as
// MaterialX images.
UsdShadeShader storm_surface(const UsdStageRefPtr& stage, const SdfPath& mat, UsdShadeShader& preview) {
  UsdShadeShader m = shader(stage, mat, "MtlxSurface", "ND_UsdPreviewSurface_surfaceshader");
  for (const UsdShadeInput& in : preview.GetInputs()) {
    const TfToken name = in.GetBaseName();
    UsdShadeConnectableAPI src;
    TfToken out;
    UsdShadeAttributeType kind;
    if (!UsdShadeConnectableAPI::GetConnectedSource(in, &src, &out, &kind)) {
      VtValue v;
      if (in.Get(&v)) m.CreateInput(name, in.GetTypeName()).Set(v);
      continue;
    }
    const UsdShadeShader up(src.GetPrim());
    TfToken up_id;
    up.GetShaderId(&up_id);
    if (up_id == "UsdPrimvarReader_float") {        // the clay mask's shade (materials.cpp)
      UsdShadeShader g = shader(stage, mat, ("Mtlx_" + name.GetString()).c_str(), "ND_geompropvalue_float");
      set(g, "geomprop", SdfValueTypeNames->String, std::string("rostrumMaskShade"));
      set(g, "default", kFloat, 1.0f);
      link(m, name.GetText(), kFloat, g, "out", kFloat);
    } else if (up_id == "UsdUVTexture") {           // a picture field: the same file through a MaterialX image
      const bool colour = in.GetTypeName() == SdfValueTypeNames->Color3f;
      UsdShadeShader t = shader(stage, mat, ("Mtlx_" + name.GetString()).c_str(),
                                colour ? "ND_image_color3" : "ND_image_float");
      UsdAttribute file = up.GetInput(TfToken("file")).GetAttr();
      UsdAttribute dst = t.CreateInput(TfToken("file"), SdfValueTypeNames->Asset).GetAttr();
      std::vector<double> times;
      file.GetTimeSamples(&times);
      SdfAssetPath a;
      if (file.Get(&a)) dst.Set(a);
      for (double tc : times)
        if (file.Get(&a, tc)) dst.Set(a, tc);
      TfToken space;
      up.GetInput(TfToken("sourceColorSpace")).Get(&space);
      if (space == "sRGB") dst.SetColorSpace(TfToken("srgb_texture"));
      link(m, name.GetText(), in.GetTypeName(), t, "out", colour ? kColor : kFloat);
    }
  }
  return m;
}

}  // namespace

void author_blocks(const UsdStageRefPtr& stage, const SdfPath& mat, const std::string& id, const std::string& file,
                   const std::string& where, UsdShadeShader& bsdf, UsdShadeShader& preview) {
  check_file(file, where, "a MaterialX document (.mtlx)");
  UsdStageRefPtr doc = UsdStage::Open(file, UsdStage::LoadNone);
  if (!doc) fail(where, "\"" + file + "\" could not be read as MaterialX", "a MaterialX 1.39 document (.mtlx)");
  SdfPath graph_path;
  UsdShadeNodeGraph graph = find_graph(doc, &graph_path);
  if (!graph) fail(where, "\"" + file + "\" has no material using a nodegraph NG_blocks", "the document graph.py writes");

  // Cycles: one node (or a few) per block, then the wires between blocks
  std::map<std::string, Block> blocks;
  std::vector<std::pair<UsdShadeShader, std::string>> order;
  for (const UsdPrim& p : graph.GetPrim().GetChildren()) {
    const UsdShadeShader s(p);
    if (!s) continue;
    TfToken sid;
    s.GetShaderId(&sid);
    const std::string type = block_type(sid.GetString());
    const std::string name = p.GetName().GetString();
    if (type.empty())
      fail(where + "." + name, "is a \"" + sid.GetString() + "\" block, which Final can't draw",
           "the Rostrum blocks (ND_rostrum_<type>: image, noise, mix, ramp, curve, colour adjust, bevel, occlusion)");
    blocks[name] = cycles_block(stage, mat, name, type, Values{s}, where);
    order.emplace_back(s, name);
  }
  for (auto& [s, name] : order) {
    Block& to = blocks[name];
    for (const UsdShadeInput& in : s.GetInputs()) {
      UsdShadeConnectableAPI src;
      TfToken out;
      UsdShadeAttributeType kind;
      if (!UsdShadeConnectableAPI::GetConnectedSource(in, &src, &out, &kind)) continue;
      const std::string from = src.GetPrim().GetName().GetString(), input = in.GetBaseName().GetString();
      auto fb = blocks.find(from);
      if (fb == blocks.end()) continue;   // the graph's own inputs: none are written
      auto o = fb->second.outs.find(out.GetString());
      auto i = to.ins.find(input);
      if (o == fb->second.outs.end())
        fail(where + "." + from, "has no output \"" + out.GetString() + "\"", "its outputs (value, colour, normal)");
      if (i == to.ins.end())
        fail(where + "." + name + "." + input, "can't take a wire", "a wire into one of the block's number or colour inputs");
      i->second.node.CreateInput(TfToken(i->second.name), i->second.type)
          .ConnectToSource(o->second.node.CreateOutput(TfToken(o->second.name), o->second.type));
    }
  }

  // Storm: the document's blocks referenced in place, and the MaterialX surface
  UsdPrim ref = stage->DefinePrim(mat.AppendChild(TfToken("Blocks")));
  ref.GetReferences().AddReference(file, graph_path);
  UsdShadeNodeGraph here(ref);
  UsdShadeShader storm = storm_surface(stage, mat, preview);

  for (const UsdShadeOutput& out : graph.GetOutputs()) {
    const std::string feed_name = out.GetBaseName().GetString();
    auto f = feeds().find(feed_name);
    if (f == feeds().end())
      fail(where + ".NG_blocks." + feed_name, "is not a Surface input",
           "baseColor, roughness, metallic, emissionColor or normal");
    UsdShadeConnectableAPI src;
    TfToken src_out;
    UsdShadeAttributeType kind;
    if (!UsdShadeConnectableAPI::GetConnectedSource(out, &src, &src_out, &kind)) continue;
    const std::string from = src.GetPrim().GetName().GetString();
    auto fb = blocks.find(from);
    if (fb == blocks.end()) fail(where + ".NG_blocks." + feed_name, "comes from \"" + from + "\", which is no block", "a block's output");
    auto o = fb->second.outs.find(src_out.GetString());
    if (o == fb->second.outs.end())
      fail(where + "." + from, "has no output \"" + src_out.GetString() + "\"", "its outputs (value, colour, normal)");
    const Feed& fd = f->second;
    bsdf.CreateInput(TfToken(fd.cycles), fd.ctype)
        .ConnectToSource(o->second.node.CreateOutput(TfToken(o->second.name), o->second.type));
    if (!fd.storm) continue;
    UsdShadeOutput mine = here.CreateOutput(TfToken(feed_name), out.GetTypeName());
    UsdShadeInput si = storm.CreateInput(TfToken(fd.storm), fd.stype);
    if (feed_name == "emissionColor") {            // the glow colour times its strength, as the Preview has it
      VtValue strength;
      float s = 1.0f;
      if (UsdShadeInput e = bsdf.GetInput(TfToken("emission_strength")); e && e.Get(&strength) && strength.IsHolding<float>())
        s = strength.UncheckedGet<float>();
      UsdShadeShader mul = shader(stage, mat, "MtlxEmissionStrength", "ND_multiply_color3FA");
      set(mul, "in2", kFloat, s);
      mul.CreateInput(TfToken("in1"), kColor).ConnectToSource(mine);
      si.ConnectToSource(mul.CreateOutput(TfToken("out"), kColor));
    } else {
      si.ConnectToSource(mine);
    }
  }
  UsdShadeMaterial(stage->GetPrimAtPath(mat))
      .CreateSurfaceOutput(TfToken("mtlx"))
      .ConnectToSource(storm.CreateOutput(TfToken("surface"), SdfValueTypeNames->Token));
  (void)id;
}

}  // namespace r3d
