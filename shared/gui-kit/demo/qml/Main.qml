import QtQuick
import RostrumKit

// The kit demo: the app shell on the toy document. Left: items. Centre: a viewer stand-in. Right: the inspector.
// Bottom, full width: a timeline stand-in.
AppShell {
    id: shell
    bridge: backend
    appName: "Rostrum"
    documentName: "Kit demo"
    saveWord: "Saved"

    left: ItemList { anchors.fill: parent; bridge: backend }
    centre: Viewer { anchors.fill: parent }
    right: Inspector { anchors.fill: parent; bridge: backend }
    bottom: Timeline { anchors.fill: parent }
}
