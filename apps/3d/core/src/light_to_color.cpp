#include "light_to_color.h"

#include <OpenImageIO/imagebuf.h>

#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/vec3d.h>
#include <pxr/base/vt/array.h>
#include <pxr/base/vt/types.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/imageable.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>
#include <pxr/usd/usdGeom/tokens.h>
#include <pxr/usd/usdGeom/xformable.h>
#include <pxr/usd/usdLux/blackbody.h>
#include <pxr/usd/usdLux/diskLight.h>
#include <pxr/usd/usdLux/distantLight.h>
#include <pxr/usd/usdLux/domeLight.h>
#include <pxr/usd/usdLux/domeLight_1.h>
#include <pxr/usd/usdLux/lightAPI.h>
#include <pxr/usd/usdLux/rectLight.h>
#include <pxr/usd/usdLux/shadowAPI.h>
#include <pxr/usd/usdLux/shapingAPI.h>
#include <pxr/usd/usdLux/sphereLight.h>
#include <pxr/usd/usdLux/tokens.h>
#include <pxr/usd/usdShade/material.h>
#include <pxr/usd/usdShade/shader.h>

#include <algorithm>
#include <cmath>
#include <map>
#include <mutex>

#include "error.h"
#include "material_nodes.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
constexpr double kPi = 3.14159265358979323846;
constexpr size_t kMaxLights = 8;
constexpr int kRampSize = 1024;  // the band table: a step lands within 1/1023 of "how lit" of where it is set

float luminance(const GfVec3f& c) { return 0.2126f * c[0] + 0.7152f * c[1] + 0.0722f * c[2]; }

template <class T>
T get(const UsdAttribute& a, UsdTimeCode t, T fallback) {
  T v = fallback;
  if (a) a.Get(&v, t);
  return v;
}

// A length along one of the transform's axes (a light's size grows with its item's scale, as in Cycles).
double axis_scale(const GfMatrix4d& m, const GfVec3d& axis) { return m.TransformDir(axis).GetLength(); }

LightTerm::Kind kind_of(const UsdPrim& p, bool* ok) {
  *ok = true;
  if (p.IsA<UsdLuxDistantLight>()) return LightTerm::Kind::distant;
  if (p.IsA<UsdLuxSphereLight>()) return LightTerm::Kind::sphere;
  if (p.IsA<UsdLuxDiskLight>()) return LightTerm::Kind::disk;
  if (p.IsA<UsdLuxRectLight>()) return LightTerm::Kind::rect;
  if (p.IsA<UsdLuxDomeLight>() || p.IsA<UsdLuxDomeLight_1>()) return LightTerm::Kind::dome;
  *ok = false;
  return LightTerm::Kind::distant;
}

// One light at each frame. k: what a white matte surface facing the light shows (scene-linear, Rec.709 luminance of
// the light's colour), i.e. its irradiance / π, in the units Storm and Cycles use (ENGINE_CONTRACT.md § lights, H19):
//   distant  intensity·2^exposure is the lux on a facing surface (normalize or not, as both renderers draw it): k = p/π
//   sphere   radiance p (normalize: ÷ 4πr²); a ball of radius r at distance d gives π·p·r²/d²: k = p·r² (at 1 m)
//   disk     radiance p (normalize: ÷ πr²); small-source E = p·πr²·cosθ_light/d²: k = p·r², × cosθ_light in the graph
//   rect     radiance p (normalize: ÷ w·h); E = p·w·h·cosθ_light/d²: k = p·w·h/π, × cosθ_light in the graph
//   dome     its picture × colour × intensity × 2^exposure; a floor facing its up shows dome_floor_level of that
LightTerm sample_light(const UsdPrim& p, LightTerm::Kind kind, int start, int end) {
  LightTerm out;
  out.path = p.GetPath();
  out.kind = kind;
  UsdLuxLightAPI light(p);
  out.shadows = get(UsdLuxShadowAPI(p).GetShadowEnableAttr(), UsdTimeCode::Default(), true);
  out.spot = kind == LightTerm::Kind::sphere && p.HasAPI<UsdLuxShapingAPI>();
  const UsdLuxShapingAPI shaping(p);
  const UsdGeomXformable xf(p);
  const UsdGeomImageable im(p);
  for (int f = start; f <= end; ++f) {
    const UsdTimeCode t(f);
    GfVec3f colour = get(light.GetColorAttr(), t, GfVec3f(1));
    if (get(light.GetEnableColorTemperatureAttr(), t, false))
      colour = GfCompMult(colour, UsdLuxBlackbodyTemperatureAsRgb(get(light.GetColorTemperatureAttr(), t, 6500.0f)));
    const double power = double(get(light.GetIntensityAttr(), t, 1.0f)) *
                         std::exp2(double(get(light.GetExposureAttr(), t, 0.0f)));
    const bool normalize = get(light.GetNormalizeAttr(), t, false);
    const bool seen = im.ComputeVisibility(t) != UsdGeomTokens->invisible;
    const GfMatrix4d m = xf.ComputeLocalToWorldTransform(t);
    const GfVec3d emit = m.TransformDir(GfVec3d(0, 0, -1)).GetNormalized();
    double k = 0;
    GfVec3f where(0.0f), back = GfVec3f(-emit);
    switch (kind) {
      case LightTerm::Kind::distant:
        k = power / kPi * luminance(colour);
        where = GfVec3f(-emit);
        break;
      case LightTerm::Kind::sphere: {
        const double r = get(UsdLuxSphereLight(p).GetRadiusAttr(), t, 0.5f) * axis_scale(m, GfVec3d(1, 0, 0));
        k = (normalize ? power / (4 * kPi) : power * r * r) * luminance(colour);
        where = GfVec3f(m.ExtractTranslation());
        break;
      }
      case LightTerm::Kind::disk: {
        const double r = get(UsdLuxDiskLight(p).GetRadiusAttr(), t, 0.5f) * axis_scale(m, GfVec3d(1, 0, 0));
        k = (normalize ? power / kPi : power * r * r) * luminance(colour);
        where = GfVec3f(m.ExtractTranslation());
        break;
      }
      case LightTerm::Kind::rect: {
        const UsdLuxRectLight rect(p);
        const double area = get(rect.GetWidthAttr(), t, 1.0f) * axis_scale(m, GfVec3d(1, 0, 0)) *
                            get(rect.GetHeightAttr(), t, 1.0f) * axis_scale(m, GfVec3d(0, 1, 0));
        k = (normalize ? power / kPi : power * area / kPi) * luminance(colour);
        where = GfVec3f(m.ExtractTranslation());
        break;
      }
      case LightTerm::Kind::dome: {
        SdfAssetPath tex;
        p.GetAttribute(UsdLuxTokens->inputsTextureFile).Get(&tex, t);
        const std::string file = tex.GetResolvedPath().empty() ? tex.GetAssetPath() : tex.GetResolvedPath();
        k = luminance(GfCompMult(dome_floor_level(file), colour) * float(power));
        where = GfVec3f(m.TransformDir(GfVec3d(0, 1, 0)).GetNormalized());
        break;
      }
    }
    if (!seen || !std::isfinite(k)) k = 0;
    out.k.push_back(float(std::max(k, 0.0)));
    out.where.push_back(where);
    out.back.push_back(back);
    if (out.spot) {  // UsdLux: the cone's half angle; softness the outer share of it that fades (Cycles' smoothstep)
      const double half = std::clamp(double(get(shaping.GetShapingConeAngleAttr(), t, 90.0f)), 0.0, 180.0);
      const double soft = std::clamp(double(get(shaping.GetShapingConeSoftnessAttr(), t, 0.0f)), 0.0, 1.0);
      const float outer = float(std::cos(half * kPi / 180.0));
      const float inner = std::max(float(std::cos(half * (1.0 - soft) * kPi / 180.0)), outer + 1e-4f);
      out.cosOuter.push_back(outer);
      out.cosInner.push_back(inner);
    }
    out.rank = std::max(out.rank, k);
  }
  return out;
}

// An input with one value, or (when it changes over the shot) a time sample per frame.
template <class T>
void put(UsdShadeShader& s, const char* input, const SdfValueTypeName& type, const std::vector<T>& v, int start) {
  UsdAttribute a = s.CreateInput(TfToken(input), type).GetAttr();
  a.Set(v.front());
  if (std::all_of(v.begin(), v.end(), [&](const T& x) { return x == v.front(); })) return;
  for (size_t i = 0; i < v.size(); ++i) a.Set(v[i], UsdTimeCode(double(start) + double(i)));
}

template <class T>
T value_of(const UsdShadeShader& s, const char* input, T fallback) {
  T v = fallback;
  if (const UsdShadeInput in = s.GetInput(TfToken(input))) in.Get(&v);
  return v;
}

// The band colour at how lit `h` (ENGINE_CONTRACT.md § 2): steps, or piecewise linear over ± softness round each edge.
GfVec3f band(float h, const GfVec3f& shadow, const GfVec3f& mid, const GfVec3f& lit, float below, float from,
             bool smooth, float soft) {
  below = std::min(below, from);  // shadowBelow past litFrom: litFrom for both
  if (!smooth) return h < below ? shadow : h < from ? mid : lit;
  soft = std::max(soft, 1e-4f);
  const auto t = [&](float edge) { return std::clamp((h - (edge - soft)) / (2 * soft), 0.0f, 1.0f); };
  const float a = t(below), b = t(from);
  const GfVec3f c = shadow * (1 - a) + mid * a;
  return c * (1 - b) + lit * b;
}
}  // namespace

GfVec3f dome_floor_level(const std::string& texture) {
  if (texture.empty()) return GfVec3f(1.0f);
  static std::mutex m;
  static std::map<std::string, GfVec3f> cache;
  std::lock_guard<std::mutex> lock(m);
  if (auto it = cache.find(texture); it != cache.end()) return it->second;
  OIIO::ImageBuf buf(texture);
  if (!buf.init_spec(texture, 0, 0))
    throw Error("light to colour: could not read the dome's picture " + texture + ": " + buf.geterror());
  const int w = buf.spec().width, h = buf.spec().height, nc = std::min(buf.spec().nchannels, 3);
  if (w < 1 || h < 1) throw Error("light to colour: the dome's picture " + texture + " is empty");
  // a grid of at most 512 × 256 samples over the upper half (lat-long, +Y up, row 0 straight up: sky.cpp's layout)
  const int sx = std::min(w, 512), sy = std::min(h, 256);
  double sum[3] = {0, 0, 0};
  float px[4] = {0, 0, 0, 0};
  for (int j = 0; j < sy; ++j) {
    const double polar = (j + 0.5) / sy * kPi;
    if (polar >= kPi / 2) break;
    const double weight = std::cos(polar) * std::sin(polar) * (kPi / sy) * (2 * kPi / sx);  // cos × solid angle
    const int y = std::min(h - 1, int((j + 0.5) / sy * h));
    for (int i = 0; i < sx; ++i) {
      buf.getpixel(std::min(w - 1, int((i + 0.5) / sx * w)), y, 0, OIIO::span<float>(px, 4));
      for (int c = 0; c < 3; ++c) sum[c] += weight * px[nc == 1 ? 0 : c];
    }
  }
  if (buf.has_error()) throw Error("light to colour: could not read the dome's picture " + texture + ": " + buf.geterror());
  const GfVec3f level(float(sum[0] / kPi), float(sum[1] / kPi), float(sum[2] / kPi));
  cache[texture] = level;
  return level;
}

std::vector<LightTerm> scene_light_terms(const UsdStageRefPtr& stage, int start, int end) {
  std::vector<LightTerm> all;
  for (const UsdPrim& p : stage->Traverse()) {
    bool ok = false;
    const LightTerm::Kind kind = kind_of(p, &ok);
    if (!ok) continue;
    LightTerm t = sample_light(p, kind, start, end);
    if (t.rank > 0) all.push_back(std::move(t));
  }
  std::stable_sort(all.begin(), all.end(), [](const LightTerm& a, const LightTerm& b) { return a.rank > b.rank; });
  if (all.size() > kMaxLights) all.resize(kMaxLights);
  return all;
}

bool apply_light_to_color(const UsdStageRefPtr& stage, const SdfPath& material, const std::vector<LightTerm>& lights,
                          int start) {
  const UsdShadeShader look(stage->GetPrimAtPath(material.AppendChild(TfToken("Stylized"))));
  if (!look || !value_of(look, "lightToColor", false)) return false;
  const UsdShadeShader bsdf(stage->GetPrimAtPath(material.AppendChild(TfToken("Cycles"))));
  if (!bsdf) throw Error("light to colour: " + material.GetString() + " has no Cycles shader");
  const SdfValueTypeName kFloat = SdfValueTypeNames->Float, kVec = SdfValueTypeNames->Vector3f,
                         kColor = SdfValueTypeNames->Color3f, kStr = SdfValueTypeNames->String,
                         kPoint = SdfValueTypeNames->Point3f, kNormal = SdfValueTypeNames->Normal3f;
  const auto node = [&](const std::string& name, const char* id) { return shader(stage, material, name.c_str(), id); };
  const auto math = [&](const std::string& name, const char* op) {
    UsdShadeShader s = node(name, "cycles_math");
    set(s, "math_type", kStr, std::string(op));
    return s;
  };
  const auto vmath = [&](const std::string& name, const char* op) {
    UsdShadeShader s = node(name, "cycles_vector_math");
    set(s, "math_type", kStr, std::string(op));
    return s;
  };
  // a × b of two float outputs (each node's float output is "value")
  int n = 0;
  const auto times = [&](UsdShadeShader& a, const char* a_out, UsdShadeShader& b, const char* b_out) {
    UsdShadeShader m = math("L2CTimes" + std::to_string(n++), "multiply");
    link(m, "value1", kFloat, a, a_out, kFloat);
    link(m, "value2", kFloat, b, b_out, kFloat);
    return m;
  };

  UsdShadeShader geo = node("L2CGeometry", "cycles_geometry");
  // shadow rays start 1 mm off the surface (or they hit their own triangle)
  UsdShadeShader lift = vmath("L2CLift", "multiply_add");
  link(lift, "vector1", kVec, geo, "normal", kNormal);
  set(lift, "vector2", kVec, GfVec3f(1e-3f));
  link(lift, "vector3", kVec, geo, "position", kPoint);

  UsdShadeShader sum;  // how lit, summed so far ("value")
  for (size_t i = 0; i < lights.size(); ++i) {
    const LightTerm& l = lights[i];
    const std::string p = "L2C" + std::to_string(i);
    UsdShadeShader term;
    if (l.kind == LightTerm::Kind::dome) {  // hemisphere: 0.5 + 0.5·N·up
      UsdShadeShader up = vmath(p + "Up", "dot_product");
      link(up, "vector1", kVec, geo, "normal", kNormal);
      put(up, "vector2", kVec, l.where, start);
      UsdShadeShader hemi = math(p + "Hemi", "multiply_add");
      link(hemi, "value1", kFloat, up, "value", kFloat);
      set(hemi, "value2", kFloat, 0.5f);
      set(hemi, "value3", kFloat, 0.5f);
      term = math(p + "Term", "multiply");
      link(term, "value1", kFloat, hemi, "value", kFloat);
      put(term, "value2", kFloat, l.k, start);
    } else {
      const bool distant = l.kind == LightTerm::Kind::distant;
      UsdShadeShader to_light, d2;
      // raycast.direction is a normal socket: unlinked, Cycles feeds it the surface normal, so the direction always
      // comes through a node (proofs/3d-painterly/README.md)
      UsdShadeShader dir = vmath(p + "Dir", "normalize");
      if (distant) {
        put(dir, "vector1", kVec, l.where, start);
      } else {
        to_light = vmath(p + "ToLight", "subtract");
        put(to_light, "vector1", kVec, l.where, start);
        link(to_light, "vector2", kVec, geo, "position", kPoint);
        link(dir, "vector1", kVec, to_light, "vector", kVec);
        d2 = vmath(p + "Dist2", "dot_product");
        link(d2, "vector1", kVec, to_light, "vector", kVec);
        link(d2, "vector2", kVec, to_light, "vector", kVec);
      }
      UsdShadeShader ndotl = vmath(p + "NdotL", "dot_product");
      link(ndotl, "vector1", kVec, geo, "normal", kNormal);
      link(ndotl, "vector2", kVec, dir, "vector", kVec);
      UsdShadeShader lit = math(p + "Facing", "maximum");
      link(lit, "value1", kFloat, ndotl, "value", kFloat);
      set(lit, "value2", kFloat, 0.0f);
      UsdShadeShader cur = lit;
      const char* cur_out = "value";
      if (l.spot || l.kind == LightTerm::Kind::disk || l.kind == LightTerm::Kind::rect) {
        UsdShadeShader away = vmath(p + "FromLight", "dot_product");  // cos of the angle off the light's own axis
        link(away, "vector1", kVec, dir, "vector", kVec);
        put(away, "vector2", kVec, l.back, start);
        if (l.spot) {  // the cone, its soft edge a smoothstep as Cycles' spot
          UsdShadeShader cone = node(p + "Cone", "cycles_map_range");
          set(cone, "range_type", kStr, std::string("smoothstep"));
          link(cone, "value", kFloat, away, "value", kFloat);
          put(cone, "from_min", kFloat, l.cosOuter, start);
          put(cone, "from_max", kFloat, l.cosInner, start);
          set(cone, "to_min", kFloat, 0.0f);
          set(cone, "to_max", kFloat, 1.0f);
          set(cone, "clamp", SdfValueTypeNames->Bool, true);
          cur = times(cur, cur_out, cone, "result");
        } else {  // a panel lights only its front, by cos of the angle off its axis
          UsdShadeShader front = math(p + "Front", "maximum");
          link(front, "value1", kFloat, away, "value", kFloat);
          set(front, "value2", kFloat, 0.0f);
          cur = times(cur, cur_out, front, "value");
        }
        cur_out = "value";
      }
      if (l.shadows) {
        UsdShadeShader ray = node(p + "Ray", "cycles_raycast");
        link(ray, "position", kPoint, lift, "vector", kVec);
        link(ray, "direction", kNormal, dir, "vector", kVec);
        if (distant) {
          set(ray, "length", kFloat, 1e4f);
        } else {  // up to just short of the light (a light's card sits at its place)
          UsdShadeShader dist = math(p + "Dist", "sqrt");
          link(dist, "value1", kFloat, d2, "value", kFloat);
          UsdShadeShader len = math(p + "RayLength", "multiply_add");
          link(len, "value1", kFloat, dist, "value", kFloat);
          set(len, "value2", kFloat, 0.999f);
          set(len, "value3", kFloat, -2e-3f);
          link(ray, "length", kFloat, len, "value", kFloat);
        }
        UsdShadeShader open = math(p + "Open", "subtract");
        set(open, "value1", kFloat, 1.0f);
        link(open, "value2", kFloat, ray, "is_hit", kFloat);
        cur = times(cur, cur_out, open, "value");
        cur_out = "value";
      }
      if (!distant) {  // 1/d² (Cycles' divide gives 0 for 0)
        UsdShadeShader fall = math(p + "Falloff", "divide");
        link(fall, "value1", kFloat, cur, cur_out, kFloat);
        link(fall, "value2", kFloat, d2, "value", kFloat);
        cur = fall;
        cur_out = "value";
      }
      term = math(p + "Term", "multiply");
      link(term, "value1", kFloat, cur, cur_out, kFloat);
      put(term, "value2", kFloat, l.k, start);
    }
    if (!sum) {
      sum = term;
    } else {
      UsdShadeShader add = math(p + "Sum", "add");
      link(add, "value1", kFloat, sum, "value", kFloat);
      link(add, "value2", kFloat, term, "value", kFloat);
      sum = add;
    }
  }

  // how lit -> the band colour (rgb_ramp clamps its fac to 0..1); steps: no blending between table entries
  const bool smooth = value_of(look, "lightSmooth", false);
  const GfVec3f shadow = value_of(look, "shadowColor", GfVec3f(0.3f)), mid = value_of(look, "midColor", GfVec3f(0.7f)),
                lit_c = value_of(look, "litColor", GfVec3f(1.0f));
  const float below = value_of(look, "shadowBelow", 0.15f), from = value_of(look, "litFrom", 0.5f),
              soft = value_of(look, "lightSoftness", 0.1f);
  VtVec3fArray table(kRampSize);
  VtFloatArray alpha(kRampSize, 1.0f);
  for (int i = 0; i < kRampSize; ++i)
    table[i] = band(float(i) / float(kRampSize - 1), shadow, mid, lit_c, below, from, smooth, soft);
  UsdShadeShader ramp = node("L2CRamp", "cycles_rgb_ramp");
  set(ramp, "ramp", SdfValueTypeNames->Color3fArray, table);
  set(ramp, "ramp_alpha", SdfValueTypeNames->FloatArray, alpha);
  set(ramp, "interpolate", SdfValueTypeNames->Bool, smooth);
  if (sum) link(ramp, "fac", kFloat, sum, "value", kFloat);
  else set(ramp, "fac", kFloat, 0.0f);  // no lights: all shadow

  // × the base colour, or what feeds it (the base colour image, decoded)
  UsdShadeShader tint = vmath("L2CTint", "multiply");
  link(tint, "vector1", kVec, ramp, "color", kColor);
  const UsdShadeInput base = bsdf.GetInput(TfToken("base_color"));
  const auto base_src = base ? base.GetConnectedSources() : UsdShadeInput::SourceInfoVector{};
  if (!base_src.empty()) tint.CreateInput(TfToken("vector2"), kVec).ConnectToSource(base_src.front());
  else set(tint, "vector2", kVec, value_of(bsdf, "base_color", GfVec3f(0.8f)));

  // + the material's own glow (colour or picture × strength)
  UsdShadeShader out = tint;
  const float strength = value_of(bsdf, "emission_strength", 0.0f);
  const UsdShadeInput glow = bsdf.GetInput(TfToken("emission_color"));
  const auto glow_src = glow ? glow.GetConnectedSources() : UsdShadeInput::SourceInfoVector{};
  const GfVec3f glow_c = value_of(bsdf, "emission_color", GfVec3f(0.0f)) * strength;
  if (strength > 0 && (!glow_src.empty() || glow_c != GfVec3f(0.0f))) {
    UsdShadeShader add = vmath("L2CGlow", "add");
    link(add, "vector1", kVec, tint, "vector", kVec);
    if (!glow_src.empty()) {
      UsdShadeShader scale = vmath("L2CGlowStrength", "scale");
      scale.CreateInput(TfToken("vector1"), kVec).ConnectToSource(glow_src.front());
      set(scale, "scale", kFloat, strength);
      link(add, "vector2", kVec, scale, "vector", kVec);
    } else {
      set(add, "vector2", kVec, glow_c);
    }
    out = add;
  }
  UsdShadeShader emit = node("L2CEmission", "cycles_emission");
  link(emit, "color", kColor, out, "vector", kVec);
  set(emit, "strength", kFloat, 1.0f);
  UsdShadeMaterial(stage->GetPrimAtPath(material))
      .CreateSurfaceOutput(TfToken("cycles"))
      .ConnectToSource(emit.CreateOutput(TfToken("Emission"), SdfValueTypeNames->Token));
  return true;
}

void publish_dome_levels(const UsdStageRefPtr& stage) {
  for (const UsdPrim& p : stage->Traverse()) {
    if (!p.IsA<UsdLuxDomeLight>() && !p.IsA<UsdLuxDomeLight_1>()) continue;
    SdfAssetPath tex;
    p.GetAttribute(UsdLuxTokens->inputsTextureFile).Get(&tex);
    const std::string file = tex.GetResolvedPath().empty() ? tex.GetAssetPath() : tex.GetResolvedPath();
    UsdGeomPrimvarsAPI(p)
        .CreatePrimvar(TfToken("rostrum:domeLevel"), SdfValueTypeNames->Color3f, UsdGeomTokens->constant)
        .Set(dome_floor_level(file));
  }
}

void build_light_to_color(const UsdStageRefPtr& stage, int start, int end) {
  const UsdPrim looks = stage->GetPrimAtPath(SdfPath("/World/Looks"));
  if (!looks) return;
  bool gathered = false;
  std::vector<LightTerm> lights;
  for (const UsdPrim& m : looks.GetChildren()) {
    const UsdShadeShader look(m.GetChild(TfToken("Stylized")));
    bool on = false;
    if (!look || !look.GetInput(TfToken("lightToColor")) || !look.GetInput(TfToken("lightToColor")).Get(&on) || !on)
      continue;
    if (!gathered) {
      lights = scene_light_terms(stage, start, end);
      gathered = true;
    }
    apply_light_to_color(stage, m.GetPath(), lights, start);
  }
}

}  // namespace r3d
