#include "view.h"

#include <cstdio>

#include <QtCore/QCoreApplication>
#include <QtGui/QImage>
#include <QtGui/QMouseEvent>
#include <QtGui/QOpenGLContext>
#include <rhi/qrhi.h>  // Qt 6.12: in the versioned headers (Qt6::GuiPrivate)
#include <QtQuick/QQuickWindow>

std::atomic<double> g_sent{0};

namespace {

class Renderer : public QQuickRhiItemRenderer {
 public:
  ~Renderer() override {
    QObject::disconnect(swapped_);
    scene_.reset();  // render thread, Qt's context current (the item renderer is destroyed there)
  }

  void initialize(QRhiCommandBuffer*) override {}

  void synchronize(QQuickRhiItem* item) override {
    auto* v = static_cast<HydraView*>(item);
    cam_ = v->cam;
    opts_ = v->opts;
    rec_ = v->rec;
    in_.insert(in_.end(), v->queue.begin(), v->queue.end());
    v->queue.clear();
    if (!v->shotPath.isEmpty()) {
      shot_ = v->shotPath;
      v->shotPath.clear();
    }
    if (!window_) {
      window_ = item->window();
      swapped_ = QObject::connect(window_, &QQuickWindow::frameSwapped, window_, [this] { swapped(); },
                                  Qt::DirectConnection);
    }
  }

  void render(QRhiCommandBuffer* cb) override {
    const double t0 = pview::now_ms();
    const QSize sz = colorTexture()->pixelSize();
    cb->beginExternal();  // plain GL from here: Qt's context is current, its state is restored after
    if (!scene_) {
      if (auto* c = QOpenGLContext::currentContext())
        std::fprintf(stderr, "Qt context: %d.%d profile %d\n", c->format().majorVersion(), c->format().minorVersion(),
                     int(c->format().profile()));
      scene_ = std::make_unique<pview::Scene>(opts_);
      std::lock_guard<std::mutex> l(rec_->m);
      rec_->glRenderer = scene_->gl_renderer();
    }
    Pending p;
    p.inputs = std::move(in_);
    in_.clear();
    const bool releases = std::any_of(p.inputs.begin(), p.inputs.end(),
                                      [](const pview::Input& e) { return e.kind == pview::Input::End; });
    scene_->apply(p.inputs, cam_, sz.width(), sz.height(), p.t);
    scene_->draw(unsigned(colorTexture()->nativeTexture().object), sz.width(), sz.height(), cam_, p.t);
    if (!shot_.isEmpty()) {
      const auto px = scene_->read(sz.width(), sz.height());
      QImage(px.data(), sz.width(), sz.height(), QImage::Format_RGBA8888).save(shot_);
      shot_.clear();
    }
    cb->endExternal();
    p.start = t0;
    p.end = pview::now_ms();
    p.release = releases ? p.t.dab : 0;
    pending_.push_back(std::move(p));
    {
      std::lock_guard<std::mutex> l(rec_->m);
      rec_->clayBlocks = scene_->clay_blocks();
    }
  }

 private:
  struct Pending {
    std::vector<pview::Input> inputs;
    pview::FrameTimes t;
    double start = 0, end = 0, release = 0;
  };

  // after SwapBuffers: every move drawn in the frames just shown is on screen now
  void swapped() {
    const double now = pview::now_ms();
    std::lock_guard<std::mutex> l(rec_->m);
    for (const Pending& p : pending_) {
      int moves = 0;
      for (const auto& e : p.inputs) moves += e.kind == pview::Input::Move || e.kind == pview::Input::Orbit;
      for (const auto& e : p.inputs) {
        if ((e.kind != pview::Input::Move && e.kind != pview::Input::Orbit) || e.tSent <= 0) continue;
        Record::Move m;
        m.total = now - e.tSent;
        m.toRender = p.start - e.tSent;
        m.dab = p.t.dab;
        m.mesh = p.t.mesh;
        m.usd = p.t.usd;
        m.storm = p.t.storm;
        m.toSwap = now - p.end;
        m.movesInFrame = moves;
        m.dabsInFrame = p.t.dabs;
        m.blocksInFrame = p.t.blocks;
        rec_->moves.push_back(m);
      }
      rec_->frames.push_back({now, p.end - p.start, p.t.storm, p.release});
    }
    pending_.clear();
  }

  std::unique_ptr<pview::Scene> scene_;
  pview::Cam cam_;
  pview::Options opts_;
  std::vector<pview::Input> in_;
  std::vector<Pending> pending_;
  std::shared_ptr<Record> rec_;
  QString shot_;
  QQuickWindow* window_ = nullptr;
  QMetaObject::Connection swapped_;
};

}  // namespace

HydraView::HydraView() {
  setAcceptedMouseButtons(Qt::LeftButton | Qt::RightButton);
  setColorBufferFormat(TextureFormat::RGBA8);
}

QQuickRhiItemRenderer* HydraView::createRenderer() { return new Renderer; }

void HydraView::push(pview::Input::Kind k, QMouseEvent* e) {
  pview::Input in;
  in.kind = k;
  const qreal dpr = window() ? window()->effectiveDevicePixelRatio() : 1.0;
  in.x = float(e->position().x() * dpr);
  in.y = float(e->position().y() * dpr);
  in.tRecv = pview::now_ms();
  in.tSent = g_sent.load() > 0 ? g_sent.load() : in.tRecv;
  queue.push_back(in);
  update();
  // Draw now rather than at Qt's next frame tick: update() alone waits for the window's update request, which
  // Windows paces at the display's refresh (~15 ms of every move in the first runs). The update request sent here
  // syncs at once (the render loop waits for its previous frame first, so frames never pile up).
  if (immediate_ && window()) {
    QEvent ev(QEvent::UpdateRequest);
    QCoreApplication::sendEvent(window(), &ev);
  }
}

void HydraView::mousePressEvent(QMouseEvent* e) {
  last_ = e->position();
  if (e->button() == Qt::RightButton) {
    orbiting_ = true;
  } else {
    sculpting_ = true;
    push(pview::Input::Begin, e);
  }
  e->accept();
}

void HydraView::mouseMoveEvent(QMouseEvent* e) {
  if (orbiting_) {
    const QPointF d = e->position() - last_;
    cam.yaw -= d.x() * 0.006;
    cam.pitch = std::clamp(cam.pitch + d.y() * 0.006, -1.2, 1.4);
    last_ = e->position();
    push(pview::Input::Orbit, e);
  } else if (sculpting_) {
    push(pview::Input::Move, e);
  }
}

void HydraView::mouseReleaseEvent(QMouseEvent* e) {
  if (orbiting_) {
    orbiting_ = false;
  } else if (sculpting_) {
    sculpting_ = false;
    push(pview::Input::End, e);
  }
}
