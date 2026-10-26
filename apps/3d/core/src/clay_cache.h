// Clay: the cache writer. Saves a copy of a clay's grid as its cache .vdb on a thread of its own, so a stroke's end
// never waits for the disk. Per clay only the newest request is kept; once a newer cache is written, the one this
// writer wrote before for that clay is deleted (with its folder when empty), so the cache root holds one file per
// clay, not one per stroke. On destruction the waiting requests are written first.
#pragma once
#include <condition_variable>
#include <map>
#include <mutex>
#include <string>
#include <thread>

#include <openvdb/openvdb.h>

namespace r3d::clay {

class CacheWriter {
 public:
  CacheWriter();
  ~CacheWriter();
  void request(const std::string& item, openvdb::FloatGrid::Ptr grid, const std::string& path);

 private:
  struct Job {
    openvdb::FloatGrid::Ptr grid;
    std::string path;
  };
  void loop();
  std::mutex m_;
  std::condition_variable cv_;
  std::map<std::string, Job> jobs_;            // item -> newest request
  std::map<std::string, std::string> written_; // item -> the cache file this writer wrote last
  bool quit_ = false;
  std::thread thread_;  // last: started once the rest exists
};

}  // namespace r3d::clay
