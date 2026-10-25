import QtQuick
import QtQuick.Controls as QQC
import "."

// A choice: the field frame showing the current option, a drawn arrow at the right (vertically centred,
// not a font glyph), and our own list under it. Click, Space or Enter opens; Up / Down move; Enter picks; Esc closes.
// A long list (more than 15) or one whose options carry `face` (a font family: the option is drawn in it, a font picker)
// opens with a search line on top: what is typed keeps only the options whose label holds it. Options carrying `section`
// are shown under a small heading per run ("In Rostrum", "On this computer"); the list scrolls only past 20 rows or the window's height
// (a 13-key list shows whole).
FieldFrame {
    id: f
    property var options: []              // [{value, label}] or plain strings: the field shows the label, sends the value
    property var current: ""              // a value of any type: matched to the options as text (48000 == "48000")
    property string more: ""              // a last entry that adds an option ("Load picture…"): picking it is moreChosen()
    readonly property bool opened: pop.item ? pop.item.opened : false
    signal moreChosen()
    signal picked(var value)              // the option's own value, type kept (a number stays a number)
    function valueAt(i) { const o = options[i]; return typeof o === "string" ? o : o.value }
    function labelAt(i) { const o = options[i]; return typeof o === "string" ? o : o.label }
    function detailAt(i) { const o = options[i]; return typeof o === "string" ? "" : (o.detail || "") }   // an option's longer words: shown in the open list under its name, never in the closed field
    function faceAt(i) { const o = options[i]; return typeof o === "string" ? "" : (o.face || "") }
    function sectionAt(i) { const o = options[i]; return typeof o === "string" ? "" : (o.section || "") }   // a heading over each run of options sharing one
    function same(a, b) { return String(a) === String(b) }
    function indexOf(v) { for (let i = 0; i < options.length; i++) if (same(valueAt(i), v)) return i; return -1 }
    readonly property bool searchable: options.length > 15 || options.some(o => typeof o === "object" && !!o.face)
    property string query: ""
    readonly property var shown: {      // the options' indices the search keeps (all without one)
        const q = query.trim().toLowerCase(), out = []
        for (let i = 0; i < options.length; i++) if (!q || labelAt(i).toLowerCase().indexOf(q) >= 0) out.push(i)
        return out
    }
    function open() { query = ""; pop.asynchronous = false; pop.active = true; pop.item.highlighted = Math.max(0, shown.indexOf(indexOf(current))); pop.item.open() }

    text: indexOf(current) >= 0 ? labelAt(indexOf(current)) : String(current === undefined || current === null ? "" : current)
    engaged: f.opened
    activeFocusOnTab: true
    Keys.onSpacePressed: open()
    Keys.onReturnPressed: open()
    trailing: Chevron { open: f.opened }

    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { f.forceActiveFocus(); f.open() } }

    // The list is made at the first opening only: a settings panel has a choice on most kinds' rows, and a popup with
    // its search line and list per field made each selection switch ~15 ms slower per choice.
    // A long searchable list (the Font list) is made a moment after its row shows, at idle and spread over frames
    // (an asynchronous Loader; open() finishes it at once if the click comes first): its first opening was ~50 ms.
    Loader { id: pop; active: false; asynchronous: true; sourceComponent: popup }
    Timer { interval: 150; running: f.searchable && f.visible && !pop.active; onTriggered: pop.active = true }
    Component { id: popup
    SmallPopup {
        id: menu
        ownKeys: ["Up", "Down", "Enter"]
        property int highlighted: 0
        y: f.height + 2
        width: f.width
        padding: Theme.grid
        margins: Theme.gap
        focus: true
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }
        onOpened: if (f.searchable) search.forceActiveFocus()
        contentItem: Column {
            id: list
            focus: true
            Keys.onUpPressed: menu.highlighted = Math.max(0, menu.highlighted - 1)
            Keys.onDownPressed: menu.highlighted = Math.min(f.shown.length - 1, menu.highlighted + 1)
            Keys.onReturnPressed: pickShown(menu.highlighted)
            Keys.onEnterPressed: pickShown(menu.highlighted)
            function pick(i) { menu.close(); if (!f.same(f.valueAt(i), f.current)) f.picked(f.valueAt(i)) }
            function pickShown(k) { if (k >= 0 && k < f.shown.length) pick(f.shown[k]) }
            Rectangle {   // the search line (a long list or a font list): type to keep only what matches
                visible: f.searchable
                width: menu.availableWidth; height: visible ? Theme.field : 0
                radius: Theme.radiusCtl; color: Theme.sunken; border.color: search.activeFocus ? Theme.accent : Theme.border
                TextInput {
                    id: search
                    objectName: "choiceSearch"
                    anchors { fill: parent; leftMargin: Theme.gap - menu.padding; rightMargin: Theme.gap }
                    verticalAlignment: TextInput.AlignVCenter; clip: true
                    color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                    text: f.query
                    onTextEdited: { f.query = text; menu.highlighted = 0 }
                    Keys.onUpPressed: menu.highlighted = Math.max(0, menu.highlighted - 1)
                    Keys.onDownPressed: menu.highlighted = Math.min(f.shown.length - 1, menu.highlighted + 1)
                    Keys.onReturnPressed: list.pickShown(menu.highlighted)
                    Keys.onEnterPressed: list.pickShown(menu.highlighted)
                    Keys.onEscapePressed: menu.close()
                    Text { visible: !search.text; anchors.verticalCenter: parent.verticalCenter; text: "Search"
                           color: Theme.fg3; font.pixelSize: Theme.body; font.family: uiFont }
                }
            }
            Text {   // the search keeps nothing
                visible: f.searchable && f.shown.length === 0
                height: visible ? Theme.popupRow : 0; leftPadding: Theme.gap - menu.padding; verticalAlignment: Text.AlignVCenter
                text: "Nothing called \"" + f.query.trim() + "\""; color: Theme.fg3; font.pixelSize: Theme.body; font.family: uiFont
            }
            ListView {   // the options (only those on screen are built: a font list can hold hundreds, each in its own face)
                id: optionList
                objectName: "choiceList"
                width: menu.availableWidth
                readonly property real room: (QQC.Overlay.overlay ? QQC.Overlay.overlay.height : 600) - 2 * (menu.margins + menu.padding) - y
                height: Math.min(contentHeight, Theme.popupRow * 20, Math.max(Theme.popupRow * 4, room))
                clip: true; boundsBehavior: Flickable.StopAtBounds
                model: f.shown
                currentIndex: menu.highlighted
                onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
                QQC.ScrollBar.vertical: QQC.ScrollBar { policy: optionList.contentHeight > optionList.height ? QQC.ScrollBar.AsNeeded : QQC.ScrollBar.AlwaysOff }
                delegate: Item {
                    id: slot
                    required property int modelData     // the option's own index
                    required property int index         // its place in the list shown
                    readonly property string section: f.sectionAt(modelData)
                    readonly property bool starts: section !== "" && (index === 0 || f.sectionAt(f.shown[index - 1]) !== section)
                    width: optionList.width; height: head.height + opt.height
                    Text {   // a group's heading ("In Rostrum", "On this computer") above its first option
                        id: head
                        visible: slot.starts; height: visible ? Theme.popupRow : 0
                        leftPadding: Theme.gap - menu.padding; verticalAlignment: Text.AlignBottom; bottomPadding: 4
                        text: slot.section; color: Theme.fg3; font.pixelSize: Theme.label; font.family: uiFont
                    }
                    Rectangle {
                        id: opt
                        y: head.height
                        readonly property int option: slot.modelData
                        readonly property int index: slot.index
                        readonly property string detail: f.detailAt(option)
                        width: parent.width; height: detail ? Theme.popupRow + detailText.implicitHeight + 2 : Theme.popupRow; radius: 4
                        color: index === menu.highlighted ? Theme.hover : "transparent"
                        Text {  // same left inset as the field's own text, so the list lines up with it
                            anchors.left: parent.left; anchors.leftMargin: Theme.gap - menu.padding
                            anchors.right: tick.left; y: opt.detail ? 4 : (parent.height - height) / 2
                            text: f.labelAt(opt.option); elide: Text.ElideRight
                            color: Theme.fg; font.pixelSize: Theme.body; font.family: f.faceAt(opt.option) || uiFont
                        }
                        Text {
                            id: detailText
                            visible: opt.detail !== ""
                            anchors.left: parent.left; anchors.leftMargin: Theme.gap - menu.padding
                            anchors.right: parent.right; anchors.rightMargin: Theme.gap
                            y: Theme.popupRow - 4; wrapMode: Text.WordWrap
                            text: opt.detail; color: Theme.fg3; font.pixelSize: Theme.label; font.family: uiFont
                        }
                        Rectangle {  // the current option: a small accent dot at the right
                            id: tick
                            visible: f.same(f.valueAt(opt.option), f.current)
                            anchors.right: parent.right; anchors.rightMargin: Theme.gap - menu.padding + 2
                            anchors.verticalCenter: parent.verticalCenter
                            width: 6; height: 6; radius: 3; color: Theme.accent
                        }
                        MouseArea { anchors.fill: parent; hoverEnabled: true
                                    onEntered: menu.highlighted = opt.index; onClicked: list.pick(opt.option) }
                    }
                }
            }
            Rectangle {  // "Load picture…": after a thin line, in the secondary colour (it adds a choice, it isn't one)
                objectName: "choiceMore"
                visible: f.more !== ""
                width: menu.availableWidth; height: visible ? Theme.popupRow : 0; radius: 4
                color: moreArea.containsMouse ? Theme.hover : "transparent"
                Rectangle { width: parent.width; height: 1; color: Theme.popupEdge }
                Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - menu.padding; anchors.verticalCenter: parent.verticalCenter
                       text: f.more; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont }
                MouseArea { id: moreArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: { menu.close(); f.moreChosen() } }
            }
        }
    }
    }
}
