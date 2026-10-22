"""The screen's tools as QML sees them (backend.pen, backend.exporter, …): each is its own object in its own file; this
mix-in for Bridge2D only makes them and hands them out."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject
from rostrum_gui.parts import SlotMixin

from .adding import Adder
from .create import Create
from .curves import Curves
from .exporter import Exporter
from .importer import Importer
from .key_select import KeySelect
from .multi import Multi
from .pen import Pen
from .problems import Problems
from .snapper import Snapper


class ToolSlots(SlotMixin):
    def _make_tools(self):
        self._pen, self._curves = Pen(self), Curves(self)
        self._multi = Multi(self)                           # several layers selected (multi.py): backend.multi
        self._keys = KeySelect(self)                        # keys picked in the timeline (key_select.py): backend.keys
        self._exporter, self._importer, self._adder = Exporter(self), Importer(self), Adder(self)
        self._problems = Problems(self)
        self._problems.failed.connect(self._fail)
        self._create = Create(self)                         # R / O / T and typing on the canvas (create.py): backend.create
        self._snap = Snapper(self)                          # canvas drags snap (snapper.py): backend.snap

    @Property(QObject, constant=True)
    def pen(self):
        """The pen tool and path point editing (pen.py)."""
        return self._pen

    @Property(QObject, constant=True)
    def create(self):
        """The creation tools: Rectangle, Ellipse, Text and typing on the canvas (create.py)."""
        return self._create

    @Property(QObject, constant=True)
    def keys(self):
        """The keys picked in the timeline: Ctrl+click adds, Shift+click a run (key_select.py)."""
        return self._keys

    @Property(QObject, constant=True)
    def snap(self):
        """Snapping while dragging on the canvas, and the lines it caught (snapper.py)."""
        return self._snap

    @Property(QObject, constant=True)
    def exporter(self):
        """The Export button's job (exporter.py)."""
        return self._exporter

    @Property(QObject, constant=True)
    def importer(self):
        """The Import panel's job (importer.py)."""
        return self._importer

    @Property(QObject, constant=True)
    def adder(self):
        """The Add menu (adding.py)."""
        return self._adder

    @Property(QObject, constant=True)
    def curves(self):
        """The timeline's curve editor (curves.py)."""
        return self._curves

    @Property(QObject, constant=True)
    def problems(self):
        """The problems list (problems.py: what inspect_diagnose finds)."""
        return self._problems
