// One item while it is built: its props, and each animatable field as a track — the props value, or
// (when the field is in `anim`) one value per frame of the shot, written as USD time samples.
#pragma once
#include <algorithm>
#include <initializer_list>
#include <set>
#include <string>
#include <vector>

#include <pxr/usd/usd/attribute.h>
#include <pxr/usd/usd/prim.h>

#include "json_read.h"
#include "stage_items.h"

namespace r3d {

template <class V>
V pick(const std::vector<V>& v, size_t i) { return v[std::min(i, v.size() - 1)]; }

inline size_t frames(std::initializer_list<size_t> sizes) { return std::max(sizes); }

class Item {
 public:
  Item(ItemsContext& c, std::string item_id, const PXR_NS::JsObject& p, const PXR_NS::JsObject* anim)
      : ctx(c), id(std::move(item_id)), props(p, id), anim_(anim) {}

  ItemsContext& ctx;
  const std::string id;
  Reader props;

  std::vector<double> nums(const std::string& key) {
    const double v = props.num(key);
    const PXR_NS::JsArray* a = track(key);
    if (!a) return {v};
    std::vector<double> out;
    for (size_t i = 0; i < a->size(); ++i) {
      if (!is_number((*a)[i])) fail(at(key, i), "is " + (*a)[i].GetTypeName(), "a number");
      out.push_back(to_number((*a)[i]));
    }
    return out;
  }

  std::vector<PXR_NS::GfVec3f> colours(const std::string& key) {
    const PXR_NS::GfVec3f v = props.vec3(key);
    const PXR_NS::JsArray* a = track(key);
    if (!a) return {v};
    std::vector<PXR_NS::GfVec3f> out;
    for (size_t i = 0; i < a->size(); ++i) out.push_back(Reader::vec3_of((*a)[i], at(key, i)));
    return out;
  }

  std::vector<bool> flags(const std::string& key) {
    const bool v = props.flag(key);
    const PXR_NS::JsArray* a = track(key);
    if (!a) return {v};
    std::vector<bool> out;
    for (size_t i = 0; i < a->size(); ++i) {
      if (!(*a)[i].IsBool()) fail(at(key, i), "is " + (*a)[i].GetTypeName(), "true or false");
      out.push_back((*a)[i].GetBool());
    }
    return out;
  }

  // n == 1: one value; otherwise one time sample per frame (time code = frame number).
  template <class T, class F>
  void write(const PXR_NS::UsdAttribute& attr, size_t n, F value) const {
    if (n <= 1) {
      attr.Set(T(value(size_t(0))));
      return;
    }
    for (size_t i = 0; i < n; ++i) attr.Set(T(value(i)), PXR_NS::UsdTimeCode(double(ctx.start) + double(i)));
  }

  // Every prop read, every anim entry a field that was read as a track.
  void finish() const {
    props.finish();
    if (!anim_) return;
    for (const auto& [key, value] : *anim_)
      if (!animatable_.count(key))
        fail(id + ".anim." + key, "cannot be animated",
             animatable_.empty() ? "none"
                                 : join(std::vector<std::string>(animatable_.begin(), animatable_.end())));
  }

 private:
  std::string at(const std::string& key, size_t i) const {
    return id + ".anim." + key + "[" + std::to_string(i) + "]";
  }

  const PXR_NS::JsArray* track(const std::string& key) {
    animatable_.insert(key);
    if (!anim_) return nullptr;
    auto it = anim_->find(key);
    if (it == anim_->end()) return nullptr;
    const size_t n = size_t(ctx.end - ctx.start + 1);
    const std::string expected = std::to_string(n) + " values, one per frame " + std::to_string(ctx.start) +
                                 ".." + std::to_string(ctx.end);
    if (!it->second.IsArray()) fail(id + ".anim." + key, "is " + it->second.GetTypeName(), expected);
    if (it->second.GetJsArray().size() != n)
      fail(id + ".anim." + key, std::to_string(it->second.GetJsArray().size()) + " values", expected);
    return &it->second.GetJsArray();
  }

  const PXR_NS::JsObject* anim_;
  std::set<std::string> animatable_;
};

// Shared by every item type (stage_items.cpp).
void author_transform(Item& it, const PXR_NS::UsdPrim& prim);
// lights_cameras.cpp
void build_light(Item& it, const PXR_NS::SdfPath& path);
void build_camera(Item& it, const PXR_NS::SdfPath& path);

}  // namespace r3d
