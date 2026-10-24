import QtQuick
import RostrumKit

// A painting opened on its own (painting_open.py, mock-4), under Seamless and Draw each frame: its Size (W, H; strokes
// keep their px from the top-left), its Loop while it draws each frame (a painted fill never runs out: Loop or
// Ping-pong), and Used by: the layers using it, each a link back to the scene with that layer picked. Each edit is one
// painting.set (backend.paintLayers.setPainting).
Column {
    id: orows
    property int labelColumn: 0
    property int rowH: Theme.row
    width: parent ? parent.width : 0
    visible: backend.opened.on
    readonly property var info: backend.opened.info
    readonly property real fieldW: width - labelColumn - Theme.keyGutter
    readonly property real half: (fieldW - Theme.grid) / 2

    component Label: Text {
        width: orows.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
    }
    component Side: Item {       // "W 128 px": one side of the size
        id: side
        property string letter: ""
        property string field: ""
        property real now: 0
        property real scrubbed: 0
        width: orows.half; height: orows.rowH
        Text { id: letterText; anchors.verticalCenter: parent.verticalCenter; text: side.letter; color: Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.label }
        NumberField {
            objectName: "paintingSize" + side.letter
            x: letterText.width + Theme.grid; width: side.width - x; anchors.verticalCenter: parent.verticalCenter
            value: side.now; from: 1; to: 8192; step: 1; unit: "px"; label: side.letter === "W" ? "Width" : "Height"
            onEdited: (v) => backend.paintLayers.setPainting(side.field, Math.round(v))
            onScrubbed: (v) => side.scrubbed = v
            onScrubEnded: backend.paintLayers.setPainting(side.field, Math.round(side.scrubbed))
        }
    }

    Item {
        width: orows.width; height: orows.rowH
        Label { text: "Size" }
        Row { x: orows.labelColumn; spacing: Theme.grid; anchors.verticalCenter: parent.verticalCenter
              Side { letter: "W"; field: "w"; now: orows.info.w || 1 }
              Side { letter: "H"; field: "h"; now: orows.info.h || 1 } }
    }
    Item {
        visible: orows.info.eachFrame === true
        width: orows.width; height: orows.rowH
        Label { text: "Loop" }
        Segmented { objectName: "paintingLoop"; x: orows.labelColumn; width: orows.fieldW; anchors.verticalCenter: parent.verticalCenter
                    options: [{ value: "loop", label: "Loop" }, { value: "pingpong", label: "Ping-pong" }]
                    current: orows.info.loop || "loop"; onPicked: (v) => backend.paintLayers.setPainting("loop", v) }
    }
    Item {
        visible: (orows.info.uses || []).length > 0
        width: orows.width; height: Math.max(orows.rowH, uses.height)
        Label { text: "Used by"; anchors.verticalCenter: undefined; y: (orows.rowH - height) / 2 }
        Flow {
            id: uses
            x: orows.labelColumn; width: orows.fieldW; y: (orows.rowH - Theme.body - 4) / 2
            spacing: 0
            Repeater {
                model: orows.info.uses || []
                delegate: Text {
                    required property var modelData
                    required property int index
                    text: modelData.name + (index < orows.info.uses.length - 1 ? ", " : "")
                    color: useArea.containsMouse ? Theme.fg : Theme.accent
                    font.family: uiFont; font.pixelSize: Theme.body
                    MouseArea { id: useArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: backend.opened.goToUse(modelData.id) }
                    HoverTip { hovered: useArea.containsMouse; text: "Back to the scene with " + modelData.name + " picked" }
                }
            }
        }
    }
}
