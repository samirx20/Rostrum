// The Qt side: a QQuickRhiItem whose renderer draws the stage with Storm straight into the item's colour texture,
// on Qt Quick's render thread, in the window's own process. The GUI thread only queues pointer events and the camera
// (draw.h has the threading rule). No pxr or GL headers here.
#pragma once
#include <QtQuick/QQuickRhiItem>

#include <atomic>
#include <memory>
#include <mutex>
#include <vector>

#include "draw.h"

// what the render thread measured; read by main.cpp when a run ends
struct Record {
  struct Move {           // one pointer move while sculpting, from the driver's send to the swap that showed it, ms
    double total = 0;     // send -> picture swapped
    double toRender = 0;  // send -> the render thread starts the frame carrying it (event queue + sync)
    double dab = 0, mesh = 0, usd = 0, storm = 0;  // that frame's work (shared by every move it carries)
    double toSwap = 0;    // end of render() -> swap done (Qt's own pass + SwapBuffers)
    int movesInFrame = 0, dabsInFrame = 0, blocksInFrame = 0;
  };
  struct Frame {
    double swap = 0;     // ms, when its swap returned
    double render = 0;   // render() time, ms (apply + Storm, glFinish included)
    double storm = 0;
    double release = 0;  // a stroke's end in this frame: apply time (the stroke re-applied as one unit)
  };
  std::mutex m;
  std::vector<Move> moves;
  std::vector<Frame> frames;
  std::string glRenderer;
  int clayBlocks = 0;
  void clear() {
    std::lock_guard<std::mutex> l(m);
    moves.clear();
    frames.clear();
  }
};

extern std::atomic<double> g_sent;  // ms: when the driver sent the event now being delivered (0 = not driven)

class HydraView : public QQuickRhiItem {
  Q_OBJECT
  Q_PROPERTY(QString stats READ stats NOTIFY statsChanged)

 public:
  HydraView();
  QQuickRhiItemRenderer* createRenderer() override;
  QString stats() const { return stats_; }
  void setStats(const QString& s) {
    if (s != stats_) { stats_ = s; Q_EMIT statsChanged(); }
  }
  // GUI-thread state, handed to the renderer in synchronize()
  pview::Cam cam;
  pview::Options opts;
  std::vector<pview::Input> queue;
  std::shared_ptr<Record> rec = std::make_shared<Record>();
  QString shotPath;  // set -> the next frame's pixels are saved there (then cleared)

 Q_SIGNALS:
  void statsChanged();

 protected:
  void mousePressEvent(QMouseEvent* e) override;
  void mouseMoveEvent(QMouseEvent* e) override;
  void mouseReleaseEvent(QMouseEvent* e) override;

 private:
  void push(pview::Input::Kind k, QMouseEvent* e);
  QString stats_;
  bool orbiting_ = false, sculpting_ = false;
  QPointF last_;
  bool immediate_ = qEnvironmentVariable("PVIEW_TICK") != "1";  // PVIEW_TICK=1: wait for Qt's frame tick (to compare)
};
