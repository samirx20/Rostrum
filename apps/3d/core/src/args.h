// A request's arguments, read loudly: a missing, mistyped or unknown argument is an error naming
// "<request>.<argument>" and what is accepted. Nothing is guessed.
#pragma once
#include <pxr/base/js/value.h>

#include <initializer_list>
#include <string>

#include "error.h"

namespace r3d {

class Args {
 public:
  Args(const PXR_NS::JsObject& o, std::string where, std::initializer_list<const char*> accepted)
      : o_(o), where_(std::move(where)) {
    for (const auto& [k, v] : o_) {
      bool ok = false;
      std::string list;
      for (const char* a : accepted) { ok |= k == a; list += (list.empty() ? "" : ", ") + std::string(a); }
      if (!ok) throw Error(where_ + ": unknown argument \"" + k + "\". Accepted: " + list);
    }
  }
  bool has(const char* k) const { return o_.count(k) && !o_.at(k).IsNull(); }
  double num(const char* k) const {
    const auto& v = need(k);
    if (v.IsReal()) return v.GetReal();
    if (v.IsInt()) return v.GetInt();
    if (v.IsUInt64()) return double(v.GetUInt64());
    throw Error(where_ + "." + k + ": needs a number, got " + v.GetTypeName());
  }
  double num(const char* k, double fallback) const { return has(k) ? num(k) : fallback; }
  int whole(const char* k) const {
    double d = num(k);
    if (d != int(d)) throw Error(where_ + "." + k + ": needs a whole number, got " + std::to_string(d));
    return int(d);
  }
  int whole(const char* k, int fallback) const { return has(k) ? whole(k) : fallback; }
  std::string str(const char* k) const {
    const auto& v = need(k);
    if (!v.IsString()) throw Error(where_ + "." + k + ": needs a string, got " + v.GetTypeName());
    return v.GetString();
  }
  std::string str(const char* k, const std::string& fallback) const { return has(k) ? str(k) : fallback; }
  bool flag(const char* k, bool fallback) const {
    if (!has(k)) return fallback;
    const auto& v = need(k);
    if (!v.IsBool()) throw Error(where_ + "." + k + ": needs true or false, got " + v.GetTypeName());
    return v.GetBool();
  }
  const PXR_NS::JsValue& need(const char* k) const {
    auto it = o_.find(k);
    if (it == o_.end() || it->second.IsNull()) throw Error(where_ + "." + k + ": missing");
    return it->second;
  }
  const std::string& where() const { return where_; }

 private:
  const PXR_NS::JsObject& o_;
  std::string where_;
};

}  // namespace r3d
