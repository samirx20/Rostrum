import QtQuick
import RostrumKit

// The action bar: a small bar on the canvas under the selected layers, clear of their handles and a path's points
// (above them when there is no room), with
// only the actions this selection allows that people reach for most (backend.actionBar, screen2d/actions.py): Group,
// Mask, Boolean, Align, Distribute … and "⋯" for the full list. Move tool only; hidden while playing and while the
// pointer is down on the canvas (a drag). Also the right-click menu on the canvas: the full list. Sits over the canvas,
// under the tool strip; places itself through the canvas's one mapping (`stage`: Stage.qml's compScale / fromComp /
// toComp / compView, in the px of the item both fill).
Item {
    id: bar
    property Item stage
    readonly property int most: 5
    property var items: []
    property var ext: ({})
    function refresh() { items = backend.actionBar(); ext = backend.selectionExtent() }
    Component.onCompleted: refresh()
    Connections {
        target: backend
        function onOutlineChanged() { bar.refresh() }
        function onSelectionChanged() { bar.refresh() }
        function onShownChanged() { bar.refresh() }
    }
    readonly property real clearance: 28        // below the box: past the resize knobs and the turn zones (Handles.qml)
    readonly property real lowest: {             // the lowest thing drawn for the selection: its box, a path's handles
        let y = ext.y1 === undefined ? 0 : ext.y1
        for (const p of backend.pen.points) y = Math.max(y, p.y, p.inY, p.outY)
        return y
    }
    readonly property rect view: stage ? stage.compView : Qt.rect(0, 0, 0, 0)
    PointHandler { id: press; acceptedButtons: Qt.LeftButton; onActiveChanged: if (!active) bar.refresh() }
    readonly property bool dragging: press.active && !strip.hovered
    readonly property bool showing: stage && backend.tool === "move" && !backend.playing && items.length > 0 && ext.x0 !== undefined && !dragging

    ActionMenu { id: choices; parent: bar; onPicked: (key) => backend.run(key) }
    function openMenu(entries, px, py) { choices.entries = entries; choices.openAt(px, py) }

    Rectangle {
        id: strip
        property bool hovered: hover.hovered
        visible: bar.showing
        z: 3
        height: Theme.button; width: row.width + Theme.grid * 2
        radius: Theme.radiusCtl; color: Theme.raised; border.color: Theme.popupEdge
        readonly property real cx: bar.stage ? bar.stage.fromComp((bar.ext.x0 + bar.ext.x1) / 2, 0).x : 0
        readonly property real below: bar.stage ? bar.stage.fromComp(0, bar.lowest).y + bar.clearance : 0
        readonly property real above: bar.stage ? bar.stage.fromComp(0, bar.ext.y0).y - bar.clearance - height : 0
        readonly property real lo: bar.view.y + Theme.grid
        readonly property real hi: bar.view.y + bar.view.height - height - Theme.grid
        x: Math.max(bar.view.x + Theme.grid, Math.min(cx - width / 2, bar.view.x + bar.view.width - width - Theme.grid))
        y: Math.max(lo, Math.min(below <= hi ? below : above >= lo ? above : hi, hi))
        HoverHandler { id: hover }
        Row {
            id: row
            x: Theme.grid; height: parent.height
            Repeater {
                model: bar.items.slice(0, bar.most)
                delegate: BarButton {
                    required property var modelData
                    label: modelData.label + (modelData.menu.length ? " ▾" : "")
                    onClicked: modelData.menu.length ? bar.openMenu(modelData.menu, strip.x + x, strip.y + strip.height + 2) : backend.run(modelData.key)
                }
            }
            BarButton {
                label: "⋯"; tip: "All actions"
                onClicked: bar.openMenu(backend.actionMenu(), strip.x + x, strip.y + strip.height + 2)
            }
        }
    }

    TapHandler {   // right-click on the canvas: the full list for the selection (the layer under the pointer first, unless picked)
        acceptedButtons: Qt.RightButton
        enabled: bar.stage && backend.tool === "move"
        onTapped: (ev) => {
            const p = bar.stage.toComp(ev.position.x, ev.position.y)
            const hit = backend.layerAt(p.x, p.y)
            if (hit !== "" && !backend.multi.has(hit)) backend.pickAt(p.x, p.y)
            bar.openMenu(backend.actionMenu(), ev.position.x, ev.position.y)
        }
    }

    component BarButton: Rectangle {
        id: button
        property string label
        property string tip
        signal clicked
        height: Theme.button - Theme.grid; width: text.implicitWidth + Theme.gap * 2; y: Theme.grid / 2
        radius: 4; color: area.containsMouse ? Theme.hover : "transparent"
        Text { id: text; anchors.centerIn: parent; text: button.label; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.body }
        MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: button.clicked() }
    }
}
