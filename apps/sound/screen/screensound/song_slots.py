"""The song's music map from the Song popup: tempo, key, sections (song_edit.py builds the calls; one undo step each)."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.edits import Drag

from . import layers, moves, song_edit, song_list, timeline

ADDED = {"add_tempo": "tempos", "add_meter": "meters", "add_key": "keys", "add_section": "sections"}   # selected once added


class SongSlots:
    def subtitle(self, item):
        """The inspector's subtitle: none (the name and the fields say the kind), but for a clip tied to a project
        marker, which one (2D's cues)."""
        return timeline.tie_words(item) or ""

    @Slot(result="QVariantMap")
    def layers(self):
        """The settings panel's Layers group: the selected sound's layer mates ({} when it has no layered group)."""
        return layers.of(self.doc, self._picks.ids)

    @Slot(result="QVariantMap")
    def songEdit(self):
        """What the song view needs now: only what is valid at the playhead."""
        sel = self.doc.item(self._sel) if self._sel and self.doc.has(self._sel) else None
        can = song_list.can(self.doc.data, self._t)
        return {**song_edit.state(self.doc.data, sel, self._t), "canTempo": can["tempo"], "canMeter": can["meter"],
                "canMarker": can["marker"]}

    @Slot(result="QVariantMap")
    def songList(self):
        """The song's timeline as the settings panel lists it: tempo, time signature, key changes, sections, markers."""
        return song_list.rows(self.doc.data)

    @Slot(str, str)
    def songDo(self, action, arg):
        """One music-map edit from the song panel: start_bpm, add_tempo, add_meter, set_key, add_key, add_section (one
        undo step each). What is added is selected, so its settings show at once."""
        t, root = self._t, self.doc.data
        make = {"start_bpm": lambda: (song_edit.start_tempo_call(float(arg)), "Set tempo"),
                "add_tempo": lambda: (song_edit.add_tempo_call(root, t), "Add tempo change"),
                "add_meter": lambda: (song_edit.add_meter_call(root, t), "Add time signature change"),
                "set_key": lambda: (song_edit.key_call(root, t, *arg.split(" ", 1), False), "Set key"),
                "add_key": lambda: (song_edit.key_call(root, t, *arg.split(" ", 1), True), "Add key change"),
                "add_section": lambda: (song_edit.add_section_call(root, t), "Add section")}
        if action not in make:
            return self._fail(f'Error: song edit: "{action}" is not one ({", ".join(make)}).')

        def go():
            call, label = make[action]()
            self._apply([call], label)
            if action in ADDED:
                self.select(self.doc.data[ADDED[action]][-1]["id"])
        self._guard(go)

    @Slot(str, str, result=bool)
    def beginEdge(self, section_id, edge):
        """Press on a section's left ("at") or right ("end") edge: select it and start one gesture."""
        self.endDrag()
        self.select(section_id)

        def go():
            self._grab = song_edit.edge_grab(self.doc, section_id, edge)
            self._drag = Drag(self.doc, self.who, moves.LABELS["edge"])
        return self._guard(go)


# ---- where the person is, kept across this window reopening the song (a rename) ------------------------------
FRESH_S = 30.0          # a place saved this long ago or less is this window's own reopen (the song renamed)


def place(bridge) -> dict:
    """Where the person is (the kit's AppFiles `place`): the selection, the Editor or Mixer open and the Editor's track,
    the playhead and the stretch of the song on screen. Screen state, never a change."""
    import time
    v = bridge._zoom
    return {"saved": time.time(), "selected": list(bridge.selectedIds), "dock": bridge.workspace.dock,
            "track": bridge._track, "t": bridge._t, "view": {"start": v.start, "span": v.span, "fit": v.fit}}


def restore_place(bridge, p: dict) -> None:
    """Put a place back (AppFiles `restore_place`), only when it was saved moments ago: this window reopening the
    song under a new name keeps the Editor, its track and the selection (critic r12 should-fix 7). A song opened
    later starts as before."""
    import time
    if time.time() - float(p.get("saved", 0)) > FRESH_S:
        return
    doc = bridge.doc
    ids = [i for i in p.get("selected", []) if doc.has(i)]
    if p.get("track") and doc.has(p["track"]):
        bridge._track = p["track"]
        bridge._show_roll()
    if ids:
        bridge._pick(ids)
    if p.get("t") is not None:
        bridge.setTime(float(p["t"]))
    view = p.get("view") or {}
    if view and not view.get("fit"):
        v = bridge._zoom
        v._span, v.fit, v.auto, v.start = float(view["span"]), False, False, float(view["start"])
        v.clamp()
        bridge._tv.changed.emit()
    if p.get("dock"):
        bridge.workspace.setDock(p["dock"])
