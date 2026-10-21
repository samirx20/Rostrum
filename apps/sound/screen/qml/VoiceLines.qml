import QtQuick
import RostrumKit

// A voice card's lines (text + when) and Make voice, which shows only while a line has no audio yet.
// Clicking a line selects it, so the inspector shows its fields (words, time, take, level, fades).
Column {
    id: v
    property string trackId: ""
    property var lines: []
    property int missing: 0
    property string status: ""
    property bool busy: false
    property bool failed: false
    spacing: Theme.grid

    Text { text: "Lines"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
           bottomPadding: 2 }
    Repeater {
        model: v.lines
        delegate: Rectangle {
            required property var modelData
            width: v.width; height: Theme.rowDense + 6
            radius: Theme.radiusCtl
            color: backend.selected === modelData.id ? Theme.accentSoft : area.containsMouse ? Theme.hover : Theme.raised
            MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; onPressed: backend.select(modelData.id) }
            Rectangle { id: dot; width: 6; height: 6; radius: 3; x: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                        color: modelData.made ? Theme.ok : Theme.warn }
            Text { id: when; anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                   text: modelData.when; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body }
            Text { anchors.left: dot.right; anchors.leftMargin: Theme.gap; anchors.right: when.left; anchors.rightMargin: Theme.gap
                   anchors.verticalCenter: parent.verticalCenter; text: modelData.text; elide: Text.ElideRight
                   color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
        }
    }
    Text { visible: v.lines.length === 0; text: "No lines yet — add one with line.add"
           color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
    Item {
        width: v.width; height: visible ? Theme.button + Theme.gap : 0
        visible: v.missing > 0 || v.status !== ""
        Button {
            id: make
            y: Theme.gap; visible: v.missing > 0 && !v.busy
            text: "Make voice"; kind: "primary"
            onClicked: instruments.makeVoice(v.trackId)
        }
        Text {
            anchors.left: make.visible ? make.right : parent.left; anchors.leftMargin: make.visible ? Theme.gap : 0
            anchors.right: parent.right; anchors.verticalCenter: make.verticalCenter
            text: v.status; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
            color: v.failed ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
        }
    }
}
