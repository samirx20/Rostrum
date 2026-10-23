import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Look harness for the open-if-changed groups option: the Inspector on a 3D-style light. See groups_preview.py.
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1280; height: 720
    color: Theme.app
    Inspector { x: Theme.gap; y: Theme.gap; width: Theme.sidePanel; height: parent.height - 2 * Theme.gap; bridge: backend }
}
