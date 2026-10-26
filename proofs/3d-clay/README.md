# P-Clay proof — the clay core (part 1 of 2)

*Team Priyam, 2026-10-26. Brief: `C:\Users\Sam\.rostrum\waves\results\3d-simplicity\PLAN-UPDATE.md` § 1 "P-Clay".
Throwaway proof code: nothing here goes into `apps\` or `shared\`. Pictures and numbers:
`C:\Users\Sam\.rostrum\waves\results\3d-clay-proof\`.*

## Verdict (part 1): the core works; the budgets are half met; not a pass yet, not a pivot

**In plain words.** Clay built on a sparse volume works. Steps go in, a closed surface comes out, and Storm and Cycles both
show it. The same list of steps always gives exactly the same clay, saved or replayed. Small and medium brush dabs
show up on screen within about one frame (10–19 ms). Three things are still too slow or too big: very large brushes
(a quarter of the clay across: 67–114 ms, 4–7× over), replaying 2,000 strokes (73 s against 15 s) and peak memory
(2.9 GB against 1.5 GB). Each has a clear, contained fix, listed below. The first sculpted head renders cleanly in
Final, but it is crude next to a Nomad Sculpt or ZBrush piece. Judging the surface against those pieces is part 2,
together with the missing brushes.

By the brief's rule ("all budgets met, or within 25 % with a clear fix"), part 1 is **not yet a pass**. It is also
**no reason to pivot**: the slow parts are known and local, and they are not limits of the method.

## What was built (`src\`)

| File | What it does |
|---|---|
| `clay.h/.cpp` (lead) | The clay: an OpenVDB `FloatGrid` narrow band (values in voxels, half-width 4, negative inside). **Steps**: pieces (sphere / capsule, Add or Carve, with a smooth **blend** distance) and brush **stamps** (Add, Carve, Smooth), each optionally **mirrored** in X in the same pass. A step works only on the 8³ chunks near the surface inside its reach. It fills them from the grid, widens the distances when a blend needs them (Jacobi upwind eikonal), applies the step, re-seeds the changed voxels next to the surface from where the surface crosses their edges, re-levels the band and writes back (chunks that end up uniform become tiles). It marks the changed **blocks** (32³) dirty. Also: surface picking (`cast`, `snap`), the replay **hash** (leaves and tiles in tree order, FNV-1a), `.vdb` save / load (the replay cache), steps as text lines whose floats round-trip exactly. |
| `mesh.h/.cpp` (member, surface nets; smooth normals added by the lead) | The surface of one block, read out by surface nets. A block owns the edges that start inside it, so blocks join without cracks or double faces (self-test: closed, consistently wound). Normals are a trilinear blend of central-difference gradients at the cell's corners, read from a one-voxel-wider window, so shading is continuous across cells. |
| `view.h/.cpp` (member) | Storm: one mesh prim per block under `/Clay`, written at the Sdf level inside one change block, so **only changed blocks are sent**. Cycles: the whole rebuilt surface as one mesh, rendered to convergence and written as an sRGB PNG; a failed render throws and leaves no file. A clay material, key / fill / rim lights and a dim dome. |
| `main.cpp` (lead) | The scripted head (the "agent" sculpt: 21 pieces plus 233 brush dabs). The timings and the 2,000-stroke replay below. `--check`: after every step the whole surface must be closed (every edge used twice). |

Build and run (both through `heavy.ps1`): `build.bat`, then `run.bat <out folder> [--samples n] [--no-final] [--strokes n]`.

## Numbers (this laptop: RTX 3050 4 GB, 16 GB, 12 threads, shared and busy; run 4, `numbers.json`)

Clay: a head and neck 0.33 units tall at voxel 0.000625 (about 530 voxels top to bottom). 3.26 M active voxels;
1.24 M triangles in 781 blocks.

| Budget | Target | Measured | |
|---|---|---|---|
| Stamp → picture, small brush (r 6 voxels) | ≤ 16 ms | **10–14 ms** p50, p95 ≤ 16 ms (step 0.8–1.1, mesh 0.8–0.9, USD 0.3–0.4, Storm 8.5–11.5) | met |
| Stamp → picture, medium (r 19 voxels) | ≤ 16 ms | **16–19 ms** p50; mirrored 22–28 ms | within 25 %; mirrored over |
| Stamp → picture, quarter of the clay across (r 66 voxels) | ≤ 16 ms | **67–70 ms** p50; mirrored 91–114 ms (step 21–55, mesh 4–11, USD 2–4, Storm 31–43) | **4–7× over** |
| Full rebuild of the close-up head | ≤ 2 s | **92 ms** (all 781 blocks, parallel) | met |
| Memory | ≤ 1.5 GB | grid **33–39 MB**; process peak **2.9 GB**, 0.8 GB at the end | **over** (see below) |
| Replay of 2,000 strokes (23,153 dabs) | ≤ 15 s | **73 s** (the head's 254 steps before it took another 55 s) | **4.9× over** |
| Replay from the cache (`.vdb`) | ≤ 2 s | **0.14 s** | met |
| Same steps → same surface hash | yes | **yes**: head live = replay (`7ab0339f574c620e`), 2,000 strokes live = replay from file = cache (`79defd62f84f2886`), and the same hashes in every run since | met |
| Storm frame with nothing changed | — | 6.9 ms (1.24 M triangles, 1280×720) | |
| Final (Cycles, 256 samples, denoised, 1280×720) | — | 5.5 s | |

Wall times measured on a shared machine; per-step CPU time is in `numbers.json` (`*_cpu_ms`).

### Found and fixed on the way (worth knowing for CL1)
- **Storm drew on the AMD integrated graphics** until the program exported `NvOptimusEnablement` /
  `AmdPowerXpressRequestHighPerformance` (as `apps\3d\core\src\main.cpp` does). That alone took a frame from about 40 ms to
  about 7 ms. Any new program that draws must export them.
- **Nested parallel loops + thread-local buffers = holes.** The block read-out ran its own parallel loop inside the
  parallel meshing of blocks. TBB then ran another block on the same thread while it waited, and that block reused the
  thread's buffers. The result was holes at block seams, different on every run (the replay hash stayed right, because
  the clay itself was fine). The read-out is now serial inside a block. `--check` shows every one of the 254 head
  steps leaves a closed surface.
- **Block listing:** a block holds the quads for edges that *start* in it, so the blocks to mesh are each leaf's block
  plus the block just below it on each axis.
- Whole-box steps were 10–20× slower than working on the chunks near the surface (first version: 160–400 ms per large
  dab, 11 ms per replay dab).

## Where part 1 stopped (and what part 2 does)

Done: sparse volume on OpenVDB; pieces with add / carve / blend; stamps Add, Carve, Smooth; mirror; blocks with only
changed ones sent to Storm; whole-surface rebuild for Cycles; replay with a stable hash and a cache; the measurements
above; a first sculpted head in Final (`head_final_cycles.png`; Storm: `head_storm.png`; the timing dabs on the cranium: `after_bench_dabs_storm.png`).

Not done (part 2):
1. **Brushes Pull, Flatten, Crease.** The stamp code has one place for each op (`clay.cpp`, step E).
2. **Large brushes to ≤ 16 ms.** Today a quarter-size dab spends about 25 ms in the step and 31–43 ms in Storm re-sending
   about 150 blocks. Fixes, in order: (a) re-level only the chunks a dab changed, not every chunk in its reach;
   (b) cap Storm's per-frame work: send the dab's blocks as they finish and the rest on the next frame, or use 64³
   blocks (fewer prims; the mesher's row masks need 128-bit rows for that); (c) for very large dabs, a coarser level.
3. **Replay to ≤ 15 s.** A replay dab costs about 3 ms (19 ms CPU spread over threads): many small parallel loops per
   dab. Fix: replay a whole stroke's dabs in one box (one fill, one write-back, re-levelling once per stroke), with live
   sculpting doing the same per stroke, so the hash stays identical.
4. **Memory to ≤ 1.5 GB.** The grid is small (39 MB). The peak comes from a step's dense scratch buffers for the big
   wide-blend pieces of the head (box up to about 420³) and from three clays alive at once in this test program. Fix: a
   chunk-sparse scratch (only the listed chunks, not the whole box) and one shared scratch.
5. **Wide blends are slow** (a 0.03 blend = 48 voxels needs about 50 re-levelling passes): the head's 21 pieces take most of
   its 43 s. Not a budget, but CL1 needs it faster: fast sweeping, or the widening done on a coarser grid.
6. **The comparison by eye.** Reference pictures (published Nomad Sculpt / ZBrush pieces) saved privately under
   `C:\Users\Sam\.rostrum\references\3d\` (not done yet: the folder doesn't exist); an agent and a member with a mouse
   sculpt a head and a small character; Final renders side by side. Today's head is a scripted first try: blobby
   forms, smeared smoothing, faint ripples on the cheeks where many smooth dabs overlap. It is not at the reference's
   level.
7. **Cycles:** a second Cycles engine made after the first is gone crashes (access violation). The proof makes one Final
   per run; part 2 keeps one engine alive, as `apps\3d\core\src\hydra.cpp` does.

## Libraries

- **OpenVDB 13.0.0** (MPL-2.0). Its DLL was already in the 3D library folder (`runtime\bin\openvdb.dll`). The headers and
  import library come from the same Blender `lib-windows_x64` bundle (tag v5.2.2, commit 60d6e96; that DLL is
  byte-identical), fetched with a sparse Git LFS checkout of just its `openvdb\` folder into
  `C:\Users\Sam\.rostrum\downloads\blender-lib-v5.2.2-openvdb\` (80 MB on disk with its Git data: include, lib, DLLs). Nothing was built
  from source. OpenVDB's own dependencies are inside the DLL and already listed for the Cycles bundle: oneTBB
  (Apache-2.0), Blosc (BSD-3-Clause), zlib (zlib), Imath (BSD-3-Clause). For CL1, `apps\3d\libs\lay_out.py` should
  copy `openvdb\include` and `openvdb.lib` into the library folder's `sdk\`.
- Everything else is already in the 3D library folder (OpenUSD / Hydra, Cycles, TBB, epoxy, OpenImageIO).

## Attribution rows

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| OpenVDB (headers + import library; DLL already listed) | 13.0.0 (Blender lib-windows_x64 v5.2.2, 60d6e96) | MPL-2.0 | `proofs/3d-clay` (the clay volume); later `apps/3d/core` | dynamic | dev only (proof); the DLL already ships with the 3D libraries | Keep the notice; changes to OpenVDB's own files stay MPL (none made) | https://github.com/AcademySoftwareFoundation/openvdb |
