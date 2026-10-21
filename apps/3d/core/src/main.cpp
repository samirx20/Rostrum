// rostrum3d-core: the Rostrum3D engine program. `rostrum3d-core serve` speaks ENGINE_CONTRACT.md § 1.
#include <windows.h>
#include <fcntl.h>
#include <io.h>

#include <cstdio>
#include <cstring>

#include "serve.h"

// Ask Windows laptops for the fast graphics chip (NVIDIA Optimus, AMD PowerXpress).
extern "C" {
__declspec(dllexport) DWORD NvOptimusEnablement = 1;
__declspec(dllexport) int AmdPowerXpressRequestHighPerformance = 1;
}

int main(int argc, char** argv) {
  if (argc != 2 || std::strcmp(argv[1], "serve") != 0) {
    std::fprintf(stderr, "usage: rostrum3d-core serve   (JSON lines on stdin/stdout; see ENGINE_CONTRACT.md)\n");
    return 2;
  }
  // Our replies get the real stdout; anything a library prints to stdout goes to stderr instead,
  // so the conversation never carries stray text.
  const int reply_fd = _dup(_fileno(stdout));
  _dup2(_fileno(stderr), _fileno(stdout));
  _setmode(reply_fd, _O_BINARY);
  _setmode(_fileno(stdin), _O_BINARY);
  std::FILE* replies = _fdopen(reply_fd, "wb");
  return r3d::serve(stdin, replies);
}
