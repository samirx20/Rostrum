import QtQuick
import RostrumKit

// The action bar: a small bar on the canvas just under the selected layers (above them when there is no room), with
// only the actions this selection allows that people reach for most (backend.actionBar, screen2d/actions.py): Group,
// Mask, Boolean, Align, Distribute … and "⋯" for the full list. Move tool only; hidden while playing and while the
// pointer is down on the canvas (a drag). Also the right-click menu on the canvas: the full list. Sits over the canvas
// (`canvas` = the canvas frame of Stage.qml), under the tool strip.
Item {
    id: bar
    property Item canvas
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
    readonly property real fit: canvas && backend.frameInfo.width > 0 ? canvas.width / backend.frameInfo.width : 1
    readonly property point origin: { if (!canvas) return Qt.point(0, 0); canvas.x; canvas.y; canvas.width; width; height; return canvas.mapToItem(bar, 0, 0) }
    PointHandler { id: press; acceptedButtons: Qt.LeftButton; onActiveChanged: if (!active) bar.refresh() }
    readonly property bool dragging: press.active && !strip.hovered
    readonly property bool showing: canvas && backend.tool === "move" && !backend.playing && items.length > 0 && ext.x0 !== undefined && !dragging

    ActionMenu { id: choices; parent: bar; onPicked: (key) => backend.run(key) }
    function openMenu(entries, px, py) { choices.entries = entries; choices.openAt(px, py) }

    Rectangle {
        id: strip
        property bool hovered: hover.hovered
        visible: bar.showing
        z: 3
        height: Theme.button; width: row.width + Theme.grid * 2
        radius: Theme.radiusCtl; color: Theme.raised; border.color: Theme.popupEdge
        readonly property real cx: bar.origin.x + (bar.ext.x0 + bar.ext.x1) / 2 * bar.fit
        readonly property real below: bar.origin.y + bar.ext.y1 * bar.fit + Theme.gap
        readonly property real above: bar.origin.y + bar.ext.y0 * bar.fit - height - Theme.gap
        readonly property real lo: bar.canvas ? bar.origin.y + Theme.grid : 0
        readonly property real hi: bar.canvas ? bar.origin.y + bar.canvas.height - height - Theme.grid : 0
        x: Math.max(bar.origin.x + Theme.grid, Math.min(cx - width / 2, bar.origin.x + (bar.canvas ? bar.canvas.width : 0) - width - Theme.grid))
        y: Math.max(lo, Math.min(below <= hi ? below : above, hi))
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
        enabled: bar.canvas && backend.tool === "move"
        onTapped: (ev) => {
            const p = bar.canvas.mapFromItem(bar, ev.position.x, ev.position.y)
            const hit = backend.layerAt(p.x / bar.fit, p.y / bar.fit)
            if (hit !== "" && !backend.multi.has(hit)) backend.pickAt(p.x / bar.fit, p.y / bar.fit)
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
