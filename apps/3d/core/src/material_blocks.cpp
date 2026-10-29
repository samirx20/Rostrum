// A material's blocks: its MaterialX document drawn by Storm and Cycles (material_blocks.h).
#include "material_blocks.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <functional>
#include <map>
#include <variant>
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

// grey / brightness: the document's number <-> colour conversions; Cycles converts by itself, so they pass through.
const char* kTypes[] = {"colouradjust", "occlusion", "bevel", "image", "noise", "pattern", "mix", "ramp", "curve", "grey",
                        "brightness"};

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
  bool pass = false;                         // a conversion: its output is what feeds its "in"
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

// Pattern (graph_blocks.PATTERNS): the same sums as its MaterialX nodegraph (tools/make_blocks_mtlx.py), from Cycles'
// math nodes, only for the shape picked. On the UVs turned by `turn` (MaterialX's rotate2d turns the other way round
// from Cycles' z rotation: negated) and times `repeats`. Value: checks / stripes 0 on A, 1 on B; weave the thread's
// height, sin(pi * fraction) across it. Colour: A..B by which, a weave's threads WEAVE_SHADE darker at their edges.
// Its outputs, plus "_a" / "_b": the colour inputs a wire feeds.
template <class Node>
std::map<std::string, Socket> pattern_block(Node node, const Values& b) {
  const SdfValueTypeName kVec = SdfValueTypeNames->Vector3f, kStr = SdfValueTypeNames->String;
  constexpr float kPi = 3.14159265f, kShade = 0.45f;
  int count = 0;
  struct Out { mutable UsdShadeShader s; const char* name; };  // link() takes the shaders by reference
  const auto math = [&](const char* op, std::vector<std::variant<Out, float>> ins) {
    UsdShadeShader m = node(("Math" + std::to_string(count++)).c_str(), "cycles_math");
    set(m, "math_type", kStr, std::string(op));
    for (size_t i = 0; i < ins.size(); ++i) {
      const std::string in = "value" + std::to_string(i + 1);
      if (const Out* o = std::get_if<Out>(&ins[i])) link(m, in.c_str(), kFloat, o->s, o->name, kFloat);
      else set(m, in.c_str(), kFloat, std::get<float>(ins[i]));
    }
    return Out{m, "value"};
  };
  UsdShadeShader coords = node("Coords", "cycles_texture_coordinate");
  UsdShadeShader rot = node("Turn", "cycles_vector_rotate");
  set(rot, "rotate_type", kStr, std::string("z_axis"));
  set(rot, "angle", kFloat, -b.num("turn", 0) * kPi / 180.0f);
  link(rot, "vector", kVec, coords, "uv", kVec);
  UsdShadeShader scale = node("Repeats", "cycles_vector_math");
  set(scale, "math_type", kStr, std::string("scale"));
  set(scale, "scale", kFloat, b.num("repeats", 10));
  link(scale, "vector1", kVec, rot, "vector", kVec);
  UsdShadeShader xyz = node("UV", "cycles_separate_xyz");
  link(xyz, "vector", kVec, scale, "vector", kVec);
  const Out u{xyz, "x"}, v{xyz, "y"};
  // 0 or 1 by the parity of a cell: fraction((floor x + floor y) / 2) * 2
  const auto parity = [&](Out x, Out y) {
    return math("multiply", {math("fraction", {math("multiply", {math("add", {math("floor", {x}), math("floor", {y})}),
                                                                 0.5f})}), 2.0f});
  };
  const std::string shape = b.text("shape", "checks");
  Out which, value;
  if (shape == "stripes") {
    which = value = math("less_than", {math("fraction", {u}), b.num("width", 0.5f)});
  } else if (shape == "weave") {
    const Out u2 = math("multiply", {u, 2.0f}), v2 = math("multiply", {v, 2.0f});
    const Out hu = math("sine", {math("multiply", {math("fraction", {u2}), kPi})});
    const Out hv = math("sine", {math("multiply", {math("fraction", {v2}), kPi})});
    which = parity(u2, v2);
    value = math("multiply_add", {which, math("subtract", {hv, hu}), hu});   // A's threads run up (hu), B's across
  } else {
    which = value = parity(u, v);
  }
  UsdShadeShader col = node("", "cycles_mix_color");
  set(col, "blend_type", kStr, std::string("mix"));
  set(col, "a", kColor, b.colour("a", GfVec3f(1)));
  set(col, "b", kColor, b.colour("b", GfVec3f(0.25f)));
  link(col, "fac", kFloat, which.s, which.name, kFloat);
  std::map<std::string, Socket> outs{{"colour", {col, "result", kColor}}, {"value", {value.s, value.name, kFloat}},
                                     {"_a", {col, "a", kColor}}, {"_b", {col, "b", kColor}}};
  if (shape == "weave") {
    UsdShadeShader shaded = node("Shade", "cycles_mix_color");
    set(shaded, "blend_type", kStr, std::string("multiply"));
    set(shaded, "fac", kFloat, 1.0f);
    link(shaded, "a", kColor, col, "result", kColor);
    const Out s = math("multiply_add", {value, kShade, 1.0f - kShade});
    link(shaded, "b", kColor, s.s, s.name, kFloat);
    outs["colour"] = {shaded, "result", kColor};
  }
  return outs;
}

Block cycles_block(const UsdStageRefPtr& stage, const SdfPath& mat, const std::string& id, const std::string& type,
                   const std::string& shader_id, const Values& b, const std::string& where) {
  Block k{id, type, {}, {}};
  const bool colour_out = squash(shader_id).size() >= 6 && squash(shader_id).substr(squash(shader_id).size() - 6) == "color3";
  if (type == "grey" || type == "brightness") {
    k.pass = true;
    return k;
  }
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
    k.outs["value"] = {n, "fac", kFloat};
    k.outs["colour"] = {n, "color", kColor};
    k.outs["out"] = colour_out ? k.outs["colour"] : k.outs["value"];
  } else if (type == "pattern") {
    k.outs = pattern_block(node, b);
    k.ins["a"] = k.outs["_a"];
    k.ins["b"] = k.outs["_b"];
    k.outs.erase("_a");
    k.outs.erase("_b");
    k.outs["out"] = colour_out ? k.outs["colour"] : k.outs["value"];
  } else if (type == "image") {
    const std::string file = b.text("file", "");
    check_picture(file, where + "." + id + ".file");
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
    k.outs["value"] = {a, "ao", kFloat};
    k.outs["colour"] = {a, "color", kColor};
    k.outs["out"] = colour_out ? k.outs["colour"] : k.outs["value"];   // "out" is its colour when it gives a colour
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
           "the Rostrum blocks (ND_rostrum_<type>: image, noise, pattern, mix, ramp, curve, colour adjust, bevel, occlusion)");
    blocks[name] = cycles_block(stage, mat, name, type, sid.GetString(), Values{s}, where);
    order.emplace_back(s, name);
  }
  // what feeds through an output: a conversion passes on whatever feeds its "in" (nothing: no wire)
  std::map<std::string, UsdShadeShader> by_name;
  for (auto& [s, name] : order) by_name[name] = s;
  std::function<Socket*(const std::string&, const std::string&, int)> resolve =
      [&](const std::string& from, const std::string& out, int depth) -> Socket* {
    auto fb = blocks.find(from);
    if (fb == blocks.end() || depth > 16) return nullptr;
    if (fb->second.pass) {
      UsdShadeConnectableAPI src;
      TfToken o;
      UsdShadeAttributeType kind;
      UsdShadeInput in = by_name[from].GetInput(TfToken("in"));
      if (!in || !UsdShadeConnectableAPI::GetConnectedSource(in, &src, &o, &kind)) return nullptr;
      return resolve(src.GetPrim().GetName().GetString(), o.GetString(), depth + 1);
    }
    auto o = fb->second.outs.find(out);
    if (o == fb->second.outs.end())
      fail(where + "." + from, "has no output \"" + out + "\"", "its outputs (out, value, colour, normal)");
    return &o->second;
  };
  for (auto& [s, name] : order) {
    Block& to = blocks[name];
    if (to.pass) continue;
    for (const UsdShadeInput& in : s.GetInputs()) {
      UsdShadeConnectableAPI src;
      TfToken out;
      UsdShadeAttributeType kind;
      if (!UsdShadeConnectableAPI::GetConnectedSource(in, &src, &out, &kind)) continue;
      const std::string from = src.GetPrim().GetName().GetString(), input = in.GetBaseName().GetString();
      if (!blocks.count(from)) continue;   // the graph's own inputs: none are written
      Socket* o = resolve(from, out.GetString(), 0);
      if (!o) continue;
      auto i = to.ins.find(input);
      if (i == to.ins.end())
        fail(where + "." + name + "." + input, "can't take a wire", "a wire into one of the block's number or colour inputs");
      i->second.node.CreateInput(TfToken(i->second.name), i->second.type)
          .ConnectToSource(o->node.CreateOutput(TfToken(o->name), o->type));
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
    if (!blocks.count(from))
      fail(where + ".NG_blocks." + feed_name, "comes from \"" + from + "\", which is no block", "a block's output");
    const Feed& fd = f->second;
    if (Socket* o = resolve(from, src_out.GetString(), 0))
      bsdf.CreateInput(TfToken(fd.cycles), fd.ctype).ConnectToSource(o->node.CreateOutput(TfToken(o->name), o->type));
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
