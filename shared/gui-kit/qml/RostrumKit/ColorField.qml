import QtQuick
import "."

// A colour: a swatch inside the field frame and the hex value, typed like any text ("#rrggbb", "#" optional).
// The app checks the value (a bad one is refused by the operation, loudly); a full picker comes later.
FieldFrame {
    id: f
    property string hex: "#ffffff"
    signal edited(string value)

    editable: true
    text: hex.toUpperCase()
    leading: Rectangle {
        width: 14; height: 14; radius: 3
        color: f.hex; border.width: 1; border.color: Qt.rgba(1, 1, 1, 0.18)
    }
    onCommitted: (t) => {
        var v = t.trim().toLowerCase()
        f.edited(v.charAt(0) === "#" ? v : "#" + v)
    }
}
