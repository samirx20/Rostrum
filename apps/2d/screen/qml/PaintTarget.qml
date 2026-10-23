import QtQuick
import RostrumKit

// Under the brush's quick rows while painting (painting design §2.1, §2.2, mockup paint-01): "Edit brush ›" (every
// brush setting on the same grid: painter.setEditing), Close gaps while Fill is on, then "Painting on": Layer ▾ (the
// selected layer, the other painted layers, New drawing: painter.targetChoices), Inside the outline (an element only:
// a drawing has no outline) and Draw each frame (backend.paintLayers.toggles), then the paint layers (PaintOn.qml).
// Absent while editing the brush.
Column {
    id: tg
    width: parent ? parent.width : 0
    visible: !painter.editing
    readonly property int labelColumn: Theme.labelColumnFor(width)
    readonly property real fieldW: width - labelColumn - Theme.keyGutter
    readonly property bool filling: backend.paintTool.now === "fill"

    component Label: Text {
        width: tg.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
        color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; elide: Text.ElideRight
    }
    component Line: Item { width: tg.width; height: Theme.row }
    component Heading: Item {
        property alias text: words.text
        width: tg.width; height: Theme.groupGap + Theme.rowDense
        Text { id: words; anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.grid + 2
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
    }

    Line {      // Fill: how far apart lines may be and still close an area
        visible: tg.filling
        Label { text: "Close gaps" }
        Segmented { x: tg.labelColumn; anchors.verticalCenter: parent.verticalCenter
                    options: backend.fill.gaps; current: backend.fill.gap; onPicked: (v) => backend.fill.setGap(v) }
    }
    Line {      // Edit brush ›
        objectName: "editBrush"
        visible: !tg.filling
        Rectangle { width: Theme.wideFor(tg.width); height: parent.height; radius: Theme.radiusCtl; color: Theme.hover; visible: editArea.containsMouse }
        Label { x: 0; text: "Edit brush"; color: editArea.containsMouse ? Theme.fg : Theme.fg2 }
        Chevron { x: Theme.wideFor(tg.width) - width - Theme.grid; anchors.verticalCenter: parent.verticalCenter
                  rotation: -90; color: editArea.containsMouse ? Theme.fg : Theme.fg3 }
        MouseArea { id: editArea; width: Theme.wideFor(tg.width); height: parent.height; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor; onClicked: painter.setEditing(true) }
    }
    Heading { text: "Painting on" }
    Line {
        Label { text: "Layer" }
        ChoiceField {
            objectName: "paintingOnLayer"
            x: tg.labelColumn; width: tg.fieldW; anchors.verticalCenter: parent.verticalCenter
            options: painter.targetChoices; current: painter.targetValue
            onPicked: (v) => painter.paintOn(v)
        }
    }
    Repeater {      // Inside the outline, Draw each frame (paint_fields), before any paint
        model: backend.paintLayers.toggles
        delegate: Line {
            id: tl
            required property var modelData
            Label { text: tl.modelData.label }
            Toggle { x: tg.labelColumn; anchors.verticalCenter: parent.verticalCenter; checked: tl.modelData.value
                     onToggled: (v) => backend.paintLayers.setToggle(tl.modelData.id, v) }
            HoverHandler { id: tHover }
            HoverTip { hovered: tHover.hovered; text: tl.modelData.help || "" }
        }
    }
    PaintOn { }
}
