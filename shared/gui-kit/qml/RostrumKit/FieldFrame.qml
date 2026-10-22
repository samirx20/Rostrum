import QtQuick
import "."

// The one field box. Number, text, choice and colour fields are all this frame, so the box, the underline,
// the hover and focus look, the padding and the text (font, size, left-aligned, vertically centred) are drawn
// here only and cannot drift between fields. A field adds an optional `leading` item (colour swatch) and
// `trailing` item (dropdown arrow), and says whether typing is allowed.
FocusScope {
    id: f
    property string text: ""
    property string prefix: ""          // dim, before the value ("f/")
    property string suffix: ""          // dim, after the value ("mm", "°")
    property string placeholder: ""
    property string atRest: ""          // shown at rest in place of the text (a path field: the file's own name)
    property int elide: Text.ElideRight   // how the text at rest is cut
    property bool editable: false       // typing allowed: a click puts the caret in
    property bool engaged: false        // the field says it is in use (scrubbing, list open): accent look
    readonly property bool active: engaged || input.activeFocus
    readonly property bool hovered: hoverHandler.hovered
    property alias input: input
    property alias leading: leadingSlot.data
    property alias trailing: trailingSlot.data
    signal committed(string text)       // Enter or focus loss with changed text
    signal entered()                    // Enter, whether or not the text changed
    signal arrow(int direction, bool big)  // Up / Down while typing (Shift = big)
    implicitWidth: 140
    implicitHeight: Theme.field

    HoverHandler { id: hoverHandler }

    Rectangle {  // the box: rounded top, square bottom that the underline closes
        id: box
        anchors.fill: parent
        topLeftRadius: Theme.radiusCtl; topRightRadius: Theme.radiusCtl
        bottomLeftRadius: 2; bottomRightRadius: 2
        color: f.active ? Theme.sunken : f.hovered ? Theme.hover : Theme.raised
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Rectangle {  // the underline: grey at rest, lighter on hover, accent when in use
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 1
        color: f.active ? Theme.accent : f.hovered ? Theme.lineHover : Theme.line
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }

    Row {
        id: leadingSlot
        anchors.left: parent.left; anchors.leftMargin: children.length ? Theme.grid + 2 : 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.grid
    }
    Text {
        id: prefixText
        visible: f.prefix !== ""
        anchors.left: leadingSlot.right; anchors.leftMargin: Theme.gap
        anchors.verticalCenter: parent.verticalCenter
        text: f.prefix; color: Theme.fg3; font: input.font
    }
    TextInput {
        id: input
        anchors.left: prefixText.visible ? prefixText.right : leadingSlot.right
        anchors.leftMargin: prefixText.visible ? 1 : Theme.gap
        anchors.right: trailingSlot.left; anchors.rightMargin: Theme.gap
        anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: TextInput.AlignLeft
        color: activeFocus ? Theme.fg : "transparent"     // at rest the elided copy below shows it, from the start
        selectionColor: Theme.accent; selectedTextColor: "white"
        font.pixelSize: Theme.body
        font.family: uiFont
        font.features: { "tnum": 1 }        // digits all one width, so numbers do not wobble while scrubbing
        clip: true
        readOnly: !f.editable
        activeFocusOnPress: f.editable
        selectByMouse: f.editable
        enabled: f.editable
        focus: true
        property string sent: ""        // what was last committed, so Enter + focus loss commit once
        function commit() { if (text !== f.text && text !== sent) { sent = text; f.committed(text) } }
        onAccepted: { commit(); f.entered(); focus = false }
        onActiveFocusChanged: if (activeFocus) sent = ""; else commit()
        Keys.onEscapePressed: { text = f.text; focus = false }
        Keys.onUpPressed: (e) => f.arrow(1, (e.modifiers & Qt.ShiftModifier) !== 0)
        Keys.onDownPressed: (e) => f.arrow(-1, (e.modifiers & Qt.ShiftModifier) !== 0)
    }
    Binding {  // the shown text follows the value, except while the person is typing
        target: input; property: "text"; value: f.text
        when: !input.activeFocus
        restoreMode: Binding.RestoreNone
    }
    Text {  // at rest: the text from its start, "…" where it doesn't fit (TextInput would show its end)
        visible: !input.activeFocus
        anchors { left: input.left; right: input.right; verticalCenter: parent.verticalCenter }
        text: f.atRest !== "" ? f.atRest : input.text; elide: f.elide; color: Theme.fg; font: input.font
    }
    Text {  // the unit sits right after the value, dim
        visible: f.suffix !== "" && input.text !== ""
        x: input.x + Math.min(input.contentWidth, input.width) + (/^[a-z]/i.test(f.suffix) ? 4 : 1)
        anchors.verticalCenter: parent.verticalCenter
        text: f.suffix; color: Theme.fg3; font: input.font
    }
    Text {
        visible: input.text === ""
        anchors.left: input.left; anchors.verticalCenter: parent.verticalCenter
        text: f.placeholder; color: Theme.fg4; font: input.font
    }
    Row {
        id: trailingSlot
        anchors.right: parent.right; anchors.rightMargin: children.length ? Theme.gap : 0
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.grid
    }
}
