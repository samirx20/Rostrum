// The core's state between requests (the stage, Hydra, colour, memory watch) and the requests that use it.
#pragma once
#include <pxr/base/js/value.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/mesh.h>

#include <atomic>
#include <exception>
#include <functional>
#include <map>
#include <future>
#include <memory>
#include <mutex>
#include <optional>

#include "clay_store.h"
#include "gpu_mem.h"
#include "hydra.h"
#include "image_out.h"
#include "shm.h"
#include "stage_build.h"
#include "view_post.h"

namespace r3d {

class Core {
 public:
  Core();
  explicit Core(GlContext::Borrow);  // inside a window: its GL context, current on the calling thread, is Hydra's
  void set_target(const ViewTarget& t) { target_ = t; }
  int views_drawn() const { return views_drawn_; }  // `view` pictures drawn so far (into the target or shared memory)
  PXR_NS::JsObject scene(const PXR_NS::JsObject& a);
  PXR_NS::JsObject render(const PXR_NS::JsObject& a, const std::function<void(const PXR_NS::JsObject&)>& progress);
  PXR_NS::JsObject view(const PXR_NS::JsObject& a);
  PXR_NS::JsObject pick(const PXR_NS::JsObject& a);
  PXR_NS::JsObject geometry(const PXR_NS::JsObject& a);  // geometry_request.cpp
  PXR_NS::JsObject unfold(const PXR_NS::JsObject& a);    // geometry_request.cpp (unfold.h)
  PXR_NS::JsObject save(const PXR_NS::JsObject& a);
  PXR_NS::JsObject sculpt(const PXR_NS::JsObject& a);     // clay_requests.cpp
  PXR_NS::JsObject clay_info(const PXR_NS::JsObject& a);  // clay_requests.cpp
  PXR_NS::JsObject clay_bench(const PXR_NS::JsObject& a); // clay_requests.cpp (a check: the replay bench)
  PXR_NS::JsObject clay_pose(const PXR_NS::JsObject& a);  // clay_requests.cpp (CL5: a pose drag's live bone moves)
  PXR_NS::JsObject clay_grid(const PXR_NS::JsObject& a);  // clay_requests.cpp (CL5: the rest clay's inside, sampled)
  PXR_NS::JsObject xform(const PXR_NS::JsObject& a);      // xform_request.cpp (a gizmo drag's live move)
  PXR_NS::JsObject copies_live(const PXR_NS::JsObject& a); // copies_request.cpp (a Count / Spacing drag, a copy moved)
  PXR_NS::JsObject material(const PXR_NS::JsObject& a);    // material_request.cpp (a material field's drag, live)
  PXR_NS::JsObject sees(const PXR_NS::JsObject& a);        // copies_request.cpp (which points a camera sees)
  PXR_NS::JsObject texels(const PXR_NS::JsObject& a);      // texels_request.cpp (which texel each pixel sees)
  // sim_request.cpp (brief 25): rigid bodies with Jolt, written to <folder>/bodies.bin
  PXR_NS::JsObject simulate(const PXR_NS::JsObject& a, const std::function<void(const PXR_NS::JsObject&)>& progress);
  PXR_NS::JsObject info();

  // A live stroke's dab, its clay work started early (clay_requests.cpp). The window (view/viewport_item.cpp) calls
  // sculpt_ahead from the GUI thread when it posts a `sculpt` dab and nothing else is waiting for an answer: the dabs
  // are applied and their blocks meshed on a worker while the request travels to the render thread, which then only
  // writes the blocks to USD and draws. The worker never touches the stage (the camera and the clay's place come from
  // the stroke's begin, cached in stroke_view_) and nothing else calls the clay store until the request is answered.
  // True when it started. Thread rules: sculpt_ahead on any one thread, never while the render thread answers.
  bool sculpt_ahead(const PXR_NS::JsObject& request);
  // the render thread, before answering anything else: waits for a started dab (its result kept for its request)
  void join_ahead();

 private:
  Hydra& hydra();  // the GL context and engines are made on first use
  void need_scene(const char* request) const;
  PXR_NS::SdfPath camera(const std::string& id, const char* request) const;
  void check_frame(int frame, const char* where) const;
  // the built mesh of a top-level `mesh` or `combine` item (geometry, unfold); loud about anything else
  PXR_NS::UsdGeomMesh built_mesh(const std::string& id, const char* request) const;
  // after a scene: each copies item seen by a camera keeps only the copies it sees (copies_request.cpp); its info
  PXR_NS::JsObject seen_test(double* ms);
  // a pick that hit a copy: `out` names the copies item, the copy and its source; false when it is no copy
  bool pick_copy(const PXR_NS::SdfPath& hit, const PXR_NS::SdfPath& instancer, int instance, int frame,
                 const PXR_NS::GfVec3d& point, PXR_NS::JsObject* out) const;

  PXR_NS::UsdStageRefPtr stage_;
  bool borrow_gl_ = false;
  ViewTarget target_;
  int views_drawn_ = 0;
  std::unique_ptr<Hydra> hydra_;
  ColorOut color_;
  GpuMemWatch mem_;
  bool loaded_ = false;
  BuildResult built_;
  PXR_NS::JsObject scene_;  // the loaded scene as sent (geometry names combine inputs from it)
  std::unique_ptr<Shm> shm_;  // the live viewport's pictures
  std::unique_ptr<ViewPost> post_;  // after hydra_: released while its GL context is still there
  std::string xform_id_;  // the item the last `xform` moved, and its prim
  PXR_NS::SdfPath xform_path_;
  std::map<std::string, PXR_NS::JsObject> material_props_;  // each material's props as the live `material` left them
  std::map<std::string, copies::State> copies_;  // the copies items as laid out (copies.h), by id
  std::unique_ptr<clay::Store> clay_;  // the clays' volumes and block prims (made with the stage, gone first)
  std::atomic<bool> final_look_{false};  // 3d-cl4: the last view was the Final look (Cycles): strokes begun get no coarse preview
  // the live stroke's camera and clay placement, from its begin (clay_requests.cpp: StrokeView)
  struct StrokeView;
  std::shared_ptr<const StrokeView> stroke_view_;
  std::mutex ahead_m_;                          // ahead_ and ahead_key_: set on the GUI thread, taken on the render one
  std::future<clay::SculptReply> ahead_;        // a dab started early, running
  std::string ahead_key_;                       // its points (the request it belongs to)
  std::optional<clay::SculptReply> ahead_done_;  // its result, waiting for its request
  std::exception_ptr ahead_error_;
  std::string ahead_done_key_;
};

}  // namespace r3d
