import QtQuick
import RostrumKit

// The Sound row, the last row of the layers list while the project has sound (backend.soundtrack, soundtrack.py;
// UX_SPEC 3.28). Its name on the left; on the right the mix's waveform under the ruler, drawn from the peaks read once
// per render (waveform.py), never worked out here. A problem (no engine, no sound output, a broken song) is said on
// the row in words, never an empty row passed off as silence. Right-click: Open in RostrumSound.
Item {
    id: row
    objectName: "soundRow"
    property Item ruler
    property int labelWidth: 240
    readonly property var st: backend.soundtrack
    visible: st.present
    height: st.present ? Theme.row : 0

    Rectangle {   // the name, like a layer's
        x: Theme.gap; width: row.labelWidth - Theme.gap; height: parent.height
        radius: Theme.radiusCtl; color: "transparent"
        Text {
            x: Theme.pad; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 2 * Theme.pad
            text: "♪  " + (row.st.name || "Sound"); elide: Text.ElideRight
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
        }
    }
    Rectangle {   // the track well, as long as the scene
        id: well
        x: row.ruler.x; width: row.ruler.width; height: parent.height
        color: Theme.sunken; radius: Theme.radiusCtl
        Canvas {
            id: wave
            anchors.fill: parent
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
                x: modelData.t * row.ruler.perSec; y: 2; height: well.height - 4
                width: Math.max(4, (modelData.end - modelData.t) * row.ruler.perSec - 2)
                radius: Theme.radiusCtl; color: Qt.rgba(0, 0, 0, 0.55); border.color: Theme.line; clip: true
                Text { x: 4; width: parent.width - 8; anchors.verticalCenter: parent.verticalCenter
                       text: modelData.text; elide: Text.ElideRight; color: Theme.fg
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
        onClicked: (m) => { menu.x = m.x; menu.y = m.y - menu.height; menu.open() }
    }
    function openMenu() { menu.x = row.labelWidth / 2; menu.y = -menu.height; menu.open() }   // (steps: the right-click)
    Menu {
        id: menu
        width: 200
        entries: [{ value: "open", label: "Open in RostrumSound" }]
        onPicked: (v) => { if (v === "open") row.st.openInSound() }
    }
}
