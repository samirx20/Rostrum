#include "viewport_item.h"

#include <QtCore/QCoreApplication>
#include <QtCore/QMetaObject>
#include <QtCore/QPointer>
#include <QtCore/QThread>
#include <QtQuick/QQuickWindow>
#include <rhi/qrhi.h>  // Qt 6.12: in the versioned headers (Qt6::GuiPrivate)

#include <chrono>
#include <cstdlib>
#include <future>
#include <memory>

#include "window_core.h"

namespace {

// ROSTRUM3D_DAB_OVERLAP=0: the dab overlap off (to measure it), as before: a dab starts early only while the render
// thread is idle and the GUI thread has every answer
bool overlap_on() {
  static const bool on = [] {
    const char* e = std::getenv("ROSTRUM3D_DAB_OVERLAP");
    return !(e && e[0] == '0');
  }();
  return on;
}

double now_ms() {
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

// the reply line with the frame's number and times added (a reply is one JSON object)
QString stamped(const std::string& reply, int frame, double t0, double t1) {
  QString s = QString::fromStdString(reply);
  const qsizetype end = s.lastIndexOf(QLatin1Char('}'));
  if (end < 0) return s;
  return s.left(end) + QStringLiteral(",\"frame\":%1,\"tRender0\":%2,\"tRender1\":%3}")
                           .arg(frame).arg(t0, 0, 'f', 3).arg(t1, 0, 'f', 3);
}

class Renderer : public QQuickRhiItemRenderer {
 public:
  ~Renderer() override {
    QObject::disconnect(swapped_);
    if (Rostrum3DView* v = item_.data()) v->setCore(nullptr);
    if (ending_.valid()) ending_.wait();  // the worker uses the core
    core_.reset();  // render thread, the window's context current (the renderer is destroyed there)
  }

  void initialize(QRhiCommandBuffer*) override {}

  void synchronize(QQuickRhiItem* item) override {
    auto* v = static_cast<Rostrum3DView*>(item);
    item_ = v;
    Rostrum3DView::Taken t = v->take();
    for (auto& r : t.requests) in_.push_back(std::move(r));
    if (t.blank) {
      view_.clear();
      newView_ = false;
      blank_ = true;
    }
    if (!t.view.empty()) {
      view_ = std::move(t.view);
      newView_ = true;
      blank_ = false;
    }
    if (!window_) {
      window_ = item->window();
      swapped_ = QObject::connect(window_, &QQuickWindow::frameSwapped, window_, [this] { swapped(); },
                                  Qt::DirectConnection);
    }
  }

  void render(QRhiCommandBuffer* cb) override {
    const QSize sz = colorTexture()->pixelSize();
    const int frame = ++frame_;
    std::unique_lock<std::mutex> busy;  // no dab starts early while this frame uses the core (Rostrum3DView::post)
    if (Rostrum3DView* v = item_.data()) busy = std::unique_lock<std::mutex>(v->coreBusy());
    cb->beginExternal();  // plain GL from here: the window's context is current; Qt restores its own state after
    if (!core_) {
      core_ = std::make_unique<r3d::WindowCore>();
      const QString gl = QString::fromStdString(core_->gl_renderer());
      QPointer<Rostrum3DView> i = item_;
      QMetaObject::invokeMethod(item_, [i, gl] { if (i) i->setGlRenderer(gl); }, Qt::QueuedConnection);
      if (item_) item_->setCore(core_.get());
    }
    const bool fresh = core_->set_texture(unsigned(colorTexture()->nativeTexture().object), sz.width(), sz.height());
    const int before = core_->views_drawn();
    std::vector<std::pair<int, QString>> answers;
    if (ending_.valid() && ending_.wait_for(std::chrono::seconds(0)) == std::future_status::ready) {
      answers.emplace_back(endingId_, stamped(ending_.get(), frame, endingT0_, now_ms()));
      ending_ = {};
    }
    size_t done = 0;
    bool restaged = false;  // a request changed the stage without a picture of its own (xform): draw the view again
    for (; done < in_.size() && !ending_.valid(); ++done) {
      const auto& [id, line] = in_[done];
      const double t0 = now_ms();
      // the slow ones (a stroke's end, a scene's clays brought to their steps) on a worker: the window keeps drawing
      // meanwhile, the view its last picture; the next frame after the worker is done collects the answer and draws
      if (r3d::WindowCore::runs_aside(line)) {
        endingId_ = id;
        endingT0_ = t0;
        r3d::WindowCore* core = core_.get();
        QPointer<Rostrum3DView> i = item_;
        ending_ = std::async(std::launch::async, [core, line, i] {
          std::string r = core->answer_without_gl(line);
          if (Rostrum3DView* v = i.data())  // a frame to collect it
            QMetaObject::invokeMethod(v, [i] { if (i) i->update(); }, Qt::QueuedConnection);
          return r;
        });
        continue;
      }
      const std::string r = core_->answer(line);
      restaged = restaged || line.rfind("{\"xform\"", 0) == 0;
      answers.emplace_back(id, stamped(r, frame, t0, now_ms()));
    }
    in_.erase(in_.begin(), in_.begin() + done);
    QString drawn;
    // the newest picture; the last one again on a new texture (a resize) unless a request (a dab) just drew one.
    // Nothing while a request runs on its worker: the core is its alone (the texture keeps the last picture)
    if (ending_.valid()) {
    } else if (!view_.empty() && (newView_ || ((fresh || restaged) && core_->views_drawn() == before))) {
      const double t0 = now_ms();
      const std::string r = core_->answer(view_);
      if (newView_) drawn = stamped(r, frame, t0, now_ms());
      newView_ = false;
    } else if (blank_) {
      core_->clear();
      blank_ = false;
    }
    cb->endExternal();
    // done with the core: a dab posted from here on may start at once. Its answers are counted here, not when the
    // GUI thread gets them (that hand-back took 5-50 ms, while the render thread sat idle)
    if (Rostrum3DView* v = item_.data(); v && !answers.empty() && overlap_on()) v->answeredSome(int(answers.size()));
    if (busy.owns_lock()) busy.unlock();
    QPointer<Rostrum3DView> i = item_;
    if (!answers.empty() || !drawn.isEmpty())
      QMetaObject::invokeMethod(item_, [i, answers = std::move(answers), drawn] {
        if (!i) return;
        if (!overlap_on()) i->answeredSome(int(answers.size()));  // before the replies: one may post the next dab
        for (const auto& [id, r] : answers) Q_EMIT i->answered(id, r);
        if (!drawn.isEmpty()) Q_EMIT i->drawn(drawn);
      }, Qt::QueuedConnection);
    shown_.push_back(frame);
  }

 private:
  void swapped() {  // render thread, after SwapBuffers: the frames rendered since the last swap are on screen
    if (shown_.empty() || !item_) return;
    const double t = now_ms();
    QPointer<Rostrum3DView> i = item_;
    QMetaObject::invokeMethod(item_, [i, frames = std::move(shown_), t] {
      if (i) for (int f : frames) Q_EMIT i->frameShown(f, t);
    }, Qt::QueuedConnection);
    shown_.clear();
  }

  std::unique_ptr<r3d::WindowCore> core_;
  std::vector<std::pair<int, std::string>> in_;
  std::future<std::string> ending_;  // a request running on its worker (WindowCore::runs_aside, answer_without_gl)
  int endingId_ = 0;
  double endingT0_ = 0;
  std::string view_;
  bool newView_ = false, blank_ = false;
  int frame_ = 0;
  std::vector<int> shown_;
  QPointer<Rostrum3DView> item_;
  QQuickWindow* window_ = nullptr;
  QMetaObject::Connection swapped_;
};

}  // namespace

Rostrum3DView::Rostrum3DView() {
  setColorBufferFormat(TextureFormat::RGBA8);
  setMirrorVertically(true);  // the core draws in GL's row order (bottom row first); Qt Quick shows top row first
}

QQuickRhiItemRenderer* Rostrum3DView::createRenderer() { return new Renderer; }

void Rostrum3DView::post(int id, const QString& line) {
  std::string text = line.toStdString();
  const int waiting = unanswered_.load();
  if (waiting <= 1 && r3d::WindowCore::is_stroke_dab(text) && !std::getenv("ROSTRUM3D_NO_AHEAD")) {
    // while the render thread is out of the core and nothing waits; or (the dab overlap) while the one request
    // waiting is the dab whose picture the render thread is drawing now: its clay work is done, this one's starts
    // beside the draw. Else it is answered in order there, as any request
    std::unique_lock<std::mutex> idle(busyM_, std::try_to_lock);
    std::lock_guard<std::mutex> l(coreM_);
    if (core_ && waiting == 0 && idle.owns_lock()) core_->ahead(text);
    else if (core_ && !idle.owns_lock() && overlap_on()) core_->ahead(text, true);
  }
  ++unanswered_;
  {
    std::lock_guard<std::mutex> l(m_);
    queue_.requests.emplace_back(id, std::move(text));
  }
  request();
}

void Rostrum3DView::setCore(r3d::WindowCore* core) {
  std::lock_guard<std::mutex> l(coreM_);
  core_ = core;
}

void Rostrum3DView::show(const QString& viewLine) {
  {
    std::lock_guard<std::mutex> l(m_);
    queue_.view = viewLine.toStdString();
    queue_.blank = false;
  }
  request();
}

void Rostrum3DView::blank() {
  {
    std::lock_guard<std::mutex> l(m_);
    queue_.view.clear();
    queue_.blank = true;
  }
  request();
}

Rostrum3DView::Taken Rostrum3DView::take() {
  std::lock_guard<std::mutex> l(m_);
  Taken t = std::move(queue_);
  queue_ = Taken{};
  return t;
}

void Rostrum3DView::setGlRenderer(const QString& s) {
  if (s != glRenderer_) {
    glRenderer_ = s;
    Q_EMIT glRendererChanged();
  }
}

void Rostrum3DView::request() {
  if (QThread::currentThread() == thread()) kick();
  else QMetaObject::invokeMethod(this, &Rostrum3DView::kick, Qt::QueuedConnection);
}

void Rostrum3DView::kick() {
  update();
  // draw now rather than at Qt's next frame tick (it follows the display's refresh: ~15 ms of every move in the
  // proof); the render loop still waits for the frame before, so frames never pile up
  if (QQuickWindow* w = window()) {
    QEvent ev(QEvent::UpdateRequest);
    QCoreApplication::sendEvent(w, &ev);
  }
}
