"""Pictures from Python for QML (image://<name>/<id>): made ahead, kept in memory, read on the screen thread only.

Why only there: Qt reads an `Image { asynchronous: true }` on its own loader thread, which holds Qt's picture lock
while it waits for Python's lock (the GIL) to call `requestImage`. Python code on the screen thread that makes such an
Image (a scripted click or key, a slot that fills a list of tiles) holds the GIL and waits for Qt's picture lock: both
wait for good. That froze the Brush panel on its first opening (2026-10-25). So a Python picture is made ahead (on a
worker thread, or it is cheap) and read with `Image { asynchronous: false }`, a lookup on the screen thread. Asked
from any other thread it fails loudly (a QML warning), so an `asynchronous: true` on one shows at once.

    class Thumbs(ScreenImages):
        def picture(self, id_): ...            # the kept picture for `id_` (QImage(), none)

`start` (app.py) takes only these as providers.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


class ScreenImages(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, id_, size, requested):  # noqa: N802 (Qt's name)
        app = QCoreApplication.instance()
        if app is not None and QThread.currentThread() != app.thread():
            raise RuntimeError(f"{type(self).__name__}: image {id_!r} asked off the screen thread; an Image showing it "
                               "must be `asynchronous: false` (rostrum_gui/screen_images.py says why)")
        return self.picture(id_)

    def picture(self, id_: str) -> QImage:
        raise NotImplementedError
