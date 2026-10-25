import QtQuick
import "."

// A panel or sheet that is not a popup but closes on Esc like one (the guides drawer, History, Export, Sound's Library,
// the start screen): while `when` holds it is in OpenPopups (newest on top), so the window's one Esc (AppShell) reaches
// it wherever the keyboard is. Esc then sends `asked()`; the panel closes itself (or ends a preview first).
//     EscCloses { when: sheet.visible; area: sheet; onAsked: sheet.closed() }
QtObject {
    id: e
    property bool when: false
    property Item area: null                    // the panel: a text box inside it never keeps Esc from closing it
    property bool escCloses: true
    property var ownKeys: []
    signal asked()
    function close() { asked() }
    onWhenChanged: when ? OpenPopups.add(e) : OpenPopups.remove(e)
    Component.onCompleted: if (when) OpenPopups.add(e)
    Component.onDestruction: OpenPopups.remove(e)
}
