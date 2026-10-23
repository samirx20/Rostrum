import QtQuick
import RostrumKit

// The Sound row, the last row of the layers list while the project has sound (backend.soundtrack, soundtrack.py;
// UX_SPEC 3.28). Its name on the left; on the right the mix's waveform under the ruler, drawn from the peaks read once
// per render (waveform.py), never worked out here. A problem (no engine, no sound output, a broken song) is said on
// the row in words, never an empty row passed off as silence. Its name opens the row's menu (so does a right-click):
// Show beats (only while the song has a tempo; BeatLines.qml draws them), Open in RostrumSound. The speaker at the
// name side's right end mutes the sound in 2D only (not the project). The well lies as a layer's track does (x =
// ruler.x - 8, 8 px wider each side), so every row's box starts and ends at the same x.
Item {
    id: row
    objectName: "soundRow"
    property Item ruler
    property int labelWidth: 240
    readonly property var st: backend.soundtrack
    visible: st.present
    height: st.present ? Theme.row : 0

    Rectangle {   // the name, like a layer's: a click opens the row's menu
        x: Theme.gap; width: row.labelWidth - Theme.gap; height: parent.height
        radius: Theme.radiusCtl; color: nameArea.containsMouse || menu.visible ? Theme.hover : "transparent"
        MouseArea { id: nameArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: row.openMenu() }
        Text {
            id: songName
            x: Theme.pad; anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, parent.width - x - mute.width - Theme.pad - 2 * Theme.gap - 12)
            text: "♪  " + (row.st.name || "Sound"); elide: Text.ElideRight
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
        }
        Chevron { anchors.left: songName.right; anchors.leftMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                  open: menu.visible; color: nameArea.containsMouse ? Theme.fg : Theme.fg3 }
        IconButton {   // the sound in 2D only, not the project (backend.soundtrack.setMuted)
            id: mute
            objectName: "soundMute"
            anchors.right: parent.right; anchors.rightMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
            width: 22; height: 22; kind: "ghost"; down: row.st.muted
            icon: row.st.muted ? "sound-off" : "sound"
            tip: row.st.muted ? "Sound is muted here (only in 2D): click to hear it" : "Mute the sound here (only in 2D, not the project)"
            onClicked: row.st.setMuted(!row.st.muted)
        }
    }
    Rectangle {   // the track well, as long as the scene, as wide as a layer's track (8 px room each side)
        id: well
        x: row.ruler.x - 8; width: row.ruler.width + 16; height: parent.height
        color: Theme.sunken; radius: Theme.radiusCtl
        Canvas {
            id: wave
            x: 8; width: parent.width - 16; height: parent.height
            visible: row.st.problem === "" && row.st.peaks.length > 0
            opacity: row.st.muted ? 0.35 : 1
            property var peaks: row.st.peaks
            property real perSec: row.ruler.perSec
            onPeaksChanged: requestPaint()
            onPerSecChanged: requestPaint()
            onWidthChanged: requestPaint()
            onPaint: {
                const g = getContext("2d"), h = height, mid = h / 2, rate = row.st.rate
                g.reset()
                g.fillStyle = Theme.ok
                const last = Math.min(width, row.st.seconds * perSec)
                for (let px = 0; px < last; px++) {
                    const i0 = Math.floor(px / perSec * rate), i1 = Math.max(i0 + 1, Math.floor((px + 1) / perSec * rate))
                    let v = 0
                    for (let i = i0; i < i1 && i < peaks.length; i++) v = Math.max(v, peaks[i])
                    const a = Math.max(1, v * (h - 4))
                    g.fillRect(px, mid - a / 2, 1, a)
                }
            }
        }
        Repeater {   // a voice-over's lines, their words where they are spoken (voice_words.py), over the waveform
            model: wave.visible ? row.st.lines : []
            delegate: Rectangle {
                required property var modelData
                x: 8 + modelData.t * row.ruler.perSec; y: 2; height: well.height - 4
                width: Math.max(4, (modelData.end - modelData.t) * row.ruler.perSec - 2)
                radius: Theme.radiusCtl; color: Qt.rgba(0, 0, 0, 0.55); border.color: Theme.line; clip: true
                opacity: modelData.pending ? 0.6 : 1     // its take is not made yet (RostrumSound's Make voice): silent
                Text { x: 4; width: parent.width - 8; anchors.verticalCenter: parent.verticalCenter
                       text: modelData.pending ? modelData.text + " · not made yet" : modelData.text
                       elide: Text.ElideRight; color: Theme.fg
                       font.family: uiFont; font.pixelSize: Theme.label }
            }
        }
        Text {   // still rendering, or what went wrong
            visible: row.st.problem !== "" || row.st.peaks.length === 0
            x: Theme.pad; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 2 * Theme.pad
            text: row.st.problem !== "" ? row.st.problem : "Sound is rendering the mix…"
            elide: Text.ElideRight
            color: row.st.problem !== "" ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
        }
    }
    MouseArea {
        anchors.fill: parent; acceptedButtons: Qt.RightButton
        onClicked: (m) => { menu.x = Math.min(m.x, row.width - menu.width); menu.y = m.y; menu.open() }
    }
    function openMenu() { menu.x = Theme.gap; menu.y = 0; menu.open() }   // over the name (steps: `sound menu`)
    Menu {
        id: menu
        width: 200
        entries: (row.st.hasBeats ? [{ value: "beats", label: row.st.showBeats ? "Hide beats" : "Show beats" }] : [])
                 .concat([{ value: "open", label: "Open in RostrumSound" }])
        onPicked: (v) => { if (v === "beats") row.st.setShowBeats(!row.st.showBeats); else if (v === "open") row.st.openInSound() }
    }
}
