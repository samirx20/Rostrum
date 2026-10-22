r"""? › Report a problem (INTERACTION.md 1.17): the log folder opens and the details a report needs are copied, so the
person pastes them into a mail or an issue. The launcher writes every run's log to %LOCALAPPDATA%\Rostrum\logs
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


def report(app_name: str, app: str, version: str) -> str:
    """Open the log folder, copy the details; returns the line the message bar shows."""
    from rostrum_core import userhome
    text = details(app_name, app, version)
    if userhome.scripted():
        return f"Report a problem: would open {LOGS} and copy {len(text.splitlines())} lines (a scripted run does neither)."
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices, QGuiApplication
    QGuiApplication.clipboard().setText(text)
    if LOGS.is_dir():
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOGS)))
        return f"The log folder is open, and {app_name} {version} with the log's name is copied: paste it into your report."
    return f"No log folder yet ({LOGS}): {app_name} {version} and your system are copied: paste them into your report."
