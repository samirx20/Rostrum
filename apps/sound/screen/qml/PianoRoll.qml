import QtQuick
import RostrumKit

// The Editor (bottom dock): the selection's track up close. Notes: bars on a keyboard (drag = time and pitch,
// double-click empty space = a new note, Delete removes). Drums: one row per drum. Recorded clips: their
// waveforms. Select first, then act (RollInput): click, Ctrl / Shift+click, a box; a drag moves every selected one
// (one undo step; Ctrl = no snapping, Shift = only in time, Alt = a copy). The context bar sits at the top centre.
Panel {
    id: p
    property Item barSlot: null          // the dock's tab row: where the context bar sits (never over the notes)
    readonly property var roll: backend.roll
    readonly property string kind: roll.kind
    readonly property int keysWidth: kind === "drums" ? 76 : 52     // drum names ("Open hat") are longer than note names
    title: roll.name !== "" ? roll.name : "Piano roll"
    headerRight: [
        BeforeAfter { anchors.verticalCenter: parent.verticalCenter; rightPadding: Theme.gap },
        Row {   // the Editor's two tools (Select V, Draw B; INTERACTION 1.1): a click adds in Draw (backend.tool)
            anchors.verticalCenter: parent.verticalCenter; spacing: 2; rightPadding: Theme.gap
            visible: p.kind === "notes" || p.kind === "drums"
            Repeater {
                model: [{ v: "select", label: "Select", key: "V" }, { v: "draw", label: "Draw", key: "B" }]
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool on: backend.tool === modelData.v
                    width: t.implicitWidth + 2 * Theme.gap; height: 22; radius: 4
                    color: on ? Theme.accentSoft : ta.containsMouse ? Theme.hover : Theme.raised
                    border.color: on ? Theme.accent : Theme.popupEdge
                    Text { id: t; anchors.centerIn: parent; text: parent.modelData.label; color: parent.on ? Theme.fg : Theme.fg2
                           font.family: uiFont; font.pixelSize: Theme.label }
                    MouseArea { id: ta; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: backend.setTool(parent.modelData.v) }
                    HoverTip { text: parent.modelData.label + "  " + parent.modelData.key; hovered: ta.containsMouse; pressed: ta.pressed }
                }
            }
        },
        Text { anchors.verticalCenter: parent.verticalCenter; rightPadding: Theme.grid
               text: p.kind === "notes" ? (backend.tool === "draw" ? "Click to add a note" : "Double-click to add a note") + "  ·  Ctrl drags freely"
                   : p.kind === "drums" || p.kind === "audio" ? "Ctrl drags freely" : ""
               color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label }
    ]

    BarRuler {
        id: bars
        visible: p.kind !== "none" && p.kind !== "empty"
        x: p.keysWidth; width: parent.width - x; height: 22
    }
    Rectangle {
        id: well
        visible: bars.visible
        anchors { left: parent.left; right: parent.right; top: bars.bottom; bottom: strip.visible ? strip.top : parent.bottom; topMargin: Theme.grid
                  bottomMargin: strip.visible ? Theme.grid : 0 }
        radius: Theme.radiusCtl; color: Theme.sunken; clip: true

        Flickable {
            id: view
            anchors.fill: parent
            contentHeight: grid.height; boundsBehavior: Flickable.StopAtBounds; interactive: false
            RollGrid { id: grid; width: view.width; viewHeight: view.height; roll: p.roll; ruler: bars; keysWidth: p.keysWidth }
            RollInput {   // every click, drag, box and right-click on the roll (select first, then act)
                id: input
                x: p.keysWidth; width: grid.width - x; height: grid.height
                grid: grid; bars: bars; flick: view; kind: p.kind; trackId: p.roll.id
                onMenuAt: (entries, px, py) => { rollMenu.entries = entries; var q = input.mapToItem(null, px, py); rollMenu.openAt(q.x, q.y) }
            }
            Component.onCompleted: centre()
            function centre() {   // the notes in view
                var ks = [], b = p.roll.blocks
                for (var i = 0; i < b.length; i++) if (b[i].keys) ks = ks.concat(b[i].keys)
                if (!ks.length || p.kind !== "notes") { contentY = 0; return }
                var mid = (Math.max.apply(null, ks) + Math.min.apply(null, ks)) / 2
                contentY = Math.max(0, Math.min(contentHeight - height, (p.roll.hi - mid) * grid.rowH - height / 2))
            }
            Connections { target: p; function onKindChanged() { view.centre() } }
        }
        Repeater {   // marker lines
            model: backend.markers
            delegate: Rectangle { required property var modelData
                x: p.keysWidth + Math.round(bars.xOf(modelData.t)); width: 1; height: well.height
                visible: bars.visibleX(x - p.keysWidth); color: Theme.fg4; opacity: 0.6 }
        }
        Rectangle { x: p.keysWidth + Math.round(bars.xOf(backend.time)); width: 1; height: well.height
                    visible: bars.visibleX(x - p.keysWidth); color: Theme.accent; opacity: 0.9 }
        Rectangle {   // the time range, shaded
            readonly property var r: backend.timeRange
            visible: r.length === 2
            x: visible ? p.keysWidth + Math.max(0, bars.xOf(r[0])) : 0; height: well.height
            width: visible ? Math.max(1, Math.min(bars.width, bars.xOf(r[1])) - Math.max(0, bars.xOf(r[0]))) : 0
            color: Theme.accentSoft
        }
        Rectangle {   // what a drag snapped to
            readonly property var s: backend.snapLine
            visible: s.t !== undefined && input.busy && bars.visibleX(bars.xOf(s.t))
            x: visible ? p.keysWidth + Math.round(bars.xOf(s.t)) : 0; width: 1; height: well.height
            color: "#ff4fd8"; opacity: s.name ? 0.95 : 0.5          // magenta: what it caught (INTERACTION.md §1.11)
            Text { visible: !!parent.s.name; x: 4; y: 2; text: parent.s.name || ""; color: "#ff4fd8"
                   font.family: uiFont; font.pixelSize: Theme.label }
        }
        ContextBar {   // the kit's: a fixed place, the Editor's top centre = the dock's tab row (INTERACTION.md §1.2)
            parent: p.barSlot || well
            hub: backend.actions
            anchors.horizontalCenter: parent.horizontalCenter; y: p.barSlot ? (parent.height - height) / 2 : Theme.grid
            maxWidth: parent.width
            dragging: input.busy || rollMenu.visible || backend.area !== "roll"
        }
    }
    VelocityStrip {   // one bar per note or hit; drag a bar, or draw a line across (DESIGN.md §3.3d)
        id: strip
        visible: bars.visible && (p.kind === "notes" || p.kind === "drums")
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 52; roll: p.roll; ruler: bars; keysWidth: p.keysWidth
    }
    ActionMenu { id: rollMenu; onPicked: (v) => backend.menuPick(v) }      // the kit's
    function menuFor(id) {   // the right-click menu on an item (a scripted step: steps_select.py)
        rollMenu.entries = backend.itemMenu(id)
        var e = backend.selectionExtent()
        var q = well.mapToItem(null, p.keysWidth + Math.max(0, bars.xOf(e.t1 || 0)) + 8, well.height / 3)
        rollMenu.openAt(q.x, q.y)
    }
    Column {   // nothing to draw: say what to do, calmly
        visible: !bars.visible
        anchors.centerIn: parent; spacing: Theme.gap
        Text { anchors.horizontalCenter: parent.horizontalCenter; font.family: uiFont; font.pixelSize: Theme.title
               color: Theme.fg2; text: p.kind === "none" ? "Nothing selected" : "Nothing on this track yet" }
        Text { anchors.horizontalCenter: parent.horizontalCenter; font.family: uiFont; font.pixelSize: Theme.body
               color: Theme.fg3
               text: p.kind === "none" ? "Select a track or something on it to edit it here."
                     : recorder.armed !== "" ? "Press Record (R) to record a take on this track."
                     : "To record: press Rec on the track's row, then press R.
To write notes: choose an instrument in the inspector." 
               horizontalAlignment: Text.AlignHCenter }
    }
}
