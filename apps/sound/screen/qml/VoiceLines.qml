import QtQuick
import RostrumKit

// A voice track's lines (text + when) and Make voice (beside the Editor), which shows only while a line has no audio yet.
// Clicking a line selects it, so the inspector shows its fields (words, time, take, level, fades). "Type what she says":
// Enter adds the line at the playhead (or after the last line) and its speech is made at once (editorSide.typeLine);
// a line being spoken shows "Speaking…". Without the voice model, one sentence says so.
Column {
    id: v
    property string trackId: ""
    property var lines: []
    property int missing: 0
    property string status: ""
    property bool busy: false
    property bool failed: false
    spacing: Theme.grid

    Repeater {
        model: v.lines
        delegate: Rectangle {
            required property var modelData
            width: v.width; height: Theme.rowDense + 6
            radius: Theme.radiusCtl
            color: !!backend.picked[modelData.id] ? Theme.accentSoft : area.containsMouse ? Theme.hover : Theme.raised
            MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; onPressed: { backend.focusArea("arrange"); backend.select(modelData.id) } }
            Rectangle { id: dot; width: 6; height: 6; radius: 3; x: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                        color: modelData.making ? Theme.accent : modelData.made ? Theme.ok : Theme.warn
                        SequentialAnimation on opacity { running: modelData.making; loops: Animation.Infinite
                            NumberAnimation { to: 0.3; duration: 500 } NumberAnimation { to: 1; duration: 500 } } }
            Row {
                id: right
                anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.grid
                Text { visible: modelData.canBack; text: "◂"; color: backArea.containsMouse ? Theme.fg : Theme.fg3
                       font.family: uiFont; font.pixelSize: Theme.body
                       MouseArea { id: backArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                                   onClicked: editorSide.stepTake(modelData.id, -1) }
                       HoverTip { text: "Earlier take"; hovered: backArea.containsMouse; pressed: backArea.pressed } }
                Text { visible: modelData.take !== ""; text: modelData.take; color: Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.label }
                Text { visible: modelData.canNext; text: "▸"; color: nextArea.containsMouse ? Theme.fg : Theme.fg3
                       font.family: uiFont; font.pixelSize: Theme.body
                       MouseArea { id: nextArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true
                                   onClicked: editorSide.stepTake(modelData.id, 1) }
                       HoverTip { text: "Later take"; hovered: nextArea.containsMouse; pressed: nextArea.pressed } }
                Text { id: when
                       text: modelData.making ? "Speaking…" : modelData.when; color: modelData.making ? Theme.accent : Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.body }
            }
            Text { anchors.left: dot.right; anchors.leftMargin: Theme.gap; anchors.right: right.left; anchors.rightMargin: Theme.gap
                   id: words; anchors.verticalCenter: parent.verticalCenter; text: modelData.text; elide: Text.ElideRight
                   color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                   HoverTip { text: words.truncated ? modelData.text : ""; hovered: area.containsMouse; pressed: area.pressed } }
        }
    }
    FieldFrame {   // type a line: Enter adds it and its speech is made at once
        id: say
        width: v.width; editable: true; placeholder: "Type what she says"
        onEntered: if (editorSide.typeLine(v.trackId, say.input.text)) say.input.text = ""
    }
    ModelDownload { width: v.width; fetch: editorSide.voiceDownload }    // asks before the voice model is downloaded
    Text { visible: !!editorSide.track.voiceMissing && editorSide.voiceDownload.state === "idle" && editorSide.track.voiceMissing !== v.status
           width: v.width; wrapMode: Text.WordWrap; text: editorSide.track.voiceMissing || ""
           color: Theme.warn; font.family: uiFont; font.pixelSize: Theme.label }
    Item {
        width: v.width; height: visible ? Theme.button + Theme.gap : 0
        visible: (v.missing > 0 || v.status !== "") && editorSide.voiceDownload.state === "idle"   // the download question says it
        Button {
            id: make
            y: Theme.gap; visible: v.missing > 0 && !v.busy
            text: "Make voice"; kind: "primary"
            onClicked: editorSide.makeVoice(v.trackId)
        }
        Text {
            anchors.left: make.visible ? make.right : parent.left; anchors.leftMargin: make.visible ? Theme.gap : 0
            anchors.right: parent.right; anchors.verticalCenter: make.verticalCenter
            text: v.status; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
            color: v.failed ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
        }
    }
}
