import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A strip's live level, upright on the fader's own scale, in the kit meter's style (LevelMeter): the RMS fills from the
// bottom with the peak as a thin bar beside it, coloured by where they reach (F.levelTone's rule: green below −6 dB,
// amber −6 .. 0, red over 0, the same on every strip and the master); a mark holds the highest peak for a second, then
// falls. `live` is [peak dB, RMS dB] from the engine while the mix plays (mixer.live: the render's own levels at the
// speaker's time); without it (stopped) everything falls to silence at `fall` dB a second.
Item {
    id: m
    property var live: null            // [peak dB, RMS dB] while playing, else null
    property string tip: ""            // the words under it while the pointer rests on it
    readonly property real fall: 20    // dB a second
    readonly property real holdMs: 1000
    property real peakDb: F.FLOOR
    property real rmsDb: F.FLOOR
    property real holdDb: F.FLOOR
    property double holdAt: 0
    property double last: 0
    width: 8

    onLiveChanged: {
        if (live) {
            peakDb = Math.max(peakDb, live[0]); rmsDb = Math.max(rmsDb, live[1])
            if (live[0] >= holdDb) { holdDb = live[0]; holdAt = Date.now() }
            if (!ticker.running) { last = Date.now(); ticker.running = true }
        } else {                                  // stopped: the bars are empty (the strip's number holds the peak)
            peakDb = rmsDb = holdDb = F.FLOOR
            ticker.running = false
        }
    }
    Timer {   // the fall between the engine's lines and after the stop
        id: ticker
        interval: 16; repeat: true
        onTriggered: {
            var now = Date.now(), drop = m.fall * (now - m.last) / 1000
            m.last = now
            m.peakDb = Math.max(m.live ? m.live[0] : F.FLOOR, m.peakDb - drop)
            m.rmsDb = Math.max(m.live ? m.live[1] : F.FLOOR, m.rmsDb - drop)
            if (now - m.holdAt > m.holdMs) m.holdDb = Math.max(m.peakDb, m.holdDb - drop)
            if (!m.live && m.holdDb <= F.FLOOR) running = false
        }
    }
    function h(db) { return height * F.posOfDb(db) }
    // A bar coloured by position, the kit meter's way: the part above −6 dB amber, above 0 dB red.
    component Zoned: Item {
        property real db: F.FLOOR
        anchors.bottom: parent.bottom; height: m.h(db); clip: true
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: m.h(-6); color: Theme.ok }
        Rectangle { anchors.bottom: parent.bottom; anchors.bottomMargin: m.h(-6); width: parent.width; height: m.h(0) - m.h(-6); color: Theme.warn }
        Rectangle { anchors.bottom: parent.bottom; anchors.bottomMargin: m.h(0); width: parent.width; height: m.height - m.h(0); color: Theme.danger }
    }
    Rectangle { anchors.fill: parent; radius: 2; color: Theme.sunken }
    Zoned { x: 0; width: parent.width - 3; db: m.rmsDb }           // RMS: the body of the sound
    Zoned { x: parent.width - 2; width: 2; db: m.peakDb }          // peak: beside it
    Rectangle {                                                     // the held peak
        visible: m.holdDb > F.FLOOR
        width: parent.width; height: 2; y: m.height - m.h(m.holdDb) - 1
        color: Theme[F.levelTone(m.holdDb)]
    }
    HoverHandler { id: hover }
    HoverTip { text: m.tip; hovered: hover.hovered }
}
