// A crash's native call stack, for finding thread-timing crashes in the live view: with ROSTRUM3D_CRASH_LOG=<file> set,
// an access violation (or another fatal fault) on any thread appends that thread's stack, symbol names from the .pdb
// files beside the DLLs, to the file. Only reads; the crash then goes on as before. Off when the variable is unset.
#include <windows.h>
#include <dbghelp.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>

namespace {

char g_path[MAX_PATH] = {};
std::mutex g_m;

bool fatal(DWORD code) {
  return code == EXCEPTION_ACCESS_VIOLATION || code == EXCEPTION_ILLEGAL_INSTRUCTION ||
         code == EXCEPTION_STACK_OVERFLOW || code == EXCEPTION_INT_DIVIDE_BY_ZERO || code == 0xC0000374;  // heap
}

LONG CALLBACK on_fault(EXCEPTION_POINTERS* e) {
  if (!fatal(e->ExceptionRecord->ExceptionCode)) return EXCEPTION_CONTINUE_SEARCH;
  std::lock_guard<std::mutex> l(g_m);
  FILE* f = std::fopen(g_path, "a");
  if (!f) return EXCEPTION_CONTINUE_SEARCH;
  const HANDLE proc = GetCurrentProcess(), th = GetCurrentThread();
  static bool sym = false;
  if (!sym) {
    SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES);
    sym = SymInitialize(proc, nullptr, TRUE) != FALSE;
  }
  const EXCEPTION_RECORD* r = e->ExceptionRecord;
  std::fprintf(f, "== fault 0x%08lx at %p, thread %lu", r->ExceptionCode, r->ExceptionAddress, GetCurrentThreadId());
  if (r->ExceptionCode == EXCEPTION_ACCESS_VIOLATION && r->NumberParameters >= 2)
    std::fprintf(f, " (%s %p)", r->ExceptionInformation[0] == 0 ? "read" : r->ExceptionInformation[0] == 1 ? "write" : "exec",
                 reinterpret_cast<void*>(r->ExceptionInformation[1]));
  std::fprintf(f, "\n");
  CONTEXT ctx = *e->ContextRecord;
  STACKFRAME64 s = {};
  s.AddrPC.Offset = ctx.Rip;
  s.AddrFrame.Offset = ctx.Rbp;
  s.AddrStack.Offset = ctx.Rsp;
  s.AddrPC.Mode = s.AddrFrame.Mode = s.AddrStack.Mode = AddrModeFlat;
  for (int i = 0; i < 48; ++i) {
    if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, proc, th, &s, &ctx, nullptr, SymFunctionTableAccess64,
                     SymGetModuleBase64, nullptr) || !s.AddrPC.Offset)
      break;
    const DWORD64 pc = s.AddrPC.Offset;
    char mod[MAX_PATH] = "?";
    if (const DWORD64 base = SymGetModuleBase64(proc, pc)) GetModuleFileNameA(HMODULE(base), mod, MAX_PATH);
    alignas(SYMBOL_INFO) char buf[sizeof(SYMBOL_INFO) + 512];
    auto* si = reinterpret_cast<SYMBOL_INFO*>(buf);
    si->SizeOfStruct = sizeof(SYMBOL_INFO);
    si->MaxNameLen = 511;
    DWORD64 off = 0;
    IMAGEHLP_LINE64 line = {sizeof(IMAGEHLP_LINE64)};
    DWORD loff = 0;
    const char* m = std::strrchr(mod, '\\');
    std::fprintf(f, "  %2d %s!%s+0x%llx", i, m ? m + 1 : mod, sym && SymFromAddr(proc, pc, &off, si) ? si->Name : "?",
                 static_cast<unsigned long long>(off));
    if (sym && SymGetLineFromAddr64(proc, pc, &loff, &line)) std::fprintf(f, "  %s:%lu", line.FileName, line.LineNumber);
    std::fprintf(f, "\n");
  }
  std::fclose(f);
  return EXCEPTION_CONTINUE_SEARCH;
}

struct Install {
  Install() {
    const char* p = std::getenv("ROSTRUM3D_CRASH_LOG");
    if (!p || !*p) return;
    strncpy_s(g_path, p, _TRUNCATE);
    AddVectoredExceptionHandler(1, on_fault);
  }
} g_install;

}  // namespace
