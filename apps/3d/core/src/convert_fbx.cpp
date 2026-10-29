// Autodesk FBX (binary and ASCII) into a converted layer (convert.h), read with ufbx (third_party/ufbx, MIT).
// ufbx turns the scene upright (right-handed, Y up) through the nodes' transforms; units are left as the file has
// them (metersPerUnit = the file's unit). Read: the node tree with local transforms, every mesh (polygons kept,
// normals, UV set 0, per-face materials as GeomSubsets), and the materials (ufbx's PBR view of them, which covers
// the classic Lambert / Phong ones: colour and its image, metalness, roughness, emission, opacity). The first
// animation stack, the skins and the blend shapes play as time samples (convert_fbx_anim.h).
#include <ufbx.h>

#include <pxr/usd/usdGeom/tokens.h>

#include <algorithm>
#include <filesystem>
#include <map>
#include <memory>

#include "convert_fbx_anim.h"
#include "convert_usd.h"
#include "error.h"
#include "udim.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace fs = std::filesystem;

namespace r3d {

namespace {

std::string str(const ufbx_string& s) { return std::string(s.data, s.length); }
GfVec3f vec(const ufbx_vec3& v) { return GfVec3f(float(v.x), float(v.y), float(v.z)); }

// ufbx's 3x4 column-vector matrix as USD's row-vector one
GfMatrix4d matrix(const ufbx_matrix& m) {
  return GfMatrix4d(m.m00, m.m10, m.m20, 0.0, m.m01, m.m11, m.m21, 0.0, m.m02, m.m12, m.m22, 0.0, m.m03, m.m13, m.m23,
                    1.0);
}

struct Reader {
  std::string file;
  UsdStageRefPtr stage;
  cv::Names names;
  std::map<const ufbx_material*, UsdShadeMaterial> materials;
  std::map<const ufbx_node*, UsdGeomXform> xforms;  // every node's Xform (animation writes into them)
  std::vector<fbx::Deformed> deformed;              // skinned / blend-shaped meshes, posed by fbx::write_animation

  // The image file of a texture: one carried inside the FBX goes to the import cache; else the first of its paths
  // that exists (next to the file, as written, by name next to the file).
  std::string image_file(const ufbx_texture* t) {
    if (t->type != UFBX_TEXTURE_FILE && t->file_textures.count > 0) t = t->file_textures.data[0];
    if (t->content.size > 0) {
      std::string name = fs::u8path(str(t->relative_filename)).filename().u8string();
      if (name.empty()) name = "texture" + std::to_string(t->typed_id) + ".png";
      return cv::cache_image(file, std::to_string(t->typed_id) + "_" + name, t->content.data, t->content.size);
    }
    std::error_code ec;
    const std::string by_name = cv::folder_of(file) + fs::u8path(str(t->relative_filename)).filename().u8string();
    for (const std::string& p : {str(t->filename), str(t->absolute_filename), by_name})
      if (!p.empty() && (fs::exists(fs::u8path(p), ec) || !udim::tiles(p).empty())) return p;
    return str(t->filename);  // missing: kept, so the texture shows as missing rather than vanishing
  }

  UsdShadeMaterial material(const ufbx_material* m) {
    auto found = materials.find(m);
    if (found != materials.end()) return found->second;
    const ufbx_material_pbr_maps& pbr = m->pbr;
    cv::MaterialDesc d;
    d.name = str(m->name);
    const float factor = pbr.base_factor.has_value ? float(pbr.base_factor.value_real) : 1.0f;
    d.base_color = vec(pbr.base_color.value_vec3) * factor;
    const ufbx_texture* tex = pbr.base_color.texture ? pbr.base_color.texture : m->fbx.diffuse_color.texture;
    if (tex) d.base_texture = image_file(tex);
    d.metallic = std::clamp(float(pbr.metalness.value_real), 0.0f, 1.0f);
    d.roughness = std::clamp(float(pbr.roughness.value_real), 0.0f, 1.0f);
    d.emissive = vec(pbr.emission_color.value_vec3) * float(pbr.emission_factor.value_real);
    d.opacity = pbr.opacity.has_value ? std::clamp(float(pbr.opacity.value_real), 0.0f, 1.0f) : 1.0f;
    UsdShadeMaterial made = cv::write_material(stage, d, names);
    materials[m] = made;
    return made;
  }

  void mesh(const SdfPath& parent, const ufbx_node* node, const ufbx_mesh* src) {
    cv::MeshArrays m;
    std::vector<int> face_material;
    const ufbx_material_list& mats = node->materials.count == src->materials.count ? node->materials : src->materials;
    const bool geo = node->has_geometry_transform;
    const ufbx_matrix normal_m = ufbx_matrix_for_normals(&node->geometry_to_node);
    m.points.reserve(src->vertices.count);
    for (size_t i = 0; i < src->vertices.count; ++i)
      m.points.push_back(vec(geo ? ufbx_transform_position(&node->geometry_to_node, src->vertices.data[i])
                                 : src->vertices.data[i]));
    const bool has_n = src->vertex_normal.exists, has_uv = src->vertex_uv.exists;
    std::vector<uint32_t> corners;  // the face corners written, for the animation's normals
    for (size_t f = 0; f < src->faces.count; ++f) {
      const ufbx_face face = src->faces.data[f];
      if (face.num_indices < 3) continue;  // a loose edge or point
      m.counts.push_back(int(face.num_indices));
      face_material.push_back(src->face_material.count ? int(src->face_material.data[f]) : 0);
      for (uint32_t k = 0; k < face.num_indices; ++k) {
        const uint32_t c = face.index_begin + k;
        corners.push_back(c);
        m.indices.push_back(int(src->vertex_indices.data[c]));
        if (has_n) m.normal_indices.push_back(int(src->vertex_normal.indices.data[c]));
        if (has_uv) m.uv_indices.push_back(int(src->vertex_uv.indices.data[c]));
      }
    }
    if (m.counts.empty()) return;
    if (has_n) {
      for (size_t i = 0; i < src->vertex_normal.values.count; ++i) {
        const ufbx_vec3 n = src->vertex_normal.values.data[i];
        GfVec3f v = vec(geo ? ufbx_transform_direction(&normal_m, n) : n);
        m.normals.push_back(v.GetLength() > 0 ? v.GetNormalized() : v);
      }
      m.normal_interp = UsdGeomTokens->faceVarying;
    }
    if (has_uv) {
      for (size_t i = 0; i < src->vertex_uv.values.count; ++i)
        m.uvs.push_back(GfVec2f(float(src->vertex_uv.values.data[i].x), float(src->vertex_uv.values.data[i].y)));
      m.uv_interp = UsdGeomTokens->faceVarying;
    }
    const std::string name = src->name.length ? str(src->name) : str(node->name);
    UsdGeomMesh out = cv::write_mesh(stage, names.child(parent, name, "Mesh"), m);
    std::vector<UsdShadeMaterial> list;
    for (size_t i = 0; i < mats.count; ++i) list.push_back(material(mats.data[i]));
    cv::bind_per_face(out, face_material, list);
    if (src->skin_deformers.count || src->blend_deformers.count)
      deformed.push_back({node, src, out, std::move(corners)});
  }

  void node(const SdfPath& parent, const ufbx_node* n) {
    const SdfPath path = names.child(parent, str(n->name), "Node");
    UsdGeomXform x = UsdGeomXform::Define(stage, path);
    xforms[n] = x;
    cv::set_transform(x, matrix(n->node_to_parent));
    if (n->mesh) mesh(path, n, n->mesh);
    for (size_t i = 0; i < n->children.count; ++i) node(path, n->children.data[i]);
  }
};

}  // namespace

void convert_fbx(const std::string& file, const UsdStageRefPtr& out) {
  ufbx_load_opts opts = {};
  opts.target_axes = ufbx_axes_right_handed_y_up;
  opts.space_conversion = UFBX_SPACE_CONVERSION_ADJUST_TRANSFORMS;  // upright through the transforms; no rescale
  opts.generate_missing_normals = true;
  opts.evaluate_skinning = true;  // the rest pose's skins and shapes (convert_fbx_anim.cpp)
  ufbx_error error;
  std::unique_ptr<ufbx_scene, void (*)(ufbx_scene*)> scene(ufbx_load_file(file.c_str(), &opts, &error),
                                                           ufbx_free_scene);
  if (!scene) throw Error(error.description.length ? str(error.description) : "it isn't a readable FBX file");

  const double unit = scene->settings.unit_meters > 0 ? double(scene->settings.unit_meters) : 0.01;
  const SdfPath root = cv::start_layer(out, file, "FBX", unit, true).GetPath();
  Reader r;
  r.file = file;
  r.stage = out;
  const ufbx_node* top = scene->root_node;
  for (size_t i = 0; i < top->children.count; ++i) r.node(root, top->children.data[i]);
  fbx::write_animation(scene.get(), r.xforms, r.deformed, out);
}

}  // namespace r3d
