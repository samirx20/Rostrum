import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// One window: top bar, project | viewer + timeline | inspector, and the Ctrl+K command bar on top.
// Everything that changes the document calls backend.select / backend.setValue (also the demo script does).
ApplicationWindow {
    id: app
    visible: true
    width: 1600; height: 960
    minimumWidth: 1100; minimumHeight: 680
    title: "Rostrum — GUI mock (Qt)"
    color: Theme.app
    font.family: uiFont
    font.pixelSize: Theme.body

    readonly property var items: backend.itemList()
    function step(d) {
        var i = items.findIndex(x => x.id === backend.selected)
        backend.select(items[(i + d + items.length) % items.length].id)
    }
    function flip(item, param) { backend.setValue(item, param, !backend.value(item, param)) }

    readonly property var commands: items.map(function(it) {
        return { name: "Select " + it.name, hint: it.kind, run: function() { backend.select(it.id) } } })
        .concat([
        { name: "Toggle depth of field", hint: "Main camera", run: function() { flip("cam1", "dof") } },
        { name: "Toggle motion blur", hint: "Main camera", run: function() { flip("cam1", "motionBlur") } },
        { name: "Toggle animate on", hint: "Title", run: function() { flip("title", "animateOn") } },
        { name: "Toggle shadows", hint: "Key light", run: function() { flip("key", "shadows") } },
        { name: "Select next item", hint: "↓", run: function() { step(1) } },
        { name: "Select previous item", hint: "↑", run: function() { step(-1) } }])

    Shortcut { sequence: "Ctrl+K"; onActivated: commandBar.open() }
    Shortcut { sequence: "Down"; enabled: !commandBar.opened; onActivated: app.step(1) }
    Shortcut { sequence: "Up"; enabled: !commandBar.opened; onActivated: app.step(-1) }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0
        TopBar { onCommandClicked: commandBar.open(); Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.leftMargin: Theme.gap; Layout.rightMargin: Theme.gap; Layout.bottomMargin: Theme.gap
            spacing: Theme.gap
            ProjectPanel { doc: backend; Layout.preferredWidth: 248; Layout.fillHeight: true }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                spacing: Theme.gap
                Viewer { doc: backend; Layout.fillWidth: true; Layout.fillHeight: true }
                Timeline { Layout.fillWidth: true; Layout.preferredHeight: 168 }
            }
            Inspector { doc: backend; Layout.preferredWidth: 280; Layout.fillHeight: true }
        }
    }
    CommandBar { id: commandBar; app: app }
}
