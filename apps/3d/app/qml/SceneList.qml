import QtQuick
import RostrumKit

// The bottom panel (SPEC §1, §9): the kit's key timeline (LayerTimeline.qml, the same as 2D's) with 3D's rows. Header:
// play, the playhead's time, Add marker (in a project folder) over the names; the ruler in seconds with the project's
// shared markers as flags over the rows (click or drag scrubs). Rows (SceneRows.qml): the scene list on the left (fold,
// kind icon, name, material), on the right the item's keys: a slim bar from its first key to its last, a diamond per
// key (click picks it, drag moves it, a box picks several; a selected item opens a row per animated setting), and a
// stretch between two keys of one setting: click it and the settings panel is that animation (AnimPanel.qml, Main.qml).
// Keys and stretches snap to marker flags while dragged. Keys | Curves (once something is animated): the kit's curve
// view (CurveEditor.qml, backend.curves: curves3d.py) in the rows' place. The page sets the height, so the height switch
// and the grab edge are absent. Under the rows, while the scene has bodies: the Simulate row (SimRow.qml).
LayerTimeline {
    id: tl
    canCompact: false; canResize: false
    emptyText: "Your scene's items appear here, their keys on the same rows."
    rows: SceneRows { ruler: tl.ruler; labelWidth: tl.labelWidth }
    layers: AnimLayers {}               // animation layers (layers3d.py): ⧉ until the first, then the chosen layer's name
    curves: CurveEditor { visible: backend.curves.on; ruler: tl.ruler; labelWidth: tl.labelWidth }
    // the Simulate row (SimRow.qml) at the bottom while the scene has bodies, under the rows' box: the kit's `footer` keeps
    // its room, so no row ever passes under it
    SimRow { id: simRow; x: 0; width: tl.width - Theme.gap; z: 4; anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.gap
             ruler: tl.ruler; labelWidth: tl.labelWidth }
    // Collections (CollectionRow.qml) above it, there once the scene has one
    CollectionRow { id: collRow; x: 0; width: tl.width - Theme.gap; z: 4; anchors.bottom: simRow.visible ? simRow.top : parent.bottom
                    anchors.bottomMargin: simRow.visible ? 0 : Theme.gap; labelWidth: tl.labelWidth }
    footer: (simRow.visible ? simRow.height + Theme.gap : 0) + (collRow.visible ? collRow.height + (simRow.visible ? 0 : Theme.gap) : 0)
}
