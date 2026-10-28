// FBX animation and skins (convert_fbx_anim.h).
#include "convert_fbx_anim.h"

#include <pxr/base/gf/matrix4d.h>

#include <algorithm>
#include <cmath>
#include <memory>
#include <set>
#include <string>
#include <utility>

#include "convert_usd.h"
#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::fbx {

namespace {

GfVec3f vec(const ufbx_vec3& v) { return GfVec3f(float(v.x), float(v.y), float(v.z)); }

// ufbx's 3x4 column-vector matrix as USD's row-vector one (as convert_fbx.cpp writes the rest transforms)
GfMatrix4d matrix(const ufbx_matrix& m) {
  return GfMatrix4d(m.m00, m.m10, m.m20, 0.0, m.m01, m.m11, m.m21, 0.0, m.m02, m.m12, m.m22, 0.0, m.m03, m.m13, m.m23,
                    1.0);
}

using ScenePtr = std::unique_ptr<ufbx_scene, void (*)(ufbx_scene*)>;

// The deformed surface as `now` (the scene evaluated at one time, or the loaded one at rest) has it, in the mesh
// node's own space: the points as written at rest (convert_fbx.cpp) and, for a skin, the normals per face corner.
void pose(const ufbx_scene* now, const Deformed& d, UsdTimeCode time) {
  const ufbx_node* node = now->nodes.data[d.node->typed_id];
  const ufbx_mesh* mesh = now->meshes.data[d.mesh->typed_id];
  const ufbx_matrix to_node = ufbx_matrix_invert(&node->node_to_world);
  // ufbx's skinned points are in the world once a skin moved them, else still in the geometry's own space
  const ufbx_matrix& from = mesh->skinned_is_local ? node->geometry_to_node : to_node;
  const size_t n = mesh->vertices.count;
  if (mesh->skinned_position.values.count < n) return;  // nothing evaluated for it
  cv::MeshArrays m;
  m.points.resize(n);
  for (size_t v = 0; v < n; ++v)
    m.points[v] = vec(ufbx_transform_position(&from, mesh->skinned_position.values.data[v]));
  cv::write_mesh_sample(d.out, m, time, false, false, time);

  if (mesh->skin_deformers.count == 0 || !mesh->vertex_normal.exists || !d.out.GetNormalsAttr().HasValue()) return;
  const ufbx_skin_deformer* skin = mesh->skin_deformers.data[0];  // ufbx skins with the first one too
  std::vector<ufbx_matrix> turn(n);  // per point: its normals from the geometry's space to the node's
  for (size_t v = 0; v < n; ++v) {
    const ufbx_matrix skinned = ufbx_get_skin_vertex_matrix(skin, v, &node->geometry_to_world);
    const ufbx_matrix to = ufbx_matrix_mul(&to_node, &skinned);
    turn[v] = ufbx_matrix_for_normals(&to);
  }
  VtVec3fArray normals(d.corners.size());
  for (size_t i = 0; i < d.corners.size(); ++i) {
    const uint32_t c = d.corners[i];
    const ufbx_vec3 rest = mesh->vertex_normal.values.data[mesh->vertex_normal.indices.data[c]];
    const GfVec3f t = vec(ufbx_transform_direction(&turn[mesh->vertex_indices.data[c]], rest));
    normals[i] = t.GetLength() > 0 ? t.GetNormalized() : t;
  }
  d.out.GetNormalsAttr().Set(normals, time);
}

// The first stack's time span in seconds: its own, else its curves' keys.
std::pair<double, double> span_of(const ufbx_anim_stack* stack) {
  if (stack->time_end > stack->time_begin) return {stack->time_begin, stack->time_end};
  double begin = HUGE_VAL, end = -HUGE_VAL;
  for (size_t l = 0; l < stack->layers.count; ++l) {
    const ufbx_anim_layer* layer = stack->layers.data[l];
    for (size_t i = 0; i < layer->anim_values.count; ++i)
      for (const ufbx_anim_curve* c : layer->anim_values.data[i]->curves)
        if (c && c->keyframes.count) begin = std::min(begin, c->min_time), end = std::max(end, c->max_time);
  }
  return begin <= end ? std::pair{begin, end} : std::pair{0.0, 0.0};
}

}  // namespace

void write_animation(const ufbx_scene* scene, const std::map<const ufbx_node*, UsdGeomXform>& xforms,
                     const std::vector<Deformed>& deformed, const UsdStageRefPtr& stage) {
  const ufbx_anim_stack* stack = scene->anim_stacks.count ? scene->anim_stacks.data[0] : nullptr;
  bool animated = false;
  std::set<const ufbx_node*> moved;
  for (size_t l = 0; stack && l < stack->layers.count; ++l) {
    const ufbx_anim_prop_list& props = stack->layers.data[l]->anim_props;
    for (size_t i = 0; i < props.count; ++i) {
      animated = true;
      if (const ufbx_node* n = ufbx_as_node(props.data[i].element)) moved.insert(n);
    }
  }
  if (!animated) {
    for (const Deformed& d : deformed) pose(scene, d, UsdTimeCode::Default());  // posed once, at rest
    return;
  }
  const auto [begin, end] = span_of(stack);
  const int codes = std::max(1, int(std::ceil((end - begin) * kCodesPerSecond - 1e-6)));
  ufbx_evaluate_opts opts = {};
  opts.evaluate_skinning = !deformed.empty();
  for (int code = 0; code <= codes; ++code) {
    ufbx_error error;
    ScenePtr now(ufbx_evaluate_scene(scene, stack->anim, begin + code / kCodesPerSecond, &opts, &error),
                 ufbx_free_scene);
    if (!now)
      throw Error("its animation can't be played: " +
                  (error.description.length ? std::string(error.description.data, error.description.length)
                                            : std::string("ufbx couldn't evaluate it")));
    const UsdTimeCode time(code);
    for (const ufbx_node* n : moved) {
      const auto x = xforms.find(n);
      if (x != xforms.end()) cv::set_transform(x->second, matrix(now->nodes.data[n->typed_id]->node_to_parent), time);
    }
    for (const Deformed& d : deformed) pose(now.get(), d, time);
  }
  cv::set_time_range(stage, 0, codes, kCodesPerSecond);
}

}  // namespace r3d::fbx
