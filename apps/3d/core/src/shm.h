// Live viewport pictures in shared memory (the `view` request; ENGINE_CONTRACT.md § 4), the same layout as
// Rostrum2D's `pixels` (apps/2d/engine/render/src/shm.rs): a named block with two slots of one picture each, used
// in turn, so the screen can still read picture n while picture n + 1 is drawn. The reply names the block, the
// slot's offset and the picture's sequence number.
// Windows: a page-file-backed named file mapping `Local\rostrum3d-<pid>-<n>`; a reader opens it by name
// (Python: mmap.mmap(-1, size, tagname=name)). Mac (to do): shm_open + mmap with the same layout.
#pragma once
#include <pxr/base/js/value.h>

#include <cstddef>
#include <cstdint>
#include <string>

namespace r3d {

class Shm {
 public:
  explicit Shm(size_t slot_bytes);  // throws r3d::Error
  ~Shm();
  Shm(const Shm&) = delete;
  Shm& operator=(const Shm&) = delete;
  size_t slot_bytes() const { return slot_; }
  // the next slot to write (slot_bytes long) and the reply's "shm" object describing it
  uint8_t* next(int width, int height, PXR_NS::JsObject* info);

 private:
  void* handle_ = nullptr;
  uint8_t* view_ = nullptr;
  size_t slot_;
  uint64_t seq_ = 0;
  std::string name_;
};

}  // namespace r3d
