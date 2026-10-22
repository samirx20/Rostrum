import QtQuick
import RostrumKit

// The bottom dock under the arrangement (DESIGN.md §2.2): a tab row — Editor (E) · Mixer (X) · fold ▾ — and the open
// tool under it: the Editor (the selection's track up close, EditorDock.qml) or the Mixer (Mixer.qml). Folded, only
// the tab row stays (one click away). Drag the top edge to resize; each tool keeps its own height (workspace.heights,
// screen state). `preferred`: the window size's default height; `room`: the most it may take.
Item {
    id: d
    property real preferred: 380
    property real room: 1000
    readonly property string tool: workspace.dock
    readonly property real want: tool === "" ? 0 : (workspace.heights[tool] || preferred)
    height: tool === "" ? tabs.height : Math.max(tabs.height + 120, Math.min(room, want))
    Behavior on height { enabled: !edge.pressed; NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }

    Row {
        id: tabs
        height: 36; spacing: 2
        Repeater {
            model: [{ value: "editor", label: "Editor", key: "E" }, { value: "mixer", label: "Mixer", key: "X" }]
            delegate: Button {
                required property var modelData
                anchors.verticalCenter: parent.verticalCenter
                id: tab
                text: modelData.label; kind: "ghost"; down: d.tool === modelData.value
                onClicked: workspace.toggleDock(modelData.value)
                HoverTip { text: modelData.label + " (" + modelData.key + ")"; hovered: tab.hovered }
            }
        }
    }
    IconButton {
        visible: d.tool !== ""; glyph: "▾"; kind: "ghost"; tip: "Fold the dock away"
        anchors { right: parent.right; verticalCenter: tabs.verticalCenter }
        onClicked: workspace.setDock("")
    }
    MouseArea {   // the top edge: drag to resize the open tool
        id: edge
        visible: d.tool !== ""
        anchors { left: tabs.right; right: parent.right; top: parent.top; leftMargin: Theme.gap; rightMargin: Theme.button + Theme.gap }
        height: tabs.height; cursorShape: Qt.SizeVerCursor; preventStealing: true
        property real y0: 0
        property real h0: 0
        onPressed: (m) => { y0 = mapToItem(null, m.x, m.y).y; h0 = d.height }
        onPositionChanged: (m) => workspace.setHeight(d.tool, Math.round(Math.min(d.room, Math.max(tabs.height + 120,
                                                          h0 - (mapToItem(null, m.x, m.y).y - y0)))))
    }
    Item {   // the Editor's context bar sits here, in the tab row: never over its notes (PianoRoll.qml places it)
        id: barSlot
        anchors { left: tabs.right; right: parent.right; top: parent.top; leftMargin: Theme.gap; rightMargin: Theme.button + Theme.gap }
        height: tabs.height
    }
    Loader {
        anchors { left: parent.left; right: parent.right; top: tabs.bottom; bottom: parent.bottom; topMargin: Theme.grid }
        active: d.tool !== ""
        sourceComponent: d.tool === "mixer" ? mixerTool : editorTool
    }
    Component { id: editorTool; EditorDock { barSlot: barSlot } }
    Component { id: mixerTool; Mixer {} }
}
