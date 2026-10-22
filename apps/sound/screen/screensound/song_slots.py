"""The song's music map from the Song popup: tempo, key, sections (song_edit.py builds the calls; one undo step each)."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.edits import Drag

from . import layers, moves, song_edit, timeline


class SongSlots:
    def kind_label(self, item):
        """The inspector's subtitle: the kind, and for a clip tied to a project marker which one (2D's cues)."""
        words = timeline.tie_words(item)
        return f"{super().kind_label(item)} · {words}" if words else super().kind_label(item)

    @Slot(result="QVariantMap")
    def layers(self):
        """The settings panel's Layers group: the selected sound's layer mates ({} when it has no layered group)."""
        return layers.of(self.doc, self._picks.ids)

    @Slot(result="QVariantMap")
    def songEdit(self):
        """What the Song popup shows now: only what is valid at the playhead with this selection."""
        sel = self.doc.item(self._sel) if self._sel and self.doc.has(self._sel) else None
        return song_edit.state(self.doc.data, sel, self._t)

    @Slot(str, str)
    def songDo(self, action, arg):
        """One music-map edit from the popup: start_bpm, add_tempo, set_key, add_key, add_section (one undo step each)."""
        t, root = self._t, self.doc.data
        make = {"start_bpm": lambda: (song_edit.start_tempo_call(float(arg)), "Set tempo"),
                "add_tempo": lambda: (song_edit.add_tempo_call(root, t), "Add tempo change"),
                "set_key": lambda: (song_edit.key_call(root, t, *arg.split(" ", 1), False), "Set key"),
                "add_key": lambda: (song_edit.key_call(root, t, *arg.split(" ", 1), True), "Add key change"),
                "add_section": lambda: (song_edit.add_section_call(root, t), "Add section")}
        if action not in make:
            return self._fail(f'Error: song edit: "{action}" is not one ({", ".join(make)}).')

        def go():
            call, label = make[action]()
            self._apply([call], label)
            if action in ("add_tempo", "add_section"):
                kind = {"add_tempo": "tempos", "add_section": "sections"}[action]
                self.select(self.doc.data[kind][-1]["id"])
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
