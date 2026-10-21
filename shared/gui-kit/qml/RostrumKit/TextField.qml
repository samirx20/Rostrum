import QtQuick
import "."

// One line of text. Enter or leaving the field commits (one edited); Esc puts the old text back.
FieldFrame {
    id: f
    property string value: ""
    signal edited(string value)
    editable: true
    text: value
    onCommitted: (t) => f.edited(t)
}
