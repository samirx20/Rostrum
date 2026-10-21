import QtQuick
import RostrumKit

// The top bar's Add: the things that make sense now (backend.adder.entries), most important first. One choice is one
// change through the same operations agents use; the new thing is selected. Duplicate and Delete sit next to it only
// while something they work on is selected.
Row {
    id: row
    property alias menuOpen: menu.visible
    function open() { menu.open() }
    spacing: Theme.gap

    Button {
        text: "+ Add"
        down: menu.visible
        onClicked: menu.visible ? menu.close() : menu.open()
        Menu {
            id: menu
            width: 190
            entries: backend.adder.entries
            onPicked: (choice) => backend.adder.add(choice)
        }
    }
    Button {
        visible: backend.adder.canDuplicate
        text: "Duplicate"; hint: "Ctrl D"
        onClicked: backend.adder.duplicate()
    }
    Button {
        visible: backend.adder.canDelete
        text: "Delete"; hint: "Del"; danger: true
        onClicked: backend.adder.remove()
    }
}
