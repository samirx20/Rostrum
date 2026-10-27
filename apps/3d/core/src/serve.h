#pragma once
#include <cstdio>
#include <functional>
#include <string>

namespace r3d {
class Core;
// ENGINE_CONTRACT.md § 1: JSON lines in, one reply line per request out (render progress lines before its reply).
int serve(std::FILE* in, std::FILE* out);
// one request line -> its reply line, on `core`; `progress` gets a render's progress lines. Never throws: a failure
// is the reply {"ok": false, "error": ...}. `quit` set: {"quit": {}} is accepted and sets it (the program's loop).
// The engine program and the window's view (window_core.h) both answer through here: one contract, two transports.
std::string answer(Core& core, const std::string& line, const std::function<void(const std::string&)>& progress,
                   bool* quit = nullptr);
}  // namespace r3d
