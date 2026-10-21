// The one error type of the core: a plain message naming the request, item and field. Thrown anywhere,
// caught once per request in serve.cpp and sent back as {"ok": false, "error": "..."}.
#pragma once
#include <stdexcept>
#include <string>

namespace r3d {
struct Error : std::runtime_error {
  using std::runtime_error::runtime_error;
};
}  // namespace r3d
