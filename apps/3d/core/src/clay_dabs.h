// Clay: dab files, the compact binary a live stroke is kept in beside the document (CL1 contract § 2; the Python side
// is rostrum3d/clay_dabs.py). Little-endian: "CLD1", uint32 count n, then n x 9 float32 (a.xyz n.xyz b.xyz: point
// on the surface, its normal, the Pull vector / Crease direction / zeros), clay space. Named by content:
// <folder>/clay/<first 32 hex of the file's sha256>.dabs, never rewritten.
#pragma once
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace r3d::clay {

using DabRow = std::array<float, 9>;

std::string sha256_hex(const void* data, size_t n);  // 64 lower-case hex characters

std::vector<uint8_t> dabs_bytes(const std::vector<DabRow>& rows);
// The file name for `rows` ("clay/<hash>.dabs", relative to the project folder) and its bytes.
std::string dabs_name(const std::vector<uint8_t>& bytes);
// Writes <folder>/clay/<hash>.dabs if it isn't there yet (side file, renamed); returns "clay/<hash>.dabs".
// Throws r3d::Error naming `where` when it can't.
std::string write_dabs(const std::string& folder, const std::vector<DabRow>& rows, const std::string& where);
// Reads a dab file; throws r3d::Error naming `where` when it is missing or not a dab file.
std::vector<DabRow> read_dabs(const std::string& path, const std::string& where);

}  // namespace r3d::clay
