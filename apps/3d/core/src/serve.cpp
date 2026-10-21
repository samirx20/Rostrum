#include "serve.h"

#include <pxr/base/js/json.h>
#include <pxr/base/tf/errorMark.h>
#include <pxr/pxr.h>

#include <functional>
#include <map>
#include <memory>
#include <string>

#include "args.h"
#include "error.h"
#include "inspect.h"
#include "requests.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
void send(std::FILE* out, const JsObject& o) {
  std::fputs(JsWriteToString(JsValue(o)).c_str(), out);
  std::fputc('\n', out);
  std::fflush(out);
}

std::string read_line(std::FILE* in, bool* eof) {
  std::string line;
  for (int c; (c = std::fgetc(in)) != EOF;) {
    if (c == '\n') return line;
    line.push_back(char(c));
  }
  *eof = true;
  return line;
}
}  // namespace

int serve(std::FILE* in, std::FILE* out) {
  Core core;
  const auto progress = [out](const JsObject& o) { send(out, o); };
  const std::map<std::string, std::function<JsObject(const JsObject&)>> handlers = {
      {"scene", [&](const JsObject& a) { return core.scene(a); }},
      {"render", [&](const JsObject& a) { return core.render(a, progress); }},
      {"pick", [&](const JsObject& a) { return core.pick(a); }},
      {"inspect_usd", [&](const JsObject& a) { return inspect_usd(Args(a, "inspect_usd", {"file"}).str("file")); }},
      {"save", [&](const JsObject& a) { return core.save(a); }},
      {"info", [&](const JsObject&) { return core.info(); }},
  };
  for (bool eof = false; !eof;) {
    const std::string line = read_line(in, &eof);
    if (line.find_first_not_of(" \t\r") == std::string::npos) continue;
    try {
      JsParseError perr;
      JsValue req = JsParseString(line, &perr);
      if (!req.IsObject() || req.GetJsObject().size() != 1)
        throw Error("request: needs one JSON object with one key, like {\"render\": {...}}" +
                    (perr.reason.empty() ? std::string() : " (" + perr.reason + ")"));
      const auto& [name, body] = *req.GetJsObject().begin();
      if (name == "quit") { send(out, JsObject{{"ok", JsValue(true)}}); return 0; }
      auto h = handlers.find(name);
      if (h == handlers.end()) {
        std::string list = "quit";
        for (const auto& kv : handlers) list += ", " + kv.first;
        throw Error("request: no request \"" + name + "\". Accepted: " + list);
      }
      if (!body.IsObject()) throw Error(name + ": its value must be an object");
      send(out, h->second(body.GetJsObject()));
    } catch (const std::exception& e) {
      send(out, JsObject{{"ok", JsValue(false)}, {"error", JsValue(std::string(e.what()))}});
    }
  }
  return 0;
}

}  // namespace r3d
