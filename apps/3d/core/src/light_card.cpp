// A panel light's visible card for Storm (light_extras.h): a mesh the size of the panel, facing where the light shines
// (−Z), whose glow is the light's own brightness frame by frame: UsdLux's colour × intensity × 2^exposure (× its colour
// temperature), ÷ its area when normalize is on. Storm doesn't light the scene from it (only its lights light), and
// the Cycles filter hides it (cycles_lights.cpp), where the light's own camera visibility shows the panel instead.
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdLux/blackbody.h>
#include <pxr/usd/usdShade/material.h>
#include <pxr/usd/usdShade/materialBindingAPI.h>
#include <pxr/usd/usdShade/shader.h>

#include <cmath>

#include "light_extras.h"
#include "primitives.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

void build_card(Item& it, const UsdPrim& light, const std::string& kind) {
  const UsdStageRefPtr& stage = it.ctx.stage;
  const SdfPath path = light.GetPath().AppendChild(TfToken(kCardName));
  Reader& p = it.props;
  const bool disk = kind == "disk";
  const double w = kind == "strip" ? p.num("length") : disk ? 2 * p.num("radius") : p.num("width");
  const double h = kind == "strip" ? p.num("width") : disk ? w : p.num("height");
  const double area = disk ? M_PI * w * w / 4 : w * h;
  MeshData d = disk ? make_disc(float(w / 2), 64) : make_plane(float(w), float(h));
  for (auto* v : {&d.points, &d.normals})  // made facing +Y in X-Z; the light faces −Z with its height along Y
    for (GfVec3f& q : *v) q = GfVec3f(q[0], q[2], -q[1]);

  UsdGeomMesh m = UsdGeomMesh::Define(stage, path);
  m.CreatePointsAttr().Set(d.points);
  m.CreateNormalsAttr().Set(d.normals);
  m.SetNormalsInterpolation(UsdGeomTokens->vertex);
  m.CreateFaceVertexCountsAttr().Set(d.counts);
  m.CreateFaceVertexIndicesAttr().Set(d.indices);
  m.CreateSubdivisionSchemeAttr().Set(UsdGeomTokens->none);
  m.CreateDoubleSidedAttr().Set(false);  // a panel shines from its front only
  VtVec3fArray extent;
  if (UsdGeomPointBased::ComputeExtent(d.points, &extent)) m.CreateExtentAttr().Set(extent);

  const UsdShadeMaterial mat = UsdShadeMaterial::Define(stage, light.GetPath().AppendChild(TfToken("RostrumCardGlow")));
  UsdShadeShader s = UsdShadeShader::Define(stage, mat.GetPath().AppendChild(TfToken("Surface")));
  s.CreateIdAttr().Set(TfToken("UsdPreviewSurface"));
  s.CreateInput(TfToken("diffuseColor"), SdfValueTypeNames->Color3f).Set(GfVec3f(0));
  s.CreateInput(TfToken("roughness"), SdfValueTypeNames->Float).Set(1.0f);
  const auto colour = it.colours("color");
  const auto intensity = it.nums("intensity"), exposure = it.nums("exposure"), kelvin = it.nums("temperature");
  const bool normalize = p.flag("normalize");
  it.write<GfVec3f>(s.CreateInput(TfToken("emissiveColor"), SdfValueTypeNames->Color3f).GetAttr(),
                    frames({colour.size(), intensity.size(), exposure.size(), kelvin.size()}), [&](size_t i) {
                      GfVec3f c = pick(colour, i) * float(pick(intensity, i) * std::exp2(pick(exposure, i)));
                      if (pick(kelvin, i) > 0) c = GfCompMult(c, UsdLuxBlackbodyTemperatureAsRgb(float(pick(kelvin, i))));
                      return normalize && area > 0 ? c / float(area) : c;
                    });
  mat.CreateSurfaceOutput().ConnectToSource(s.ConnectableAPI(), TfToken("surface"));
  UsdShadeMaterialBindingAPI::Apply(m.GetPrim()).Bind(mat);
}

}  // namespace r3d
