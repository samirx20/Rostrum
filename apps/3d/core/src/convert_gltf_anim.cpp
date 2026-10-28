// glTF animation and skins (convert_gltf_anim.h).
#include "convert_gltf_anim.h"

#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/quatf.h>

#include <algorithm>
#include <cmath>
#include <set>
#include <string>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::gltf {

namespace {

// cgltf's column-major matrix with column vectors is USD's row-major matrix with row vectors
GfMatrix4d mat(const float m[16]) {
  return GfMatrix4d(m[0], m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9], m[10], m[11], m[12], m[13], m[14],
                    m[15]);
}
GfMatrix4d local_of(const cgltf_node* n) {
  float m[16];
  cgltf_node_transform_local(n, m);
  return mat(m);
}
GfMatrix4d world_of(const cgltf_node* n) {
  float m[16];
  cgltf_node_transform_world(n, m);
  return mat(m);
}

std::vector<float> floats(const cgltf_accessor* a) {
  std::vector<float> v(a ? cgltf_accessor_unpack_floats(a, nullptr, 0) : 0);
  if (!v.empty()) cgltf_accessor_unpack_floats(a, v.data(), v.size());
  return v;
}

struct Channel {
  cgltf_node* node = nullptr;
  cgltf_animation_path_type path{};
  cgltf_interpolation_type interp{};
  std::vector<float> times, values;
  int width = 3;  // 4 for a rotation (x y z w)

  const float* key(size_t k) const {  // a key's value (a cubic key is in-tangent, value, out-tangent)
    return &values[(interp == cgltf_interpolation_type_cubic_spline ? 3 * k + 1 : k) * size_t(width)];
  }
  void sample(float t, float* out) const {
    const size_t last = times.size() - 1;
    const auto copy = [&](const float* v) { std::copy(v, v + width, out); };
    if (t <= times.front()) return copy(key(0));
    if (t >= times.back()) return copy(key(last));
    const size_t k = size_t(std::upper_bound(times.begin(), times.end(), t) - times.begin()) - 1;
    const float dt = times[k + 1] - times[k], s = dt > 0 ? (t - times[k]) / dt : 0.0f;
    const float *a = key(k), *b = key(k + 1);
    if (interp == cgltf_interpolation_type_step) return copy(a);
    if (interp == cgltf_interpolation_type_cubic_spline) {
      const float* out_t = a + width;      // key k's out-tangent
      const float* in_t = b - width;       // key k+1's in-tangent
      const float s2 = s * s, s3 = s2 * s;
      for (int i = 0; i < width; ++i)
        out[i] = (2 * s3 - 3 * s2 + 1) * a[i] + (s3 - 2 * s2 + s) * dt * out_t[i] + (-2 * s3 + 3 * s2) * b[i] +
                 (s3 - s2) * dt * in_t[i];
    } else if (width == 4) {
      const GfQuatf q = GfSlerp(double(s), GfQuatf(a[3], a[0], a[1], a[2]), GfQuatf(b[3], b[0], b[1], b[2]));
      out[0] = q.GetImaginary()[0], out[1] = q.GetImaginary()[1], out[2] = q.GetImaginary()[2], out[3] = q.GetReal();
      return;
    } else {
      for (int i = 0; i < width; ++i) out[i] = a[i] + (b[i] - a[i]) * s;
    }
    if (width == 4) {  // a cubic rotation, kept a unit quaternion
      const float l = std::sqrt(out[0] * out[0] + out[1] * out[1] + out[2] * out[2] + out[3] * out[3]);
      for (int i = 0; l > 0 && i < 4; ++i) out[i] /= l;
    }
  }
  void apply(float t) const {
    float v[4];
    sample(t, v);
    if (path == cgltf_animation_path_type_translation) std::copy(v, v + 3, node->translation), node->has_translation = 1;
    if (path == cgltf_animation_path_type_rotation) std::copy(v, v + 4, node->rotation), node->has_rotation = 1;
    if (path == cgltf_animation_path_type_scale) std::copy(v, v + 3, node->scale), node->has_scale = 1;
  }
};

std::vector<Channel> channels_of(const cgltf_data* data) {
  std::vector<Channel> out;
  if (!data->animations_count) return out;
  const cgltf_animation& anim = data->animations[0];
  for (size_t i = 0; i < anim.channels_count; ++i) {
    const cgltf_animation_channel& ch = anim.channels[i];
    const cgltf_animation_path_type p = ch.target_path;
    if (!ch.target_node || !ch.sampler || ch.target_node->has_matrix ||
        (p != cgltf_animation_path_type_translation && p != cgltf_animation_path_type_rotation &&
         p != cgltf_animation_path_type_scale))
      continue;  // morph weights are not read; a node given as a matrix can't be animated (glTF)
    Channel c;
    c.node = ch.target_node;
    c.path = p;
    c.interp = ch.sampler->interpolation;
    c.width = p == cgltf_animation_path_type_rotation ? 4 : 3;
    c.times = floats(ch.sampler->input);
    c.values = floats(ch.sampler->output);
    const size_t per = c.interp == cgltf_interpolation_type_cubic_spline ? 3 : 1;
    if (c.times.empty() || c.values.size() < c.times.size() * per * size_t(c.width)) continue;
    out.push_back(std::move(c));
  }
  return out;
}

// One skinned primitive's weights and bind matrices, read once.
struct Skin {
  const Skinned* s = nullptr;
  std::vector<unsigned> joints;  // 4 per point
  std::vector<float> weights;    // 4 per point
  std::vector<GfMatrix4d> inverse_bind;
};

Skin read_skin(const Skinned& s) {
  Skin k;
  k.s = &s;
  const cgltf_skin* skin = s.node->skin;
  const cgltf_accessor *j = nullptr, *w = nullptr;
  for (size_t i = 0; i < s.prim->attributes_count; ++i) {
    const cgltf_attribute& a = s.prim->attributes[i];
    if (a.type == cgltf_attribute_type_joints && a.index == 0) j = a.data;
    if (a.type == cgltf_attribute_type_weights && a.index == 0) w = a.data;
  }
  const size_t n = s.rest.points.size();
  if (!j || !w || j->count != n || w->count != n)
    throw Error("a skinned mesh has no JOINTS_0 / WEIGHTS_0 for each of its points");
  k.joints.resize(n * 4);
  for (size_t i = 0; i < n; ++i)
    if (!cgltf_accessor_read_uint(j, i, &k.joints[i * 4], 4)) throw Error("a skinned mesh's JOINTS_0 can't be read");
  k.weights = floats(w);
  if (k.weights.size() != n * 4) throw Error("a skinned mesh's WEIGHTS_0 isn't 4 numbers per point");
  for (unsigned v : k.joints)
    if (v >= skin->joints_count) throw Error("a skinned mesh names a joint its skin doesn't have");
  const std::vector<float> ibm = floats(skin->inverse_bind_matrices);
  for (size_t i = 0; i < skin->joints_count; ++i)
    k.inverse_bind.push_back(ibm.size() >= (i + 1) * 16 ? mat(&ibm[i * 16]) : GfMatrix4d(1.0));
  return k;
}

// The skinned points and normals as the joints stand now, in the mesh node's own space.
void pose(const Skin& k, UsdTimeCode time) {
  const cgltf_skin* skin = k.s->node->skin;
  std::vector<GfMatrix4d> joint(skin->joints_count);
  for (size_t i = 0; i < joint.size(); ++i) joint[i] = k.inverse_bind[i] * world_of(skin->joints[i]);
  const GfMatrix4d to_local = world_of(k.s->node).GetInverse();
  cv::MeshArrays m = k.s->rest;
  const bool normals = !m.normals.empty();
  for (size_t v = 0; v < m.points.size(); ++v) {
    GfMatrix4d sum(0.0);
    double total = 0;
    for (int i = 0; i < 4; ++i) {
      const float w = k.weights[v * 4 + i];
      if (w <= 0) continue;
      sum += joint[k.joints[v * 4 + i]] * double(w);
      total += w;
    }
    const GfMatrix4d mv = total > 0 ? sum * (1.0 / total) * to_local : GfMatrix4d(1.0);  // no joint: as it was
    m.points[v] = GfVec3f(mv.Transform(GfVec3d(k.s->rest.points[v])));
    if (normals) m.normals[v] = GfVec3f(mv.TransformDir(GfVec3d(k.s->rest.normals[v])).GetNormalized());
  }
  cv::write_mesh_sample(k.s->mesh, m, time, false, false, time);
  if (normals) k.s->mesh.GetNormalsAttr().Set(m.normals, time);
}

}  // namespace

void write_animation(cgltf_data* data, const std::map<const cgltf_node*, UsdGeomXform>& xforms,
                     const std::vector<Skinned>& skinned, const UsdStageRefPtr& stage) {
  const std::vector<Channel> chans = channels_of(data);
  std::vector<Skin> skins;
  for (const Skinned& s : skinned) skins.push_back(read_skin(s));
  if (chans.empty()) {
    for (const Skin& k : skins) pose(k, UsdTimeCode::Default());  // skinned once, at rest
    return;
  }
  float end = 0;
  std::set<cgltf_node*> moved;
  for (const Channel& c : chans) end = std::max(end, c.times.back()), moved.insert(c.node);
  const int codes = std::max(1, int(std::ceil(double(end) * kCodesPerSecond - 1e-6)));
  for (int code = 0; code <= codes; ++code) {
    const float t = float(code / kCodesPerSecond);
    for (const Channel& c : chans) c.apply(t);
    const UsdTimeCode time(code);
    for (cgltf_node* n : moved) {
      const auto x = xforms.find(n);
      if (x != xforms.end()) cv::set_transform(x->second, local_of(n), time);
    }
    for (const Skin& k : skins) pose(k, time);
  }
  cv::set_time_range(stage, 0, codes, kCodesPerSecond);
}

}  // namespace r3d::gltf
