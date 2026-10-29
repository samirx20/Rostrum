import QtQuick
import RostrumKit

// The Clay panel's Steps group (CL3; screen3d/clay_steps_qt.py, `viewport.clay.stepsObj`): the selected clay's steps,
// newest at the bottom, each its name or what it is. The eye hides a step (claystep.set hidden), a double-click names
// it in place (claystep.set name), a click shows that step's own rows under the list (the kit's InspectorRow,
// claystep.set). A ListView draws only the rows in sight: a clay may hold thousands of steps; past eight rows the list
// scrolls on its own and starts at the newest.
Column {
    id: box
    objectName: "claySteps"
    property real inner: width           // the tiles' width (the rows reach the panel's edge, as the brush rows do)
    readonly property var steps: viewport.clay.stepsObj
    readonly property int shown: Math.min(steps.count, 8)

    Item {
        width: box.inner; height: Math.max(head.implicitHeight, newLayer.height)
        Text { id: head; objectName: "clayStepsHead"; anchors.verticalCenter: parent.verticalCenter; text: "Steps"
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
        Text {      // a sculpt layer: the strokes after it go on it, with an Amount (ClayLayers.qml)
            id: newLayer
            objectName: "clayLayerAdd"
            anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
            text: "+ Layer"; color: layerArea.containsMouse ? Theme.fg : Theme.fg2
            font.family: uiFont; font.pixelSize: Theme.label
            height: Theme.rowDense; verticalAlignment: Text.AlignVCenter
            MouseArea { id: layerArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor; onClicked: viewport.clay.layersObj.add() }
            HoverTip { text: "New sculpt layer"; help: "The next strokes go on it, with an Amount to dial them in and out."; hovered: layerArea.containsMouse }
        }
    }
    Item { width: 1; height: Theme.gap }
    ListView {
        id: list
        objectName: "clayStepList"
        width: box.inner; height: box.shown * Theme.rowDense
        model: box.steps.items
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        reuseItems: true
        WheelScroll { flick: list }   // the first click after a wheel scroll lands (the kit's WheelScroll.qml)
        onCountChanged: positionViewAtEnd()
        Component.onCompleted: positionViewAtEnd()
        delegate: Item {
            id: row
            required property var model           // roles: id, label, hidden, chosen (ClaySteps.ROLES)
            required property int index
            objectName: "clayStep" + index
            width: ListView.view.width; height: Theme.rowDense
            Rectangle {
                anchors.fill: parent; radius: Theme.radiusCtl
                color: row.model.chosen ? Theme.accentSoft : area.containsMouse ? Theme.hover : "transparent"
            }
            MouseArea {
                id: area
                anchors.fill: parent; hoverEnabled: true
                onClicked: box.steps.choose(row.model.id)
                onDoubleClicked: namer.visible = true
            }
            Text {
                anchors { left: parent.left; leftMargin: Theme.gap; right: eye.left; rightMargin: Theme.gap
                          verticalCenter: parent.verticalCenter }
                visible: !namer.visible
                text: row.model.label; elide: Text.ElideRight
                color: row.model.hidden ? Theme.fg4 : Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
            }
            NameBox {
                id: namer
                objectName: "clayStepName" + row.index
                visible: false
                anchors { left: parent.left; leftMargin: Theme.gap; right: eye.left; rightMargin: Theme.gap
                          verticalCenter: parent.verticalCenter }
                current: row.model.label
                onDone: (t) => { visible = false; box.steps.rename(row.model.id, t) }
                onCancelled: visible = false
            }
            Item {      // the eye: open = shown, struck through = hidden
                id: eye
                objectName: "clayStepEye" + row.index
                anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                width: Theme.rowDense; height: Theme.rowDense
                visible: row.model.hidden || area.containsMouse || eyeArea.containsMouse || row.model.chosen
                Canvas {
                    id: eyeDraw
                    anchors.centerIn: parent; width: 16; height: 16
                    property color ink: eyeArea.containsMouse ? Theme.fg : Theme.fg2
                    property bool struck: row.model.hidden
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
                    onClicked: box.steps.toggleHidden(row.model.id)
                }
            }
        }
    }
    Item { width: 1; height: box.steps.chosen !== "" ? Theme.gap : 0 }
    Repeater {      // the chosen step's own rows: Puff, Blend, Mode, Radius, a stroke's Size and Strength …
        objectName: "clayStepRows"
        model: box.steps.rows.rows
        delegate: InspectorRow { width: box.width; bridge: box.steps.rows; instant: box.steps.rows.rows.instant }
    }
}
