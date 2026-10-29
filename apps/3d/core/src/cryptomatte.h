// The Cryptomatte pass (passes.h "cryptomatte"): soft-edged masks per item in the open Cryptomatte form that Nuke,
// Resolve/Fusion and Natron read (https://github.com/Psyop/Cryptomatte, specification 1.2.0).
//
// Cycles makes the ranks (our patch -r5, libs/cycles-rostrum.patch): per pixel, the 6 objects covering it most, each
// as (id, share of the pixel), two a layer in CryptoObject00..02. An object's id is MurmurHash3_32 of its name as a
// float; the plug-in names every object after its Hydra prim (its scene path). Here each object is folded into its
// top-level item (/World/<item>, everything it holds; as the Masks pass), the shares of one item's parts added, the
// ranks sorted again, and the id re-hashed from the item's id ("chair"), so a compositor lists items by their names.
// The file's header carries what readers need: cryptomatte/<key>/name, hash, conversion and manifest (name -> hash).
#pragma once
#include <pxr/usd/usd/stage.h>

#include <cstdint>
#include <string>
#include <vector>

#include "aovs.h"
#include "image_out.h"

namespace r3d {

// the Hydra outputs Cycles makes the ranks in: CryptoObject00, 01, 02
const std::vector<std::string>& crypto_aovs();

// CryptoObject00..02 .R G B A (32-bit; ids per item, shares added and sorted), the first carrying the header entries
std::vector<ExrLayer> cryptomatte(const Aovs& lit, const PXR_NS::UsdStageRefPtr& stage);

// MurmurHash3 (x86, 32-bit, seed 0) of `s`, and the float Cryptomatte stores for a hash (exponent kept off 0 and 255)
uint32_t murmur3(const std::string& s);
float hash_to_float(uint32_t h);

}  // namespace r3d
