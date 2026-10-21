import QtQuick

// The one ruler for time: seconds (unit "seconds", 0..duration) or frames (unit "frames", first..last, last is the
// final frame so the width ends one past it). Ticks, labels, the playhead's head, optional shared marker flags.
// Press or drag emits scrubbed(value), in the ruler's unit; the screen decides what to do with it. With editMarkers
// a flag drags (markerMoved on release), renames on double-click and shows × to delete on hover; the screen runs
// the marker operations (rostrum_gui.markers.MarkerWatch).
// xOf(v) / tOf(x) (alias fOf) are the one mapping the key rows use too.
Item {
    id: r
    property string unit: "seconds"
    property real duration: 1          // seconds
    property real fps: 30
    property int first: 0              // frames
    property int last: 47
    property real value: 0             // the playhead: seconds or a frame
    property var markers: []           // [{id, name, at, colour}], at in seconds (either unit): a flag with its name
    property bool editMarkers: false   // drag a flag = markerMoved, double-click = rename, × = delete
    signal scrubbed(real t)
    signal markerMoved(string id, real at)        // seconds, on whole frames
    signal markerRenamed(string id, string name)
    signal markerRemoved(string id)

    readonly property bool frames: unit === "frames"
    readonly property real origin: frames ? first : 0
    readonly property real span: frames ? Math.max(1, last + 1 - first) : Math.max(duration, 0.001)
    readonly property real perUnit: width / span
    readonly property real perSec: perUnit
    // label every `major` (at least ~90 px / ~70 px apart), small ticks every `minor`
    readonly property real major: frames ? ([1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000].find(n => n * perUnit >= 70) || 10000)
                                         : ([0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 300].find(s => s * perUnit >= 90) || 600)
    readonly property real minor: frames ? (major >= 10 ? major / (major % 4 === 0 ? 4 : 5) : 1)
                                         : major / (major === 1 || major === 2 ? 4 : 5)
    function xOf(v) { return (v - origin) * perUnit }
    function tOf(x) { return frames ? origin + x / perUnit : Math.max(0, Math.min(duration, x / perUnit)) }
    function fOf(x) { return tOf(x) }
    function xOfSec(s) { return xOf(frames ? s * fps : s) }           // a time in seconds (markers), either unit
    function secOf(x) { const v = tOf(x); return Math.max(0, Math.round((frames ? v : v * fps)) / fps) }
    function label(v) {
        if (frames) return v
        return v >= 60 ? Math.floor(v / 60) + ":" + ("0" + Math.round(v % 60)).slice(-2) : (Math.round(v * 100) / 100) + "s"
    }
    implicitHeight: 22

    Repeater {
        model: Math.floor(r.span / r.minor + 1e-6) + 1
        delegate: Rectangle {
            required property int index
            readonly property real v: r.origin + index * r.minor
            readonly property bool big: Math.abs((index * r.minor / r.major) - Math.round(index * r.minor / r.major)) < 1e-6
            x: Math.round(r.xOf(v)); y: r.height - height
            width: 1; height: big ? 7 : 3; color: big ? Theme.lineHover : Theme.line
            Text { visible: parent.big && r.xOf(parent.v) < r.width - 24; x: 4; y: -r.height + 5 + parent.height
                   text: r.label(parent.v); color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                   font.features: { "tnum": 1 } }
        }
    }
    MouseArea {  // scrubbing: under the flags, so a flag takes its own presses
        anchors.fill: parent
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        onPressed: (m) => r.scrubbed(r.tOf(m.x))
        onPositionChanged: (m) => r.scrubbed(r.tOf(m.x))
    }
    Repeater {   // the project's shared markers: a flag with its name; editable: drag, double-click, ×
        model: r.markers
        delegate: Item {
            id: mk
            required property var modelData
            property real dx: 0                      // while dragging (one move on release)
            property bool naming: false
            readonly property color tint: modelData.colour ? modelData.colour : Theme.warn
            x: Math.round(r.xOfSec(modelData.at) + dx); width: 1; height: r.height
            z: hit.containsMouse || crossHit.containsMouse || naming ? 2 : 1
            Rectangle { width: 1; height: parent.height; color: mk.tint }
            Rectangle {
                id: flag
                x: 1; y: 0; height: 16; radius: 2; color: hit.containsMouse || crossHit.containsMouse ? Theme.raised : Theme.panel
                border.color: mk.tint
                width: mk.naming ? Math.max(editor.contentWidth + 12, 60)
                                 : Math.min(name.implicitWidth + 8 + (cross.visible ? 14 : 0),
                                            Math.max(r.width - mk.x - 1, 14))
                clip: true
                Text { id: name; x: 4; anchors.verticalCenter: parent.verticalCenter; text: modelData.name
                       visible: !mk.naming; color: mk.tint; font.family: uiFont; font.pixelSize: Theme.label - 1 }
                MouseArea {
                    id: hit
                    anchors.fill: parent
                    enabled: r.editMarkers && !mk.naming
                    hoverEnabled: true
                    preventStealing: true
                    cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    property real x0: 0
                    onPressed: (m) => { x0 = m.x; mk.dx = 0 }
                    onPositionChanged: (m) => { if (pressed) mk.dx = m.x - x0 }
                    onReleased: {
                        if (Math.abs(mk.dx) >= 2)
                            r.markerMoved(modelData.id, r.secOf(r.xOfSec(modelData.at) + mk.dx))
                        mk.dx = 0
                    }
                    onDoubleClicked: { mk.naming = true; editor.text = modelData.name; editor.selectAll(); editor.forceActiveFocus() }
                }
                Text {      // delete, on hover
                    id: cross
                    visible: r.editMarkers && (hit.containsMouse || crossHit.containsMouse) && !mk.naming
                    anchors.right: parent.right; anchors.rightMargin: 4; anchors.verticalCenter: parent.verticalCenter
                    text: "×"; color: crossHit.containsMouse ? Theme.danger : Theme.fg3
                    font.family: uiFont; font.pixelSize: Theme.label + 1
                    MouseArea { id: crossHit; anchors.fill: parent; anchors.margins: -3; hoverEnabled: true
                                onClicked: r.markerRemoved(modelData.id) }
                }
                TextInput {
                    id: editor
                    visible: mk.naming
                    x: 4; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 8
                    color: Theme.fg; selectionColor: Theme.accentSoft; selectByMouse: true
                    font.family: uiFont; font.pixelSize: Theme.label - 1
                    onAccepted: { mk.naming = false; if (text.trim() && text !== modelData.name) r.markerRenamed(modelData.id, text.trim()) }
                    onActiveFocusChanged: if (!activeFocus) mk.naming = false
                    Keys.onEscapePressed: mk.naming = false
                }
            }
        }
    }
    Rectangle {  // the playhead: a line through the ruler, its head at the top
        x: Math.round(r.xOf(r.value)); width: 1; height: r.height; color: Theme.accent
        Rectangle { x: -4; y: 0; width: 9; height: 8; radius: 2; color: Theme.accent }
    }
}
