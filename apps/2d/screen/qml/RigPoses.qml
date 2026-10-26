import QtQuick
import RostrumKit

// The settings panel's "Poses" group while a rig (or one of its bones) is in hand (UX_SPEC 3.23 › Pose library;
// backend.poses: screen2d/rig_poses.py). Laid on the settings rows' own columns: name in the label column, the amount
// slider and its value in the field column, ⋯ in the key-mark gutter. Save pose keeps the pose at the playhead; a click
// on a pose keys it there; its slider keys part of the way from the pose there now (one change on release); ⋯ or
// right-click › Rename, Delete; double-click renames. A rig with no poses yet shows Save pose alone. Absent when a
// pose can't apply (no rig, or a part picked with a bone: Attach to bone's selection).
Column {
    id: pl
    readonly property var p: backend.poses
    readonly property real full: parent ? parent.width : 0
    readonly property real wide: Theme.wideFor(full)          // label + field: every row ends where the fields end
    readonly property bool any: p.poses.length > 0
    width: full
    visible: p.shown
    spacing: 2

    Item {  // the heading, like a group's, with Save pose at its right; no poses yet: Save pose alone
        width: pl.wide; height: Theme.groupGap + Theme.row
        Text {
            visible: pl.any
            anchors { left: parent.left; bottom: parent.bottom; bottomMargin: Theme.grid + 4 }
            text: "Poses"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        }
        Button {
            x: pl.any ? parent.width - width : 0; anchors.bottom: parent.bottom
            text: "Save pose"; help: "Pose the character on the canvas, then keep its pose at the playhead in the library."
            onClicked: pl.p.save()
        }
    }
    Repeater {
        model: pl.p.poses
        delegate: Rectangle {
            id: row
            required property var modelData
            property bool renaming: false
            readonly property real labelW: Theme.labelColumnFor(pl.full)
            width: pl.full; height: Theme.row; radius: Theme.radiusCtl
            color: rowArea.containsMouse ? Theme.hover : "transparent"
            function startRename() { renaming = true }
            NameLabel {
                id: nameText
                visible: !row.renaming
                anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                width: row.labelW - Theme.gap
                text: row.modelData.name; help: "Click: key this pose at the playhead · double-click: rename"
            }
            NameBox {     // rename in place (the kit's box): Enter keeps it, Esc or a click elsewhere leaves the name as it was
                id: nameEdit
                visible: row.renaming
                current: row.modelData.name
                anchors { left: nameText.left; right: nameText.right; verticalCenter: parent.verticalCenter }
                onDone: (t) => { row.renaming = false; if (t.trim() && t.trim() !== row.modelData.name) pl.p.rename(row.modelData.id, t.trim()) }
                onCancelled: row.renaming = false
            }
            MouseArea {
                id: rowArea
                anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
                width: row.labelW
                enabled: !row.renaming
                hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: (m) => { if (m.button === Qt.RightButton) row.openMenu(m.x, m.y); else pl.p.apply(row.modelData.id) }
                onDoubleClicked: (m) => { if (m.button === Qt.LeftButton) row.startRename() }
            }
            Slider {
                id: amount
                anchors { left: parent.left; leftMargin: row.labelW; right: value.left; rightMargin: Theme.gap + 2; verticalCenter: parent.verticalCenter }
                from: 0; to: 1; value: row.modelData.amount; display: "percent"
                onScrubbed: (v) => pl.p.blendTo(row.modelData.id, v)
                onEdited: (v) => { pl.p.blendTo(row.modelData.id, v); pl.p.endBlend() }
                onScrubEnded: pl.p.endBlend()
                HoverTip { hovered: amount.hovered && !amount.pressed; text: "How much of the pose to key"
                           help: "Drag to key part of the way from the pose there now to this one (one change on release)." }
            }
            Text {
                id: value
                anchors { right: parent.right; rightMargin: Theme.keyGutter; verticalCenter: parent.verticalCenter }
                width: Theme.amountFieldShort; horizontalAlignment: Text.AlignRight
                text: Math.round(row.modelData.amount * 100) + " %"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
            }
            IconButton {
                id: more
                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                width: Theme.keyGutter - 4; height: Theme.field
                glyph: "⋯"; kind: "ghost"; tip: "Rename or delete"
                onClicked: row.openMenu(more.x, more.y + more.height)
            }
            function openMenu(x, y) { const g = row.mapToItem(null, x, y); poseMenu.pose = row.modelData.id; poseMenu.row = row; poseMenu.openAt(g.x, g.y) }
        }
    }
    Item {  // the end of the group: a line and a group's gap, so the settings below don't read as poses
        width: pl.wide; height: Theme.groupGap
        Rectangle { visible: pl.any; anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 1; color: Theme.line }
    }
    ActionMenu {
        id: poseMenu
        property string pose: ""
        property var row: null
        entries: [{ value: "rename", label: "Rename" }, { value: "delete", label: "Delete pose" }]
        onPicked: (v) => v === "rename" ? row.startRename() : pl.p.remove(pose)
    }
}
