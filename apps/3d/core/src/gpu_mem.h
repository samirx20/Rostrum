// Video memory, so agents see what fits on a 4 GB card: this process's own use (DXGI, sampled while
// rendering, peak kept) and the whole card's (NVML, when the NVIDIA driver is there).
#pragma once
#include <string>

namespace r3d {

struct GpuMem {
  double processMb = -1;  // -1 = unknown
  double gpuUsedMb = -1, gpuTotalMb = -1;
};

class GpuMemWatch {
 public:
  GpuMemWatch();
  ~GpuMemWatch();
  GpuMemWatch(const GpuMemWatch&) = delete;
  GpuMemWatch& operator=(const GpuMemWatch&) = delete;
  GpuMem sample();               // now; also raises the peak
  // the last sample when it is under `ms` old, else a new one: the live view asks once a picture, and the two
  // queries (DXGI, NVML) cost up to a millisecond of a sculpt dab's 16
  GpuMem recent(double ms = 250);
  void reset_peak() { peak_ = 0; }
  double peak_mb() const { return peak_; }
  std::string adapter() const { return adapter_; }

 private:
  void* dxgi_ = nullptr;  // IDXGIAdapter3* of the adapter with the most dedicated memory
  void* nvml_ = nullptr;  // nvml.dll module
  void* nvdev_ = nullptr;
  double peak_ = 0;
  GpuMem last_;
  double lastMs_ = -1e9;
  std::string adapter_;
};

}  // namespace r3d
