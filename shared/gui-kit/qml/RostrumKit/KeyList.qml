import QtQuick
import QtQuick.Controls as QQC
import "."

// The key list (Ctrl+/, INTERACTION.md 1.17): every key of this app, grouped by job, searchable. Built from the same
// key map the shortcuts are made from (`keys`: the hub's [{job, keys, label, area}]), so it can never be out of date.
// Esc closes it and the keys go back to the work.
QQC.Popup {
    id: dlg
    objectName: "keyList"
    property var keys: []
    property string query: ""
    readonly property var shown: {
        const words = query.toLowerCase().split(/\s+/).filter(w => w)
        const rows = keys.filter(k => k.keys.length && words.every(w => (k.label + " " + k.keys.join(" ") + " " + k.area)
                                                                          .toLowerCase().indexOf(w) >= 0))
        const out = []
        let area = ""
        for (const r of rows) {
            if (r.area !== area) { area = r.area; out.push({ head: area }) }
            out.push(r)
        }
        return out
    }
    signal done()
    parent: QQC.Overlay.overlay
    width: Math.min(parent.width - 4 * Theme.groupGap, 560); height: parent.height - 4 * Theme.groupGap
    x: Math.round((parent.width - width) / 2); y: Math.round((parent.height - height) / 2)
    modal: true; focus: true; padding: Theme.pad
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    onOpened: { find.input.text = ""; query = ""; find.input.forceActiveFocus() }
    onClosed: done()

    Text { id: title; text: "Keys"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
    IconButton { anchors { right: parent.right; verticalCenter: title.verticalCenter } glyph: "×"; kind: "ghost"
                 tip: "Close the key list"; job: "key_list"; onClicked: dlg.close() }
    FieldFrame {
        id: find
        anchors { left: parent.left; right: parent.right; top: title.bottom; topMargin: Theme.gap }
        height: Theme.field; editable: true; placeholder: "Find a key or what it does"
        Connections { target: find.input; function onTextEdited() { dlg.query = find.input.text } }
        onEscaped: dlg.close()
    }
    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: find.bottom; bottom: parent.bottom; topMargin: Theme.gap }
        clip: true; boundsBehavior: Flickable.StopAtBounds
        model: dlg.shown
        delegate: Item {
            required property var modelData
            width: list.width; height: modelData.head ? Theme.rowDense + Theme.grid : Theme.rowDense
            Text { visible: !!parent.modelData.head; anchors.bottom: parent.bottom; text: parent.modelData.head || ""
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
                   font.capitalization: Font.AllUppercase; font.letterSpacing: Theme.capsSpacing }
            Text { visible: !parent.modelData.head; anchors.verticalCenter: parent.verticalCenter
                   width: parent.width - keysRow.width - Theme.gap; elide: Text.ElideRight
                   text: parent.modelData.label || ""; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
            Row {
                id: keysRow
                visible: !parent.modelData.head
                anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                spacing: Theme.grid
                Repeater { model: parent.parent.modelData.keys || []
                           KeyHint { required property string modelData; text: modelData.replace(/\+/g, " ") } }
            }
        }
        EmptyHint { visible: list.count === 0; width: list.width; y: Theme.groupGap
                    text: dlg.query ? "Nothing called “" + dlg.query + "”. Try a shorter word." : "This app has no keys yet." }
    }
    VScrollBar { flick: list }
}
