import QtQuick
import RostrumKit

// The context bar (UX_SPEC 4.3, INTERACTION 1.1): one row at a fixed place, the top-centre of the canvas view, so the
// eyes go to the same place every time. With the Move tool and a selection: what is selected ("3 layers") and the top
// five actions this selection allows, by rank (backend.actionBar, screen2d/actions.py), then "⋯" for the whole list.
// Hidden while playing, while dragging on the canvas and with nothing selected; never wraps; never covers the tool
// strip. Also the right-click menu on the canvas (the full list). Places itself through the canvas's one mapping
// (`stage`: Stage.qml's compView, in the px of the item both fill). Replaced by the kit's ContextBar once S31 is in main.
// With another tool it shows that tool's few options instead (4.3): Pen: how to click, Close path, Done. Paint: the
// tip, Size, Colour, Opacity, Eraser (E), and [ / ] for size — the brush panel holds the rest.
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
    readonly property int count: backend.multi.count
    readonly property rect view: stage ? stage.compView : Qt.rect(0, 0, 0, 0)
    PointHandler { id: press; acceptedButtons: Qt.LeftButton; onActiveChanged: if (!active) bar.refresh() }
    readonly property bool dragging: press.active && !strip.hovered
    readonly property string mode: backend.playing || dragging ? "" : backend.tool === "move" ? (items.length > 0 && ext.x0 !== undefined ? "select" : "")
                                  : backend.tool === "pen" ? "pen" : backend.tool === "draw" ? "paint" : ""
    readonly property bool showing: stage && mode !== ""
    readonly property var brush: painter.brushNow
    function setBrush(name, v) { painter.setValue(name, v) }
    Shortcut { sequence: "E"; enabled: bar.mode === "paint"; onActivated: bar.setBrush("mode", bar.brush.mode === "erase" ? "normal" : "erase") }
    Shortcut { sequence: "["; enabled: bar.mode === "paint"; onActivated: bar.setBrush("size", Math.max(0.5, Math.round(bar.brush.size / 1.25 * 2) / 2)) }
    Shortcut { sequence: "]"; enabled: bar.mode === "paint"; onActivated: bar.setBrush("size", Math.min(2000, Math.round(bar.brush.size * 1.25 * 2) / 2)) }

    ActionMenu { id: choices; parent: bar; onPicked: (key) => backend.run(key) }
    function openMenu(entries, px, py) { choices.entries = entries; choices.openAt(px, py) }

    Rectangle {
        id: strip
        property bool hovered: hover.hovered
        visible: bar.showing
        z: 3
        height: Theme.button; width: row.width + Theme.grid * 2
        radius: Theme.radiusCtl; color: Theme.raised; border.color: Theme.popupEdge
        readonly property real clear: bar.view.x + Theme.gap + 40 + Theme.gap      // clear of the tool strip
        x: Math.max(clear, bar.view.x + (bar.view.width - width) / 2)
        y: bar.view.y + Theme.gap
        HoverHandler { id: hover }
        Row {
            id: row
            x: Theme.grid; height: parent.height; spacing: 2
            Text {      // what is selected, or the tool's own hint
                visible: bar.mode === "select" || bar.mode === "pen"
                anchors.verticalCenter: parent.verticalCenter
                leftPadding: Theme.grid; rightPadding: Theme.gap
                text: bar.mode === "pen" ? (backend.pen.draft.length === 0 ? "Click: corner  ·  Drag: curve" : "Click the first point to close")
                    : bar.count === 1 ? "1 layer" : bar.count + " layers"
                color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
            }
            Repeater {
                model: bar.mode === "select" ? bar.items.slice(0, bar.most) : []
                delegate: BarButton {
                    required property var modelData
                    label: modelData.label + (modelData.menu.length ? " ▾" : "")
                    onClicked: modelData.menu.length ? bar.openMenu(modelData.menu, strip.x + x, strip.y + strip.height + 2) : backend.run(modelData.key)
                }
            }
            BarButton {
                visible: bar.mode === "select"
                label: "⋯"; tip: "All actions"
                onClicked: bar.openMenu(backend.actionMenu(), strip.x + x, strip.y + strip.height + 2)
            }
            BarButton { visible: bar.mode === "pen" && backend.pen.draft.length > 2; label: "Close path"; onClicked: { backend.pen.close(); backend.setTool("move") } }
            BarButton { visible: bar.mode === "pen"; label: "Done"; onClicked: { backend.pen.finish(); backend.setTool("move") } }
            Row {       // Paint: quick brush controls (the next stroke's; the brush panel on the right has every setting)
                visible: bar.mode === "paint"
                height: parent.height; spacing: Theme.gap
                ChoiceField {
                    anchors.verticalCenter: parent.verticalCenter; width: 92
                    options: (bar.brush.tips || []).map(t => ({ value: t, label: t.charAt(0).toUpperCase() + t.slice(1) })); current: bar.brush.brush
                    onPicked: (v) => bar.setBrush("brush", v)
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Size"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                NumberField {
                    anchors.verticalCenter: parent.verticalCenter; width: 72
                    value: bar.brush.size || 0; from: 0.5; to: 2000; step: 0.5; unit: "px"
                    onEdited: (v) => bar.setBrush("size", v); onScrubbed: (v) => bar.setBrush("size", v)
                }
                ColorField {
                    anchors.verticalCenter: parent.verticalCenter; width: 96
                    hex: bar.brush.color || "#ffffff"; onEdited: (v) => bar.setBrush("color", v)
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Opacity"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                NumberField {
                    anchors.verticalCenter: parent.verticalCenter; width: 64
                    value: bar.brush.opacity === undefined ? 1 : bar.brush.opacity; from: 0; to: 1; step: 0.01
                    onEdited: (v) => bar.setBrush("opacity", v); onScrubbed: (v) => bar.setBrush("opacity", v)
                }
                BarButton {
                    label: bar.brush.mode === "erase" ? "Eraser on  E" : "Eraser  E"
                    color: bar.brush.mode === "erase" ? Theme.accentSoft : area.containsMouse ? Theme.hover : "transparent"
                    onClicked: bar.setBrush("mode", bar.brush.mode === "erase" ? "normal" : "erase")
                }
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
        property alias area: area
        radius: 4; color: area.containsMouse ? Theme.hover : "transparent"
        Text { id: text; anchors.centerIn: parent; text: button.label; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.body }
        MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: button.clicked() }
    }
}
