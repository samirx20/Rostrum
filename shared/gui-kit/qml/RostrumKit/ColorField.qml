import QtQuick
import QtQuick.Controls as QQC
import "."

// A colour: the swatch alone fills the field box; a click (or Enter / Space) opens the picker under it, where the hex
// value is typed ("#rrggbb", "#" optional; Enter sets it, Esc closes). The app checks the value (a bad one is refused
// by the operation, loudly). `atRest` ("Mixed") shows in words beside a small swatch.
FieldFrame {
    id: f
    property string hex: "#ffffff"
    signal edited(string value)

    activeFocusOnTab: true
    engaged: picker.visible
    text: ""
    leading: Rectangle {
        width: f.atRest ? 14 : f.width - 2 * Theme.gap; height: 14; radius: 3
        color: f.hex; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18)
    }
    TapHandler { onTapped: picker.open() }
    Keys.onReturnPressed: picker.open()
    Keys.onSpacePressed: picker.open()

    QQC.Popup {
        id: picker
        y: f.height + 2
        width: Math.max(f.width, 160); padding: Theme.grid
        focus: true
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        onOpened: { hexField.input.text = f.hex.toUpperCase(); hexField.input.forceActiveFocus(); hexField.input.selectAll() }
        contentItem: FieldFrame {
            id: hexField
            editable: true
            text: f.hex.toUpperCase()
            leading: Rectangle { width: 14; height: 14; radius: 3; color: f.hex; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18) }
            onCommitted: (t) => {
                const v = t.trim().toLowerCase()
                f.edited(v.charAt(0) === "#" ? v : "#" + v)
            }
            onEntered: picker.close()
            onEscaped: picker.close()
        }
    }
}
