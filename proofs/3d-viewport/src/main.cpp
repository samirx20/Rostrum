// P-3D-viewport proof: one Qt Quick window, a QQuickRhiItem drawing a USD stage with Storm in-process, the clay core
// sculpted in the same process. Drives itself with QTest mouse events (60 per second, like the CL2b hop runs) and
// writes what it measured.
//
//   r3d_viewport_proof.exe --mode sculpt --brush medium|quarter --out <folder>
//   r3d_viewport_proof.exe --mode orbit --items 300 [--interval 16|1] --out <folder>
//   other: --moves N, --vsync 0|1, --loop threaded|basic, --no-finish, --interactive (no driver; drag yourself)
#include <windows.h>
#include <psapi.h>

#include <QtCore/QCommandLineParser>
#include <QtCore/QDir>
#include <QtCore/QFile>
#include <QtCore/QJsonArray>
#include <QtCore/QJsonDocument>
#include <QtCore/QJsonObject>
#include <QtCore/QTimer>
#include <QtGui/QGuiApplication>
#include <QtGui/QOffscreenSurface>
#include <QtGui/QOpenGLContext>
#include <QtGui/QOpenGLFunctions>
#include <QtGui/QSurfaceFormat>
#include <QtQml/QQmlApplicationEngine>
#include <QtQuick/QQuickWindow>
#include <QtTest/QTest>

#include <algorithm>
#include <cstdio>
#include <functional>

#include "view.h"

// draw on the fast graphics chip (the RTX), not the built-in one
extern "C" {
__declspec(dllexport) DWORD NvOptimusEnablement = 1;
__declspec(dllexport) int AmdPowerXpressRequestHighPerformance = 1;
}

namespace {

const char* kQml = R"(
import QtQuick
import PView
Window {
  width: 1280; height: 800; visible: false; color: "#1c1d20"
  title: "Rostrum3D viewport proof: Storm in the window's process"
  HydraView { id: view; objectName: "view"; anchors.fill: parent }
  Rectangle {
    x: 16; y: 16; radius: 8; color: "#d0202226"
    width: label.implicitWidth + 24; height: label.implicitHeight + 16
    Text { id: label; anchors.centerIn: parent; color: "#e8e8ea"; font.pixelSize: 14; text: view.stats }
  }
}
)";

double pct(std::vector<double> v, double p) {
  if (v.empty()) return 0;
  std::sort(v.begin(), v.end());
  return v[std::min(v.size() - 1, size_t(p * (v.size() - 1) + 0.5))];
}

QJsonObject spread(const std::vector<double>& v) {
  return QJsonObject{{"median", pct(v, 0.5)}, {"p90", pct(v, 0.9)}, {"max", pct(v, 1.0)}, {"n", int(v.size())}};
}

struct Mem {
  double peakWs = 0, ws = 0, priv = 0;  // MB
};
Mem mem() {
  PROCESS_MEMORY_COUNTERS_EX c{};
  GetProcessMemoryInfo(GetCurrentProcess(), reinterpret_cast<PROCESS_MEMORY_COUNTERS*>(&c), sizeof c);
  return {c.PeakWorkingSetSize / 1048576.0, c.WorkingSetSize / 1048576.0, c.PrivateUsage / 1048576.0};
}

double thread_cpu_ms() {
  FILETIME a, b, k, u;
  GetProcessTimes(GetCurrentProcess(), &a, &b, &k, &u);
  auto ms = [](FILETIME f) { return (double(f.dwHighDateTime) * 4294967296.0 + f.dwLowDateTime) / 1e4; };
  return ms(k) + ms(u);
}

// one scripted step of the driver
struct Act {
  enum Kind { Press, Move, Release, Pause, Mark, Shot, Done } k;
  QPoint p;
  Qt::MouseButton b = Qt::LeftButton;
};

}  // namespace

int main(int argc, char** argv) {
  QCommandLineParser cl;
  cl.addOptions({{"mode", "sculpt | orbit", "m", "sculpt"}, {"brush", "medium | quarter", "b", "medium"}, {"clay", "ball | head", "c", "ball"},
                 {"items", "extra prims", "n", "0"}, {"moves", "moves per run", "n", "200"},
                 {"interval", "ms between driver moves", "ms", "16"}, {"vsync", "swap interval", "n", "0"},
                 {"loop", "threaded | basic", "l", "threaded"}, {"out", "result folder", "dir", "."},
                 {"no-finish", "no glFinish after Storm"}, {"interactive", "no driver"}});
  {
    QStringList args;
    for (int i = 0; i < argc; ++i) args << QString::fromLocal8Bit(argv[i]);
    cl.parse(args);
  }
  qputenv("QSG_RENDER_LOOP", cl.value("loop").toUtf8());
  QQuickWindow::setGraphicsApi(QSGRendererInterface::OpenGL);
  QSurfaceFormat fmt;
  fmt.setRenderableType(QSurfaceFormat::OpenGL);
  fmt.setVersion(4, 6);
  fmt.setProfile(QSurfaceFormat::CompatibilityProfile);  // Hydra's HgiGL wants 4.5+; Storm uses compat calls too
  fmt.setDepthBufferSize(24);
  fmt.setStencilBufferSize(8);
  fmt.setSwapInterval(cl.value("vsync").toInt());
  QSurfaceFormat::setDefaultFormat(fmt);

  QGuiApplication app(argc, argv);
  std::fprintf(stderr, "platform %s, QT_QPA_PLATFORM=%s QT_OPENGL=%s\n", qPrintable(QGuiApplication::platformName()), qgetenv("QT_QPA_PLATFORM").constData(), qgetenv("QT_OPENGL").constData());
  if (qEnvironmentVariableIsSet("PVIEW_PROBE")) {  // which GL a plain Qt context gets in this process
    std::fprintf(stderr, "raw wgl: %s\n", pview::probe_raw_wgl().c_str());
    for (int prof : {0, 1, 2}) {
      QSurfaceFormat f = fmt;
      f.setProfile(QSurfaceFormat::OpenGLContextProfile(prof));
      QOffscreenSurface s;
      s.setFormat(f);
      s.create();
      QOpenGLContext c;
      c.setFormat(f);
      const bool ok = c.create() && c.makeCurrent(&s);
      std::fprintf(stderr, "probe profile %d: ok %d -> %d.%d %s | %s\n", prof, ok, c.format().majorVersion(),
                   c.format().minorVersion(), ok ? (const char*)c.functions()->glGetString(0x1F02) : "-",
                   ok ? (const char*)c.functions()->glGetString(0x1F01) : "-");
    }
    return 0;
  }
  qmlRegisterType<HydraView>("PView", 1, 0, "HydraView");
  QQmlApplicationEngine engine;
  engine.loadData(kQml);
  if (engine.rootObjects().isEmpty()) return 2;
  auto* win = qobject_cast<QQuickWindow*>(engine.rootObjects().first());
  auto* view = win->findChild<HydraView*>("view");
  win->setFormat(fmt);  // the default format alone gave a GL 1.2 context

  const QString mode = cl.value("mode"), out = cl.value("out");
  QDir().mkpath(out);
  const bool orbit = mode == "orbit";
  view->opts.items = cl.value("items").toInt();
  view->opts.head = cl.value("clay") == "head";
  // quarter: a brush a quarter of the clay across (the ball: 0.3 m; the head: 0.331 m, as CL1b/CL2b measured it)
  view->opts.brushRadius = cl.value("brush") == "quarter" ? (view->opts.head ? 0.331f / 8 : 0.0375f) : 0.012f;
  if (view->opts.head) {
    view->cam.dist = 0.5;
    view->cam.pitch = 0.1;
    view->cam.target[1] = -0.03;
  }
  view->opts.finish = !cl.isSet("no-finish");
  if (orbit) {
    view->cam.dist = 3.2;
    view->cam.pitch = 0.42;
  }

  if (qgetenv("ROSTRUM_BACKGROUND_WINDOWS") == "1") {  // behind the person's work, never takes the keyboard
    win->setProperty("_q_showWithoutActivating", true);
    win->setFlags(win->flags() | Qt::WindowDoesNotAcceptFocus | Qt::WindowStaysOnBottomHint);
  }
  win->setVisible(true);

  // stats label: the last 60 moves
  QTimer label;
  QObject::connect(&label, &QTimer::timeout, [&] {
    std::vector<double> t;
    std::string gl;
    {
      std::lock_guard<std::mutex> l(view->rec->m);
      const auto& m = view->rec->moves;
      for (size_t i = m.size() > 60 ? m.size() - 60 : 0; i < m.size(); ++i) t.push_back(m[i].total);
      gl = view->rec->glRenderer;
    }
    view->setStats(QString("%1 → on screen: median %2 ms · slowest 10% %3 ms\n%4")
                       .arg(orbit ? "orbit move" : "mouse move")
                       .arg(pct(t, 0.5), 0, 'f', 1)
                       .arg(pct(t, 0.9), 0, 'f', 1)
                       .arg(QString::fromStdString(gl)));
  });
  label.start(250);
  if (cl.isSet("interactive")) return app.exec();

  // the script: four strokes across the ball (sculpt) or one long right-drag around the scene (orbit)
  const QPoint c(win->width() / 2, win->height() / 2);
  const int moves = cl.value("moves").toInt();
  std::vector<Act> acts;
  for (int i = 0; i < 20; ++i) acts.push_back({Act::Pause, {}});
  acts.push_back({Act::Mark, {}});
  double cpu0 = 0;
  if (orbit) {
    auto at = [&](int i) {  // back and forth over 600 px, 3 px a move
      const int t = 3 * i % 1200;
      return QPoint(c.x() - 300 + (t < 600 ? t : 1200 - t), c.y());
    };
    acts.push_back({Act::Press, at(0), Qt::RightButton});
    for (int i = 1; i <= moves; ++i) acts.push_back({Act::Move, at(i)});
    acts.push_back({Act::Release, at(moves), Qt::RightButton});
  } else {
    const int strokes = 4, per = moves / strokes;
    for (int s = 0; s < strokes; ++s) {
      const int y = c.y() - 90 + 60 * s;
      acts.push_back({Act::Press, QPoint(c.x() - 160, y)});
      for (int i = 1; i <= per; ++i) acts.push_back({Act::Move, QPoint(c.x() - 160 + 320 * i / per, y)});
      acts.push_back({Act::Release, QPoint(c.x() + 160, y)});
      for (int i = 0; i < 6; ++i) acts.push_back({Act::Pause, {}});
    }
  }
  for (int i = 0; i < 10; ++i) acts.push_back({Act::Pause, {}});
  acts.push_back({Act::Shot, {}});
  for (int i = 0; i < 10; ++i) acts.push_back({Act::Pause, {}});
  acts.push_back({Act::Done, {}});

  size_t next = 0;
  double tStart = 0;
  QTimer drive;
  drive.setTimerType(Qt::PreciseTimer);
  const QString tag = orbit ? QString("orbit-%1items-every%2ms").arg(view->opts.items).arg(cl.value("interval"))
                            : QString("sculpt-add-%1-%2").arg(cl.value("brush"), cl.value("clay"));
  QObject::connect(&drive, &QTimer::timeout, [&] {
    if (next >= acts.size()) return;
    const Act a = acts[next++];
    auto send = [&](const std::function<void()>& f) {
      g_sent = pview::now_ms();
      f();
      g_sent = 0;
    };
    switch (a.k) {
      case Act::Press: send([&] { QTest::mousePress(win, a.b, {}, a.p); }); break;
      case Act::Move: send([&] { QTest::mouseMove(win, a.p); }); break;
      case Act::Release: send([&] { QTest::mouseRelease(win, a.b, {}, a.p); }); break;
      case Act::Pause: view->update(); break;
      case Act::Mark: view->rec->clear(); tStart = pview::now_ms(); cpu0 = thread_cpu_ms(); break;
      case Act::Shot:
        view->shotPath = out + "/" + tag + "-item.png";
        view->update();
        break;
      case Act::Done: {
        drive.stop();
        const double wall = pview::now_ms() - tStart, cpu = thread_cpu_ms() - cpu0;
        win->grabWindow().save(out + "/" + tag + "-window.png");
        std::vector<double> total, toRender, dab, mesh, usd, storm, toSwap, frameRender, frameStorm, interval;
        double release = 0;
        QJsonArray raw;
        QJsonObject j;
        {
          std::lock_guard<std::mutex> l(view->rec->m);
          for (const auto& m : view->rec->moves) {
            total.push_back(m.total);
            toRender.push_back(m.toRender);
            dab.push_back(m.dab);
            mesh.push_back(m.mesh);
            usd.push_back(m.usd);
            storm.push_back(m.storm);
            toSwap.push_back(m.toSwap);
            raw.append(QJsonArray{m.total, m.toRender, m.dab, m.mesh, m.usd, m.storm, m.toSwap, m.movesInFrame,
                                  m.dabsInFrame, m.blocksInFrame});
          }
          const auto& f = view->rec->frames;
          for (size_t i = 0; i < f.size(); ++i) {
            frameRender.push_back(f[i].render);
            frameStorm.push_back(f[i].storm);
            if (i) interval.push_back(f[i].swap - f[i - 1].swap);
            release = std::max(release, f[i].release);
          }
          j["gl_renderer"] = QString::fromStdString(view->rec->glRenderer);
          j["clay_blocks"] = view->rec->clayBlocks;
        }
        const Mem m = mem();
        j["run"] = tag;
        j["loop"] = cl.value("loop");
        j["vsync"] = cl.value("vsync").toInt();
        j["glFinish_after_storm"] = view->opts.finish;
        j["brush_radius_m"] = view->opts.brushRadius;
        j["items"] = view->opts.items;
        j["window_px"] = QJsonArray{int(win->width() * win->devicePixelRatio()), int(win->height() * win->devicePixelRatio())};
        j["move_to_screen_ms"] = spread(total);
        j["hops_ms"] = QJsonObject{{"send_to_render_start", spread(toRender)}, {"dabs", spread(dab)},
                                   {"mesh", spread(mesh)}, {"usd", spread(usd)}, {"storm_draw_and_finish", spread(storm)},
                                   {"render_end_to_swap", spread(toSwap)}};
        j["frames"] = QJsonObject{{"render_ms", spread(frameRender)}, {"storm_ms", spread(frameStorm)},
                                  {"swap_to_swap_ms", spread(interval)}, {"count", int(frameRender.size())},
                                  {"fps", wall > 0 ? 1000.0 * frameRender.size() / wall : 0}};
        j["stroke_release_ms_max"] = release;
        j["process_cpu_ms_per_wall_ms"] = wall > 0 ? cpu / wall : 0;
        j["memory_mb"] = QJsonObject{{"peak_working_set", m.peakWs}, {"working_set", m.ws}, {"private", m.priv}};
        j["raw_moves_columns"] = "total toRender dab mesh usd storm toSwap movesInFrame dabsInFrame blocksInFrame";
        j["raw_moves"] = raw;
        QFile fjs(out + "/" + tag + ".json");
        if (!fjs.open(QIODevice::WriteOnly)) std::fprintf(stderr, "cannot write %s\n", qPrintable(fjs.fileName()));
        fjs.write(QJsonDocument(j).toJson());
        std::printf("%s: move->screen median %.1f p90 %.1f max %.1f ms (n=%d); frame render median %.1f; "
                    "swap-to-swap median %.1f p90 %.1f; peak WS %.0f MB; GL %s\n",
                    tag.toUtf8().constData(), pct(total, .5), pct(total, .9), pct(total, 1), int(total.size()),
                    pct(frameRender, .5), pct(interval, .5), pct(interval, .9), m.peakWs,
                    j["gl_renderer"].toString().toUtf8().constData());
        std::fflush(stdout);
        QTimer::singleShot(200, &app, [&] { app.quit(); });
        break;
      }
    }
  });
  // start once the first frame is on screen (the scene and Storm are made in the first render)
  QMetaObject::Connection first;
  first = QObject::connect(win, &QQuickWindow::frameSwapped, &app, [&] {
    QObject::disconnect(first);
    QTimer::singleShot(500, &app, [&] { drive.start(cl.value("interval").toInt()); });
  }, Qt::QueuedConnection);
  QTimer::singleShot(120000, &app, [&] {
    std::fprintf(stderr, "timed out: the window drew no frame / the run did not finish\n");
    app.exit(3);
  });
  return app.exec();
}
