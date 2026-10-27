// glTF 2.0 (.gltf and .glb) into a converted layer (convert.h), read with cgltf (third_party/cgltf, MIT).
// glTF is metres and Y up already. Read: the scene's node tree (matrix or TRS), every triangle primitive (indexed
// or not) with POSITION, NORMAL and TEXCOORD_0, and the metallic-roughness materials with their base colour image
// (a file next to the .gltf, or one carried inside the file, written once to the import cache). Skins, morph
// targets and animations are not read: the model comes in its rest pose.
#define _CRT_SECURE_NO_WARNINGS  // cgltf's strncpy / fopen
#define CGLTF_IMPLEMENTATION
#include <cgltf.h>

#include <pxr/usd/usdGeom/tokens.h>

#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>

#include "convert_usd.h"
#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {

const char* reason(cgltf_result r) {
  switch (r) {
    case cgltf_result_data_too_short: return "the file is cut short";
    case cgltf_result_unknown_format: return "it isn't a glTF file";
    case cgltf_result_invalid_json: return "its JSON is broken";
    case cgltf_result_invalid_gltf: return "it isn't valid glTF";
    case cgltf_result_file_not_found: return "a file it uses is missing (a .bin buffer next to it?)";
    case cgltf_result_io_error: return "the file couldn't be read";
    case cgltf_result_out_of_memory: return "out of memory";
    case cgltf_result_legacy_gltf: return "it is glTF 1.0 (only glTF 2.0 is read)";
    default: return "unknown error";
  }
}

// cgltf's file reads through std::filesystem (its own fopen can't open folder names outside the ANSI code page)
cgltf_result read_file(const cgltf_memory_options*, const cgltf_file_options*, const char* path, cgltf_size* size,
                       void** data) {
  std::ifstream in(std::filesystem::u8path(path), std::ios::binary | std::ios::ate);
  if (!in) return cgltf_result_file_not_found;
  const std::streamoff n = in.tellg();
  void* bytes = std::malloc(size_t(n > 0 ? n : 1));
  if (!bytes) return cgltf_result_out_of_memory;
  in.seekg(0);
  if (!in.read(static_cast<char*>(bytes), n)) {
    std::free(bytes);
    return cgltf_result_io_error;
  }
  *size = cgltf_size(n);
  *data = bytes;
  return cgltf_result_success;
}

void release_file(const cgltf_memory_options*, const cgltf_file_options*, void* data) { std::free(data); }

struct Reader {
  std::string file;
  UsdStageRefPtr stage;
  cgltf_options options{};
  cgltf_data* data = nullptr;
  cv::Names names;
  std::map<const cgltf_material*, UsdShadeMaterial> materials;
  std::map<const cgltf_image*, std::string> images;  // image -> file on disk

  // The file an image is in: next to the .gltf, or written out of a buffer / data URI into the cache.
  std::string image_file(const cgltf_image* img) {
    auto found = images.find(img);
    if (found != images.end()) return found->second;
    std::string path;
    const std::string ext = img->mime_type && std::strstr(img->mime_type, "jpeg") ? ".jpg" : ".png";
    const std::string name = "image" + std::to_string(img - data->images) + ext;
    if (img->buffer_view) {
      const uint8_t* bytes = cgltf_buffer_view_data(img->buffer_view);
      if (bytes) path = cv::cache_image(file, name, bytes, img->buffer_view->size);
    } else if (img->uri && std::strncmp(img->uri, "data:", 5) == 0) {
      const char* comma = std::strchr(img->uri, ',');
      if (comma && std::strstr(img->uri, ";base64,")) {
        const char* b64 = comma + 1;
        size_t len = std::strlen(b64), size = len / 4 * 3;
        while (len > 0 && b64[len - 1] == '=') --len, --size;
        void* out = nullptr;
        if (cgltf_load_buffer_base64(&options, size, b64, &out) == cgltf_result_success) {
          const std::string ext2 = std::strstr(img->uri, "image/jpeg") ? ".jpg" : ext;
          path = cv::cache_image(file, "image" + std::to_string(img - data->images) + ext2, out, size);
          std::free(out);
        }
      }
    } else if (img->uri) {
      std::string uri = img->uri;
      uri.resize(cgltf_decode_uri(uri.data()));  // %20 and the like
      path = cv::folder_of(file) + uri;
    }
    images[img] = path;
    return path;
  }

  UsdShadeMaterial material(const cgltf_material* m) {
    auto found = materials.find(m);
    if (found != materials.end()) return found->second;
    cv::MaterialDesc d;
    d.name = m->name ? m->name : "Material";
    if (m->has_pbr_metallic_roughness) {
      const cgltf_pbr_metallic_roughness& pbr = m->pbr_metallic_roughness;
      d.base_color = GfVec3f(pbr.base_color_factor[0], pbr.base_color_factor[1], pbr.base_color_factor[2]);
      d.opacity = pbr.base_color_factor[3];
      d.metallic = pbr.metallic_factor;
      d.roughness = pbr.roughness_factor;
      if (pbr.base_color_texture.texture && pbr.base_color_texture.texture->image)
        d.base_texture = image_file(pbr.base_color_texture.texture->image);
    }
    const float strength = m->has_emissive_strength ? m->emissive_strength.emissive_strength : 1.0f;
    d.emissive = GfVec3f(m->emissive_factor[0], m->emissive_factor[1], m->emissive_factor[2]) * strength;
    if (m->alpha_mode == cgltf_alpha_mode_opaque) d.opacity = 1.0f;
    if (m->alpha_mode == cgltf_alpha_mode_mask) d.opacity_threshold = m->alpha_cutoff > 0 ? m->alpha_cutoff : 0.5f;
    UsdShadeMaterial made = cv::write_material(stage, d, names);
    materials[m] = made;
    return made;
  }

  // One primitive as a Mesh (triangles only; points and lines are left out).
  void primitive(const SdfPath& parent, const std::string& name, const cgltf_primitive& p) {
    if (p.type != cgltf_primitive_type_triangles) return;
    if (p.has_draco_mesh_compression)
      throw Error("its meshes are Draco-compressed, which isn't read yet; export it without mesh compression");
    const cgltf_accessor *pos = nullptr, *nrm = nullptr, *uv = nullptr;
    for (size_t i = 0; i < p.attributes_count; ++i) {
      const cgltf_attribute& a = p.attributes[i];
      if (a.type == cgltf_attribute_type_position) pos = a.data;
      if (a.type == cgltf_attribute_type_normal) nrm = a.data;
      if (a.type == cgltf_attribute_type_texcoord && a.index == 0) uv = a.data;
    }
    if (!pos || pos->count == 0) return;
    cv::MeshArrays m;
    m.points.resize(pos->count);
    cgltf_accessor_unpack_floats(pos, m.points.data()->data(), pos->count * 3);
    if (nrm && nrm->count == pos->count) {
      m.normals.resize(nrm->count);
      cgltf_accessor_unpack_floats(nrm, m.normals.data()->data(), nrm->count * 3);
      m.normal_interp = UsdGeomTokens->vertex;
    }
    if (uv && uv->count == pos->count) {
      m.uvs.resize(uv->count);
      cgltf_accessor_unpack_floats(uv, m.uvs.data()->data(), uv->count * 2);
      for (GfVec2f& t : m.uvs) t[1] = 1.0f - t[1];  // glTF's v runs down the image, USD's up
      m.uv_interp = UsdGeomTokens->vertex;
    }
    const size_t n = p.indices ? p.indices->count : pos->count;
    m.indices.resize(n / 3 * 3);
    for (size_t i = 0; i < m.indices.size(); ++i)
      m.indices[i] = int(p.indices ? cgltf_accessor_read_index(p.indices, i) : i);
    m.counts.assign(m.indices.size() / 3, 3);
    UsdGeomMesh mesh = cv::write_mesh(stage, names.child(parent, name, "Mesh"), m);
    if (p.material) cv::bind(mesh.GetPrim(), material(p.material));
  }

  void node(const SdfPath& parent, const cgltf_node* n) {
    const SdfPath path = names.child(parent, n->name ? n->name : "", "Node");
    UsdGeomXform x = UsdGeomXform::Define(stage, path);
    float m[16];
    cgltf_node_transform_local(n, m);  // column-major with column vectors = USD's row-major with row vectors
    cv::set_transform(x, GfMatrix4d(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11], m[12],
                                    m[13], m[14], m[15]));
    if (const cgltf_mesh* mesh = n->mesh) {
      const std::string base = mesh->name ? mesh->name : "Mesh";
      for (size_t i = 0; i < mesh->primitives_count; ++i)
        primitive(path, mesh->primitives_count == 1 ? base : base + "_" + std::to_string(i), mesh->primitives[i]);
    }
    for (size_t i = 0; i < n->children_count; ++i) node(path, n->children[i]);
  }
};

}  // namespace

void convert_gltf(const std::string& file, const UsdStageRefPtr& out) {
  Reader r;
  r.file = file;
  r.stage = out;
  r.options.file.read = read_file;
  r.options.file.release = release_file;
  cgltf_result res = cgltf_parse_file(&r.options, file.c_str(), &r.data);
  std::unique_ptr<cgltf_data, void (*)(cgltf_data*)> hold(r.data, cgltf_free);
  if (res == cgltf_result_success) res = cgltf_load_buffers(&r.options, r.data, file.c_str());
  if (res != cgltf_result_success)
    throw Error(reason(res));

  const SdfPath root = cv::start_layer(out, file, "glTF", 1.0, true).GetPath();
  const cgltf_scene* scene = r.data->scene ? r.data->scene : r.data->scenes_count ? r.data->scenes : nullptr;
  if (scene) {
    for (size_t i = 0; i < scene->nodes_count; ++i) r.node(root, scene->nodes[i]);
  } else {  // no scene listed: every top node
    for (size_t i = 0; i < r.data->nodes_count; ++i)
      if (!r.data->nodes[i].parent) r.node(root, &r.data->nodes[i]);
  }
}

}  // namespace r3d
