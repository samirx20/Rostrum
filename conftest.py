"""Tests run this checkout's code (see checkout_paths.py), and every test shares one screen-capable Qt app.

Qt allows one application object per process, and the first one made wins. A test file that made a plain
QCoreApplication while being loaded left a screen-less app for every later file, and the first clipboard or window
call crashed the run. Making the one QGuiApplication here, before any test file is loaded, settles it for all.
"""
import os

import checkout_paths

checkout_paths.use_this_checkout()

try:
    from PySide6.QtGui import QGuiApplication
except ImportError:                       # an environment without Qt (engine-only tests)
    QGuiApplication = None
if QGuiApplication is not None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    APP = QGuiApplication.instance() or QGuiApplication([])
