"""The one key map, as data (INTERACTION.md Part 2). Shared keys mean the same thing in every app; an app adds only
its own keys (tools, panels, its own actions) and may never give a shared key another meaning. The map builds the
screen's shortcuts, the Ctrl+/ key list and hover help, and the action list takes every action's key from it, so a
key is typed in one place only.

A key held down and let go (`"hold": True` on an entry: Sound's "hold H to hear the original") runs its job on the
press, once (no auto-repeat), and the job's release when the key comes up (keyhold.py watches the release).

A clash is refused at start-up with a plain message naming both meanings (fail loudly): an app key that takes a
shared key, or one key meaning two things in one app. Pointer gestures (click, box, wheel, drag modifiers) are in
1.3 and 1.10, not here: they are not shortcuts.
"""
from __future__ import annotations

MODS = ("Ctrl", "Alt", "Shift", "Meta")
NAMES = {"esc": "Esc", "escape": "Esc", "return": "Enter", "del": "Delete", "bksp": "Backspace", "pgup": "PgUp",
         "pgdown": "PgDown", "←": "Left", "→": "Right", "↑": "Up", "↓": "Down", "control": "Ctrl", "cmd": "Ctrl",
         "option": "Alt", "opt": "Alt"}


def _area(area, rows):
    return [{"job": j, "keys": list(k), "label": label, "area": area} for j, k, label in rows]


_ARROWS = [(f"nudge_{d}{s}", [f"{m}{d.capitalize()}"], f"Nudge {d}{w}")
           for d in ("left", "right", "up", "down")
           for s, m, w in (("", "", ""), ("_big", "Shift+", ", a big step"), ("_fine", "Alt+", ", a fine step"))]

SHARED = [
    *_area("Play", [
        ("play", ["Space"], "Play / stop"), ("play_from_selection", ["Shift+Space"], "Play from the selection"),
        ("to_start", ["Home"], "Playhead to the start"), ("to_end", ["End"], "Playhead to the end"),
        ("frame_back", ["Ctrl+Left"], "Playhead back one frame"), ("frame_on", ["Ctrl+Right"], "Playhead on one frame"),
        ("frame_back_ten", ["Ctrl+Shift+Left"], "Playhead back ten frames"),
        ("frame_on_ten", ["Ctrl+Shift+Right"], "Playhead on ten frames"),
        ("prev_event", [","], "Previous thing that happens"), ("next_event", ["."], "Next thing that happens"),
        ("prev_beat", ["Shift+,"], "Previous beat"), ("next_beat", ["Shift+."], "Next beat"),
        ("next_marker", ["Alt+M"], "Next marker"), ("prev_marker", ["Alt+Shift+M"], "Previous marker"),
        ("loop", ["Shift+L"], "Loop on / off"),
        ("range_start", ["Shift+I"], "Time range starts here"), ("range_end", ["Shift+O"], "Time range ends here")]),
    *_area("Select", [
        ("go_in", ["Enter"], "Go in"), ("go_out", ["Shift+Enter"], "Go out"),
        ("next_item", ["Tab"], "Next item"), ("prev_item", ["Shift+Tab"], "Previous item"),
        ("find_item", ["Ctrl+Shift+F"], "Find an item"), ("select_all", ["Ctrl+A"], "Select all"),
        ("step_back", ["Esc"], "Step back")]),
    *_area("Edit", [
        ("undo", ["Ctrl+Z"], "Undo"), ("redo", ["Ctrl+Shift+Z", "Ctrl+Y"], "Redo"),
        ("copy", ["Ctrl+C"], "Copy"), ("cut", ["Ctrl+X"], "Cut"), ("paste", ["Ctrl+V"], "Paste"),
        ("paste_other", ["Ctrl+Shift+V"], "Paste at the pointer / at the original time"),
        ("duplicate", ["Ctrl+D"], "Duplicate"), ("delete", ["Delete", "Backspace"], "Delete"),
        ("delete_close_gap", ["Shift+Delete"], "Delete and close the gap"), ("rename", ["F2"], "Rename"),
        *_ARROWS,
        ("forward", ["Ctrl+]"], "Bring forward"), ("backward", ["Ctrl+["], "Send backward"),
        ("front", ["Ctrl+Shift+]"], "Bring to front"), ("back", ["Ctrl+Shift+["], "Send to back"),
        ("group", ["Ctrl+G"], "Group"), ("ungroup", ["Ctrl+Shift+G"], "Ungroup"),
        ("hide", ["Ctrl+Shift+H"], "Hide / show"), ("lock", ["Ctrl+Shift+L"], "Lock / unlock"),
        ("split", ["Ctrl+T"], "Split at the playhead"), ("join", ["Ctrl+J"], "Join"),
        ("trim_start", ["Alt+["], "Trim the start to the playhead"),
        ("trim_end", ["Alt+]"], "Trim the end to the playhead"),
        ("copy_style", ["Ctrl+Alt+C"], "Copy style"), ("paste_style", ["Ctrl+Alt+V"], "Paste style")]),
    *_area("Animate", [
        ("key_here", ["K"], "Key the selection here"), ("animated_rows", ["A"], "Show / hide animated rows"),
        ("smooth", ["F9"], "Smooth"), ("ease_in", ["Shift+F9"], "Ease in"), ("ease_out", ["Ctrl+Shift+F9"], "Ease out"),
        ("jump", ["Ctrl+Alt+J"], "Jump"), ("marker", ["M"], "Marker at the playhead")]),
    *_area("View", [
        ("zoom_in", ["Ctrl+="], "Zoom in"), ("zoom_out", ["Ctrl+-"], "Zoom out"), ("fit_all", ["Ctrl+0"], "Fit all"),
        ("actual_size", ["Ctrl+1"], "100 %"), ("fit", ["F"], "Fit the selection"),
        ("fold_panels", ["Ctrl+\\"], "Hide / bring back the side panels"), ("next_area", ["F6"], "Next area")]),
    *_area("Panels", [
        ("library", ["Ctrl+L"], "Library"), ("history", ["Ctrl+H"], "History"),
        ("find_setting", ["Ctrl+F"], "Find a setting")]),
    *_area("Find and help", [
        ("command_box", ["Ctrl+K"], "Search and run anything"), ("guides", ["F1"], "Guides"),
        ("key_list", ["Ctrl+/"], "Key list")]),
    *_area("Files", [
        ("new", ["Ctrl+N"], "New"), ("open", ["Ctrl+O"], "Open"), ("save_version", ["Ctrl+S"], "Save a version"),
        ("duplicate_file", ["Ctrl+Shift+S"], "Duplicate (a separate copy)"), ("add_file", ["Ctrl+I"], "Add from a file"),
        ("export", ["Ctrl+E"], "Export…"), ("export_again", ["Ctrl+Shift+E"], "Export again"),
        ("preferences", ["Ctrl+,"], "Preferences"), ("quit", ["Ctrl+Q"], "Quit")]),
    *_area("Tools", [("move_tool", ["V"], "Move / Select"), ("paint_tool", ["B"], "Paint / Draw"),
                     ("notes_tool", ["N"], "Notes on the picture")]),
]


_MODIFIER_KEYS = {"ctrl", "control", "alt", "altgr", "shift", "meta", "super", "capslock"}


def normal(key: str) -> str:
    """One spelling per key: "ctrl+shift+g" and "Shift+Ctrl+G" are both "Ctrl+Shift+G"; Escape is Esc."""
    parts = [p.strip() for p in key.replace("++", "+plus").split("+")]
    mods, rest = set(), []
    for p in parts:
        word = NAMES.get(p.lower(), p)
        if word.capitalize() in MODS:
            mods.add(word.capitalize())
        else:
            rest.append(word)
    if len(rest) != 1 or not rest[0]:
        raise ValueError(f'"{key}" is not one key (a key with Ctrl / Alt / Shift in front)')
    name = "+" if rest[0] == "plus" else rest[0]
    name = name.upper() if len(name) == 1 else NAMES.get(name.lower(), name[0].upper() + name[1:])
    return "+".join([m for m in MODS if m in mods] + [name])


class KeyMap:
    """The shared keys plus one app's own (`app_keys`: [{job, keys, label, hold?}]). An app entry whose job is a
    shared job adds another key for it (2D's Shift+2 for Fit). A hold key is a single key without Ctrl / Alt, so
    letting it go is never mistaken for letting go of a modifier."""

    def __init__(self, app: str, app_keys=(), drop=(), words=None):
        """`drop`: shared jobs this app has nothing behind (2D has no Preferences): no key, not in the key list.
        `words`: {job: label}, what a shared key is called in this app's own words (Sound's "one frame" is a grid step)."""
        self.app = app
        words = words or {}
        unknown = [j for j in (*drop, *words) if j not in {r["job"] for r in SHARED}]
        if unknown:
            raise ValueError(f"{app}'s key map names shared jobs that do not exist: {', '.join(unknown)}")
        self._rows = [{**r, "keys": [normal(k) for k in r["keys"]], "where": "shared", "hold": False,
                       "label": words.get(r["job"], r["label"])}
                      for r in SHARED if r["job"] not in drop]
        jobs = {r["job"]: r for r in self._rows}
        self._by_key = _index(self._rows, "the shared key map")
        for a in app_keys:
            keys = [normal(k) for k in a["keys"]]
            if a.get("hold") and any("Ctrl+" in k or "Alt+" in k for k in keys):
                raise ValueError(f'{app} gives "{a["label"]}" the hold key {", ".join(keys)}: a hold key must be '
                                 "a key on its own, without Ctrl or Alt")
            for k in keys:
                if k in self._by_key:
                    have = self._by_key[k]
                    if have["job"] == a["job"]:
                        continue
                    whose = "the shared key for" if have["where"] == "shared" else f"{app}'s key for"
                    raise ValueError(f'{app} gives {k} to "{a["label"]}", but {k} is {whose} "{have["label"]}". '
                                     f"Pick another key for \"{a['label']}\".")
            if a["job"] in jobs and jobs[a["job"]]["where"] == "shared":
                row = jobs[a["job"]]
                row["keys"] += [k for k in keys if k not in row["keys"]]
            else:
                row = {"job": a["job"], "keys": keys, "label": a["label"], "area": a.get("area", app), "where": app,
                       "hold": bool(a.get("hold"))}
                self._rows.append(row)
                jobs[row["job"]] = row
            for k in keys:
                self._by_key[k] = row
        self._jobs = jobs

    def has(self, job: str) -> bool:
        return job in self._jobs

    def key_of(self, job: str) -> str:
        """The key shown beside an action ("Ctrl+G"); "" for a job without a key. An unknown job is a mistake."""
        if job not in self._jobs:
            raise KeyError(f'"{job}" is not a job in {self.app}\'s key map')
        keys = self._jobs[job]["keys"]
        return keys[0] if keys else ""

    def job_of(self, sequence: str) -> str:
        """The job a pressed key does in this app; "" when the key does nothing."""
        row = self._by_key.get(normal(sequence))
        return row["job"] if row else ""

    def where(self, sequence: str) -> str:
        row = self._by_key.get(normal(sequence))
        return row["where"] if row else ""

    def held(self, key_name: str) -> list[str]:
        """The hold jobs a released key ends ("H" -> ["hear_original"]); modifiers held with it don't matter.
        A modifier on its own (Qt names it "Control", "Shift" ...) ends nothing: hold keys never carry one."""
        if key_name.strip().lower() in _MODIFIER_KEYS:
            return []
        name = normal(key_name).split("+")[-1]
        return [r["job"] for r in self._rows if r["hold"] and any(k.split("+")[-1] == name for k in r["keys"])]

    def entries(self) -> list[dict]:
        """Every key, shared first: {job, keys, label, area, where, hold} for Qt shortcuts and the Ctrl+/ list."""
        return [dict(r, keys=list(r["keys"])) for r in self._rows]


def _index(rows, where) -> dict:
    out = {}
    for r in rows:
        for k in r["keys"]:
            if k in out:
                raise ValueError(f'{where} gives {k} to both "{out[k]["label"]}" and "{r["label"]}"')
            out[k] = r
    return out
