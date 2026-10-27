#include "material_stylized.h"

#include <set>

#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usdShade/material.h>

#include "material_nodes.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

StylizedLook read_stylized(Reader& p) {
  StylizedLook l;
  l.lines = p.flag("lines");
  l.linesWidth = float(p.num("linesWidth"));
  l.linesColor = p.vec3("linesColor");
  l.linesTaper = float(p.num("linesTaper"));
  l.linesWobble = float(p.num("linesWobble"));
  l.linesCreaseAngle = float(p.num("linesCreaseAngle"));
  l.lightToColor = p.flag("lightToColor");
  l.litColor = p.vec3("litColor");
  l.midColor = p.vec3("midColor");
  l.shadowColor = p.vec3("shadowColor");
  l.shadowBelow = float(p.num("shadowBelow"));
  l.litFrom = float(p.num("litFrom"));
  l.lightSmooth = p.one_of("lightEdges", {"steps", "smooth"}) == "smooth";
  l.lightSoftness = float(p.num("lightSoftness"));
  l.halftone = p.flag("halftone");
  l.halftoneLines = p.one_of("halftoneShape", {"dots", "lines"}) == "lines";
  l.halftoneSize = float(p.num("halftoneSize"));
  l.halftoneAngle = float(p.num("halftoneAngle"));
  l.halftoneColor = p.vec3("halftoneColor");
  return l;
}

bool stylized_only_field(const std::string& key) {
  static const std::set<std::string> kOnly = {"lines",       "linesWidth",    "linesColor",   "linesTaper",
                                              "linesWobble", "linesCreaseAngle", "halftone", "halftoneShape",
                                              "halftoneSize", "halftoneAngle", "halftoneColor"};
  return kOnly.count(key) != 0;
}

void set_stylized_inputs(UsdShadeShader& s, const StylizedLook& l) {
  const SdfValueTypeName kFloat = SdfValueTypeNames->Float, kColor = SdfValueTypeNames->Color3f,
                         kBool = SdfValueTypeNames->Bool;
  set(s, "lines", kBool, l.lines);
  set(s, "linesWidth", kFloat, l.linesWidth);
  set(s, "linesColor", kColor, l.linesColor);
  set(s, "linesTaper", kFloat, l.linesTaper);
  set(s, "linesWobble", kFloat, l.linesWobble);
  set(s, "linesCreaseAngle", kFloat, l.linesCreaseAngle);
  set(s, "lightToColor", kBool, l.lightToColor);
  set(s, "litColor", kColor, l.litColor);
  set(s, "midColor", kColor, l.midColor);
  set(s, "shadowColor", kColor, l.shadowColor);
  set(s, "shadowBelow", kFloat, l.shadowBelow);
  set(s, "litFrom", kFloat, l.litFrom);
  set(s, "lightSoftness", kFloat, l.lightSoftness);
  set(s, "lightSmooth", kBool, l.lightSmooth);
  set(s, "halftone", kBool, l.halftone);
  set(s, "halftoneLines", kBool, l.halftoneLines);
  set(s, "halftoneSize", kFloat, l.halftoneSize);
  set(s, "halftoneAngle", kFloat, l.halftoneAngle);
  set(s, "halftoneColor", kColor, l.halftoneColor);
}

void author_stylized(const UsdStageRefPtr& stage, const SdfPath& material, const StylizedLook& look,
                     const GfVec3f& base, UsdShadeShader base_image, const GfVec3f& emission, float opacity) {
  const SdfValueTypeName kColor = SdfValueTypeNames->Color3f;
  UsdShadeShader s = shader(stage, material, "Stylized", "rostrum_stylized");
  set(s, "baseColor", kColor, base);  // the value stays authored under a link (what a reader without images shows)
  if (base_image) link(s, "baseColor", kColor, base_image, "rgb", SdfValueTypeNames->Float3);
  set(s, "emission", kColor, emission);
  set(s, "opacity", SdfValueTypeNames->Float, opacity);
  set_stylized_inputs(s, look);
  UsdShadeMaterial(stage->GetPrimAtPath(material))
      .CreateSurfaceOutput(TfToken("rostrum"))
      .ConnectToSource(s.CreateOutput(TfToken("surface"), SdfValueTypeNames->Token));
}

}  // namespace r3d
