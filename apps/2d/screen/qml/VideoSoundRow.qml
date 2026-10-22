import QtQuick
import RostrumKit

// A video layer's own sound, the thin row under its layer row (backend.soundtrack.videos, screen2d/video_sound.py;
// UX_SPEC 3.28 Sync sound). The waveform lies along the layer's bar, read from the bar's own times (rowData), so it
// moves and trims with the bar, live while dragging; it shows only what Sound plays (Clip starts at, Speed, Loop's
// rounds, cut to its groups' times: info.pieces).
// RostrumSound mixes it. 🔊 mutes it in Sound's song (one change, Ctrl+Z takes it back). No project sound: it says so.
Item {
    id: sub
    property var rowData            // the video layer's row (start, end)
    property var info               // its entry in backend.soundtrack.videos.rows
    property Item ruler
    property int labelWidth: 240
    objectName: "videoSound_" + (rowData ? rowData.id : "")

    Rectangle {   // the name side: indented under its layer, with the mute button
        x: Theme.gap + 22; width: sub.labelWidth - Theme.gap - 22; height: parent.height
        color: "transparent"
        Text {
            x: Theme.pad; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 2 * Theme.pad - mute.width
            text: "♪  Its sound"; elide: Text.ElideRight
            color: sub.info.muted ? Theme.fg3 : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        }
        IconButton {
            id: mute
            objectName: "videoSoundMute_" + (sub.rowData ? sub.rowData.id : "")
            anchors.right: parent.right; anchors.rightMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
            visible: sub.info.problem === ""
            width: 20; height: 20; kind: "ghost"; down: sub.info.muted
            glyph: sub.info.muted ? "🔇" : "🔊"
            tip: sub.info.muted ? "Unmute this video's sound" : "Mute this video's sound (in Sound's mix)"
            onClicked: backend.soundtrack.videos.setMuted(sub.rowData.id, !sub.info.muted)
        }
    }
    Item {   // the time side, under the ruler, as the layer track lies (x = ruler.x - 8 in LayerTrack)
        x: sub.ruler.x; width: sub.ruler.width; height: parent.height
        readonly property real x0: Math.max(0, sub.ruler.xOf(sub.rowData.start || 0))
        readonly property real x1: Math.min(width, sub.ruler.xOf(sub.rowData.end || 0))
        Rectangle {
            x: parent.x0; width: Math.max(2, parent.x1 - parent.x0); y: 1; height: parent.height - 2
            radius: 3; color: Theme.sunken; border.width: 1; border.color: Theme.border
            opacity: sub.info.muted ? 0.4 : 1
            Canvas {
                id: wave
                anchors.fill: parent; anchors.margins: 1
                visible: sub.info.problem === "" && sub.info.peaks.length > 0
                property var peaks: sub.info.peaks
                property real perSec: sub.ruler.perSec
                property real start: sub.rowData.start || 0
                property var pieces: sub.info.pieces
                onPeaksChanged: requestPaint()
                onPerSecChanged: requestPaint()
                onWidthChanged: requestPaint()
                onStartChanged: requestPaint()
                onPiecesChanged: requestPaint()
                onPaint: {   // only what Sound plays: in each piece, file time = in + (time after the bar's start − from) · speed
                    const g = getContext("2d"), h = height, mid = h / 2, rate = sub.info.rate, sp = sub.info.speed
                    const t0 = Math.max(0, start) - start      // a bar starting before 0 s shows from 0 s
                    g.reset()
                    g.fillStyle = Theme.ok
                    for (let px = 0; px < width; px++) {
                        const r = t0 + px / perSec
                        const p = pieces.find(q => q.from <= r && r < q.from + q.length / sp)
                        if (!p) continue
                        const f0 = p.in + (r - p.from) * sp, f1 = f0 + sp / perSec
                        const i0 = Math.floor(f0 * rate), i1 = Math.max(i0 + 1, Math.floor(f1 * rate))
                        if (i0 >= peaks.length) continue
                        let v = 0
                        for (let i = Math.max(0, i0); i < i1 && i < peaks.length; i++) v = Math.max(v, peaks[i])
                        const a = Math.max(1, v * (h - 2))
                        g.fillRect(px, mid - a / 2, 1, a)
                    }
                }
            }
            Text {
                visible: !wave.visible
                x: Theme.pad; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 2 * Theme.pad
                text: sub.info.problem !== "" ? sub.info.problem : "Reading the video's sound…"
                elide: Text.ElideRight; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
            }
        }
    }
}
