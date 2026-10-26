import QtQuick
import RostrumKit

// One painting in the Library's Paintings section (painting_library.py): a 42 px picture (four repeats when the painting is
// seamless, so the repeat reads; the painting alone otherwise), its name and one small line. Click = use it on the picked
// layers (nothing picked: pick its uses), its Open button (↗) = open it, right-click = the menu, rename
// types in place. No double-click: its first click would already have put the painting on the picked layers.
Rectangle {
    id: row
    property var p: ({})                 // {id, name, line, seamless, picture}
    property int canUse: 0               // layers a click would fill (the right-click menu says it)
    signal asked(string what)            // "use", "open", "duplicate", "delete" from the menu; the rows' own clicks too
    signal renamed(string name)
    property bool renaming: false
    objectName: "paintingRow:" + p.id
    height: 42 + 2 * Theme.grid; radius: Theme.radiusCtl
    color: area.containsMouse ? Theme.hover : "transparent"

    function startRename() { renaming = true }
    function openMenu(x, y) {
        const g = row.mapToItem(null, x, y)
        menu.entries = [
            ...(row.canUse > 0 ? [{ value: "use", label: "Use as the fill of " + (row.canUse === 1 ? "1 layer" : row.canUse + " layers"), group: 0 }] : []),
            { value: "open", label: "Open", group: 0 },
            { value: "rename", label: "Rename", group: 1 }, { value: "duplicate", label: "Duplicate", group: 1 },
            { value: "delete", label: "Delete", group: 2 }]
        menu.openAt(g.x, g.y)
    }

    Rectangle {
        id: pic
        width: 42; height: 42; radius: 4; color: "transparent"; clip: true; border.color: Theme.line
        anchors { left: parent.left; leftMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        Checker { anchors.fill: parent; anchors.margins: 1; radius: 3; cell: 4; light: "#7a7a7a"; dark: "#5a5a5a" }
        Image {      // seamless: the tile at half the square, so four repeats fill it; otherwise the painting alone
            anchors.fill: parent; anchors.margins: 1; source: row.p.picture
            fillMode: row.p.seamless ? Image.Tile : Image.PreserveAspectFit
            sourceSize.width: row.p.seamless ? 20 : 80; sourceSize.height: row.p.seamless ? 20 : 80
            smooth: true; cache: false; asynchronous: true
        }
    }
    Column {
        id: words
        visible: !row.renaming
        anchors { left: pic.right; leftMargin: Theme.gap; right: openButton.left
                  rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        Text { id: titleText; width: parent.width; text: row.p.name; elide: Text.ElideRight; color: Theme.fg
               font.family: uiFont; font.pixelSize: Theme.body }
        Text { id: subText; width: parent.width; text: row.p.line; elide: Text.ElideRight; color: Theme.fg3
               font.family: uiFont; font.pixelSize: Theme.label }
    }
    NameBox {     // rename in place (the kit's box): Enter keeps it, Esc or a click elsewhere leaves the name as it was
        id: nameEdit
        visible: row.renaming
        current: row.p.name
        anchors { left: words.left; right: words.right; verticalCenter: parent.verticalCenter }
        onDone: (t) => { row.renaming = false; row.renamed(t) }
        onCancelled: row.renaming = false
    }
    MouseArea {
        id: area
        anchors.fill: parent; enabled: !row.renaming; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: (m) => { if (m.button === Qt.RightButton) row.openMenu(m.x, m.y); else row.asked("use") }
    }
    IconButton {    // after the row's MouseArea, so its click is its own
        id: openButton
        objectName: "openPainting:" + row.p.id
        visible: !row.renaming
        anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        glyph: "↗"; kind: "ghost"; tip: "Open"
        help: "Open the painting on its own, to paint it and see how it repeats."
        onClicked: row.asked("open")
    }
    HoverTip { hovered: area.containsMouse && (titleText.truncated || subText.truncated)
               text: row.p.name + "\n" + row.p.line }
    ActionMenu {
        id: menu
        onPicked: (v) => v === "rename" ? row.startRename() : row.asked(v)
    }
}
