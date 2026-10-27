// Wavefront OBJ into a converted layer (convert.h), read with tinyobjloader (third_party/tinyobjloader, MIT).
// One Mesh per OBJ shape (an `o` / `g` group), polygons kept as they are (not cut into triangles), normals and UVs
// per face corner, and the .mtl materials (Kd colour, map_Kd image, Ns shininess as roughness, d / Tr opacity,
// Ke glow; PBR Pr / Pm when the .mtl has them). OBJ has no unit (metersPerUnit 1, unitsKnown false) and is Y up.
#define TINYOBJLOADER_IMPLEMENTATION
#include <tiny_obj_loader.h>

#include <pxr/usd/usdGeom/tokens.h>

#include <algorithm>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <unordered_map>

#include "convert_usd.h"
#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace fs = std::filesystem;

namespace r3d {

namespace {

// Reads the .mtl files an OBJ names from its own folder (opened through std::filesystem so folder names in any
// script work, unlike tinyobjloader's own reader).
struct MtlReader : tinyobj::MaterialReader {
  std::string folder;
  bool operator()(const std::string& name, std::vector<tinyobj::material_t>* materials,
                  std::map<std::string, int>* map, std::string* warn, std::string* err) override {
    std::ifstream in(fs::u8path(folder + name));
    if (!in) {
      if (warn) *warn += "material file " + name + " not found\n";
      return false;
    }
    tinyobj::LoadMtl(map, materials, &in, warn, err);
    return true;
  }
};

// Numbers a shape's own copy of the file-wide values it uses (points, normals or UVs) from 0.
struct Compact {
  std::unordered_map<int, int> local;
  std::vector<int> used;  // local -> file-wide
  int at(int global) {
    auto [it, fresh] = local.emplace(global, int(used.size()));
    if (fresh) used.push_back(global);
    return it->second;
  }
};

cv::MaterialDesc describe(const tinyobj::material_t& m, const std::string& folder) {
  cv::MaterialDesc d;
  d.name = m.name;
  d.base_color = GfVec3f(float(m.diffuse[0]), float(m.diffuse[1]), float(m.diffuse[2]));
  d.emissive = GfVec3f(float(m.emission[0]), float(m.emission[1]), float(m.emission[2]));
  d.opacity = float(m.dissolve);
  // Phong shininess to roughness: the usual Blinn-Phong to GGX match, roughness = sqrt(2 / (Ns + 2))
  d.roughness = float(std::sqrt(2.0 / (std::max(0.0, double(m.shininess)) + 2.0)));
  if (m.roughness > 0) d.roughness = float(m.roughness);
  d.metallic = float(m.metallic);
  if (!m.diffuse_texname.empty()) {
    const fs::path t = fs::u8path(m.diffuse_texname);
    d.base_texture = t.is_absolute() ? m.diffuse_texname : folder + m.diffuse_texname;
  }
  return d;
}

}  // namespace

void convert_obj(const std::string& file, const UsdStageRefPtr& out) {
  std::ifstream in(fs::u8path(file));
  if (!in) throw Error("the file couldn't be opened");
  MtlReader mtl;
  mtl.folder = cv::folder_of(file);
  tinyobj::attrib_t attrib;
  std::vector<tinyobj::shape_t> shapes;
  std::vector<tinyobj::material_t> mats;
  std::string warn, err;
  if (!tinyobj::LoadObj(&attrib, &shapes, &mats, &warn, &err, &in, &mtl, /*triangulate*/ false))
    throw Error(err.empty() ? "it isn't a readable OBJ file" : err);

  const SdfPath root = cv::start_layer(out, file, "OBJ", 1.0, false).GetPath();
  cv::Names names;
  std::vector<UsdShadeMaterial> materials;
  for (const tinyobj::material_t& m : mats) materials.push_back(cv::write_material(out, describe(m, mtl.folder), names));

  for (const tinyobj::shape_t& shape : shapes) {
    const tinyobj::mesh_t& sm = shape.mesh;
    if (sm.num_face_vertices.empty()) continue;  // lines or points only
    cv::MeshArrays m;
    Compact points, normals, uvs;
    bool has_n = !attrib.normals.empty(), has_uv = !attrib.texcoords.empty();
    for (const tinyobj::index_t& c : sm.indices) {
      has_n = has_n && c.normal_index >= 0;
      has_uv = has_uv && c.texcoord_index >= 0;
    }
    for (unsigned int n : sm.num_face_vertices) m.counts.push_back(int(n));
    for (const tinyobj::index_t& c : sm.indices) {
      m.indices.push_back(points.at(c.vertex_index));
      if (has_n) m.normal_indices.push_back(normals.at(c.normal_index));
      if (has_uv) m.uv_indices.push_back(uvs.at(c.texcoord_index));
    }
    for (int v : points.used) {
      const auto* p = &attrib.vertices[size_t(v) * 3];
      m.points.push_back(GfVec3f(float(p[0]), float(p[1]), float(p[2])));
    }
    if (has_n) {
      for (int v : normals.used) {
        const auto* p = &attrib.normals[size_t(v) * 3];
        m.normals.push_back(GfVec3f(float(p[0]), float(p[1]), float(p[2])));
      }
      m.normal_interp = UsdGeomTokens->faceVarying;
    }
    if (has_uv) {
      for (int v : uvs.used) {
        const auto* p = &attrib.texcoords[size_t(v) * 2];
        m.uvs.push_back(GfVec2f(float(p[0]), float(p[1])));
      }
      m.uv_interp = UsdGeomTokens->faceVarying;
    }
    UsdGeomMesh mesh = cv::write_mesh(out, names.child(root, shape.name, "Mesh"), m);
    cv::bind_per_face(mesh, sm.material_ids, materials);
  }
}

}  // namespace r3d
