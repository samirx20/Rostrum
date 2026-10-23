import QtQuick
import QtQuick.Controls as QQC
import "."
import "ColourMath.js" as M

// The body of the colour picker, for ONE colour (every app's colour field and fill uses it): a square for saturation and
// brightness, a hue strip, an alpha strip, then pipette · hex · alpha % (· `extra`, e.g. a gradient stop's place in %),
// then the project's swatches and the brand's. It keeps the colour as HSV inside, so the hue stays put when the
// brightness reaches 0. `changed` comes live while dragging; the owner sets `hex` / `alpha` back (or not: it keeps its own).
// The pipette needs the optional `colourBank` (its pixel(x, y) reads the screen); without it the button is not shown.
Column {
    id: p
    property string hex: "#ffffff"
    property real alpha: 1
    property bool showAlpha: true
    property string extra: ""             // a number in %, shown as a third box when set
    property var project: []
    property var brand: []
    property string brandName: ""
    signal changed(string hex, real alpha)
    signal swatchAdd(string hex)
    signal extraEdited(string text)

    property real h: 0
    property real s: 0
    property real v: 1
    property real a: 1
    property bool picking: false
    readonly property bool canPick: typeof colourBank !== "undefined"
    readonly property string current: M.hsvHex(h, s, v)

    width: 234; spacing: Theme.gap
    function take(hx) {                    // the owner's colour in: the hue only follows when the colour has one
        if (hx === current) return
        const c = M.hexHsv(hx)
        s = c.s; v = c.v
        if (c.s > 0 && c.v > 0) h = c.h
    }
    function send() { changed(current, a) }
    function choose(hx) { take(hx); send() }
    Component.onCompleted: { take(M.parseHex(hex) || "#ffffff"); a = alpha }
    onHexChanged: take(M.parseHex(hex) || "#ffffff")
    onAlphaChanged: a = alpha

    Rectangle {   // saturation (across) and brightness (down)
        id: sv
        objectName: "colourSquare"
        width: parent.width; height: 140; radius: Theme.radiusCtl
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: "#ffffff" }
            GradientStop { position: 1; color: M.hsvHex(p.h, 1, 1) }
        }
        Rectangle { anchors.fill: parent; radius: parent.radius
                    gradient: Gradient { GradientStop { position: 0; color: "transparent" }
                                         GradientStop { position: 1; color: "#000000" } } }
        function at(m) { p.s = M.clamp01(m.x / width); p.v = 1 - M.clamp01(m.y / height); p.send() }
        MouseArea { anchors.fill: parent; cursorShape: Qt.CrossCursor
                    onPressed: (m) => sv.at(m); onPositionChanged: (m) => { if (pressed) sv.at(m) } }
        Rectangle {   // the ring on the colour
            x: p.s * sv.width - 7; y: (1 - p.v) * sv.height - 7; width: 14; height: 14; radius: 7
            color: "transparent"; border.width: 2; border.color: "#ffffff"
            Rectangle { anchors.fill: parent; anchors.margins: -1; radius: 8; color: "transparent"; border.width: 1; border.color: Qt.rgba(0, 0, 0, 0.5); z: -1 }
        }
    }

    Item {   // hue
        objectName: "hueStrip"
        width: parent.width; height: 14
        Rectangle {
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
            height: 10; radius: 5
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "#ff0000" }
                GradientStop { position: 1 / 6; color: "#ffff00" }
                GradientStop { position: 2 / 6; color: "#00ff00" }
                GradientStop { position: 3 / 6; color: "#00ffff" }
                GradientStop { position: 4 / 6; color: "#0000ff" }
                GradientStop { position: 5 / 6; color: "#ff00ff" }
                GradientStop { position: 1.0; color: "#ff0000" }
            }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    function at(m) { p.h = M.clamp01((m.x - 7) / (width - 14)); p.send() }
                    onPressed: (m) => at(m); onPositionChanged: (m) => { if (pressed) at(m) } }
        Rectangle { x: p.h * (parent.width - 14); width: 14; height: 14; radius: 7; color: M.hsvHex(p.h, 1, 1)
                    border.width: 2; border.color: "#ffffff" }
    }

    Item {   // alpha
        visible: p.showAlpha
        width: parent.width; height: 14
        Item {
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
            height: 10
            Checker { anchors.fill: parent; radius: 5; cell: 5 }
            Rectangle { id: tintBox; anchors.fill: parent; radius: 5
                        readonly property color tint: p.current
                        gradient: Gradient { orientation: Gradient.Horizontal
                                             GradientStop { position: 0; color: Qt.rgba(tintBox.tint.r, tintBox.tint.g, tintBox.tint.b, 0) }
                                             GradientStop { position: 1; color: tintBox.tint } } }
        }
        MouseArea { objectName: "alphaStrip"; anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    function at(m) { p.a = M.clamp01((m.x - 7) / (width - 14)); p.send() }
                    onPressed: (m) => at(m); onPositionChanged: (m) => { if (pressed) at(m) } }
        Rectangle { x: p.a * (parent.width - 14); width: 14; height: 14; radius: 7; color: Qt.rgba(1, 1, 1, 0.9 * (1 - p.a) + 0.1)
                    border.width: 2; border.color: "#ffffff"
                    Rectangle { anchors.centerIn: parent; width: 6; height: 6; radius: 3; color: p.current; opacity: p.a } }
    }

    Row {   // pipette · hex · alpha · extra
        spacing: Theme.grid + 2
        width: parent.width
        IconButton {
            objectName: "eyedropper"; visible: p.canPick; down: p.picking
            width: Theme.field; height: Theme.field; tip: "Pick from the screen"
            onClicked: p.picking = true
            PaintIcon { anchors.centerIn: parent; kind: "pipette"; ink: parent.ink }
        }
        FieldFrame {
            id: hexBox
            objectName: "hexField"
            editable: true
            width: parent.width - x0 - (p.showAlpha ? 56 + Theme.grid + 2 : 0) - (p.extra !== "" ? 56 + Theme.grid + 2 : 0)
            readonly property real x0: p.canPick ? Theme.field + Theme.grid + 2 : 0
            text: p.current.toUpperCase()
            onCommitted: (t) => {
                const hx = M.parseHex(t)
                if (hx) p.choose(hx); else input.text = text      // not a colour: back to what it was
            }
        }
        FieldFrame {
            visible: p.showAlpha; editable: true; width: 56
            text: String(Math.round(p.a * 100)); suffix: "%"
            function put(n) { p.a = M.clamp01(n / 100); p.send() }
            onCommitted: (t) => { const n = parseFloat(t); if (isNaN(n)) input.text = text; else put(n) }
            onArrow: (d, big) => put(Math.round(p.a * 100) + d * (big ? 10 : 1))
        }
        FieldFrame {
            visible: p.extra !== ""; editable: true; width: 56
            text: p.extra; suffix: "%"
            onCommitted: (t) => { if (isNaN(parseFloat(t))) input.text = text; else p.extraEdited(t) }
        }
    }

    Column {   // the project's swatches
        spacing: Theme.grid + 2; width: parent.width
        Text { text: "Project"; color: Theme.fg3; font.pixelSize: Theme.label; font.family: uiFont }
        Flow {
            width: parent.width; spacing: Theme.grid + 2
            Repeater { model: p.project; delegate: Swatch { required property string modelData; hex: modelData } }
            IconButton { objectName: "swatchAdd"; glyph: "+"; kind: "ghost"; width: 20; height: 20; tip: "Add this colour to the project"
                         onClicked: p.swatchAdd(p.current) }
        }
    }
    Column {   // the brand's
        visible: p.brand.length > 0
        spacing: Theme.grid + 2; width: parent.width
        Text { text: "Brand · " + p.brandName; color: Theme.fg3; font.pixelSize: Theme.label; font.family: uiFont }
        Flow {
            width: parent.width; spacing: Theme.grid + 2
            Repeater { model: p.brand; delegate: Swatch { required property string modelData; hex: modelData } }
        }
    }

    component Swatch: Rectangle {   // a saved colour: a click takes it
        property string hex: "#000000"
        width: 20; height: 20; radius: 4; color: hex
        border.width: hex === p.current ? 2 : 1; border.color: hex === p.current ? Theme.accent : Qt.rgba(1, 1, 1, 0.18)
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: p.choose(parent.hex) }
    }

    MouseArea {   // the pipette: the next click anywhere takes the colour under it; Esc cancels
        id: dropper
        parent: QQC.Overlay.overlay
        anchors.fill: parent
        visible: p.picking; enabled: p.picking; z: 100000
        cursorShape: Qt.CrossCursor
        focus: p.picking
        onVisibleChanged: if (visible) forceActiveFocus()
        Keys.onEscapePressed: p.picking = false
        onClicked: (m) => {
            const g = mapToGlobal(m.x, m.y)
            p.picking = false
            if (p.canPick) { const hx = M.parseHex(colourBank.pixel(g.x, g.y)); if (hx) p.choose(hx) }
        }
    }
}
