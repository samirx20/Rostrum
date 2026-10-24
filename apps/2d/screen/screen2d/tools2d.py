"""The screen's tools as QML sees them (backend.pen, backend.exporter, …): each is its own object in its own file; this
mix-in for Bridge2D only makes them and hands them out."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Slot
from rostrum_gui.parts import SlotMixin

from .adding import Adder
from .bone_tool import BoneTool
from .create import Create
from .curves import Curves
from .exporter import Exporter
from .filler import Filler
from .frame_drag import FrameDrag
from .importer import Importer
from .brand_view import LibraryView
from .key_bar import KeyBar
from .key_select import KeySelect
from .motion_path import MotionPath
from .multi import Multi
from .paint_layers import PaintLayers
from .paint_pick import ColourPick
from .paint_tool import PaintTool
from .pen import Pen
from .problems import Problems
from .rig_blinks import BlinkSheet
from .rig_lipsync import LipSyncSheet
from .rig_poses import PoseList
from .rig_view import RigView
from .snapper import Snapper
from .stagger import Stagger
from .stroke_select import StrokeSelect
from .stretch_select import StretchSelect
from .time_snap import TimeSnap
from .depth_typed import DepthTyped
from .ease_play import EasePlay


class ToolSlots(SlotMixin):
    def _make_tools(self):
        self._pen, self._curves = Pen(self), Curves(self)
        self._multi = Multi(self)                           # several layers selected (multi.py): backend.multi
        self._keys = KeySelect(self)                        # keys picked in the timeline (key_select.py): backend.keys
        self._keys.changed.connect(self._curves.changed)    # the curve editor shows the picked key's handles
        self._stretch = StretchSelect(self)                 # the stretch picked in the timeline (stretch_select.py): backend.stretch
        self._key_bar = KeyBar(self)                        # the settings panel's Key block (key_bar.py): backend.keyBar
        self._stagger = Stagger(self)                       # Stagger…'s popover (stagger.py): backend.stagger
        self._depth_typed = DepthTyped(self)                # Set depth ▾ › Other depth…'s popover (depth_typed.py): backend.depthTyped
        self._time_snap = TimeSnap(self)                    # the "+6 f" label of a time drag (time_snap.py): backend.timeSnap
        self._ease_play = EasePlay(self)                    # an ease picked plays once on the canvas (ease_play.py)
        self._exporter, self._importer, self._adder = Exporter(self), Importer(self), Adder(self)
        self._library = LibraryView(self)                   # the Library drawer's brand kit and styles (brand_view.py): backend.library
        self._problems = Problems(self)
        self._problems.failed.connect(self._fail)
        self._frame_drag = FrameDrag(self)                  # picking the frame, moving, zooming, turning it (frame_drag.py): backend.frameDrag
        self._motion = MotionPath(self)                     # the selection's motion path on the canvas (motion_path.py): backend.motionPath
        self._create = Create(self)                         # R / O / T and typing on the canvas (create.py): backend.create
        self._snap = Snapper(self)                          # canvas drags snap (snapper.py): backend.snap
        self._paint_layers = PaintLayers(self)              # Draw's "Paint on …" group (paint_layers.py): backend.paintLayers
        self._filler = Filler(self)                         # Fill, G while Draw is on (filler.py): backend.fill
        self._pick = ColourPick(self)                       # Alt picks a colour (paint_pick.py): backend.colourPick
        self._strokes = StrokeSelect(self)                  # lasso, move, copy, delete strokes (stroke_select.py): backend.strokeSelect
        self._paint_tool = PaintTool(self)                  # Brush, Eraser, Fill, Pick, Select: which is on (paint_tool.py): backend.paintTool
        self._rig = RigView(self)                           # the rig in hand's bones on the canvas (rig_view.py): backend.rig
        self._bone_tool = BoneTool(self, self._rig)         # the Bone tool (J): draw bones by hand (bone_tool.py): backend.boneTool
        self._poses = PoseList(self)                        # the rig's pose library in the settings (rig_poses.py): backend.poses
        self._lipsync, self._blinks = LipSyncSheet(self), BlinkSheet(self)   # Lip sync…, Add blinks… (rig_lipsync.py, rig_blinks.py)

    @Property(QObject, constant=True)
    def pen(self):
        """The pen tool and path point editing (pen.py)."""
        return self._pen

    @Property(QObject, constant=True)
    def frameDrag(self):
        """Pick the frame (C, its name tab); drag inside it, its corners or turn zones to move, zoom, turn it (frame_drag.py)."""
        return self._frame_drag

    @Property(QObject, constant=True)
    def motionPath(self):
        """Where the selected layer (or the frame) travels, its keys and handles on the canvas (motion_path.py)."""
        return self._motion

    @Property(QObject, constant=True)
    def boneTool(self):
        """The Bone tool: draw a rig's bones joint by joint (bone_tool.py)."""
        return self._bone_tool

    @Property(QObject, constant=True)
    def create(self):
        """The creation tools: Rectangle, Ellipse, Text and typing on the canvas (create.py)."""
        return self._create

    @Property(QObject, constant=True)
    def keys(self):
        """The keys picked in the timeline: Ctrl+click adds, Shift+click a run (key_select.py)."""
        return self._keys

    @Property(QObject, constant=True)
    def stretch(self):
        """The stretch picked in the timeline and its animation in the settings panel (stretch_select.py)."""
        return self._stretch

    @Property(QObject, constant=True)
    def keyBar(self):
        """Ease, the small curve, Time / Value and Spring for the picked keys (key_bar.py)."""
        return self._key_bar

    @Property(QObject, constant=True)
    def stagger(self):
        """Stagger…: layers start one after another, live, one change (stagger.py)."""
        return self._stagger

    @Property(QObject, constant=True)
    def depthTyped(self):
        """Set depth ▾ › Other depth…: a typed camera depth for the selected drawings, live, one change (depth_typed.py)."""
        return self._depth_typed

    @Property(QObject, constant=True)
    def timeSnap(self):
        """The label by the pointer while keys or bars are dragged in time: "+6 f · drop" (time_snap.py)."""
        return self._time_snap

    @Property(QObject, constant=True)
    def easePlay(self):
        """Picking an ease plays the stretch it shapes once on the canvas (ease_play.py)."""
        return self._ease_play

    @Property(QObject, constant=True)
    def snap(self):
        """Snapping while dragging on the canvas, and the lines it caught (snapper.py)."""
        return self._snap

    @Property(QObject, constant=True)
    def paintLayers(self):
        """The paint layers of what Draw paints on, and its paint switches (paint_layers.py)."""
        return self._paint_layers

    @Property(QObject, constant=True)
    def fill(self):
        """Fill while Draw is on (filler.py)."""
        return self._filler

    @Property(QObject, constant=True)
    def colourPick(self):
        """Hold Alt while Draw is on: pick the colour under the pointer (paint_pick.py)."""
        return self._pick

    @Property(QObject, constant=True)
    def paintTool(self):
        """The Brush group's five tools: which is on, and switching (paint_tool.py)."""
        return self._paint_tool

    @Property(QObject, constant=True)
    def strokeSelect(self):
        """Select strokes with a lasso, then move, copy, delete them (stroke_select.py)."""
        return self._strokes

    @Property(QObject, constant=True)
    def rig(self):
        """The rig in hand: its bones and joints on the canvas, posing and fixing drags (rig_view.py, rig_drag.py)."""
        return self._rig

    @Property(QObject, constant=True)
    def poses(self):
        """The rig's pose library: Save pose, apply at the playhead, blend (rig_poses.py)."""
        return self._poses

    @Property(QObject, constant=True)
    def lipsync(self):
        """Lip sync… on a mouth swap set: a voice line of the project, a drawing per mouth shape (rig_lipsync.py)."""
        return self._lipsync

    @Property(QObject, constant=True)
    def blinks(self):
        """Add blinks… on an eyes swap set (rig_blinks.py)."""
        return self._blinks

    @Property(QObject, constant=True)
    def exporter(self):
        """The Export button's job (exporter.py)."""
        return self._exporter

    @Property(QObject, constant=True)
    def importer(self):
        """The Import panel's job (importer.py)."""
        return self._importer

    @Property(QObject, constant=True)
    def library(self):
        """The Library drawer: the project's brand kit and this document's text styles (brand_view.py)."""
        return self._library

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
