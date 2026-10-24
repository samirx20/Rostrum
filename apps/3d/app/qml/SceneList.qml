import QtQuick
import RostrumKit

// The bottom panel (SPEC §1, §9): the kit's key timeline (LayerTimeline.qml, the same as 2D's) with 3D's rows. Header:
// play, the playhead's time, Add marker (in a project folder) over the names; the ruler in seconds with the project's
// shared markers as flags over the rows (click or drag scrubs). Rows (SceneRows.qml): the scene list on the left (fold,
// kind icon, name, material), on the right the item's keys: a slim bar from its first key to its last, a diamond per
// key (click picks it, drag moves it, a box picks several; a selected item opens a row per animated setting), and a
// stretch between two keys of one setting: click it and the settings panel is that animation (AnimPanel.qml, Main.qml).
// Keys and stretches snap to marker flags while dragged. 3D has no curve view yet and the page sets the height, so
// the Keys | Curves switch, the height switch and the grab edge are absent.
LayerTimeline {
    id: tl
    canCurves: false; canCompact: false; canResize: false
    emptyText: "Your scene's items appear here, their keys on the same rows."
    rows: SceneRows { ruler: tl.ruler; labelWidth: tl.labelWidth }
}
