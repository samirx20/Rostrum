// Rostrum3DView: the live 3D view drawn inside the app's own window (proofs/3d-viewport). A QQuickRhiItem (OpenGL)
// whose renderer holds the engine's Core (core/src/window_core.h) on Qt Quick's render thread: the same requests and
// replies as the engine program (ENGINE_CONTRACT.md), with `view` pictures drawn straight into this item's texture.
//
// Threading: the render thread owns the stage, the clay and Hydra; nothing else touches them, except a slow request
// that needs no GL (a stroke's end, a scene holding a clay: WindowCore::runs_aside), which render() hands to a worker
// and holds every later request and picture until it is answered, so the window keeps drawing meanwhile. Requests come
// in from any thread (post / show), wait in a queue, are moved over in synchronize() and answered in render(), in
// order, then the newest picture is drawn. Replies go back to the GUI thread as signals. A request asks for a frame at
// once (draw on input: an UpdateRequest, not Qt's next frame tick).
#pragma once
#include <QtQml/qqmlregistration.h>
#include <QtQuick/QQuickRhiItem>

#include <atomic>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

namespace r3d {
class WindowCore;
}

class Rostrum3DView : public QQuickRhiItem {
  Q_OBJECT
  QML_NAMED_ELEMENT(Rostrum3DView)
  Q_PROPERTY(QString glRenderer READ glRenderer NOTIFY glRendererChanged)

 public:
  Rostrum3DView();
  QQuickRhiItemRenderer* createRenderer() override;
  QString glRenderer() const { return glRenderer_; }

  // Any thread. One ENGINE_CONTRACT request line; answered(id, reply) comes back on the GUI thread.
  Q_INVOKABLE void post(int id, const QString& line);
  // Any thread. The picture to show (a `view` request line); replaces one not drawn yet. drawn(reply) comes back.
  Q_INVOKABLE void show(const QString& viewLine);
  // Any thread. Drop the picture: nothing drawn until the next show.
  Q_INVOKABLE void blank();

  // the render thread's side of the queue (viewport_item.cpp)
  struct Taken {
    std::vector<std::pair<int, std::string>> requests;
    std::string view;  // empty: none new
    bool blank = false;
  };
  Taken take();
  void setGlRenderer(const QString& s);
  // the render thread's core, for a dab started early (post): set when made, null before it goes
  void setCore(r3d::WindowCore* core);
  void answeredSome(int n) { unanswered_ -= n; }
  // held by the render thread while it uses the core (render(), up to its replies): a dab is started early only
  // while the render thread is not inside the core, never under a scene, a view or a pose it is drawing (CL7b)
  std::mutex& coreBusy() { return busyM_; }

 Q_SIGNALS:
  // replies carry, besides the engine's own fields, "frame" (the frame that drew it) and "tRender0"/"tRender1"
  // (steady clock ms: on Windows the same clock as Python's time.perf_counter)
  void answered(int id, const QString& reply);
  void drawn(const QString& reply);
  void frameShown(int frame, double tMs);  // that frame's swap returned: it is on screen
  void glRendererChanged();

 private Q_SLOTS:
  void kick();

 private:
  void request();
  std::mutex m_;
  Taken queue_;
  // A `sculpt` dab posted while no other request waits for its answer has its clay work started at once on a worker
  // (WindowCore::ahead): it runs while the request travels to the render thread (Qt's polish and sync, or the frame
  // before still being shown), which then only writes the blocks and draws.
  std::mutex coreM_;
  std::mutex busyM_;
  r3d::WindowCore* core_ = nullptr;
  std::atomic<int> unanswered_{0};
  QString glRenderer_;
};
