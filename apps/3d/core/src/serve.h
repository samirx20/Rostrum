// `rostrum3d-core serve`: one JSON object per line in, one per line out (ENGINE_CONTRACT.md § 1).
#pragma once
#include <cstdio>

namespace r3d {
int serve(std::FILE* in, std::FILE* out);  // returns the exit code
}
