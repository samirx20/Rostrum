import QtQuick
import RostrumKit

// Under "Draw each frame" while it is on (painting design §2.5, mockup paint-03): the drawing navigator (‹ Drawing 5 of 9
// · held 2 frames ›, also , and .), New and Copy (Alt+N, Alt+Shift+N), New ones hold 1 · 2 · 3 · 4 (the layer's
// newHold), Onion skin and, while it is on, how many drawings Before (red) and After (green) it shows (painter).
Column {
    id: de
    width: parent ? parent.width : 0
    visible: backend.paintLayers.onionApplies
    readonly property int labelColumn: Theme.labelColumnFor(width)
    readonly property real fieldW: width - labelColumn - Theme.keyGutter
    readonly property real wide: Theme.wideFor(width)
    readonly property var now: painter.now
    readonly property var counts: [0, 1, 2, 3, 4, 5].map(k => ({ value: k, label: k === 1 ? "1 drawing" : k + " drawings" }))

    component Label: Text {
        width: de.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
    }
    component Line: Item { width: de.width; height: Theme.row }
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

    Line {      // the navigator
        objectName: "drawingNavigator"
        Rectangle { width: de.wide; height: parent.height - 4; anchors.verticalCenter: parent.verticalCenter
                    radius: Theme.radiusCtl; color: Theme.raised }
        Arrow { step: -1; x: 0 }
        Text {
            width: de.wide - 2 * Theme.row; x: Theme.row; anchors.verticalCenter: parent.verticalCenter
            horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
            color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont; font.features: { "tnum": 1 }
            text: !de.now.has ? "No drawing here" : "Drawing " + de.now.index + " of " + de.now.count
                  + (de.now.last ? " · held to the end" : " · held " + de.now.held + (de.now.held === 1 ? " frame" : " frames"))
        }
        Arrow { step: 1; x: de.wide - width }
    }
    Line {      // New · Copy
        Row {
            spacing: Theme.grid; anchors.verticalCenter: parent.verticalCenter
            Button { objectName: "newDrawing"; width: (de.wide - Theme.grid) / 2; text: "New"; hint: "Alt N"
                     help: "A blank drawing after this one (or at the playhead on an empty frame)"; onClicked: painter.newFrame(false) }
            Button { objectName: "copyDrawing"; width: (de.wide - Theme.grid) / 2; text: "Copy"; hint: "Alt Shift N"
                     visible: de.now.has === true
                     help: "A copy of this drawing after it, to change part of it"; onClicked: painter.newFrame(true) }
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
    Line {
        Label { text: "Onion skin" }
        Toggle { objectName: "onionSkin"; x: de.labelColumn; anchors.verticalCenter: parent.verticalCenter
                 checked: painter.onionOn; onToggled: (v) => painter.setOnion(v) }
    }
    Repeater {      // Before (red) · After (green): how many drawings each way
        model: painter.onionOn ? [{ side: "before", label: "Before", colour: Theme.danger },
                                  { side: "after", label: "After", colour: Theme.ok }] : []
        delegate: Line {
            id: ol
            required property var modelData
            Label { text: ol.modelData.label }
            Rectangle { x: de.labelColumn - Theme.gap - width; width: 10; height: 10; radius: 2
                        anchors.verticalCenter: parent.verticalCenter; color: ol.modelData.colour }
            ChoiceField {
                x: de.labelColumn; width: de.fieldW; anchors.verticalCenter: parent.verticalCenter
                options: de.counts; current: painter.onionReach[ol.modelData.side]
                onPicked: (v) => painter.setOnionReach(ol.modelData.side, v)
            }
        }
    }
}
