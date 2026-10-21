#include "shm.h"

#include <windows.h>

#include <atomic>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

Shm::Shm(size_t slot_bytes) : slot_(slot_bytes) {
  static std::atomic<unsigned> n{0};
  name_ = "Local\\rostrum3d-" + std::to_string(GetCurrentProcessId()) + "-" + std::to_string(n++);
  const unsigned long long size = slot_bytes * 2;
  handle_ = CreateFileMappingA(INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, DWORD(size >> 32), DWORD(size),
                               name_.c_str());
  if (!handle_)
    throw Error("view: shared memory " + name_ + ": CreateFileMapping failed, error " + std::to_string(GetLastError()));
  if (GetLastError() == ERROR_ALREADY_EXISTS) {
    CloseHandle(handle_);
    throw Error("view: shared memory " + name_ + " already exists");
  }
  view_ = static_cast<uint8_t*>(MapViewOfFile(handle_, FILE_MAP_ALL_ACCESS, 0, 0, size));
  if (!view_) {
    const auto e = GetLastError();
    CloseHandle(handle_);
    throw Error("view: shared memory " + name_ + ": MapViewOfFile failed, error " + std::to_string(e));
  }
}

Shm::~Shm() {
  if (view_) UnmapViewOfFile(view_);
  if (handle_) CloseHandle(handle_);
}

uint8_t* Shm::next(int width, int height, JsObject* info) {
  ++seq_;
  const size_t offset = (seq_ % 2) * slot_;
  *info = JsObject{{"name", JsValue(name_)}, {"size", JsValue(uint64_t(slot_ * 2))}, {"offset", JsValue(uint64_t(offset))},
                   {"bytes", JsValue(uint64_t(slot_))}, {"stride", JsValue(width * 4)}, {"format", JsValue(std::string("rgba8"))},
                   {"seq", JsValue(seq_)}, {"width", JsValue(width)}, {"height", JsValue(height)}};
  return view_ + offset;
}

}  // namespace r3d
