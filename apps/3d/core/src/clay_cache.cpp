// Clay: the cache writer (clay_cache.h).
#include "clay_cache.h"

#include <cstdio>
#include <filesystem>

#include "clay_volume.h"

namespace r3d::clay {

CacheWriter::CacheWriter() : thread_([this] { loop(); }) {}

CacheWriter::~CacheWriter() {
  {
    std::lock_guard<std::mutex> lock(m_);
    quit_ = true;
  }
  cv_.notify_all();
  thread_.join();
}

void CacheWriter::request(const std::string& item, openvdb::FloatGrid::Ptr grid, const std::string& path,
                          openvdb::FloatGrid::Ptr mask) {
  {
    std::lock_guard<std::mutex> lock(m_);
    jobs_[item] = Job{std::move(grid), path, std::move(mask)};
  }
  cv_.notify_all();
}

void CacheWriter::loop() {
  namespace fs = std::filesystem;
  for (;;) {
    std::string item;
    Job job;
    {
      std::unique_lock<std::mutex> lock(m_);
      cv_.wait(lock, [&] { return quit_ || !jobs_.empty(); });
      if (jobs_.empty()) return;  // quit, and everything asked for is written
      item = jobs_.begin()->first;
      job = std::move(jobs_.begin()->second);
      jobs_.erase(jobs_.begin());
    }
    std::string error;
    if (!Volume::save(job.grid, job.path, &error, job.mask)) {
      std::fprintf(stderr, "clay: cache %s not written: %s\n", job.path.c_str(), error.c_str());
      continue;
    }
    job.grid.reset();
    job.mask.reset();
    std::string old;
    {
      std::lock_guard<std::mutex> lock(m_);
      old = written_[item];
      written_[item] = job.path;
      for (const auto& [other, path] : written_)
        if (other != item && path == old) old.clear();  // another clay with the same steps uses it
    }
    if (!old.empty() && old != job.path) {
      std::error_code ec;
      fs::remove(fs::u8path(old), ec);
      fs::remove(fs::u8path(old).parent_path(), ec);  // only when empty
    }
  }
}

}  // namespace r3d::clay
