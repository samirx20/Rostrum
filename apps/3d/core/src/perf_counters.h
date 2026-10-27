// Storm's own counters (HdPerfLog) per picture, for finding where a picture's time goes (CL2b). On only when the
// environment has ROSTRUM3D_PERF=1: then the `view` reply carries `perf`, every counter that moved since the last
// picture. Off, it costs nothing.
#pragma once
#include <pxr/base/js/value.h>

namespace r3d {

bool perf_on();
PXR_NS::JsObject perf_moved();  // the counters that changed since the last call (name -> change)
// With ROSTRUM3D_TRACE=<file> too: USD's trace (Storm's own timed scopes) is collected, and each `info` request
// appends the tree since the last one to that file and starts a new one (a check's tool: clay_dab_bench.py).
void trace_report();

}  // namespace r3d
