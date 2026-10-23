import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// The Brush group's flyout = the brush panel (painting design §2.1, mockup paint-04): beside the rail at the Brush
// icon. The top row: the five paint tools (backend.paintTool). Below: the brushes as real strokes painted by the kit's
// engine (image://brushes/<id>, screen2d/brush_presets.py), three across, by group. A click on a brush makes it the
// brush (the Brush tool goes on) and closes the panel; Esc or a click anywhere else closes it without changing
// anything. Too tall for the window: the brushes scroll, the tools stay.
QQC.Popup {
    id: fly
    objectName: "brushFlyout"
    parent: QQC.Overlay.overlay
    padding: 8
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    readonly property int tileW: 112
    readonly property int tileH: 27
    readonly property var tools: [
        { id: "brush", name: "Brush", key: "B" }, { id: "eraser", name: "Eraser", key: "E" }, { id: "fill", name: "Fill", key: "G" },
        { id: "pick", name: "Pick", key: "I" }, { id: "select", name: "Select", key: "S" }]
    property real room: 10000          // the brushes' most height: the window's, less the tools row
    property real at: 8                // the Brush icon's top: the panel starts there, moved up as far as it must fit
    // a binding, not set once in show(): the list's height settles only after the positioners lay it out
    y: Math.max(8, Math.min(at, (parent ? parent.height : 0) - implicitHeight - 8))
    function show(button) {
        const p = button.mapToItem(parent, button.width, 0)
        room = parent.height - 16 - 2 * padding - 48 - 1 - 2 * 6
        x = p.x + 8
        at = p.y - padding
        open()
    }
    function pickBrush(id) { painter.setPreset(id); backend.paintTool.use("brush"); close() }
    function pickTool(id) { backend.paintTool.use(id); close() }

    contentItem: Column {
        spacing: 6
        Row {       // the five paint tools, icon over name, the key small beside the name
            spacing: 2
            Repeater {
                model: fly.tools
                delegate: Rectangle {
                    id: tool
                    required property var modelData
                    readonly property bool on: backend.tool === "draw" && backend.paintTool.now === modelData.id
                    objectName: "paint_" + modelData.id
                    width: (3 * fly.tileW + 2 * 8 - 4 * 2) / 5; height: 48; radius: Theme.radiusCtl
                    color: toolTap.pressed || tool.on ? Theme.active : toolHover.hovered ? Theme.hover : "transparent"
                    border.color: tool.on ? Theme.accent : "transparent"
                    PaintToolIcon { anchors { horizontalCenter: parent.horizontalCenter; top: parent.top; topMargin: 7 }
                                    name: tool.modelData.id; ink: tool.on || toolHover.hovered ? Theme.fg : Theme.fg2 }
                    Row {
                        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 5 }
                        spacing: 3
                        Text { text: tool.modelData.name; color: tool.on || toolHover.hovered ? Theme.fg : Theme.fg2
                               font.family: uiFont; font.pixelSize: Theme.label }
                        Text { text: tool.modelData.key; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label - 2
                               anchors.baseline: parent.children[0].baseline }
                    }
                    HoverHandler { id: toolHover; cursorShape: Qt.PointingHandCursor }
                    MouseArea { id: toolTap; anchors.fill: parent; onClicked: fly.pickTool(tool.modelData.id) }
                }
            }
        }
        Rectangle { width: parent.width; height: 1; color: Theme.popupEdge }
        Flickable {
            id: list
            width: 3 * fly.tileW + 2 * 8
            height: Math.min(groups.height, fly.room)
            contentHeight: groups.height; clip: true; boundsBehavior: Flickable.StopAtBounds
            Column {
                id: groups
                width: parent.width
                Repeater {
                    model: painter.presets
                    delegate: Column {
                        id: grp
                        required property var modelData
                        width: groups.width
                        Text { text: grp.modelData.group; height: 22; verticalAlignment: Text.AlignVCenter
                               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
                        Grid {
                            columns: 3; columnSpacing: 8; rowSpacing: 4
                            Repeater {
                                model: grp.modelData.presets
                                delegate: Rectangle {
                                    id: tile
                                    required property var modelData
                                    readonly property bool on: painter.brushNow.preset === modelData.id
                                    objectName: "brush_" + modelData.id
                                    width: fly.tileW; height: fly.tileH + 22; radius: Theme.radiusCtl
                                    color: tileTap.pressed ? Theme.active : tileHover.hovered ? Theme.hover : "transparent"
                                    border.color: tile.on ? Theme.accent : "transparent"
                                    Image {
                                        x: 3; y: 3; width: parent.width - 6; height: fly.tileH
                                        source: "image://brushes/" + tile.modelData.id
                                        asynchronous: true; fillMode: Image.PreserveAspectCrop; smooth: true; mipmap: true
                                    }
                                    Text {
                                        x: 5; anchors { bottom: parent.bottom; bottomMargin: 4 }
                                        width: parent.width - 10; elide: Text.ElideRight
                                        text: tile.modelData.name; color: tile.on || tileHover.hovered ? Theme.fg : Theme.fg2
                                        font.family: uiFont; font.pixelSize: Theme.label
                                    }
                                    HoverHandler { id: tileHover; cursorShape: Qt.PointingHandCursor }
                                    MouseArea { id: tileTap; anchors.fill: parent; onClicked: fly.pickBrush(tile.modelData.id) }
                                }
                            }
                        }
                        Item { width: 1; height: 4 }
                    }
                }
            }
        }
    }
}
