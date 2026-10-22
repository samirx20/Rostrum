import QtQuick
import "."

// The window's shortcuts, made from the key map. `hub.keys` is [{job, keys: [sequences], label}]; a pressed key
// calls hub.key(job). Put one in the root window. `skip`: jobs the host handles itself (a text field's own keys).
// `enabled: false` turns every shortcut off (a dialog with its own typing).
Instantiator {
    id: km
    property var hub
    property bool enabled: true
    property var skip: []
    model: hub ? hub.keys : []
    delegate: Shortcut {
        required property var modelData
        sequences: modelData.keys
        context: Qt.WindowShortcut
        enabled: km.enabled && km.skip.indexOf(modelData.job) < 0
        onActivated: km.hub.key(modelData.job)
    }
}
