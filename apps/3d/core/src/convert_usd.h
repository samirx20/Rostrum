// What the four format readers (convert_gltf / _obj / _fbx / _abc.cpp) share to write a converted layer the way
// convert.h describes it: the layer's metadata and default prim, valid unique prim names, a Mesh from plain arrays,
// UsdPreviewSurface materials and their binding, and the cache folder for textures that live inside a file.
#pragma once

#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/tf/token.h>
#include <pxr/base/vt/array.h>
#include <pxr/base/vt/types.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usd/timeCode.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/xform.h>
#include <pxr/usd/usdShade/material.h>

#include <cstddef>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace r3d::cv {

// The file name without folder and extension ("chair" for C:\x\chair.glb).
std::string stem_of(const std::string& file);
// The folder `file` is in, with a trailing separator ("" when it has none).
std::string folder_of(const std::string& file);
// An absolute path with forward slashes, as a USD asset path.
std::string asset_path(const std::string& path);

// Starts a converted layer: its metadata (upAxis Y, metersPerUnit, rostrum:format, rostrum:unitsKnown) and the
// default prim, an Xform named after the file. Returns that Xform.
pxr::UsdGeomXform start_layer(const pxr::UsdStageRefPtr& stage, const std::string& file, const std::string& format,
                              double meters_per_unit, bool units_known);
// The layer's animation range: one time code per source frame.
void set_time_range(const pxr::UsdStageRefPtr& stage, double start, double end, double codes_per_second);

// Child names made valid identifiers and unique among one parent's children ("Body", "Body_1", ...).
class Names {
 public:
  pxr::SdfPath child(const pxr::SdfPath& parent, const std::string& raw, const std::string& fallback);

 private:
  std::map<pxr::SdfPath, std::set<std::string>> taken_;
};

// A local transform as one xformOp:transform (left out when it is the identity and not animated). `time` is
// Default for a still transform, a time code for one sample of an animated one.
void set_transform(const pxr::UsdGeomXformable& x, const pxr::GfMatrix4d& m,
                   pxr::UsdTimeCode time = pxr::UsdTimeCode::Default());

// A mesh as plain arrays. Normals and UVs are optional (empty = none); each is per point ("vertex") or per face
// corner ("faceVarying"), and may carry indices into its values (indexed primvar; normals are expanded).
struct MeshArrays {
  pxr::VtVec3fArray points;
  pxr::VtIntArray counts, indices;
  pxr::VtVec3fArray normals;
  pxr::VtIntArray normal_indices;
  pxr::TfToken normal_interp;  // UsdGeomTokens->vertex or ->faceVarying
  pxr::VtVec2fArray uvs;
  pxr::VtIntArray uv_indices;
  pxr::TfToken uv_interp;
  bool subdivided = false;  // false: subdivisionScheme "none" (a polygon model, drawn as is)
};
// write_mesh: a still Mesh (topology, points, extent, normals, st). write_mesh_sample: one sample of an animated
// one: points and extent at `time`, counts / indices too if `with_topology` (topology that changes over time), and
// normals / UVs if `with_extras`, at `extras` (Default when they don't change).
pxr::UsdGeomMesh write_mesh(const pxr::UsdStageRefPtr& stage, const pxr::SdfPath& path, const MeshArrays& m);
void write_mesh_sample(pxr::UsdGeomMesh mesh, const MeshArrays& m, pxr::UsdTimeCode time, bool with_topology,
                       bool with_extras, pxr::UsdTimeCode extras);

// A material as the formats give it (glTF's metallic-roughness model; others map onto it).
struct MaterialDesc {
  std::string name;
  pxr::GfVec3f base_color{0.8f, 0.8f, 0.8f};
  std::string base_texture;  // an absolute file path, or "" (one tile of a UDIM set is written as the set, udim.h)
  float metallic = 0.0f, roughness = 0.5f;
  pxr::GfVec3f emissive{0.0f, 0.0f, 0.0f};
  float opacity = 1.0f;
  float opacity_threshold = 0.0f;  // > 0: cut-out (glTF alphaMode MASK)
};
// The UsdPreviewSurface network of `d` under <default prim>/Materials.
pxr::UsdShadeMaterial write_material(const pxr::UsdStageRefPtr& stage, const MaterialDesc& d, Names& names);
void bind(const pxr::UsdPrim& prim, const pxr::UsdShadeMaterial& m);
// Per-face materials: one GeomSubset (familyName materialBind) per material, bound to it. `face_material[i]` is
// face i's index into `materials` (-1 or out of range: left unbound). One material for every face binds the mesh.
void bind_per_face(const pxr::UsdGeomMesh& mesh, const std::vector<int>& face_material,
                   const std::vector<pxr::UsdShadeMaterial>& materials);

// The folder for images a file carries inside it: %LOCALAPPDATA%\Rostrum\3d-import-cache\<hash of path, size,
// modification time>\ (made on first use). Writes `bytes` there as `name` once and returns the file's path.
std::string cache_image(const std::string& file, const std::string& name, const void* bytes, std::size_t size);

}  // namespace r3d::cv
