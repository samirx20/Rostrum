# Manifold 3.5.4 (vendored, unmodified)

Mesh booleans for the Rostrum3D core's `combine` items (`src/boolean.cpp`).

- Source: https://github.com/elalish/manifold/releases/tag/v3.5.4 (tarball sha256 db2a8e7aac6abac12fe54fa7b055d24741362b5706fee6f5c5b8f0bccd2de4ec)
- Licence: Apache-2.0 (`LICENSE`, `AUTHORS`).
- Kept: `include/manifold/*.h` except `cross_section.h`, and `src/*.cpp`, `src/*.h` (not `src/cross_section/`). Files are byte-for-byte as released.
- Built serial (`MANIFOLD_PAR=-1`): no TBB, Clipper2 or Tracy (`../../CMakeLists.txt`).
- Files with their own notices, kept as they are: `src/svd.h` (MIT, wi-re tbtSVD; parts BSD-3 PhysX), `src/tri_dist.h` (BSD-3, NVIDIA PhysX), `src/utils.h` (Apache-2.0, Thrust), `src/disjoint_sets.h` (zlib, Wenzel Jakob's dset), `src/quickhull.*` (from Antti Kuukka's public-domain quickhull).
