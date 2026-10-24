import QtQuick
import RostrumKit

// Typing a 3D text in place (SPEC §4.4; type_in_place.py): right after Type & logo › 3D text lands, a text cursor shows
// where it was placed and typing changes the words live in the viewport (the whole typing is one undo step). Enter or
// Esc ends it; a click elsewhere ends it too. The words themselves show in the picture, not here: only the cursor and
// a one-line hint.
Item {
    id: tip
    readonly property var typer: backend.adder.typer
    readonly property bool on: typer.item !== ""
    visible: on
    x: typer.at[0] / Screen.devicePixelRatio
    y: typer.at[1] / Screen.devicePixelRatio
    onOnChanged: if (on) input.forceActiveFocus()

    TextInput {    // the keys' home (an IME works too); it draws nothing itself
        id: input
        objectName: "typeInPlace"
        width: 1; height: 1; opacity: 0
        text: tip.typer.text
        onTextEdited: tip.typer.setText(text)
        Keys.onReturnPressed: tip.typer.end()
        Keys.onEnterPressed: tip.typer.end()
        Keys.onEscapePressed: tip.typer.end()
        Keys.onShortcutOverride: (e) => e.accepted = e.key === Qt.Key_Escape   // Esc ends the typing, not the selection
        onActiveFocusChanged: if (!activeFocus && tip.on) tip.typer.end()
    }
    Rectangle {    // the cursor
        x: -1; y: -Theme.row; width: 2; height: Theme.row
        color: Theme.accent          // steady, not blinking: a screen at rest stays still (the snap and layout check need it)
    }
    Rectangle {    // the hint under it
        y: Theme.grid
        x: -width / 2
        width: hint.implicitWidth + 2 * Theme.grid; height: hint.implicitHeight + Theme.grid
        radius: Theme.radiusCtl; color: Theme.raised; border.color: Theme.popupEdge
        Text { id: hint; anchors.centerIn: parent
               text: tip.typer.text === "" ? "Type the words  ·  Enter ends" : "Enter or Esc ends"
               color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
    }
}
