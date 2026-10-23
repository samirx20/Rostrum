import QtQuick
import "."
import "ColourMath.js" as M

// The one colour row piece (ColorField, PaintField): a swatch square, field-high, and right of it a box with the
// hex code. A click on the square (or Enter / Space on it) asks for the picker: `pick()`. The hex is typed in place
// (# optional, 3 / 6 / 8 digits) and goes out on Enter or on leaving the box as `typed("#rrggbb")`, one change; a
// value that is not a colour is refused in place: the box turns red and says why, the old colour stays. With `words`
// set (a gradient: "Linear · 3 stops", "None", "Mixed") the box shows them instead and a click on it opens the picker.
//   look: {type: "solid" | "none" | "mixed" | "linear" | "radial" | "angular" | "image", color, stops}; "mixed": several colours, an empty swatch
Item {
    id: s
    property var look: ({ type: "solid", color: "#ffffff" })
    property string words: ""
    property bool engaged: false
    signal pick()
    signal typed(string hex)
    readonly property string lookKind: look && look.type ? look.type : "none"
    readonly property string lookHex: look && look.color ? String(look.color) : "#ffffff"
    implicitWidth: 140
    implicitHeight: Theme.field

    Item {
        id: square
        objectName: "swatch"
        width: Theme.field; height: Theme.field
        activeFocusOnTab: true
        Checker { anchors.fill: parent; radius: Theme.radiusCtl; cell: 4; visible: s.lookKind !== "solid" && s.lookKind !== "image" }
        Canvas {
            anchors.fill: parent
            property var shown: s.look
            onShownChanged: requestPaint()
            onPaint: {
                const g = getContext("2d"), t = s.lookKind, w = width
                g.reset()
                g.roundedRect(0, 0, w, w, Theme.radiusCtl, Theme.radiusCtl); g.clip()
                if (t === "solid" || t === "image") { g.fillStyle = M.rgba(s.lookHex, 1); g.fillRect(0, 0, w, w) }
                else if (t === "mixed") { /* the checker alone: no one colour to show */ }
                else if (t === "none") { g.strokeStyle = "#c0392b"; g.lineWidth = 1.5; g.beginPath(); g.moveTo(2, w - 2); g.lineTo(w - 2, 2); g.stroke() }
                else {
                    const grad = t === "radial" ? g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w * 0.7)
                               : t === "angular" ? g.createConicalGradient(w / 2, w / 2, 0)
                               : g.createLinearGradient(0, 0, w, 0)
                    M.addStops(grad, M.sorted(s.look.stops || []))
                    g.fillStyle = grad; g.fillRect(0, 0, w, w)
                }
            }
        }
        Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: "transparent"
                    border.width: s.engaged || square.activeFocus ? 2 : 1
                    border.color: s.engaged || square.activeFocus ? Theme.accent : hover.hovered ? Qt.rgba(1, 1, 1, 0.4) : Qt.rgba(1, 1, 1, 0.18) }
        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: s.pick() }
        Keys.onReturnPressed: s.pick()
        Keys.onSpacePressed: s.pick()
    }
    FieldFrame {
        id: box
        objectName: "hexField"
        x: Theme.field + Theme.grid + 2; width: s.width - x; height: s.height
        editable: s.words === ""
        engaged: s.engaged && s.words !== ""
        text: s.lookHex.replace(/^#/, "").toUpperCase()
        prefix: s.words === "" ? "#" : ""
        atRest: s.words
        onCommitted: (t) => {
            const c = M.readHex(t)
            const why = !c ? "“" + t + "” is not a colour: type 3 or 6 hex digits, like 4AA3FF"
                      : c.a < 1 ? "This colour can’t be see-through here: type 6 digits (Opacity is its own setting)" : ""
            input.text = text                                  // the box shows the colour it has until the change lands
            if (why) problem = why; else if (c.hex !== s.lookHex.toLowerCase()) s.typed(c.hex)
        }
        TapHandler { enabled: s.words !== ""; onTapped: s.pick() }
    }
}
