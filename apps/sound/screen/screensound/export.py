"""RostrumSound's fill of the kit's Export sheet (rostrum_gui/export_sheet.py, EXPORT.md; the settings: qml/ExportSettings.qml):
the same versioned render the MCP `render_mix` makes (`handoff.render`: `renders/<item>/vNNN/` with its manifest, every
track's stem, and a stem per bus when the engine writes them), in the background on its own engine process. Exposed to
QML as `mixer.export` (and `backend.exporter`).

What for = where it is going (delivery.py's targets: Streaming −14 …); choosing one is the one master.set change it
always was (mixer.loudness.choose). Then the file type, the quality (sample rate), stems, trimming the silent end, and
the live pass / miss against the target. Browse: the mix is also copied into that folder, under its song's name (the
version folder keeps everything). "MIDI file" is one more What for choice: the song's notes, playing lanes, tempo map
and markers as a .mid, written by the same `midi.export` the agents' `render_midi` uses, to the same place
(`renders/<item>/midi/<item>.mid`); none of the sound's settings apply to it, so none show. A failure is written in words and is the bridge's red error (never a quiet "done").
"""
from __future__ import annotations

import copy
import os
import re
import shutil
from pathlib import Path

from PySide6.QtCore import Property, Signal, Slot
from rostrum_core import RostrumError
from rostrum_gui.export_sheet import ExportSheet
from rostrum_sound import compile as compile_doc
from rostrum_sound import deliver, handoff, midi, presets
from rostrum_sound.doc import markers

from . import delivery, export_stems, loudness, playback
from .export_versions import Versions, ranges, schedule_for


MIDI = "midi"     # the What for choice that writes a MIDI file, not a mix


def summary(r: dict) -> str:
    n_bus, n_track = len(r.get("busStems") or {}), len(r.get("stems") or {})
    stems = (f"{n_track + n_bus} stems by group" if r.get("stemsBy") else
             f"{n_track} track stems" + (f" + {n_bus} group stems" if n_bus else "")) if n_track or n_bus else "no stems"
    stems += ", markers beside" if r.get("markersFile") else ""
    if r.get("silentStems"):
        stems += " (silent: " + ", ".join(r["silentStems"]) + ")"
    cut = f", {r['songSeconds'] - r['seconds']:.1f} s of silence trimmed" if r.get("trimmed") else ""
    return (f"Version {r['version']} · {r.get('format', {}).get('label', '')}, {r.get('sampleRate', 0) / 1000:g} kHz · "
            f"{r['seconds']:.1f} s{cut} · {stems}")


def option(c: dict) -> dict:
    """A choice's short name (the closed field shows only it) and what it means (the open list shows it under the name)."""
    return {"label": c["label"], "detail": c["detail"]}


class RenderExport(ExportSheet):
    own = Signal()                                    # = changed, for this class's own properties

    def __init__(self, bridge, loudness=None, open_engine=playback.open_engine, parent=None):
        super().__init__(bridge, parent)
        self._loud, self._open_engine = loudness, open_engine
        self.changed.connect(self.own)                # (a subclass's property can't notify on the kit's signal: PySide6 crashes)
        self._stems, self._format, self._rate, self._trim = "off", deliver.DEFAULT_FORMAT, 0, True   # rate 0: the song's own
        self._markers = False                         # markers.json beside the files
        self._choice = self._target_key()
        self._more = Versions()
        bridge.docChanged.connect(self._sync)
        bridge.renderChanged.connect(self.changed)       # each extra version's line follows the sound that plays
        bridge.rangeChanged.connect(self.changed)        # What: a time range on the ruler is a choice

    def _target_key(self) -> str:
        return (self._loud.target.get("key") or "") if self._loud is not None else ""

    def _sync(self, *_):
        """The master's target changed (here, by undo, or by an agent): the list shows it. A chosen row whose numbers
        the master still has stays chosen (Podcast and Apple Music ask for the same numbers)."""
        t = self._loud.target if self._loud is not None else {}
        if self._choice == MIDI:                         # not a loudness target: the master's doesn't move it
            return
        row = delivery.BY_KEY.get(self._choice)
        if row and t.get("shown") and (t.get("lufs"), t.get("peak")) == (row["lufs"], row["peak"]):
            return
        key = self._target_key()
        if key != self._choice:
            self._choice = key
            self.changed.emit()

    # ---- the kit's questions --------------------------------------------------------------------------------
    def choices_list(self):
        return [*({"value": c["id"], "label": c["label"], "tip": c["detail"].replace("-", "−")} for c in delivery.choices()),
                {"value": MIDI, "label": "MIDI file", "tip": "Notes, sustain, expression, bend, tempo and markers for "
                                                             "another music app; no sound"}]

    def chose(self):
        if self._choice == MIDI:
            return
        if self._loud is not None and self._choice != self._target_key():
            self._loud.choose(self._choice)                # one master.set: Normalize on, its loudness and peak

    def ranges_list(self):
        all_ = ranges(self.bridge.doc, self.bridge._picks.range)
        return all_[:1] if self._choice == MIDI else all_       # a MIDI file is the whole song

    def default_folder(self):
        doc = self.bridge.doc
        if not doc.folder or not doc.item_id:
            return "Nowhere yet: save the song into a project first"
        return str(Path(doc.folder) / 'renders' / doc.item_id)

    def file_name(self):
        name = re.sub(r'[<>:"/\\|?*]+', " ", self.bridge.docName or self.bridge.doc.item_id or "Song").strip() or "Song"
        return f"{name}.{'mid' if self._choice == MIDI else deliver.BY_FORMAT[self._format]['ext']}"

    def begin(self, out, overwrite):
        doc = self.bridge.doc
        if not doc.folder or not doc.item_id:
            raise RuntimeError("save the song into a project first (open it with a project folder), so the render has a place to go")
        if self._choice == MIDI:            # the agents' render_midi path and file
            return {"midi": Path(doc.folder) / "renders" / doc.item_id / "midi" / f"{doc.item_id}.mid",
                    "root": copy.deepcopy(doc.data), "out": out}
        # A preset's own render choice (the Editor's: the mix before mastering), while the sheet still shows it chosen.
        master = presets.PRESETS.get(self.preset, {}).get("master", True)
        try:
            schedule = compile_doc(doc, master=master)
        except RostrumError as e:
            raise RuntimeError(e.line()) from e
        span = self.range_times()
        if self._range != "all" and span is None:
            raise RuntimeError("the range chosen is not there any more (a time range or section was removed): choose What again")
        o = self.options()
        base = {"format": o.format, "sampleRate": o.sample_rate, "trim": o.trim, **({"from": span[0], "to": span[1]} if span else {})}
        versions = [{"schedule": schedule, "options": base, "markers": self._markers,
                     "stems": export_stems.REQUEST[export_stems.mode(self._stems, doc.data)]}]
        for r in self._more.rows:               # each extra version: its own target, file type and quality (no stems)
            rate = r["rate"] if r["rate"] in [x["id"] for x in deliver.rates_for(r["format"])] else 0
            versions.append({"schedule": schedule_for(doc, r["target"]), "stems": [], "markers": False,
                             "options": {**base, "format": r["format"], "sampleRate": rate or doc.data.get("sampleRate", 48000)}})
        return {"doc": doc, "versions": versions, "who": f"{self.bridge.who.kind}:{self.bridge.who.name}", "out": out}

    def work(self, p, progress):
        if "midi" in p:
            return self._write_midi(p)
        progress(-1.0)                                     # the engine can't say how far it is
        eng, made = self._open_engine(), []
        try:
            for v in p["versions"]:
                made.append(handoff.render(p["doc"].folder, p["doc"], eng, v["schedule"], p["who"], stems=v["stems"], options=v["options"],
                                           markers_file=v["markers"]))
        finally:
            eng.close()
        for m in made:
            if not Path(m["file"]).is_file():
                raise RuntimeError(f"the mix is not at {m['file']}")
        r = made[0]
        files = [x for m in made for x in (m["file"], *(m.get("stems") or {}).values(), *(m.get("busStems") or {}).values())]
        main = r["file"]
        if p["out"] is not None:                            # Browse: the first mix, copied in; the old file stays until it is whole
            out = Path(p["out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            part = out.with_name(out.stem + ".partial" + out.suffix)
            shutil.copyfile(r["file"], part)
            os.replace(part, out)
            main, files = str(out), [str(out), *files]
        return {**r, "file": main, "files": files, "version": f"v{int(r['version']):03d}",
                "summary": " | ".join(summary(m) for m in made), "versions": [f"v{int(m['version']):03d}" for m in made]}

    def _write_midi(self, p):
        skipped = midi.export(p["root"], p["midi"])
        files = [str(p["midi"])]
        if p["out"] is not None:
            out = Path(p["out"])
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p["midi"], out)
            files.insert(0, str(out))
        said = f"; skipped: {'; '.join(skipped)}" if skipped else ""
        return {"file": files[0], "files": files, "summary": f"MIDI file · {Path(files[0]).name}{said}"}

    @Property(bool, notify=own)
    def isMidi(self):
        """The MIDI file is chosen: the sound's settings (file type, stems, versions …) don't apply and don't show."""
        return self._choice == MIDI

    # ---- Sound's own settings (qml/ExportSettings.qml) --------------------------------------------------------
    @Property("QVariantList", constant=True)
    def formats(self):
        return [{"value": c["id"], **option(c)} for c in deliver.choices()["formats"]]

    @Property("QVariantList", notify=own)
    def rates(self):
        return [{"value": str(c["id"]), **option(c)} for c in deliver.rates_for(self._format)]

    @Property(str, constant=True)
    def sheetTitle(self):
        """The sheet's heading: what it makes ("Export" is the button under it, so the title is not a second one)."""
        return "Make the file"

    @Property(str, notify=own)
    def format(self):
        return self._format

    @Property(str, notify=own)
    def rate(self):
        return str(self.options().sample_rate)

    @Property(str, notify=own)
    def stemsMode(self):
        """"off", "all" or "groups" (a file per group, ungrouped tracks each their own)."""
        return export_stems.mode(self._stems, self.bridge.doc.data)

    @Property("QVariantList", notify=own)
    def stemChoices(self):
        """Only the stems choices that mean something for this song ("groups" needs a group)."""
        return export_stems.choices(self.bridge.doc.data)

    @Property(bool, notify=own)
    def markers(self):
        return self._markers

    @Property(bool, notify=own)
    def hasMarkers(self):
        """Offered only when the song has a named marker or a section to write."""
        d = self.bridge.doc.data
        with markers.project(self.bridge.doc.folder):
            return bool(markers.all(d) or d.get("sections"))

    @Property("QVariantList", constant=True)
    def presets(self):
        return export_stems.listed()

    @Property(str, notify=own)
    def preset(self):
        """The preset the sheet's choices equal now ("" when none)."""
        return export_stems.matching({"format": self._format, "sampleRate": self.options().sample_rate, "trim": self._trim,
                                      "stems": self.stemsMode, "markers": self._markers})

    @Property(bool, notify=own)
    def trim(self):
        return self._trim

    @Property(str, notify=own)
    def folderMade(self):
        """The version folder the last export made (Browse copies the mix out of it)."""
        return self._result.get("folder", "")

    def options(self) -> deliver.Options:
        """The choices as the render takes them; a rate the format cannot have gives way to the song's own."""
        doc_rate = self.bridge.doc.data.get("sampleRate", 48000)
        rate = self._rate or doc_rate
        if rate not in [r["id"] for r in deliver.rates_for(self._format)]:
            rate = 0
        return deliver.Options.read({"format": self._format, "sampleRate": rate or None, "trim": self._trim}, doc_rate)

    @Slot(str)
    def setFormat(self, value):
        self._format = value
        self.changed.emit()

    @Slot(str)
    def setRate(self, value):
        self._rate = int(value)
        self.changed.emit()

    @Slot(str)
    def setStemsMode(self, value):
        if value in export_stems.MODES:
            self._stems = value
            self.changed.emit()

    @Slot(bool)
    def setMarkers(self, on):
        self._markers = bool(on)
        self.changed.emit()

    @Slot(str)
    def usePreset(self, name):
        """A delivery preset (presets.py): sets the file, quality, trimming, stems and markers in one go."""
        p = presets.PRESETS.get(name)
        if p is None:           # a typo must not leave the old choices standing as if it had worked
            self.bridge._fail(f'Error: export: no preset named "{name}". Use one of: {", ".join(presets.PRESETS)}.')
            return
        if self.running():
            return
        self._format, self._rate, self._trim, self._stems, self._markers = p["format"], p["sampleRate"], p["trim"], p["stems"], p["markers"]
        self.changed.emit()

    @Slot(bool)
    def setTrim(self, on):
        self._trim = bool(on)
        self.changed.emit()

    def _measured(self) -> dict:
        """The render that plays now, with the loudness and peak of the exported range alone when one is chosen (the file
        is the range, so the check reads the range, not the whole song). The whole song's when the range can't be measured."""
        r, span = self.bridge.lastRender or {}, self.range_times()
        return {**r, **loudness.for_span(r.get("series") or {}, *span)} if span else r

    @Property("QVariantMap", notify=own)
    def check(self):
        """{ok, text}: the live pass / miss of what will be exported (the chosen range, else the whole song) against the target."""
        t = self._loud.target if self._loud is not None else {}
        m, fields = self._loud._fields() if self._loud is not None else ({}, [])
        return delivery.verdict(m, self._measured(), fields) if t.get("shown") else {}

    @Property("QVariantList", notify=own)
    def more(self):
        """The extra delivery rows ("+ Another version"): {target, format, rate, verdict}."""
        m = self.bridge.doc.item("master")
        return self._more.shown(m, self._measured(), self.bridge.doc.data.get("sampleRate", 48000))

    @Property("QVariantList", constant=True)
    def targets(self):
        return [{"value": c["id"], "label": c["label"]} for c in delivery.choices()]

    @Slot(str, result="QVariantList")
    def ratesFor(self, fmt):
        return [{"value": str(c["id"]), **option(c)} for c in deliver.rates_for(fmt)] if fmt in deliver.BY_FORMAT else []

    @Slot()
    def addVersion(self):
        if not self.running():
            self._more.add(self._choice, self._format)
            self.changed.emit()

    @Slot(int)
    def removeVersion(self, i):
        if not self.running():
            self._more.remove(i)
            self.changed.emit()

    @Slot(int, str, str)
    def setVersion(self, i, key, value):
        """One row's `target`, `format` or `rate`."""
        if not self.running() and key in ("target", "format", "rate"):
            self._more.set(i, **{key: int(value) if key == "rate" else value})
            self.changed.emit()

    @Slot(bool)
    def setDialogOpen(self, on):                       # (the old name: scripts and the ≡ menu)
        self.setOpen(on)

    def close(self):
        self.wait(120)
