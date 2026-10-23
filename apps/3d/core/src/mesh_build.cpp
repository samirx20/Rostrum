#include "mesh_build.h"

#include <algorithm>

#include <pxr/usd/usdGeom/primvarsAPI.h>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

MeshData shape(Reader& p, FaceGroups& groups) {
  const std::string s = p.one_of("shape", {"box", "sphere", "cylinder", "plane", "disc", "torus", "outline"});
  const bool smooth = p.flag("smooth");
  auto size = [&](const char* key) { return float(p.num_min(key, 0.0, false)); };
  auto bevel = [&](float most) {
    const float b = float(p.num_min("bevel", 0.0, true));
    if (b > most) fail(p.at("bevel"), std::to_string(b) + " is too big for the shape", "0 .. " + std::to_string(most));
    return b;
  };
  if (s == "box") {
    const float w = size("width"), h = size("height"), d = size("depth");
    const float b = bevel(std::min({w, h, d}) / 2);
    return make_box(w, h, d, b, p.count("segments", 1, 256), smooth);
  }
  if (s == "cylinder") {
    const float r = size("radius"), h = size("height");
    const float b = bevel(std::min(r, h / 2));
    return make_cylinder(r, h, b, p.count("segments", 3, 1024), smooth);
  }
  if (s == "sphere") {
    const float r = size("radius");
    return make_sphere(r, p.count("segments", 3, 1024), smooth);
  }
  if (s == "torus") {
    const float r = size("radius"), tube = size("tube");
    return make_torus(r, tube, p.count("segments", 3, 1024), smooth);
  }
  if (s == "disc") {
    const float r = size("radius");
    return make_disc(r, p.count("segments", 3, 1024));
  }
  if (s == "outline") {
    const float d = float(p.num_min("depth", 0.0, true));
    const float b = bevel(d / 2);
    const std::vector<OutlineShape> shapes = read_outline(p.list("outline"), p.at("outline"));
    Extruded e = make_extrusion(shapes, d, b, p.count("segments", 1, 1024), smooth, p.where());
    groups = std::move(e.groups);
    return std::move(e.mesh);
  }
  const float w = size("width"), d = size("depth");
  return make_plane(w, d);
}

void mesh_known(Reader& p) {
  p.known({"width", "height", "depth", "radius", "tube", "bevel", "segments", "outline", "frontMaterial",
           "bevelMaterial", "sideMaterial", "backMaterial"});
}

void write_mesh(UsdGeomMesh m, const MeshData& d) {
  m.CreatePointsAttr().Set(d.points);
  m.CreateNormalsAttr().Set(d.normals);
  m.SetNormalsInterpolation(UsdGeomTokens->vertex);  // Cycles ignores face-varying normals
  m.CreateFaceVertexCountsAttr().Set(d.counts);
  m.CreateFaceVertexIndicesAttr().Set(d.indices);
  m.CreateSubdivisionSchemeAttr().Set(UsdGeomTokens->none);
  UsdGeomPrimvarsAPI(m.GetPrim())
      .CreatePrimvar(TfToken("st"), SdfValueTypeNames->TexCoord2fArray, UsdGeomTokens->faceVarying)
      .Set(d.st);
  VtVec3fArray extent;
  if (UsdGeomPointBased::ComputeExtent(d.points, &extent)) m.CreateExtentAttr().Set(extent);
}

}  // namespace r3d
