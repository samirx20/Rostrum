import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Look harness for the timeline kit (TimelineHeader, Ruler, HScroll) on a fake view and long texts; see
// timeline_preview.py. Nothing here is an app: the signals only print.
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1280; height: 720
    color: Theme.app
    property bool compact: false
    property bool playing: false
    function name() { ruler.newMarker() }
    readonly property var marks: [
        { id: "a", name: "Logo lands on the beat with a very long name", at: 2.0, shared: true },
        { id: "b", name: "Drop", at: 5.5, shared: true },
        { id: "c", name: "Our own note for this scene only", at: 8.25, shared: false, colour: "#4cc38a" },
        { id: "d", name: "End card", at: 13.9, shared: false }]
    readonly property var bars: {
        const out = []
        for (let b = 0; b * 2.4 < 20; b += 1) out.push({ at: b * 2.4, text: "Bar " + (b + 1) })
        return out
    }

    Rectangle {
        id: panel
        x: Theme.gap; y: parent.height - height - Theme.gap; width: parent.width - 2 * Theme.gap
        height: win.compact ? 120 : Math.min(320, parent.height - 2 * Theme.gap)
        radius: Theme.radiusPanel; color: Theme.panel
        TimelineHeader {
            id: header
            width: parent.width
            compact: win.compact
            onFoldClicked: win.compact = !win.compact
            transport: [
                PlayButton { playing: win.playing; implicitWidth: 24; implicitHeight: 24; onClicked: win.playing = !win.playing },
                Text { text: "0:07.25 · bar 4.1"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                       anchors.verticalCenter: parent.verticalCenter },
                Button { text: "⟳ Loop"; kind: "ghost"; implicitHeight: 24; help: "Play the time range again and again." }
            ]
            context: [
                Button { text: "Add a key to every selected setting"; kind: "ghost"; implicitHeight: 24 },
                Button { text: "Ease in and out"; kind: "ghost"; implicitHeight: 24 }
            ]
            view: [
                Button { text: "◇ Marker"; kind: "ghost"; implicitHeight: 24; onClicked: ruler.newMarker() },
                Button { text: "Snap"; kind: "ghost"; implicitHeight: 24 },
                IconButton { glyph: "−"; kind: "ghost"; implicitWidth: 24; implicitHeight: 24; tip: "Zoom out"
                             onClicked: timeView.zoomStep(1 / 1.25, ruler.value) },
                IconButton { glyph: "+"; kind: "ghost"; implicitWidth: 24; implicitHeight: 24; tip: "Zoom in"
                             onClicked: timeView.zoomStep(1.25, ruler.value) },
                Button { text: "Fit"; kind: "ghost"; implicitHeight: 24; onClicked: timeView.showAll() }
            ]
        }
        Ruler {
            id: ruler
            x: 140; y: header.height; width: parent.width - x - Theme.pad; height: implicitHeight
            duration: 20; value: 7.25; view: timeView
            markers: win.marks; editMarkers: true; canShare: true
            rangeBand: true; range: ({ start: 4.0, end: 9.6 })
            upper: win.bars
            onScrubbed: (t) => value = t
            onMarkerAdded: (n, s, at) => console.log("marker", n, s, at)
            onRangeSet: (a, b) => console.log("range", a, b)
        }
        Text { x: Theme.pad; anchors.bottom: ruler.bottom; anchors.bottomMargin: 4; text: "Layers"; color: Theme.fg2
               font.family: uiFont; font.pixelSize: Theme.label; font.capitalization: Font.AllUppercase }
        HScroll { x: ruler.x; width: ruler.width; y: parent.height - height - Theme.grid; view: timeView }
    }
}
