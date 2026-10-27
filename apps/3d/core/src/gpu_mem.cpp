#include "gpu_mem.h"

#include <chrono>

#include <windows.h>
#include <dxgi1_4.h>

namespace r3d {

namespace {
struct NvmlMemory { unsigned long long total, free, used; };
using NvmlInit = int (*)();
using NvmlHandle = int (*)(unsigned, void**);
using NvmlMem = int (*)(void*, NvmlMemory*);
}  // namespace

GpuMemWatch::GpuMemWatch() {
  IDXGIFactory4* f = nullptr;
  if (SUCCEEDED(CreateDXGIFactory1(__uuidof(IDXGIFactory4), reinterpret_cast<void**>(&f)))) {
    SIZE_T best = 0;
    IDXGIAdapter1* a = nullptr;
    for (UINT i = 0; f->EnumAdapters1(i, &a) != DXGI_ERROR_NOT_FOUND; ++i) {
      DXGI_ADAPTER_DESC1 d{};
      a->GetDesc1(&d);
      IDXGIAdapter3* a3 = nullptr;
      if (d.DedicatedVideoMemory > best &&
          SUCCEEDED(a->QueryInterface(__uuidof(IDXGIAdapter3), reinterpret_cast<void**>(&a3)))) {
        if (dxgi_) static_cast<IDXGIAdapter3*>(dxgi_)->Release();
        dxgi_ = a3;
        best = d.DedicatedVideoMemory;
        char name[128];
        WideCharToMultiByte(CP_UTF8, 0, d.Description, -1, name, sizeof(name), nullptr, nullptr);
        adapter_ = name;
      }
      a->Release();
    }
    f->Release();
  }
  if (HMODULE m = LoadLibraryA("nvml.dll")) {
    auto init = reinterpret_cast<NvmlInit>(GetProcAddress(m, "nvmlInit_v2"));
    auto handle = reinterpret_cast<NvmlHandle>(GetProcAddress(m, "nvmlDeviceGetHandleByIndex_v2"));
    void* dev = nullptr;
    if (init && handle && init() == 0 && handle(0, &dev) == 0) {
      nvml_ = m;
      nvdev_ = dev;
    } else {
      FreeLibrary(m);
    }
  }
}

GpuMemWatch::~GpuMemWatch() {
  if (dxgi_) static_cast<IDXGIAdapter3*>(dxgi_)->Release();
  if (nvml_) FreeLibrary(static_cast<HMODULE>(nvml_));
}

GpuMem GpuMemWatch::sample() {
  GpuMem m;
  if (dxgi_) {
    DXGI_QUERY_VIDEO_MEMORY_INFO info{};
    if (SUCCEEDED(static_cast<IDXGIAdapter3*>(dxgi_)->QueryVideoMemoryInfo(
            0, DXGI_MEMORY_SEGMENT_GROUP_LOCAL, &info)))
      m.processMb = double(info.CurrentUsage) / (1 << 20);
  }
  if (nvml_) {
    auto mem = reinterpret_cast<NvmlMem>(GetProcAddress(static_cast<HMODULE>(nvml_), "nvmlDeviceGetMemoryInfo"));
    NvmlMemory nm{};
    if (mem && mem(nvdev_, &nm) == 0) {
      m.gpuUsedMb = double(nm.used) / (1 << 20);
      m.gpuTotalMb = double(nm.total) / (1 << 20);
    }
  }
  if (m.processMb > peak_) peak_ = m.processMb;
  last_ = m;
  lastMs_ = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
  return m;
}

GpuMem GpuMemWatch::recent(double ms) {
  const double now = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
  return now - lastMs_ < ms ? last_ : sample();
}

}  // namespace r3d
