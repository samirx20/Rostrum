import QtQuick
import QtQuick.Controls as QQC
import "."

// A choice: the field frame showing the current option, a drawn arrow at the right (vertically centred,
// not a font glyph), and our own list under it. Click, Space or Enter opens; Up / Down move; Enter picks; Esc closes.
FieldFrame {
    id: f
    property var options: []              // [{value, label}] or plain strings: the field shows the label, sends the value
    property var current: ""              // a value of any type: matched to the options as text (48000 == "48000")
    readonly property bool opened: menu.opened
    signal picked(var value)              // the option's own value, type kept (a number stays a number)
    function valueAt(i) { const o = options[i]; return typeof o === "string" ? o : o.value }
    function labelAt(i) { const o = options[i]; return typeof o === "string" ? o : o.label }
    function same(a, b) { return String(a) === String(b) }
    function indexOf(v) { for (let i = 0; i < options.length; i++) if (same(valueAt(i), v)) return i; return -1 }
    function open() { menu.highlighted = Math.max(0, indexOf(current)); menu.open() }

    text: indexOf(current) >= 0 ? labelAt(indexOf(current)) : String(current === undefined || current === null ? "" : current)
    engaged: menu.opened
    activeFocusOnTab: true
    Keys.onSpacePressed: open()
    Keys.onReturnPressed: open()
    trailing: Chevron { open: menu.opened }

    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { f.forceActiveFocus(); f.open() } }

    QQC.Popup {
        id: menu
        property int highlighted: 0
        y: f.height + 2
        width: f.width
        padding: Theme.grid
        margins: Theme.gap
        focus: true
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }
        contentItem: Column {
            focus: true
            Keys.onUpPressed: menu.highlighted = Math.max(0, menu.highlighted - 1)
            Keys.onDownPressed: menu.highlighted = Math.min(f.options.length - 1, menu.highlighted + 1)
            Keys.onReturnPressed: pick(menu.highlighted)
            Keys.onEnterPressed: pick(menu.highlighted)
            function pick(i) { menu.close(); if (!f.same(f.valueAt(i), f.current)) f.picked(f.valueAt(i)) }
            Repeater {
                model: f.options
                delegate: Rectangle {
                    id: opt
                    required property int index
                    width: menu.availableWidth; height: Theme.popupRow; radius: 4
                    color: index === menu.highlighted ? Theme.hover : "transparent"
                    Text {  // same left inset as the field's own text, so the list lines up with it
                        anchors.left: parent.left; anchors.leftMargin: Theme.gap - menu.padding
                        anchors.right: tick.left; anchors.verticalCenter: parent.verticalCenter
                        text: f.labelAt(opt.index); elide: Text.ElideRight
                        color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                    }
                    Rectangle {  // the current option: a small accent dot at the right
                        id: tick
                        visible: f.same(f.valueAt(opt.index), f.current)
                        anchors.right: parent.right; anchors.rightMargin: Theme.gap - menu.padding + 2
                        anchors.verticalCenter: parent.verticalCenter
                        width: 6; height: 6; radius: 3; color: Theme.accent
                    }
                    MouseArea { anchors.fill: parent; hoverEnabled: true
                                onEntered: menu.highlighted = opt.index; onClicked: parent.parent.pick(opt.index) }
                }
            }
        }
    }
}
