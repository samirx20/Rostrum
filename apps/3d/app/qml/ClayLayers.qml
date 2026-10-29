import QtQuick
import RostrumKit

// The Clay panel's sculpt layers (PR4; screen3d/clay_layers_qt.py, `viewport.clay.layersObj`). Absent until the clay
// has one (the Steps head's "+ Layer" makes it). Base first, then each layer: a click says where the next stroke goes
// (clay.set sculptLayer), the eye turns a layer off and on (claylayer.set on), a double-click names it, the number is its
// Amount; the chosen layer's Amount row sits under the list (the kit's InspectorRow: drag, type, scrub) with its "⋯"
// menu (Bake into Base, Remove layer).
Column {
    id: box
    objectName: "clayLayers"
    property real inner: width
    readonly property var layers: viewport.clay.layersObj
    visible: layers.count > 0

    Text { objectName: "clayLayersHead"; text: "Layers"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
    Item { width: 1; height: Theme.gap }
    Repeater {
        model: box.layers.items
        delegate: Item {
            id: row
            required property var model           // roles: id, label, on, chosen, amount (clay_layers_qt.ROLES)
            required property int index
            objectName: "clayLayer" + index
            width: box.inner; height: Theme.rowDense
            Rectangle {
                anchors.fill: parent; radius: Theme.radiusCtl
                color: row.model.chosen ? Theme.accentSoft : area.containsMouse ? Theme.hover : "transparent"
            }
            MouseArea {
                id: area
                anchors.fill: parent; hoverEnabled: true
                onClicked: box.layers.choose(row.model.id)
                onDoubleClicked: if (row.model.id !== "") namer.visible = true
            }
            Text {
                anchors { left: parent.left; leftMargin: Theme.gap; right: amount.left; rightMargin: Theme.gap
                          verticalCenter: parent.verticalCenter }
                visible: !namer.visible
                text: row.model.label; elide: Text.ElideRight
                color: row.model.on ? Theme.fg : Theme.fg4; font.family: uiFont; font.pixelSize: Theme.body
            }
            NameBox {
                id: namer
                objectName: "clayLayerName" + row.index
                visible: false
                anchors { left: parent.left; leftMargin: Theme.gap; right: amount.left; rightMargin: Theme.gap
                          verticalCenter: parent.verticalCenter }
                current: row.model.label
                onDone: (t) => { visible = false; box.layers.rename(row.model.id, t) }
                onCancelled: visible = false
            }
            Text {
                id: amount
                anchors { right: eye.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                text: row.model.amount; color: row.model.on ? Theme.fg2 : Theme.fg4
                font.family: uiFont; font.pixelSize: Theme.body
            }
            Item {      // the eye: open = on, struck through = off (the Base has none: it is always there)
                id: eye
                objectName: "clayLayerEye" + row.index
                anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                width: row.model.id === "" ? 0 : Theme.rowDense; height: Theme.rowDense
                visible: row.model.id !== ""
                Canvas {
                    anchors.centerIn: parent; width: 16; height: 16
                    property color ink: eyeArea.containsMouse ? Theme.fg : Theme.fg2
                    property bool struck: !row.model.on
                    onInkChanged: requestPaint()
                    onStruckChanged: requestPaint()
                    onPaint: {
                        const g = getContext("2d")
                        g.reset(); g.strokeStyle = ink; g.fillStyle = ink; g.lineWidth = 1.5; g.lineCap = "round"
                        g.beginPath(); g.moveTo(1.5, 8); g.quadraticCurveTo(8, 1, 14.5, 8); g.quadraticCurveTo(8, 15, 1.5, 8); g.stroke()
                        g.beginPath(); g.ellipse(6, 6, 4, 4); g.fill()
                        if (struck) { g.beginPath(); g.moveTo(2.5, 13.5); g.lineTo(13.5, 2.5); g.stroke() }
                    }
                }
                MouseArea {
                    id: eyeArea
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: box.layers.toggleOn(row.model.id)
                }
            }
        }
    }
    Item { width: 1; height: box.layers.chosen !== "" ? Theme.gap : 0 }
    Repeater {      // the chosen layer's Amount
        objectName: "clayLayerRows"
        model: box.layers.rows.rows
        delegate: InspectorRow { width: box.width; bridge: box.layers.rows; instant: box.layers.rows.rows.instant }
    }
    Item { width: 1; height: box.layers.chosen !== "" ? Theme.gap : 0 }
    RowButton {
        objectName: "clayLayerMore"
        visible: box.layers.chosen !== ""
        text: "⋯"
        menu: [{ value: "bake", label: "Bake into Base" }, { value: "remove", label: "Remove layer" }]
        onChosen: (v) => v === "bake" ? box.layers.bake(box.layers.chosen) : box.layers.remove(box.layers.chosen)
    }
}
