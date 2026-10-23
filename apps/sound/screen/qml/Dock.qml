import QtQuick
import RostrumKit

// The bottom dock under the arrangement (DESIGN.md §2.2): one strip — Editor (E) | Mixer (X), the Editor's own header
// (EditorHeader: the track, Select / Draw, Note ▾), fold ▾ / open ▴ — and the open tool under it: the Editor (the selection's track up close, EditorDock.qml) or the Mixer (Mixer.qml). Folded, only
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

    Rectangle {   // the tab row as one strip, open or folded: Editor | Mixer, then the fold / open arrow at its right
        id: tabs
        width: parent.width; height: 36
        radius: Theme.radiusPanel; color: Theme.panel
        Segmented {
            id: pick
            anchors { left: parent.left; leftMargin: Theme.grid; verticalCenter: parent.verticalCenter }
            options: [{ value: "editor", label: "Editor" }, { value: "mixer", label: "Mixer" }]
            current: d.tool
            onPicked: (v) => workspace.setDock(v)
            HoverHandler { id: pickHover }
            HoverTip { text: "Editor (E) · Mixer (X)"; hovered: pickHover.hovered }
        }
    }
    IconButton {
        id: fold
        glyph: d.tool !== "" ? "▾" : "▴"; kind: "ghost"
        tip: d.tool !== "" ? "Fold the dock away" : "Open the Editor"
        anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: tabs.verticalCenter }
        onClicked: workspace.setDock(d.tool !== "" ? "" : "editor")
    }
    MouseArea {   // the top edge: drag to resize the open tool
        id: edge
        visible: d.tool !== ""
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: pick.width + Theme.gap + Theme.grid; rightMargin: Theme.button + Theme.gap + Theme.grid }
        height: tabs.height; cursorShape: Qt.SizeVerCursor; preventStealing: true
        property real y0: 0
        property real h0: 0
        onPressed: (m) => { y0 = mapToItem(null, m.x, m.y).y; h0 = d.height }
        onPositionChanged: (m) => workspace.setHeight(d.tool, Math.round(Math.min(d.room, Math.max(tabs.height + 120,
                                                          h0 - (mapToItem(null, m.x, m.y).y - y0)))))
    }
    EditorHeader {   // on the same line as the tabs: the Editor has no second header row
        visible: d.tool === "editor"
        x: tabs.x + pick.x + pick.width + Theme.pad; width: fold.x - Theme.gap - x; y: tabs.y; height: tabs.height
    }
    Loader {
        anchors { left: parent.left; right: parent.right; top: tabs.bottom; bottom: parent.bottom; topMargin: Theme.grid }
        active: d.tool !== ""
        sourceComponent: d.tool === "mixer" ? mixerTool : editorTool
    }
    Component { id: editorTool; EditorDock { } }
    Component { id: mixerTool; Mixer {} }
}
