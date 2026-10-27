"""The merged title bar's window side (SHELL.md › Window frame; header design SPEC §7 route A).

Windows keeps the window's frame: the shadow, the rounded corners, the 1 px edge, the resize borders, snapping, the
window menu (Alt+Space, right-click) and the snap layouts on the maximise button. Only the caption goes: a native
event filter answers WM_NCCALCSIZE so the client starts at the window's top, and WM_NCHITTEST so the top bar's drag room
reads as the caption (HTCAPTION), its buttons as client (HTCLIENT) and our drawn maximise button as Windows' own
(HTMAXBUTTON). The bar tells us where its buttons are (setZones); the hit test reads that list, never QML.

QML reads the context property `windowChrome` on every window. Where nothing native runs (an offscreen picture, a
check's real window, another system) it is the same object with `native` false, so QML never checks for undefined.
Tried and dropped in the spike (Qt 6.12): `_q_windowsCustomMargins` removes the caption but leaves a 5 px frame strip
at the top; Qt.ExpandedClientAreaHint makes Qt paint its own title bar over the window's content."""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import Property, QAbstractNativeEventFilter, QObject, Signal, Slot

HTCLIENT, HTCAPTION, HTMAXBUTTON, HTTOP, HTTOPLEFT, HTTOPRIGHT = 1, 2, 9, 12, 13, 14
BAR_H = 40                                    # Theme.topBar
WM_NCCREATE, WM_NCCALCSIZE, WM_NCHITTEST, WM_DPICHANGED = 0x81, 0x83, 0x84, 0x2E0
WM_NCMOUSEMOVE, WM_NCLBUTTONDOWN, WM_NCLBUTTONUP, WM_NCLBUTTONDBLCLK, WM_NCMOUSELEAVE = 0xA0, 0xA1, 0xA2, 0xA3, 0x2A2
WM_NCRBUTTONUP, WM_SYSCOMMAND = 0xA5, 0x112


def _inside(x, y, r) -> bool:
    return bool(r) and r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]


def hit_test(x, y, width, maximised, band, zones, max_rect, bar_h=BAR_H) -> int:
    """What the pointer at client pixel (x, y) is over, as Windows asks it. `zones`: the bar's clickable rects
    [x, y, w, h]; `max_rect` the maximise button's (minimise sits left of it at the same width, close right of it).
    The top `band` px resize the window, except when maximised and over the three window buttons."""
    if not 0 <= y < bar_h:
        return HTCLIENT
    buttons_x = max_rect[0] - max_rect[2] if max_rect else width
    if not maximised and y < band and x < buttons_x:
        return HTTOPLEFT if x < band else HTTOPRIGHT if x >= width - band else HTTOP
    if _inside(x, y, max_rect):
        return HTMAXBUTTON
    return HTCLIENT if any(_inside(x, y, z) for z in zones) else HTCAPTION


class WindowChrome(QObject):
    """One window's side of the merged bar: what QML binds to, and what the filter reads on every pointer move."""
    activeChanged = Signal(); maximisedChanged = Signal(); maxHoveredChanged = Signal()
    maxPressedChanged = Signal(); resizeBandChanged = Signal()

    def __init__(self, merged: bool, native: bool, parent=None):
        super().__init__(parent)
        self._merged, self._native = merged, native
        self._active = self._maximised = self._max_hovered = self._max_pressed = False
        self._band, self._zones, self._max_rect = 0, [], ()
        self.win, self.hwnd = None, 0

    def _set(self, attr, value, signal):
        if getattr(self, attr) != value:
            setattr(self, attr, value)
            signal.emit()

    merged = Property(bool, lambda s: s._merged, constant=True)
    native = Property(bool, lambda s: s._native, constant=True)
    active = Property(bool, lambda s: s._active, notify=activeChanged)
    maximised = Property(bool, lambda s: s._maximised, notify=maximisedChanged)
    maxHovered = Property(bool, lambda s: s._max_hovered, notify=maxHoveredChanged)
    maxPressed = Property(bool, lambda s: s._max_pressed, notify=maxPressedChanged)
    resizeBand = Property(int, lambda s: 0 if s._maximised else s._band, notify=resizeBandChanged)

    @Slot("QVariantList", "QVariantList")
    def setZones(self, rects, max_rect):
        self._zones = [tuple(float(v) for v in r) for r in rects or [] if r and len(r) == 4]
        self._max_rect = tuple(float(v) for v in max_rect) if max_rect and len(max_rect) == 4 else ()

    @Slot(result="QVariantMap")
    def zones(self):
        return {"rects": [list(r) for r in self._zones], "maxRect": list(self._max_rect)}

    @Slot()
    def minimise(self):
        if self.win is not None:
            self.win.showMinimized()

    @Slot()
    def toggleMaximise(self):
        if self.win is not None:
            self.win.showNormal() if self._maximised else self.win.showMaximized()

    @Slot()
    def close(self):
        if self.win is not None:
            self.win.close()

    def attach(self, win):
        """Follow the window's active / maximised state; natively also take its caption away (claimed when it was
        made during engine.load; if it was not made yet, winId() makes it now, still before it is shown)."""
        self.win = win
        win.activeChanged.connect(self._follow)
        win.visibilityChanged.connect(self._follow)
        self._follow()
        if self._native:
            _FILTER.claim(int(win.winId()), self)
            _u32.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, 0x37)   # FRAMECHANGED | NOMOVE | NOSIZE | NOZORDER | NOACTIVATE
            hwnd = self.hwnd
            win.destroyed.connect(lambda *_: _FILTER.chromes.pop(hwnd, None))

    def _follow(self, *_):
        from PySide6.QtGui import QWindow
        self._set("_active", self.win.isActive(), self.activeChanged)
        was = self._maximised
        self._set("_maximised", self.win.visibility() == QWindow.Visibility.Maximized, self.maximisedChanged)
        if was != self._maximised:
            self.resizeBandChanged.emit()

    def read_frame(self, dpi=0):
        """The top resize band: Windows' frame width at the window's DPI plus its 1 px edge (5 px at 100 %)."""
        self._set("_band", _u32.GetSystemMetricsForDpi(33, dpi or _u32.GetDpiForWindow(self.hwnd)) + 1,
                  self.resizeBandChanged)

    def hit(self, cx, cy) -> int:
        r = self.win.devicePixelRatio() or 1.0          # 1 while QT_ENABLE_HIGHDPI_SCALING=0 (app.py › start)
        return hit_test(cx / r, cy / r, self.win.width(), self._maximised, self._band / r, self._zones, self._max_rect)

    def max_hover(self, on: bool):
        self._set("_max_hovered", on, self.maxHoveredChanged)
        if not on:
            self._set("_max_pressed", False, self.maxPressedChanged)


# ---- Windows: the messages ---------------------------------------------------------------------------------------

class _NCCALCSIZE(ctypes.Structure):
    _fields_ = [("rgrc", wintypes.RECT * 3), ("lppos", ctypes.c_void_p)]


class _APPBAR(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uCallbackMessage", wintypes.UINT),
                ("uEdge", wintypes.UINT), ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD)]


class _TRACK(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("hwndTrack", wintypes.HWND),
                ("dwHoverTime", wintypes.DWORD)]


if sys.platform == "win32":
    _u32, _dwm, _shell = ctypes.WinDLL("user32"), ctypes.WinDLL("dwmapi"), ctypes.WinDLL("shell32")
    _u32.DefWindowProcW.restype = ctypes.c_ssize_t
    _u32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.UINT]
    _u32.MonitorFromWindow.restype = wintypes.HANDLE
    _u32.GetSystemMenu.restype = wintypes.HMENU
    _u32.GetSystemMenu.argtypes = [wintypes.HWND, wintypes.BOOL]
    _u32.EnableMenuItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
    _u32.SetMenuDefaultItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
    _u32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    wintypes.HWND, ctypes.c_void_p]
    _u32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _shell.SHAppBarMessage.restype = ctypes.c_size_t
    _dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]


def _dwm_look(hwnd):
    """Dark window menu and edge, round corners, the edge in Theme.border (Windows 11). Windows 10 loses its top 1 px
    edge with the caption gone: the frame reaches 1 px into the client there (Windows Terminal's way)."""
    for attr, v in ((20, ctypes.c_int(1)), (33, ctypes.c_int(2)), (34, ctypes.c_uint(0x2E2E2E))):
        _dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4)   # fails quietly where not supported
    if sys.getwindowsversion().build < 22000:
        _dwm.DwmExtendFrameIntoClientArea(wintypes.HWND(hwnd), ctypes.byref((ctypes.c_int * 4)(0, 0, 1, 0)))


def _autohide_edge(hwnd):
    """The screen edge an auto-hiding taskbar sits on (0 left, 1 top, 2 right, 3 bottom), or None."""
    abd = _APPBAR(cbSize=ctypes.sizeof(_APPBAR))
    if not _shell.SHAppBarMessage(4, ctypes.byref(abd)) & 1:          # ABM_GETSTATE & ABS_AUTOHIDE
        return None
    mi = _MONITORINFO(cbSize=ctypes.sizeof(_MONITORINFO))
    _u32.GetMonitorInfoW(_u32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
    for edge in range(4):
        abd.uEdge, abd.rc = edge, mi.rcMonitor
        if _shell.SHAppBarMessage(11, ctypes.byref(abd)):             # ABM_GETAUTOHIDEBAREX
            return edge
    return None


def _calc_size(h, wp, lp):
    """The caption goes: Windows works out its frame, then the client's top goes back to the window's top. A maximised
    window hangs over the screen by its frame, so its client starts that much lower; with an auto-hiding taskbar it
    leaves 2 px free on that edge, so the taskbar can still slide in."""
    p = _NCCALCSIZE.from_address(lp)
    top = p.rgrc[0].top
    _u32.DefWindowProcW(h, WM_NCCALCSIZE, wp, lp)
    p.rgrc[0].top = top
    if _u32.IsZoomed(h):
        dpi = _u32.GetDpiForWindow(h)
        p.rgrc[0].top += _u32.GetSystemMetricsForDpi(33, dpi) + _u32.GetSystemMetricsForDpi(92, dpi)
        edge = _autohide_edge(h)
        if edge is not None:
            r = p.rgrc[0]
            if edge == 0: r.left += 2
            elif edge == 1: r.top += 2
            elif edge == 2: r.right -= 2
            else: r.bottom -= 2
    return True, 0


def _window_menu(h, lp):
    """Windows' window menu at the pointer, as a right-click on a caption opens it (with the caption gone Windows no
    longer does it itself): Restore / Move / Size / Maximise enabled as the window's state allows."""
    menu = _u32.GetSystemMenu(h, False)
    if not menu:
        return
    zoomed = bool(_u32.IsZoomed(h))
    for cmd, on in ((0xF120, zoomed), (0xF010, not zoomed), (0xF000, not zoomed), (0xF020, True), (0xF030, not zoomed),
                    (0xF060, True)):     # SC_RESTORE, SC_MOVE, SC_SIZE, SC_MINIMIZE, SC_MAXIMIZE, SC_CLOSE
        _u32.EnableMenuItem(menu, cmd, 0 if on else 3)                    # MF_BYCOMMAND | MF_ENABLED / MF_GRAYED
    _u32.SetMenuDefaultItem(menu, 0xF060, 0)
    cmd = _u32.TrackPopupMenu(menu, 0x100 | 0x2, ctypes.c_short(lp & 0xFFFF).value,      # TPM_RETURNCMD | TPM_RIGHTBUTTON
                              ctypes.c_short((lp >> 16) & 0xFFFF).value, 0, h, None)
    if cmd:
        _u32.PostMessageW(h, WM_SYSCOMMAND, cmd, 0)


def _handle(c: WindowChrome, m):
    msg, wp, lp, h = m.message, m.wParam, m.lParam, m.hWnd
    if msg == WM_NCHITTEST:
        r = _u32.DefWindowProcW(h, msg, wp, lp)
        if r != HTCLIENT:                                    # the side and bottom borders stay Windows'
            return True, r
        pt = wintypes.POINT(ctypes.c_short(lp & 0xFFFF).value, ctypes.c_short((lp >> 16) & 0xFFFF).value)
        _u32.ScreenToClient(h, ctypes.byref(pt))
        return True, c.hit(pt.x, pt.y)
    if msg == WM_NCCALCSIZE and wp:
        return _calc_size(h, wp, lp)
    if msg == WM_NCMOUSEMOVE:                                # our maximise button's hover while Windows owns the pointer
        if wp == HTMAXBUTTON and not c._max_hovered:
            t = _TRACK(ctypes.sizeof(_TRACK), 0x12, h, 0)    # TME_LEAVE | TME_NONCLIENT: WM_NCMOUSELEAVE follows
            _u32.TrackMouseEvent(ctypes.byref(t))
        c.max_hover(wp == HTMAXBUTTON)
    elif msg == WM_NCMOUSELEAVE:
        c.max_hover(False)
    elif msg in (WM_NCLBUTTONDOWN, WM_NCLBUTTONDBLCLK) and wp == HTMAXBUTTON:
        c._set("_max_pressed", True, c.maxPressedChanged)
        return True, 0                                       # else Windows paints its old grey button over ours
    elif msg == WM_NCLBUTTONUP and wp == HTMAXBUTTON:
        if c._max_pressed:
            c._set("_max_pressed", False, c.maxPressedChanged)
            c.toggleMaximise()
        return True, 0
    elif msg == WM_NCRBUTTONUP and wp == HTCAPTION:
        _window_menu(h, lp)
        return True, 0
    elif msg == WM_DPICHANGED:                               # moved to a screen of another scale: Qt handles the rest
        c.read_frame((wp >> 16) & 0xFFFF)
    return False, 0


class _Filter(QAbstractNativeEventFilter):
    """Installed once per app; answers only for the windows it was given (chromes: hwnd -> WindowChrome)."""
    def __init__(self):
        super().__init__()
        self.chromes: dict[int, WindowChrome] = {}
        self.pending: WindowChrome | None = None     # the next framed top-level window made is this chrome's
        self.installed = False

    def claim(self, hwnd, chrome):
        if chrome.hwnd != hwnd:
            self.chromes.pop(chrome.hwnd, None)
            chrome.hwnd = hwnd
            self.chromes[hwnd] = chrome
            _dwm_look(hwnd)
            chrome.read_frame()
            chrome.destroyed.connect(lambda *_: self.chromes.pop(hwnd, None))
        if self.pending is chrome:
            self.pending = None

    def nativeEventFilter(self, event_type, message):
        m = wintypes.MSG.from_address(int(message))
        c = self.chromes.get(m.hWnd or 0)
        if c is not None:
            return _handle(c, m)
        if self.pending is not None and m.message == WM_NCCREATE:   # claimed as it is made: no caption flash at all
            style = ctypes.c_long.from_address(m.lParam + 4 * ctypes.sizeof(ctypes.c_void_p) + 16).value
            if style & 0xC00000 == 0xC00000 and not style & 0x40000000:   # WS_CAPTION, not WS_CHILD
                self.claim(m.hWnd, self.pending)
        return False, 0


_FILTER = _Filter()


def make(app, background: bool, parent=None) -> WindowChrome:
    """The window's chrome, made before engine.load (QML binds to it). A person's window on Windows and an offscreen
    picture draw the merged bar; a check's real window keeps Windows' frame unless ROSTRUM_MERGED_FRAME=1."""
    platform = app.platformName()
    native = platform == "windows" and (not background or os.environ.get("ROSTRUM_MERGED_FRAME") == "1")
    chrome = WindowChrome(merged=native or platform in ("offscreen", "minimal"), native=native, parent=parent)
    if native:
        if not _FILTER.installed:
            app.installNativeEventFilter(_FILTER)
            _FILTER.installed = True
        _FILTER.pending = chrome
    return chrome
