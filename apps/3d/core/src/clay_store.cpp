// Clay: the store (clay_store.h).
#include "clay_store.h"

#include <tbb/parallel_for.h>

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <map>
#include <set>
#include <thread>

#include "clay_cache.h"
#include "clay_preview.h"
#include "clay_replay.h"
#include "clay_shapes.h"
#include "clay_stroke.h"
#include "clay_surface.h"
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
  std::string surface;            // 3d-cl4: the CLS1 file whose st the blocks were last given ("" none; clay_surface.h)
  // 3d-v4: the coarse copy kept ready for the next preview stroke (clay_preview.h), as `vol` (coarseOf) was when the
  // copy was last brought up to date; kept up to date after every change once a preview stroke ran on the clay
  std::unique_ptr<Volume> coarse;
  const Volume* coarseOf = nullptr;
  bool wantsCoarse = false;
};

// What a kept coarse copy needs to be up to date: the clay's chunks changed since (all: anything may differ), and a
// preview handed back by a stroke with the chunks its own dabs changed
struct CoarseTask {
  Entry* e = nullptr;
  std::vector<openvdb::Coord> fine, own;
  bool all = false;
  std::unique_ptr<Volume> back;
};

// the clay's coarse copy brought up to date (the preview handed back, else the kept one, refreshed; or a new copy).
// Reads the clay and moves the entry's kept copy out: nothing else may touch either meanwhile.
std::unique_ptr<Volume> bring_coarse(CoarseTask& t) {
  Entry& e = *t.e;
  std::unique_ptr<Volume> c = std::move(t.back);
  if (!c && e.coarse && e.coarseOf == e.vol.get()) c = std::move(e.coarse);
  e.coarse.reset();
  e.coarseOf = nullptr;
  if (c && !t.all) c->refresh_coarse(*e.vol, t.fine, t.own);
  else c = e.vol->coarse_copy();
  c->take_dirty();
  return c;
}

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
  explicit Impl(const UsdStageRefPtr& st) : blocks(st), stage(st) {}
  Blocks blocks;
  UsdStageRefPtr stage;  // CL3: an item piece's source is read from it
  std::map<std::string, Entry> clays;
  struct Live {
    std::string item;
    Brush brush;
    std::unique_ptr<ChunkRecord> rec;
    std::unique_ptr<StrokeDabs> dabs;
    std::unique_ptr<Resampler> rs;  // made by the first points (the spacing needs the brush's size on screen)
    double sampleMs = 0;            // what one sample's dabs cost so far (a running average; the event budget)
    // 3d-v4, a stroke with the coarse preview (clay_preview.h): the preview (made on the catch-up thread at begin),
    // how many dabs were handed to the catch-up, the samples that cast a ray (the clay's cost per sample), the clay's
    // blocks taken down and the preview's prims shown, and the catch-up applying the stroke's dabs to the clay.
    // `fine` is declared after everything its thread uses, so it is stopped first.
    std::unique_ptr<Volume> pv;
    size_t sent = 0, samples = 0;
    std::set<BlockKey> hidden, shown;
    std::unique_ptr<Catchup> fine;
  };
  std::unique_ptr<Live> live;
  std::map<BlockKey, BlockMesh> kept;  // a live stroke's meshes waiting for sculpt_publish (empty: take the prim down)
  CacheWriter cache;

  // 3d-v4: the kept coarse copies brought up to date after a change, on a thread of their own (low priority, half the
  // cores), so a stroke's begin finds its preview ready. Joined before anything changes a clay or its kept copy.
  std::thread coarseJob;
  ~Impl() { join_coarse(); }
  void join_coarse() {
    if (coarseJob.joinable()) coarseJob.join();
  }
  // what clay `e` changed since its copy was brought up to date (taken from the clay), with a preview handed back
  CoarseTask task_for(Entry& e, std::unique_ptr<Volume> back) {
    CoarseTask t;
    t.e = &e;
    t.all = !e.vol->take_changes(t.fine);
    if (back) {
      back->forget_stroke();
      t.all = !back->take_changes(t.own) || t.all;
      t.back = std::move(back);
    }
    return t;
  }
  void start_coarse(std::vector<CoarseTask> tasks) {
    join_coarse();
    if (tasks.empty()) return;
    coarseJob = std::thread([tasks = std::move(tasks)]() mutable {
      tbb::task_arena arena(std::max(2, int(std::thread::hardware_concurrency()) / 2), 1,
                            tbb::task_arena::priority::low);
      for (CoarseTask& t : tasks) {
        Entry& e = *t.e;
        try {
          arena.execute([&] {
            e.coarse = bring_coarse(t);
            e.coarseOf = e.vol.get();
          });
        } catch (...) {  // (out of memory) the next preview stroke makes its copy at its begin
          e.coarse.reset();
          e.coarseOf = nullptr;
        }
      }
    });
  }
  // after a change to `e`: its copy brought up to date, when it keeps one
  void refresh_coarse_of(Entry& e, std::unique_ptr<Volume> back = nullptr) {
    if (!e.wantsCoarse) return;
    std::vector<CoarseTask> tasks;
    tasks.push_back(task_for(e, std::move(back)));
    start_coarse(std::move(tasks));
  }

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
    std::vector<std::pair<BlockKey, const BlockMesh*>> filled;
    for (size_t i = 0; i < keys.size(); ++i) filled.emplace_back(keys[i], &meshes[i]);
    reserve_ring(e, filled);
  }

  // 3d-cl4: empty prims kept ready one ring out around the blocks with a surface, and (a clay that previews) the
  // preview's coarse blocks over them and one ring of those, so a stroke that grows the clay into the next block, or a
  // preview that shows a coarse block for the first time, fills a prim that is there instead of adding one: Storm
  // rebuilds its draw batches for a prim added (part of 3d-v4's 30-75 ms start-of-stroke spikes). Each is what an
  // emptied block is (clay_usd.h): one triangle of no area, here at a vertex of the block beside it, so the clay's
  // bounds don't move and nothing draws (Storm, Cycles). Made where the stage changes anyway (a scene's publish, a
  // stroke's end), never between a stroke's dabs. `madeEmpty`: how many so far (ROSTRUM3D_CLAY_PROFILE).
  // ROSTRUM3D_CLAY_RING=0 turns it off (an A/B on one build).
  size_t madeEmpty = 0;
  void reserve_ring(Entry& e, const std::vector<std::pair<BlockKey, const BlockMesh*>>& filled) {
    static const bool on = [] {
      const char* v = std::getenv("ROSTRUM3D_CLAY_RING");
      return !(v && std::string(v) == "0");
    }();
    if (!on) return;
    const bool coarse = e.wantsCoarse || e.vol->voxel() <= kKeepCopyGrain;
    std::map<BlockKey, std::array<float, 3>> want;  // the first block beside it gives the point
    for (const auto& [k, m] : filled) {
      if (is_preview_key(k) || m->empty()) continue;
      const std::array<float, 3> at{m->points[0], m->points[1], m->points[2]};
      for (int dz = -1; dz <= 1; ++dz)
        for (int dy = -1; dy <= 1; ++dy)
          for (int dx = -1; dx <= 1; ++dx) {
            const BlockKey n{k.x + dx, k.y + dy, k.z + dz};
            if (!e.blocks.count(n)) want.emplace(n, at);
            if (!coarse) continue;
            const BlockKey c = preview_key({(k.x >> 1) + dx, (k.y >> 1) + dy, (k.z >> 1) + dz});  // floor(k / 2)
            if (!e.blocks.count(c)) want.emplace(c, at);
          }
    }
    if (want.empty()) return;
    BlockMesh m;
    m.points.resize(9);
    m.normals = {0, 0, 1, 0, 0, 1, 0, 0, 1};
    m.indices = {0, 1, 2};
    blocks.begin();
    try {
      for (const auto& [k, at] : want) {
        for (int v = 0; v < 3; ++v) std::copy(at.begin(), at.end(), m.points.begin() + 3 * v);
        blocks.set(e.path, k, m, e.blocks);
      }
    } catch (...) {
      blocks.end();
      throw;
    }
    blocks.end();
    madeEmpty += want.size();
  }

  // 3d-v4: a live stroke's meshing and writing, apart (sculpt_compute / sculpt_publish)
  static void mesh_blocks(const Volume& v, const std::vector<BlockKey>& keys, std::map<BlockKey, BlockMesh>& out,
                          bool preview) {
    std::vector<BlockMesh> m(keys.size());
    tbb::parallel_for(size_t(0), keys.size(), [&](size_t i) {
      v.mesh(keys[i], m[i]);
      if (preview && !m[i].empty()) add_skirts(m[i], kSkirtGrains * v.voxel());
    });
    for (size_t i = 0; i < keys.size(); ++i) out[preview ? preview_key(keys[i]) : keys[i]] = std::move(m[i]);
  }
  void write(Entry& e, const std::map<BlockKey, BlockMesh>& m) {
    if (m.empty()) return;
    blocks.begin();
    try {
      for (const auto& kv : m) blocks.set(e.path, kv.first, kv.second, e.blocks);
    } catch (...) {
      blocks.end();
      throw;
    }
    blocks.end();
  }
  // the clay's changed blocks (no preview), kept
  int mesh_changed(Entry& e) {
    const std::set<BlockKey> d = e.vol->take_dirty();
    const std::vector<BlockKey> keys(d.begin(), d.end());
    mesh_blocks(*e.vol, keys, kept, false);
    return int(keys.size());
  }
  // the preview's changed blocks, kept, and the 8 blocks of the clay under each taken down (once)
  int mesh_preview(Live& l) {
    const std::set<BlockKey> d = l.pv->take_dirty();
    const std::vector<BlockKey> keys(d.begin(), d.end());
    mesh_blocks(*l.pv, keys, kept, true);
    for (const BlockKey& k : keys) {
      l.shown.insert(preview_key(k));
      for (int i = 0; i < 8; ++i) {
        const BlockKey f{2 * k.x + (i & 1), 2 * k.y + ((i >> 1) & 1), 2 * k.z + (i >> 2)};
        if (l.hidden.insert(f).second) kept[f] = BlockMesh{};
      }
    }
    return int(keys.size());
  }
  // a stroke's end or cancel: the meshes not yet published, the clay's changed blocks and the ones taken down meshed
  // again, the preview's prims taken down; written at once
  void settle(Entry& e, Live& l) {
    std::map<BlockKey, BlockMesh> out;
    out.swap(kept);
    std::set<BlockKey> fine = e.vol->take_dirty();
    fine.insert(l.hidden.begin(), l.hidden.end());
    for (const BlockKey& k : l.shown) out[k] = BlockMesh{};
    const auto t0 = std::chrono::steady_clock::now();
    mesh_blocks(*e.vol, std::vector<BlockKey>(fine.begin(), fine.end()), out, false);
    last_blocks = int(fine.size());
    last_mesh_ms = ms_since(t0);
    const auto t1 = std::chrono::steady_clock::now();
    write(e, out);
    std::vector<std::pair<BlockKey, const BlockMesh*>> filled;
    for (const auto& kv : out) filled.emplace_back(kv.first, &kv.second);
    reserve_ring(e, filled);  // the blocks this stroke grew into get their ring before the next stroke
    last_usd_ms = ms_since(t1);
  }

  void fresh(Entry& e) {
    e.vol = std::make_unique<Volume>(e.detail);
    e.coarse.reset();  // made again from the new volume (callers have joined the coarse job)
    e.coarseOf = nullptr;
    e.keys.clear();
    e.undo.clear();
    e.pending.clear();
    e.full = true;
  }

  // CL3: the fields of drawn, spun and item pieces, kept for the pieces applied lately (an item's level set is the
  // costly one: an undo and redo doesn't make it again). By clay, step key and grain.
  struct KeptField {
    std::shared_ptr<const Field> field;
    uint64_t used = 0;
  };
  static constexpr size_t kKeptFields = 8;  // an item's level set can be tens of MB
  std::map<std::string, KeptField> fields;
  uint64_t fieldUse = 0;

  std::shared_ptr<const Field> field_of(const Entry& e, const StepNode& s) {
    using K = ShapeSpec::Kind;
    if (s.spec.kind == K::Ball) return nullptr;
    const std::string id = e.path.GetString() + "|" + s.key + "|" + std::to_string(e.detail);
    auto it = fields.find(id);
    if (it == fields.end()) {
      std::shared_ptr<const Field> f;
      if (s.spec.kind == K::Outline) f = make_outline(s.spec, e.detail, s.where);
      else if (s.spec.kind == K::Spin) f = make_spin(s.spec, e.detail, s.where);
      else f = make_item(s.spec, stage, e.path, e.detail, item_half_width(s.shape.blend / e.detail), s.where);
      while (fields.size() >= kKeptFields) {  // the least lately used goes
        auto old = fields.begin();
        for (auto j = fields.begin(); j != fields.end(); ++j)
          if (j->second.used < old->second.used) old = j;
        fields.erase(old);
      }
      it = fields.emplace(id, KeptField{std::move(f), 0}).first;
    }
    it->second.used = ++fieldUse;
    return it->second.field;
  }

  void apply(Entry& e, const StepNode& s, bool keepUndo) {
    std::unique_ptr<ChunkRecord> rec = keepUndo ? std::make_unique<ChunkRecord>() : nullptr;
    {
      Recording r(*e.vol, rec.get());
      if (s.piece) {
        Step shape = s.shape;
        const std::shared_ptr<const Field> field = field_of(e, s);  // null: a sphere / capsule
        shape.field = field.get();
        e.vol->apply(shape);
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

  // 3d-cl4: a painted clay at its steps gets its unfolding as st on its full-detail blocks (clay_surface.h: read from
  // the node's paint file, else made and written there); a clay with no paint has none. A block re-written since
  // (Blocks::set) lost its st; the blocks are looked at as drawn, so nothing is done when all still hold this file's.
  void unfold(Entry& e, const Node& n) {
    const bool want = !n.paintFile.empty() && e.keys.size() == n.steps.size() && e.pending.empty();
    if (!want && e.surface.empty()) return;
    std::vector<SurfaceBlock> surf;
    bool current = want && e.surface == n.paintFile;
    for (const BlockKey& k : e.blocks) {  // BlockKey order; the preview's prims (all after the fine ones) never
      if (is_preview_key(k)) continue;
      SurfaceBlock b;
      b.key = k;
      if (!blocks.get(e.path, k, b.points, b.normals, b.indices)) continue;
      current = current && blocks.has_st(e.path, k);
      surf.push_back(std::move(b));
    }
    if (current) return;
    const auto t0 = std::chrono::steady_clock::now();
    std::vector<VtVec2fArray> st;
    SurfaceStats stats;
    if (want) st = clay_surface(surf, n.paintSize, n.paintFile, n.id + ".paint", &stats);
    blocks.begin();
    try {
      for (size_t i = 0; i < surf.size(); ++i) {
        if (want) blocks.set_st(e.path, surf[i].key, std::move(st[i]));
        else blocks.clear_st(e.path, surf[i].key);
      }
    } catch (...) {
      blocks.end();
      e.surface.clear();
      throw;
    }
    blocks.end();
    e.surface = want ? n.paintFile : std::string();
    static const bool prof = std::getenv("ROSTRUM3D_CLAY_PROFILE") != nullptr;
    if (prof && want)
      std::fprintf(stderr, "claysurf %s %s points=%zu tris=%zu charts=%d weld=%.1f unfold=%.1f file=%.1f all=%.1f ms\n",
                   n.id.c_str(), stats.made ? "made" : "read", stats.points, stats.triangles, stats.charts,
                   stats.weldMs, stats.unfoldMs, stats.fileMs, ms_since(t0));
  }

  void cancel_live() {
    if (!live) return;
    struct Drop {
      Impl& s;
      ~Drop() {
        s.kept.clear();
        s.live.reset();
      }
    } drop{*this};
    if (live->fine) live->fine->cancel();  // the clay is this thread's again
    auto it = clays.find(live->item);
    if (it != clays.end()) {
      it->second.vol->record_into(nullptr);
      it->second.vol->cancel_stroke();
      it->second.vol->restore(*live->rec);  // the stroke's dabs wrote only chunks the record holds
      settle(it->second, *live);
      refresh_coarse_of(it->second, std::move(live->pv));  // the preview handed back, brought up to date
    }
  }
};

Store::Store(UsdStageRefPtr stage) : p_(std::make_unique<Impl>(stage)) {}
Store::~Store() = default;

bool Store::has(const std::string& item) const { return p_->clays.count(item) != 0; }
bool Store::sculpting() const { return p_->live != nullptr; }
bool Store::previewing() const { return p_->live && p_->live->fine; }
std::string Store::sculpt_item() const { return p_->live ? p_->live->item : std::string(); }

void Store::sync(const std::vector<Node>& nodes) {
  Impl& s = *p_;
  s.cancel_live();  // a scene in the middle of a stroke: the stroke is dropped
  s.join_coarse();  // nothing reads a clay behind this
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
    s.unfold(e, n);
  }
  // the kept coarse copies of the clays that changed, brought up to date behind
  std::vector<CoarseTask> tasks;
  for (auto& kv : s.clays) {
    Entry& e = kv.second;
    // a clay fine enough that its brushes usually preview (a 25 mm brush is 16 grains at 1.56 mm) gets its copy
    // made now, behind, so even its first stroke starts without the full copy (~15-25 ms at 1 mm)
    if (e.vol && e.vol->voxel() <= 0.0016f) e.wantsCoarse = true;
    if (!e.wantsCoarse) continue;
    CoarseTask t = s.task_for(e, nullptr);
    if (t.all || !t.fine.empty() || !e.coarse || e.coarseOf != e.vol.get()) tasks.push_back(std::move(t));
  }
  s.start_coarse(std::move(tasks));
}

void Store::sculpt_begin(const std::string& item, const Brush& brush, bool preview) {
  Impl& s = *p_;
  s.cancel_live();
  s.join_coarse();  // the stroke writes the clay, and its preview starts from the kept copy
  Entry& e = s.entry(item, "sculpt.item");
  auto live = std::make_unique<Impl::Live>();
  live->item = item;
  live->brush = brush;
  live->rec = std::make_unique<ChunkRecord>();
  e.vol->record_into(live->rec.get());
  e.vol->begin_stroke();
  if (preview && preview_stroke(brush, e.vol->voxel())) {
    // the preview is the kept copy (round 2: making it here took 14-18 ms of the first event), brought up to date with
    // what changed since, or a new copy the first time: on the catch-up thread (the first event waits for it); from
    // then on that thread owns the clay
    e.wantsCoarse = true;
    auto task = std::make_shared<CoarseTask>(s.task_for(e, nullptr));
    Impl::Live* l = live.get();
    live->fine = std::make_unique<Catchup>(*e.vol, [task, l] {
      l->pv = bring_coarse(*task);
      l->pv->begin_stroke();  // Build up off reads where the stroke began, on the preview too
    });
  } else {
    live->dabs = std::make_unique<StrokeDabs>(*e.vol, brush);
  }
  s.live = std::move(live);
}

SculptReply Store::sculpt_compute(const std::vector<std::array<float, 3>>& px, const RayFn& ray,
                                  const PixelsPerMetreFn& ppm) {
  Impl& s = *p_;
  if (!s.live) throw Error("sculpt.phase: no stroke begun; send phase \"begin\" first");
  const auto t0 = std::chrono::steady_clock::now();
  Impl::Live& l = *s.live;
  Entry& e = s.entry(l.item, "sculpt.item");
  if (l.fine) l.fine->wait_ready();       // the preview (made from the begin on; counted in applyMs)
  Volume& shown = l.pv ? *l.pv : *e.vol;  // what the rays meet and the dabs are shown on
  if (!l.dabs) l.dabs = std::make_unique<StrokeDabs>(shown, l.brush, e.vol->voxel());
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
      if (ray(x, y, o, d)) depth = shown.cast(o, d, 1e4f, on, nrm) ? len(sub(on, o)) : len(o);
      const float radiusPx = depth > 0 ? l.brush.radius * ppm(depth) : 3.0f;
      l.rs = std::make_unique<Resampler>(l.brush.spacing * std::max(radiusPx, 3.0f));
    }
    l.rs->push(V3{x, y, 0}, q[2], samples, pressures);
  }
  // The event's budget (CL2b): when the samples since the last event would cost more than kEventBudgetMs, keep an
  // even share of them, the last always. Without it a slow event let more pointer moves pile up, the next event
  // carried more dabs and was slower again (Pull: 62 dabs, 240 ms an event). The dabs kept are the stroke: what is
  // stored and replayed, so live = replay still holds; a fast pointer on a slow machine gets slightly wider spacing.
  // 3d-v4: the first event has no cost measured yet; it kept every sample since the press (part of the start-of-stroke
  // spike), now kFirstSamples. With the preview the budget is the preview's, and the clay's own work an event adds is
  // held to what the catch-up does in an event (kCatchupMs, less what still waits): a drag faster than the clay keeps
  // up with gets wider spacing, as above, never a long wait at the end. Over kBacklogMs waiting, the event adds no dab
  // (its samples are dropped; the next event's start where this one's ended).
  // 3d-cl4: the catch-up runs narrow while the brush moves and lets up to Catchup::kWidenMs wait (at the wide pace)
  // before it goes wide, so only the wait past that counts against an event's room: no fewer dabs than before.
  // ROSTRUM3D_CLAY_EVENT_MS sets kEventBudgetMs (to measure; fewer dabs an event, wider spacing on a fast drag)
  static const double kEventBudgetMs = [] {
    const char* env = std::getenv("ROSTRUM3D_CLAY_EVENT_MS");
    const double v = env ? std::atof(env) : 0.0;
    return v > 0 ? v : 6.0;
  }();
  constexpr size_t kFirstSamples = 2;
  constexpr double kCatchupMs = 12.0, kBacklogMs = 50.0;
  std::vector<size_t> keep;
  const size_t n = samples.size();
  size_t most = l.sampleMs > 0 ? std::max<size_t>(1, size_t(kEventBudgetMs / l.sampleMs)) : std::min(n, kFirstSamples);
  if (l.fine) {
    const double dabMs = l.fine->dab_ms(), backlog = l.fine->backlog_ms();
    if (dabMs > 0 && l.samples > 0) {
      const double perSample = dabMs * double(l.dabs->dabs().size()) / double(l.samples);
      const double room = kCatchupMs - std::max(0.0, backlog - Catchup::kWidenMs);
      most = std::min(most, room > perSample ? size_t(room / perSample) : size_t(1));
    }
    if (backlog > kBacklogMs) most = 0;
  }
  if (n <= most) {
    for (size_t i = 0; i < n; ++i) keep.push_back(i);
  } else if (most > 0) {
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
    l.samples += done;
  }
  if (l.fine) {  // the new dabs, to the clay
    const std::vector<Step>& all = l.dabs->dabs();
    l.fine->push(all.data() + l.sent, all.size() - l.sent);
    l.sent = all.size();
  }
  r.applyMs = ms_since(t0);
  const auto tm = std::chrono::steady_clock::now();
  r.blocks = l.pv ? s.mesh_preview(l) : s.mesh_changed(e);
  r.meshMs = ms_since(tm);
  r.dabs = int(l.dabs->dabs().size());
  r.hit = keep.empty() ? l.dabs->hit : any && l.dabs->hit;
  r.point = l.dabs->point;
  r.normal = l.dabs->normal;
  r.ms = ms_since(t0);
  return r;
}

void Store::sculpt_publish(SculptReply& r) {
  Impl& s = *p_;
  if (s.kept.empty() || !s.live) return;
  const auto t0 = std::chrono::steady_clock::now();
  Entry& e = s.entry(s.live->item, "sculpt.item");
  std::map<BlockKey, BlockMesh> m;
  m.swap(s.kept);
  s.write(e, m);
  r.usdMs = ms_since(t0);
  r.ms += r.usdMs;
}

SculptReply Store::sculpt_points(const std::vector<std::array<float, 3>>& px, const RayFn& ray,
                                 const PixelsPerMetreFn& ppm) {
  SculptReply r = sculpt_compute(px, ray, ppm);
  sculpt_publish(r);
  return r;
}

SculptReply Store::sculpt_end(const std::string& folder, const std::string& where) {
  Impl& s = *p_;
  if (!s.live) throw Error("sculpt.phase: no stroke begun; send phase \"begin\" first");
  const auto t0 = std::chrono::steady_clock::now();
  Impl::Live& l = *s.live;
  Entry& e = s.entry(l.item, "sculpt.item");
  const double waitBacklog = l.fine ? l.fine->backlog_ms() : 0.0;
  if (l.fine) {  // the dabs the clay hasn't caught up with yet (then the thread is joined: the clay is this one's again)
    try {
      l.fine->finish();
    } catch (...) {
      s.cancel_live();
      throw;
    }
  }
  SculptReply r;
  const std::vector<Step> dabs = l.dabs ? l.dabs->dabs() : std::vector<Step>();
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
  const double tFinish = ms_since(t0);
  const auto tEnd = std::chrono::steady_clock::now();
  {
    Recording rec(*e.vol, l.rec.get());  // still recording: the unit may write chunks no dab touched
    e.vol->end_stroke(dabs);
  }
  const double tEndMs = ms_since(tEnd);
  s.settle(e, l);  // the clay's blocks (and any not yet published) replace the preview's
  // ROSTRUM3D_CLAY_PROFILE=1: where the release went (the catch-up's wait and what it expected, the end's own unit:
  // a whole replay with ROSTRUM3D_CLAY_VERIFY=1, the blocks meshed and written)
  static const bool prof = std::getenv("ROSTRUM3D_CLAY_PROFILE") != nullptr;
  if (prof)
    std::fprintf(stderr,
                 "clayend wait=%.1f (backlog %.1f) end=%.1f mesh=%.1f usd=%.1f blocks=%d hidden=%zu dabs=%zu narrow=%d"
                 " made=%zu\n",
                 tFinish, waitBacklog, tEndMs, s.last_mesh_ms, s.last_usd_ms, s.last_blocks, l.hidden.size(),
                 dabs.size(), l.fine ? l.fine->narrow_dabs() : 0, s.madeEmpty);
  r.blocks = s.last_blocks;
  r.meshMs = s.last_mesh_ms;
  r.usdMs = s.last_usd_ms;
  s.refresh_coarse_of(e, std::move(l.pv));  // behind: the preview handed back, brought up to date with the clay
  e.pending.push_back(Pending{name.substr(name.find('/') + 1), std::move(l.rec)});
  s.live.reset();
  r.file = name;
  r.ms = ms_since(t0);
  return r;
}

void Store::sculpt_cancel() { p_->cancel_live(); }

ClayInfo Store::info(const std::string& item) const {
  Entry& e = p_->entry(item, "clay_info.item");
  // 3d-cl4: mid-stroke the clay catches up behind the preview (narrow while the brush moves): it is hashed once it
  // has every dab so far, so the hash is the clay the stroke has made, whatever the pace
  if (p_->live && p_->live->item == item && p_->live->fine) p_->live->fine->drain();
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
