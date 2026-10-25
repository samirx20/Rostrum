r"""? › Report a problem (INTERACTION.md 1.17): a small window (qml ReportDialog.qml) shows the details a report needs
and the log folder, with two buttons: Open log folder, Copy details; the person pastes them into a mail or an issue. The launcher writes every run's log to %LOCALAPPDATA%\Rostrum\logs
(tools/release/rostrum.pyw); a development run without the launcher has none, and the line says so. A scripted run
never opens a folder or touches the person's clipboard: it only says what it would have done.
"""
from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

LOGS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Rostrum" / "logs"     # the launcher's folder (rostrum.pyw)


def newest_log(app: str) -> Path | None:
    logs = sorted(LOGS.glob(f"{app}-*.log")) if LOGS.is_dir() else []
    return logs[-1] if logs else None


def details(app_name: str, app: str, version: str) -> str:
    """What gets copied: the app and its version, the system, and the newest log's path."""
    from PySide6 import __version__ as pyside
    log = newest_log(app)
    return "\n".join([f"{app_name} {version}", f"{platform.system()} {platform.release()} ({platform.version()})",
                      f"Python {sys.version.split()[0]} · Qt for Python {pyside}",
                      f"Log: {log}" if log else f"Log: none yet in {LOGS} (started without the Rostrum launcher)"])


def open_logs() -> str:
    """The Open log folder button: opens it; returns the line the dialog shows. A scripted run only says what it would do."""
    from rostrum_core import userhome
    if not LOGS.is_dir():
        return f"There is no log folder yet ({LOGS}): this run did not start through the Rostrum launcher."
    if userhome.scripted():
        return f"Would open {LOGS} (a scripted run opens no folder)."
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOGS)))
    return "The log folder is open."


def copy_details(app_name: str, app: str, version: str) -> str:
    """The Copy details button: the details go to the clipboard (never in a scripted run); returns the line shown."""
    from rostrum_core import userhome
    if userhome.scripted():
        return "Would copy the details (a scripted run leaves the clipboard alone)."
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.clipboard().setText(details(app_name, app, version))
    return "Copied: paste it into your report."
