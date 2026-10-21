// Strict reading of one JSON object of the scene (ENGINE_CONTRACT.md § 2). Every field is present and
// nothing is guessed: a missing field, a wrong type or a field nobody read is an r3d::Error
// "<where>.<field>: <problem>. Accepted: …". Ranges live in rostrum3d/fields.py (the one table); the core
// checks only what would make broken geometry or a broken file.
#pragma once
#include <cmath>
#include <initializer_list>
#include <set>
#include <string>
#include <vector>

#include <pxr/base/gf/vec3f.h>
#include <pxr/base/js/value.h>

#include "error.h"

namespace r3d {

[[noreturn]] inline void fail(const std::string& where, const std::string& problem,
                              const std::string& accepted) {
  throw Error(where + ": " + problem + ". Accepted: " + accepted);
}

inline bool is_number(const PXR_NS::JsValue& v) { return v.IsInt() || v.IsUInt64() || v.IsReal(); }

inline double to_number(const PXR_NS::JsValue& v) {
  if (v.IsReal()) return v.GetReal();
  if (v.IsUInt64()) return static_cast<double>(v.GetUInt64());
  return static_cast<double>(v.GetInt64());
}

inline std::string join(const std::vector<std::string>& words) {
  std::string out;
  for (const auto& w : words) out += (out.empty() ? "" : ", ") + w;
  return out;
}

// Reads one object and remembers which fields were read; finish() rejects the rest.
class Reader {
 public:
  Reader(const PXR_NS::JsObject& obj, std::string where) : obj_(obj), where_(std::move(where)) {}

  std::string at(const std::string& key) const { return where_ + "." + key; }
  const std::string& where() const { return where_; }
  bool has(const std::string& key) const { return obj_.count(key) != 0; }

  const PXR_NS::JsValue& get(const std::string& key, const char* expected) {
    auto it = obj_.find(key);
    if (it == obj_.end()) fail(at(key), "missing", expected);
    used_.insert(key);
    return it->second;
  }

  double num(const std::string& key) {
    const auto& v = get(key, "a number");
    if (!is_number(v)) fail(at(key), "is " + v.GetTypeName(), "a number");
    const double d = to_number(v);
    if (!std::isfinite(d)) fail(at(key), "is not finite", "a finite number");
    return d;
  }

  double num_min(const std::string& key, double lo, bool inclusive) {
    const double d = num(key);
    if (inclusive ? d < lo : d <= lo)
      fail(at(key), std::to_string(d) + " is too small",
           std::string("a number ") + (inclusive ? ">= " : "> ") + std::to_string(lo));
    return d;
  }

  int count(const std::string& key, int lo, int hi) {
    const double d = num(key);
    if (d != std::floor(d) || d < lo || d > hi)
      fail(at(key), std::to_string(d) + " is out of range",
           "a whole number " + std::to_string(lo) + " .. " + std::to_string(hi));
    return static_cast<int>(d);
  }

  bool flag(const std::string& key) {
    const auto& v = get(key, "true or false");
    if (!v.IsBool()) fail(at(key), "is " + v.GetTypeName(), "true or false");
    return v.GetBool();
  }

  std::string str(const std::string& key) {
    const auto& v = get(key, "a string");
    if (!v.IsString()) fail(at(key), "is " + v.GetTypeName(), "a string");
    return v.GetString();
  }

  std::string one_of(const std::string& key, const std::vector<std::string>& accepted) {
    std::string s = str(key);
    for (const auto& a : accepted)
      if (s == a) return s;
    fail(at(key), "\"" + s + "\" is unknown", join(accepted));
  }

  PXR_NS::GfVec3f vec3(const std::string& key) { return vec3_of(get(key, "[x, y, z]"), at(key)); }

  const PXR_NS::JsArray& list(const std::string& key) {
    const auto& v = get(key, "a list");
    if (!v.IsArray()) fail(at(key), "is " + v.GetTypeName(), "a list");
    return v.GetJsArray();
  }

  const PXR_NS::JsObject& object(const std::string& key) {
    const auto& v = get(key, "an object");
    if (!v.IsObject()) fail(at(key), "is " + v.GetTypeName(), "an object");
    return v.GetJsObject();
  }

  // Fields of this item type that the chosen shape / kind doesn't use: present (every field is), not read.
  void known(std::initializer_list<const char*> keys) {
    for (const char* k : keys)
      if (obj_.count(k)) used_.insert(k);
  }

  // Every field of the object must have been read: anything else is unknown.
  void finish() const {
    std::vector<std::string> accepted(used_.begin(), used_.end());
    for (const auto& [key, value] : obj_)
      if (!used_.count(key)) fail(at(key), "unknown field", accepted.empty() ? "none" : join(accepted));
  }

  static PXR_NS::GfVec3f vec3_of(const PXR_NS::JsValue& v, const std::string& where) {
    if (!v.IsArray() || v.GetJsArray().size() != 3) fail(where, "is not a list of 3", "[x, y, z] numbers");
    const auto& a = v.GetJsArray();
    PXR_NS::GfVec3f out;
    for (int i = 0; i < 3; ++i) {
      if (!is_number(a[i])) fail(where, "holds " + a[i].GetTypeName(), "[x, y, z] numbers");
      out[i] = static_cast<float>(to_number(a[i]));
    }
    return out;
  }

 private:
  const PXR_NS::JsObject& obj_;
  std::string where_;
  std::set<std::string> used_;
};

}  // namespace r3d
