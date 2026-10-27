#include "perf_counters.h"

#include <pxr/base/trace/collector.h>
#include <pxr/base/trace/reporter.h>
#include <pxr/imaging/hd/perfLog.h>

#include <fstream>

#include <cstdlib>
#include <map>
#include <string>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

bool perf_on() {
  static const bool on = [] {
    const char* v = std::getenv("ROSTRUM3D_PERF");
    const bool yes = v && std::string(v) == "1";
    if (yes) HdPerfLog::GetInstance().Enable();
    if (yes && std::getenv("ROSTRUM3D_TRACE")) TraceCollector::GetInstance().SetEnabled(true);
    return yes;
  }();
  return on;
}

JsObject perf_moved() {
  static std::map<TfToken, double> last;
  JsObject out;
  HdPerfLog& log = HdPerfLog::GetInstance();
  for (const TfToken& name : log.GetCounterNames()) {
    const double v = log.GetCounter(name), d = v - last[name];
    last[name] = v;
    if (d != 0) out[name.GetString()] = JsValue(d);
  }
  return out;
}

void trace_report() {
  const char* file = std::getenv("ROSTRUM3D_TRACE");
  if (!file || !perf_on()) return;
  TraceReporterPtr r = TraceReporter::GetGlobalReporter();
  r->UpdateTraceTrees();
  std::ofstream out(file, std::ios::app);
  out << "==== trace report\n";
  r->Report(out);
  r->ClearTree();
}

}  // namespace r3d
