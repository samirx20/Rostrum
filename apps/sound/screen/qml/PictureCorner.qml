import QtQuick
import QtQuick.Dialogs
import QtMultimedia
import RostrumKit

// The project's picture in the corner of the Timeline page: the video's frame at the playhead, so sound is made
// to picture. The file is the document's `picture` field (an agent can set it too). Paused or scrubbing: the
// frame at the playhead; playing: the video plays along, and is set back to the playhead when it drifts by more
// than a frame. The video's own sound is not played (the engine's render is the one audio).
Panel {
    id: pc
    readonly property real playheadMs: backend.time * 1000
    readonly property real frameMs: {
        var f = mp.metaData.value(MediaMetaData.VideoFrameRate)
        return f > 0 ? 1000 / f : 40
    }
    property real lastSeek: 0
    title: "Picture"
    height: Theme.header + Math.round((width - 2 * bodyPad) * 9 / 16) + Theme.gap + Theme.button + bodyPad
    headerRight: [
        Text { anchors.verticalCenter: parent.verticalCenter; visible: backend.picture !== ""
               text: backend.pictureName; elide: Text.ElideMiddle
               width: Math.min(implicitWidth, pc.width - 140); color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
    ]

    function seek() { mp.position = Math.min(playheadMs, Math.max(0, mp.duration)) }
    function follow() {
        if (mp.source == "") return
        if (!backend.playing) { seek(); return }
        if (mp.playbackState !== MediaPlayer.PlayingState && playheadMs < mp.duration) mp.play()
        else if (Math.abs(mp.position - playheadMs) > frameMs && Date.now() - lastSeek > 250) { seek(); lastSeek = Date.now() }
    }
    function transport() {
        if (mp.source == "") return
        seek()
        if (backend.playing) mp.play(); else mp.pause()
    }

    MediaPlayer {
        id: mp
        source: backend.pictureUrl
        videoOutput: out
        onMediaStatusChanged: if (mediaStatus === MediaPlayer.LoadedMedia) pc.transport()
    }
    Connections {
        target: backend
        function onTimeChanged() { pc.follow() }
        function onPlayingChanged() { pc.transport() }
    }
    Rectangle {
        id: well
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Math.round(width * 9 / 16); radius: Theme.radiusCtl; color: Theme.sunken; clip: true
        VideoOutput { id: out; anchors.fill: parent; fillMode: VideoOutput.PreserveAspectFit }
        Column {
            visible: backend.picture === "" || mp.error !== MediaPlayer.NoError
            anchors.centerIn: parent; spacing: Theme.grid; width: parent.width - 2 * Theme.pad
            Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
                   text: mp.error !== MediaPlayer.NoError ? "Can't show this file: " + mp.errorString : "No picture yet"
                   color: mp.error !== MediaPlayer.NoError ? Theme.danger : Theme.fg2
                   font.family: uiFont; font.pixelSize: Theme.body }
            Text { visible: backend.picture === ""; width: parent.width; horizontalAlignment: Text.AlignHCenter
                   wrapMode: Text.Wrap; text: "Choose a video to make the sound to."; color: Theme.fg4
                   font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
    Row {
        anchors { left: parent.left; top: well.bottom; topMargin: Theme.gap }
        spacing: Theme.gap
        Button { text: backend.picture === "" ? "Choose video…" : "Change…"; kind: backend.picture === "" ? "primary" : "normal"
                 onClicked: chooser.open() }
        Button { visible: backend.picture !== ""; text: "Remove"; kind: "ghost"; onClicked: backend.setPicture("") }
    }
    FileDialog {
        id: chooser
        title: "Choose the video"
        nameFilters: ["Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)", "All files (*)"]
        onAccepted: { backend.setPicture(selectedFile.toString()); backend.setPictureOpen(true) }
    }
}
