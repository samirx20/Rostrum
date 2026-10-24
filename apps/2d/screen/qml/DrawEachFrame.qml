import QtQuick
import RostrumKit

// Under "Draw each frame" while it is on (painting design §2.5, mockup paint-03): the drawing navigator (‹ Drawing 5 of 9 ›,
// also , and .) with the drawing's hold at its right ("2 frames", "to the end"), New and Copy (keys in their hover help), New ones hold 1 · 2 · 3 · 4 (the layer's
// newHold), Onion skin and, while it is on, how many drawings Before (red) and After (green) it shows (painter).
Column {
    id: de
    width: parent ? parent.width : 0
    visible: backend.paintLayers.onionApplies
    readonly property int labelColumn: Theme.labelColumnFor(width)
    readonly property real fieldW: width - labelColumn - Theme.keyGutter
    readonly property real wide: Theme.wideFor(width)
    readonly property real holdW: Math.ceil(holdWords.advanceWidth) + 2      // as wide as the longest hold label says
    TextMetrics { id: holdWords; font.pixelSize: Theme.body; font.family: uiFont; text: "to the end" }
    readonly property var now: painter.now
    readonly property var counts: [0, 1, 2, 3, 4, 5].map(k => ({ value: k, label: k === 1 ? "1 drawing" : k + " drawings" }))

    component Label: Text {
        width: de.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
    }
    component Line: Item { width: de.width; height: Theme.tightFor(Window.height) ? Theme.rowTight : Theme.row }
    component Arrow: Item {     // ‹ or ›: one step to the previous / next drawing
        id: ar
        property int step: 1
        readonly property bool can: (step < 0 ? de.now.prev : de.now.next) != null
        width: Theme.row; height: parent.height
        Chevron { anchors.centerIn: parent; rotation: ar.step < 0 ? 90 : -90; color: arArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: arArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: painter.goFrame(ar.step) }
        HoverTip { hovered: arArea.containsMouse; text: ar.step < 0 ? "Previous drawing" : "Next drawing"; key: ar.step < 0 ? "," : "." }
        visible: can
    }

    Line {      // the navigator, and how long this drawing holds at the right
        objectName: "drawingNavigator"
        readonly property real navW: de.wide - de.holdW - Theme.gap
        Rectangle { width: parent.navW; height: parent.height - 4; anchors.verticalCenter: parent.verticalCenter
                    radius: Theme.radiusCtl; color: Theme.raised }
        Arrow { step: -1; x: 0 }
        Text {
            width: parent.navW - 2 * Theme.row; x: Theme.row; anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
            color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont; font.features: { "tnum": 1 }
            text: de.now.has ? "Drawing " + de.now.index + " of " + de.now.count : "No drawing here"
        }
        Arrow { step: 1; x: parent.navW - width }
        Text {      // the hold: "hold 2" frames, or "to end" for the last drawing
            visible: de.now.has === true
            x: de.wide - de.holdW; width: de.holdW; anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignRight; elide: Text.ElideRight
            color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; font.features: { "tnum": 1 }
            text: de.now.last ? "to the end" : de.now.held + (de.now.held === 1 ? " frame" : " frames")
        }
    }
    Line {      // New · Copy (their keys are in the hover help)
        Row {
            spacing: Theme.grid; anchors.verticalCenter: parent.verticalCenter
            Button { objectName: "newDrawing"; width: (de.wide - Theme.grid) / 2; height: Theme.row - 4; text: "New"; tip: "New drawing"; job: "new_drawing"
                     help: "A blank drawing after this one (or at the playhead on an empty frame)."; onClicked: painter.newFrame(false) }
            Button { objectName: "copyDrawing"; width: (de.wide - Theme.grid) / 2; height: Theme.row - 4; text: "Copy"; tip: "Copy drawing"; job: "copy_drawing"
                     visible: de.now.has === true
                     help: "A copy of this drawing after it, to change part of it."; onClicked: painter.newFrame(true) }
        }
    }
    Line {
        Label { text: "New ones hold" }
        Segmented {
            objectName: "newOnesHold"
            x: de.labelColumn; width: de.fieldW; anchors.verticalCenter: parent.verticalCenter
            options: ["1", "2", "3", "4"]; current: String(painter.newHold)
            onPicked: (v) => painter.setNewHold(Number(v))
        }
    }
    SwitchRow {      // Onion skin; while on, Show before (red) and Show after (green)
        switchName: "onionSkin"; visible: painter.onionHere; height: Theme.tightFor(Window.height) ? Theme.rowTight : Theme.row; labelColumn: de.labelColumn; label: "Onion skin"
        checked: painter.onionOn; onToggled: (v) => painter.setOnion(v)
    }
    Repeater {      // how many drawings each way
        model: painter.onionOn && painter.onionHere ? [{ side: "before", label: "Show before", colour: Theme.danger },
                                  { side: "after", label: "Show after", colour: Theme.ok }] : []
        delegate: Line {
            id: ol
            required property var modelData
            Label { text: ol.modelData.label }
            Rectangle { x: de.labelColumn - Theme.gap - width; width: 8; height: 8; radius: 2
                        anchors.verticalCenter: parent.verticalCenter; color: ol.modelData.colour }
            ChoiceField {
                x: de.labelColumn; width: de.fieldW; anchors.verticalCenter: parent.verticalCenter
                options: de.counts; current: painter.onionReach[ol.modelData.side]
                onPicked: (v) => painter.setOnionReach(ol.modelData.side, v)
            }
        }
    }
}
