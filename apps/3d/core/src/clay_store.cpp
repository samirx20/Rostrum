// Clay: the store (clay_store.h).
#include "clay_store.h"

#include <tbb/parallel_for.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <deque>
#include <filesystem>
#include <map>

#include "clay_cache.h"
#include "clay_replay.h"
#include "clay_stroke.h"
#include "clay_usd.h"
#include "clay_volume.h"
#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::clay {

namespace {
constexpr size_t kUndoUnits = 64;                  // steps whose replaced chunks are kept
constexpr size_t kUndoBytes = size_t(512) << 20;   // ... at most this much per clay (a big piece's record is big)
constexpr size_t kCacheOverUndo = 8;               // more steps than this to apply: the cache file is quicker
constexpr size_t kReplayTogether = 8;              // at least this many strokes in a row: replayed in parallel

double ms_since(std::chrono::steady_clock::time_point t0) {
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}

struct Unit {
  std::string key;
  std::unique_ptr<ChunkRecord> rec;
};

struct Pending {  // a live stroke applied at its end, not yet in the scene's steps
  std::string name;  // its dab file's name, "<hash>.dabs"
  std::unique_ptr<ChunkRecord> rec;
};

struct Entry {
  PXR_NS::SdfPath path;
  float detail = 0;
  std::unique_ptr<Volume> vol;
  std::vector<std::string> keys;  // applied steps
  std::deque<Unit> undo;          // the newest last; its keys are the tail of `keys`
  std::deque<Pending> pending;    // applied after `keys`, oldest first
  std::set<BlockKey> blocks;      // block prims authored
  bool full = false;              // re-author every block (a new volume, a cache load, a new path)
};

// records the volume's replaced chunks into `rec` while it lives
struct Recording {
  Volume& v;
  Recording(Volume& vol, ChunkRecord* rec) : v(vol) { v.record_into(rec); }
  ~Recording() { v.record_into(nullptr); }
};

size_t undo_bytes(const std::deque<Unit>& u) {
  size_t n = 0;
  for (const Unit& x : u) n += x.rec ? x.rec->bytes() : 0;
  return n;
}
}  // namespace

struct Store::Impl {
  explicit Impl(const UsdStageRefPtr& stage) : blocks(stage) {}
  Blocks blocks;
  std::map<std::string, Entry> clays;
  struct Live {
    std::string item;
    Brush brush;
    std::unique_ptr<ChunkRecord> rec;
    std::unique_ptr<StrokeDabs> dabs;
    std::unique_ptr<Resampler> rs;  // made by the first points (the spacing needs the brush's size on screen)
    double sampleMs = 0;            // what one sample's dabs cost so far (a running average; the event budget)
  };
  std::unique_ptr<Live> live;
  CacheWriter cache;

  Entry& entry(const std::string& item, const char* where) {
    auto it = clays.find(item);
    if (it == clays.end()) {
      std::string list;
      for (const auto& kv : clays) list += (list.empty() ? "" : ", ") + kv.first;
      throw Error(std::string(where) + ": no clay \"" + item + "\". Accepted: " + (list.empty() ? "(none)" : list));
    }
    return it->second;
  }

  // the changed blocks (or all of them) meshed in parallel and sent to the stage in one change (one prim per block:
  // CL2 tried 2x2x2 blocks per prim, and Storm's time after a dab went up 23 -> 90-170 ms: its cost follows the
  // surface re-sent, not the number of prims)
  int last_blocks = 0;                      // the last publish: blocks, ms meshing them, ms writing them (sculpt replies)
  double last_mesh_ms = 0, last_usd_ms = 0;
  void publish(Entry& e) {
    std::vector<BlockKey> keys;
    if (e.full) {
      e.vol->take_dirty();
      blocks.begin();
      blocks.remove_all(e.path, e.blocks);
      blocks.end();
      keys = e.vol->all_blocks();
      e.full = false;
    } else {
      const std::set<BlockKey> d = e.vol->take_dirty();
      keys.assign(d.begin(), d.end());
    }
    last_blocks = int(keys.size());
    last_mesh_ms = last_usd_ms = 0;
    if (keys.empty()) return;
    const auto t0 = std::chrono::steady_clock::now();
    std::vector<BlockMesh> meshes(keys.size());
    tbb::parallel_for(size_t(0), keys.size(), [&](size_t i) { e.vol->mesh(keys[i], meshes[i]); });
    last_mesh_ms = ms_since(t0);
    const auto t1 = std::chrono::steady_clock::now();
    struct UsdTime {
      std::chrono::steady_clock::time_point t;
      double* out;
      ~UsdTime() { *out = ms_since(t); }
    } usd_time{t1, &last_usd_ms};
    blocks.begin();
    try {
      for (size_t i = 0; i < keys.size(); ++i) blocks.set(e.path, keys[i], meshes[i], e.blocks);
    } catch (...) {
      blocks.end();
      throw;
    }
    blocks.end();
  }

  void fresh(Entry& e) {
    e.vol = std::make_unique<Volume>(e.detail);
    e.keys.clear();
    e.undo.clear();
    e.pending.clear();
    e.full = true;
  }

  void apply(Entry& e, const StepNode& s, bool keepUndo) {
    std::unique_ptr<ChunkRecord> rec = keepUndo ? std::make_unique<ChunkRecord>() : nullptr;
    {
      Recording r(*e.vol, rec.get());
      if (s.piece) {
        e.vol->apply(s.shape);
      } else if (s.path == StepNode::Path::Along) {
        stroke_along(*e.vol, s.brush, s.along, s.dir);
      } else {
        const std::vector<DabRow> rows = s.path == StepNode::Path::File ? read_dabs(s.file, s.where + ".dabs") : s.rows;
        e.vol->apply_stroke(dabs_from_rows(rows, s.brush));
      }
    }
    e.keys.push_back(s.key);
    if (!keepUndo) return;
    e.undo.push_back(Unit{s.key, std::move(rec)});
    while (e.undo.size() > kUndoUnits || (e.undo.size() > 1 && undo_bytes(e.undo) > kUndoBytes)) e.undo.pop_front();
  }

  // steps[from..] applied in order. Strokes from stored dabs that keep no undo record (all but the last 64 steps) are
  // gathered and replayed together, in parallel where they don't touch (clay_replay.h): the same clay, bit for bit.
  void apply_from(Entry& e, const std::vector<StepNode>& steps, size_t from) {
    std::vector<std::vector<Step>> batch;
    std::vector<std::string> keys;
    auto flush = [&] {
      try {
        if (batch.size() >= kReplayTogether) replay_strokes(*e.vol, batch);
        else
          for (const auto& dabs : batch) e.vol->apply_stroke(dabs);
      } catch (...) {
        fresh(e);  // part of the batch applied: the clay matches no list of steps, so it starts again next time
        throw;
      }
      e.keys.insert(e.keys.end(), keys.begin(), keys.end());
      batch.clear();
      keys.clear();
    };
    for (size_t i = from; i < steps.size(); ++i) {
      const StepNode& s = steps[i];
      const bool keepUndo = steps.size() - i <= kUndoUnits;
      if (keepUndo || s.piece || s.path == StepNode::Path::Along) {
        flush();
        apply(e, s, keepUndo);
        continue;
      }
      std::vector<DabRow> rows;
      try {
        rows = s.path == StepNode::Path::File ? read_dabs(s.file, s.where + ".dabs") : s.rows;
      } catch (...) {
        flush();  // the clay keeps the steps before the one that failed
        throw;
      }
      batch.push_back(dabs_from_rows(rows, s.brush));
      keys.push_back(s.key);
    }
    flush();
  }

  // brings one clay to `n`'s steps; true when its volume changed
  bool reconcile(Entry& e, const Node& n) {
    const std::vector<StepNode>& steps = n.steps;
    // live strokes ended on this clay: adopted in order while the scene's next steps name their dab files
    while (!e.pending.empty()) {
      const size_t at = e.keys.size();
      bool same = at < steps.size();
      for (size_t i = 0; same && i < at; ++i) same = e.keys[i] == steps[i].key;
      const StepNode* s = same ? &steps[at] : nullptr;
      if (!s || s->piece || s->path != StepNode::Path::File || s->name != e.pending.front().name) break;
      e.keys.push_back(s->key);
      e.undo.push_back(Unit{s->key, std::move(e.pending.front().rec)});
      e.pending.pop_front();
      while (e.undo.size() > kUndoUnits) e.undo.pop_front();
    }
    bool changed = false;
    while (!e.pending.empty()) {  // not in the scene: put back, newest first
      e.vol->restore(*e.pending.back().rec);
      e.pending.pop_back();
      changed = true;
    }
    size_t p = 0;
    while (p < e.keys.size() && p < steps.size() && e.keys[p] == steps[p].key) ++p;
    const size_t drop = e.keys.size() - p, add = steps.size() - p;
    if (drop == 0 && add == 0) return changed;
    namespace fs = std::filesystem;
    const bool cached = !n.cache.empty() && fs::is_regular_file(fs::u8path(n.cache));
    if (cached && (drop > e.undo.size() || add > kCacheOverUndo)) {
      std::string error;
      if (e.vol->load(n.cache, &error)) {
        e.keys.clear();
        for (const StepNode& s : steps) e.keys.push_back(s.key);
        e.undo.clear();
        e.full = true;
        return true;
      }
      std::fprintf(stderr, "clay: cache %s not used (%s); replaying\n", n.cache.c_str(), error.c_str());
    }
    if (drop <= e.undo.size()) {
      for (size_t i = 0; i < drop; ++i) {  // undo: the replaced chunks back, newest first
        e.vol->restore(*e.undo.back().rec);
        e.undo.pop_back();
        e.keys.pop_back();
      }
    } else {
      fresh(e);
      p = 0;
    }
    apply_from(e, steps, p);
    return true;
  }

  void cancel_live() {
    if (!live) return;
    auto it = clays.find(live->item);
    if (it != clays.end()) {
      it->second.vol->record_into(nullptr);
      it->second.vol->cancel_stroke();
      it->second.vol->restore(*live->rec);  // the stroke's dabs wrote only chunks the record holds
      publish(it->second);
    }
    live.reset();
  }
};

Store::Store(UsdStageRefPtr stage) : p_(std::make_unique<Impl>(stage)) {}
Store::~Store() = default;

bool Store::has(const std::string& item) const { return p_->clays.count(item) != 0; }
bool Store::sculpting() const { return p_->live != nullptr; }
std::string Store::sculpt_item() const { return p_->live ? p_->live->item : std::string(); }

void Store::sync(const std::vector<Node>& nodes) {
  Impl& s = *p_;
  s.cancel_live();  // a scene in the middle of a stroke: the stroke is dropped
  std::set<std::string> ids;
  for (const Node& n : nodes) ids.insert(n.id);
  for (auto it = s.clays.begin(); it != s.clays.end();) {
    if (ids.count(it->first)) {
      ++it;
      continue;
    }
    s.blocks.begin();
    s.blocks.remove_all(it->second.path, it->second.blocks);
    s.blocks.end();
    it = s.clays.erase(it);
  }
  for (const Node& n : nodes) {
    Entry& e = s.clays[n.id];
    if (!e.vol || e.detail != n.detail) {
      if (e.vol) {
        s.blocks.begin();
        s.blocks.remove_all(e.path, e.blocks);
        s.blocks.end();
      }
      e.detail = n.detail;
      e.path = n.path;
      s.fresh(e);
    }
    if (e.path != n.path) {  // moved into another group: its blocks go under the new path
      s.blocks.begin();
      s.blocks.remove_all(e.path, e.blocks);
      s.blocks.end();
      e.path = n.path;
      e.full = true;
    }
    bool changed = false;
    try {
      changed = s.reconcile(e, n);
    } catch (...) {
      s.publish(e);  // show what was applied before the step that failed
      throw;
    }
    s.publish(e);
    namespace fs = std::filesystem;
    if (changed && !n.cache.empty() && e.keys.size() == n.steps.size() && !fs::exists(fs::u8path(n.cache)))
      s.cache.request(n.id, e.vol->copy(), n.cache, e.vol->copy_mask());
  }
}

void Store::sculpt_begin(const std::string& item, const Brush& brush) {
  Impl& s = *p_;
  s.cancel_live();
  Entry& e = s.entry(item, "sculpt.item");
  auto live = std::make_unique<Impl::Live>();
  live->item = item;
  live->brush = brush;
  live->rec = std::make_unique<ChunkRecord>();
  e.vol->record_into(live->rec.get());
  e.vol->begin_stroke();
  live->dabs = std::make_unique<StrokeDabs>(*e.vol, brush);
  s.live = std::move(live);
}

SculptReply Store::sculpt_points(const std::vector<std::array<float, 3>>& px, const RayFn& ray,
                                 const PixelsPerMetreFn& ppm) {
  Impl& s = *p_;
  if (!s.live) throw Error("sculpt.phase: no stroke begun; send phase \"begin\" first");
  const auto t0 = std::chrono::steady_clock::now();
  Impl::Live& l = *s.live;
  Entry& e = s.entry(l.item, "sculpt.item");
  SculptReply r;
  std::vector<V3> samples;
  std::vector<float> pressures;
  for (const auto& q : px) {
    const float x = q[0], y = q[1];
    if (!l.rs) {
      // dabs every `spacing` (0.3 by default) of the brush radius as the brush looks on screen where the stroke starts (dabs every couple of
      // pixels piled up and grew towards the camera, each landing on the one before)
      V3 o, d, on, nrm;
      float depth = 0;
      if (ray(x, y, o, d)) depth = e.vol->cast(o, d, 1e4f, on, nrm) ? len(sub(on, o)) : len(o);
      const float radiusPx = depth > 0 ? l.brush.radius * ppm(depth) : 3.0f;
      l.rs = std::make_unique<Resampler>(l.brush.spacing * std::max(radiusPx, 3.0f));
    }
    l.rs->push(V3{x, y, 0}, q[2], samples, pressures);
  }
  // The event's budget (CL2b): when the samples since the last event would cost more than kEventBudgetMs, keep an
  // even share of them, the last always. Without it a slow event let more pointer moves pile up, the next event
  // carried more dabs and was slower again (Pull: 62 dabs, 240 ms an event). The dabs kept are the stroke: what is
  // stored and replayed, so live = replay still holds; a fast pointer on a slow machine gets slightly wider spacing.
  constexpr double kEventBudgetMs = 6.0;
  std::vector<size_t> keep;
  const size_t n = samples.size();
  const size_t most = l.sampleMs > 0 ? std::max<size_t>(1, size_t(kEventBudgetMs / l.sampleMs)) : n;
  if (n <= most) {
    for (size_t i = 0; i < n; ++i) keep.push_back(i);
  } else {
    for (size_t k = 1; k <= most; ++k) keep.push_back((k * n) / most - 1);  // evenly, ending on the newest
  }
  bool any = false;
  const auto ta = std::chrono::steady_clock::now();
  size_t done = 0;
  for (size_t i : keep) {
    V3 o, d;
    if (!ray(samples[i].x, samples[i].y, o, d)) continue;
    l.dabs->add(o, d, 1e4f, pressures[i]);
    any = true;
    ++done;
  }
  if (done) {
    const double per = ms_since(ta) / double(done);
    l.sampleMs = l.sampleMs > 0 ? 0.7 * l.sampleMs + 0.3 * per : per;
  }
  r.applyMs = ms_since(t0);
  s.publish(e);
  r.meshMs = s.last_mesh_ms;
  r.usdMs = s.last_usd_ms;
  r.blocks = s.last_blocks;
  r.dabs = int(l.dabs->dabs().size());
  r.hit = any && l.dabs->hit;
  r.point = l.dabs->point;
  r.normal = l.dabs->normal;
  r.ms = ms_since(t0);
  return r;
}

SculptReply Store::sculpt_end(const std::string& folder, const std::string& where) {
  Impl& s = *p_;
  if (!s.live) throw Error("sculpt.phase: no stroke begun; send phase \"begin\" first");
  const auto t0 = std::chrono::steady_clock::now();
  Impl::Live& l = *s.live;
  Entry& e = s.entry(l.item, "sculpt.item");
  SculptReply r;
  const std::vector<Step> dabs = l.dabs->dabs();
  r.dabs = int(dabs.size());
  if (dabs.empty()) {
    s.cancel_live();
    r.ms = ms_since(t0);
    return r;
  }
  std::vector<DabRow> rows;
  for (const Step& d : dabs) rows.push_back(row_of(d));
  std::string name;
  try {
    name = write_dabs(folder, rows, where);
  } catch (...) {
    s.cancel_live();  // no file, no stroke: the clay goes back as it was
    throw;
  }
  {
    Recording rec(*e.vol, l.rec.get());  // still recording: the unit may write chunks no dab touched
    e.vol->end_stroke(dabs);
  }
  s.publish(e);
  e.pending.push_back(Pending{name.substr(name.find('/') + 1), std::move(l.rec)});
  s.live.reset();
  r.file = name;
  r.ms = ms_since(t0);
  return r;
}

void Store::sculpt_cancel() { p_->cancel_live(); }

ClayInfo Store::info(const std::string& item) const {
  Entry& e = p_->entry(item, "clay_info.item");
  ClayInfo i;
  char hex[17];
  std::snprintf(hex, sizeof hex, "%016llx", static_cast<unsigned long long>(e.vol->hash()));
  i.hash = hex;
  i.steps = e.keys.size();
  i.voxels = e.vol->active_voxels();
  i.memoryMb = double(e.vol->memory_bytes()) / (1 << 20);
  i.blocks = e.blocks.size();
  return i;
}

}  // namespace r3d::clay
