import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// A question in the window (unsaved changes, a recovery copy, a new project's name): a title, one plain sentence,
// an optional name field, and the answers as buttons (the last one is the main one). Esc = the first answer.
// ask(title, text, answers [{value, label, danger}], name) shows it; answered(value, name) says what was picked.
QQC.Popup {
    id: dlg
    property string title: ""
    property string text: ""
    property var answers: []
    property bool asksName: false
    signal answered(string value, string name)
    function ask(t, body, choices, name) {
        title = t; text = body; answers = choices
        asksName = name !== undefined; field.input.text = name || ""
        open()
        if (asksName) { field.input.forceActiveFocus(); field.input.selectAll() }
    }
    function pick(v) { close(); answered(v, field.input.text) }
    parent: QQC.Overlay.overlay
    x: Math.round((parent.width - width) / 2); y: Math.round(parent.height * 0.28)
    width: 440
    padding: Theme.groupGap
    modal: true; focus: true
    closePolicy: QQC.Popup.NoAutoClose
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }

    contentItem: FocusScope {
        implicitHeight: col.implicitHeight
        Keys.onEscapePressed: dlg.pick(dlg.answers[0].value)
        Column {
            id: col
            width: parent.width
            spacing: Theme.pad
            Text { text: dlg.title; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold
                   width: parent.width; wrapMode: Text.WordWrap }
            Text { text: dlg.text; visible: text !== ""; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
                   width: parent.width; wrapMode: Text.WordWrap; lineHeight: 1.25 }
            FieldFrame {
                id: field
                visible: dlg.asksName
                width: parent.width; height: 32
                editable: true
                placeholder: "Project name"
                onEntered: dlg.pick(dlg.answers[dlg.answers.length - 1].value)
            }
            Item { width: 1; height: Theme.grid }
            Row {
                anchors.right: parent.right
                spacing: Theme.gap
                Repeater {
                    model: dlg.answers
                    delegate: Button {
                        required property var modelData
                        required property int index
                        text: modelData.label
                        danger: !!modelData.danger
                        kind: index === dlg.answers.length - 1 ? "primary" : "normal"
                        onClicked: dlg.pick(modelData.value)
                    }
                }
            }
        }
    }
}
