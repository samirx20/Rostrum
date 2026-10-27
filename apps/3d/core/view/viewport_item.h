// Rostrum3DView: the live 3D view drawn inside the app's own window (proofs/3d-viewport). A QQuickRhiItem (OpenGL)
// whose renderer holds the engine's Core (core/src/window_core.h) on Qt Quick's render thread: the same requests and
// replies as the engine program (ENGINE_CONTRACT.md), with `view` pictures drawn straight into this item's texture.
//
// Threading: the render thread owns the stage, the clay and Hydra; nothing else touches them. Requests come in from
// any thread (post / show), wait in a queue, are moved over in synchronize() and answered in render(), in order, then
// the newest picture is drawn. Replies go back to the GUI thread as signals. A request asks for a frame at once
// (draw on input: an UpdateRequest, not Qt's next frame tick).
#pragma once
#include <QtQml/qqmlregistration.h>
#include <QtQuick/QQuickRhiItem>

#include <mutex>
#include <string>
#include <utility>
#include <vector>

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
  QString glRenderer_;
};
