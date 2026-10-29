// UDIM tile sets (contract v1.34): one picture spread over several files, `name.1001.png`, `name.1002.png` …, named
// together as `name.<UDIM>.png`. Tile 1001 covers u 0..1 v 0..1; tile = 1001 + u_tile + 10 * v_tile (u_tile 0..9).
// The same rule as rostrum3d/udim.py (the Python side's copy of it, for picking and copying pictures).
#pragma once
#include <string>
#include <vector>

namespace r3d::udim {

inline constexpr const char* kToken = "<UDIM>";

// The path names a set: it carries `<UDIM>`.
bool is_set(const std::string& path);

// The tile files of a set that exist, sorted by tile number (empty when none does, or `path` is not a set).
std::vector<std::string> tiles(const std::string& path);

// Their tile numbers, in the same order.
std::vector<int> tile_numbers(const std::string& path);

// One tile of a set (`<stem>.1001.<ext>` or `<stem>_1001.<ext>`, 1001..1099) with at least one other tile of the
// same pattern beside it -> the set's `<UDIM>` path; anything else comes back unchanged.
std::string as_set(const std::string& path);

}  // namespace r3d::udim
