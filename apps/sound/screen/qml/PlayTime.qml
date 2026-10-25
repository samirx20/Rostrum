import QtQuick

// The time a playhead line is drawn at. The engine reports where it plays about 30 times a second (transport.py's
// tick); a line set from that moved in 33 ms steps, every other frame, so playback never looked like 60 fps. While
// playing, this carries the last report forward on every frame by the time since it came, and never steps back by
// the little the next report lags (a seek, a loop or Stop moves it at once). Stopped: the time as it is.
Item {
    id: p
    visible: false
    readonly property real reported: backend.time
    readonly property bool playing: backend.playing
    property real value: reported
    property real base: reported         // the last report, and the frame clock when it came
    property real baseAt: 0
    onReportedChanged: {
        var jump = reported < value - 0.06 || reported > value + 0.25     // a seek or a loop, not a report's lag
        base = reported; baseAt = Date.now()
        if (!playing || jump) value = reported
    }
    onPlayingChanged: { base = value = reported; baseAt = Date.now() }
    FrameAnimation {
        running: p.playing
        onTriggered: p.value = Math.max(p.value, p.base + Math.min(0.1, (Date.now() - p.baseAt) / 1000))
    }
}
