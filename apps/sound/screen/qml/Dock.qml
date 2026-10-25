import QtQuick
import RostrumKit

// The bottom dock under the arrangement (DESIGN.md §2.2): one strip — Editor (E) | Mixer (X), the Editor's own header
// (EditorHeader: the track, Select / Draw, Note ▾), fold ▾ / open ▴ — and the open tool under it: the Editor (the selection's track up close, EditorDock.qml) or the Mixer (Mixer.qml). Folded, only
// the tab row stays (one click away). Drag the top edge to resize; both tools share one height (workspace.heights,
// screen state), so switching E / X never moves the arrangement above (its rows were laid out and every lane painted
// again on each switch). `preferred`: the window size's default height; `room`: the most it may take.
Item {
    id: d
    property real preferred: 380
    property real room: 1000
    readonly property string tool: workspace.dock
    readonly property real shared: {   // the open dock's height, either tool: tall enough to frame a whole part
        let want = workspace.heights.editor || workspace.heights.mixer || Math.max(preferred + 60, Math.round(room * 0.72))
        return Math.max(tabs.height + 120, Math.min(room, want))
    }
    readonly property real editorHeight: shared
    readonly property real mixerHeight: shared
    height: tool === "" ? tabs.height : tool === "editor" ? editorHeight : mixerHeight
    // No height animation: a tool opens at its height at once (eased, the roll was laid out and painted whole on each of
    // its 3-5 frames, and the tab row a person aims at next moved under the pointer).

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
        onPositionChanged: (m) => { const h = Math.round(Math.min(d.room, Math.max(tabs.height + 120, h0 - (mapToItem(null, m.x, m.y).y - y0))))
                                    workspace.setHeight("editor", h); workspace.setHeight("mixer", h) }
    }
    function openInKey() { header.openInKey() }
    function openNote() { header.openNote() }
    EditorHeader {   // on the same line as the tabs: the Editor has no second header row
        id: header
        visible: d.tool === "editor"
        x: tabs.x + pick.x + pick.width + Theme.pad; width: fold.x - Theme.gap - x; y: tabs.y; height: tabs.height
    }
    // Both tools are made once, when first opened, and kept (hidden while the other shows): making the Mixer's strips
    // again on every E / X cost ~0.6 s on a 16-track song (S59). Not made ahead: building both behind every song
    // opened kept the screen busy for seconds on a loaded machine (the layout check's pictures never settled). Both
    // tools share the dock's height, shown or hidden: the hidden roll is never laid out or painted again for nothing.
    property var made: ({})
    function mark(t) { if (t !== "" && !made[t]) { let m = Object.assign({}, made); m[t] = true; made = m } }
    onToolChanged: mark(tool)
    Component.onCompleted: mark(tool)
    Loader {
        id: editorTool
        objectName: "editorTool"
        anchors { left: parent.left; right: parent.right; top: tabs.bottom; topMargin: Theme.grid }
        active: !!d.made.editor; visible: d.tool === "editor"
        height: d.editorHeight - tabs.height - Theme.grid
        sourceComponent: EditorDock { }
    }
    Loader {
        id: mixerTool
        objectName: "mixerTool"
        anchors { left: parent.left; right: parent.right; top: tabs.bottom; topMargin: Theme.grid }
        active: !!d.made.mixer; visible: d.tool === "mixer"
        height: d.mixerHeight - tabs.height - Theme.grid
        sourceComponent: Mixer { }
    }
}
