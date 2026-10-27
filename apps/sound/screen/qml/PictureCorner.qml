import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs
import QtQuick.Templates as T
import QtMultimedia
import RostrumKit

// The project's picture in the corner of the Timeline page: the video's frame at the playhead, so sound is made
// to picture. The document's `picture` field (an agent can set it too) is a video file or a link to a 2D item of
// the project, which shows that item's newest render. Paused or scrubbing: the
// frame at the playhead; playing: the video plays along, and is set back to the playhead when it drifts by more
// than a frame. The video's own sound is not played (the engine's render is the one audio).
Panel {
    id: pc
    readonly property real playheadMs: Math.max(0, backend.time - backend.pictureStart) * 1000   // the video's own time
    readonly property bool before: backend.time < backend.pictureStart                           // not started yet: its first frame
    readonly property real frameMs: {
        var f = mp.metaData.value(MediaMetaData.VideoFrameRate)
        return f > 0 ? 1000 / f : 40
    }
    property real lastSeek: 0
    readonly property real fps: mp.metaData.value(MediaMetaData.VideoFrameRate) || 0
    onFpsChanged: backend.setPictureFps(fps)        // the ruler's seconds line snaps to the picture's frames
    readonly property real videoSec: mp.source != "" && mp.duration > 0 ? mp.duration / 1000 : 0
    onVideoSecChanged: backend.setPictureLength(videoSec)   // the song has room for the whole picture (mark its cuts first)
    title: "Picture"
    readonly property bool hasVideo: backend.picture !== ""      // no video yet: just "Choose video…", no empty box over the tracks
    height: Theme.header + well.height + below.height + Theme.gap + bodyPad
    headerRight: [
        NameLabel { anchors.verticalCenter: parent.verticalCenter; visible: backend.pictureChoice !== ""
                    text: backend.pictureName; elide: Text.ElideMiddle
                    width: Math.min(implicitWidth, pc.width - 140); color: Theme.fg3; font.pixelSize: Theme.label }
    ]

    function openItems() { items.open() }
    function seek() { mp.position = Math.min(playheadMs, Math.max(0, mp.duration)) }
    function follow() {
        if (mp.source == "") return
        if (!backend.playing || before) { if (before && mp.playbackState === MediaPlayer.PlayingState) mp.pause(); seek(); return }
        if (mp.playbackState !== MediaPlayer.PlayingState && playheadMs < mp.duration) mp.play()
        else if (Math.abs(mp.position - playheadMs) > frameMs && Date.now() - lastSeek > 250) { seek(); lastSeek = Date.now() }
    }
    function transport() {
        if (mp.source == "") return
        seek()
        if (backend.playing && !before) mp.play(); else mp.pause()
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
        function onTimelineChanged() { pc.follow() }       // the start marker moved
        function onPlayingChanged() { pc.transport() }
    }
    Rectangle {
        id: well
        visible: pc.hasVideo
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: visible ? Math.round(width * 9 / 16) : 0; radius: Theme.radiusCtl; color: Theme.sunken; clip: true
        VideoOutput { id: out; anchors.fill: parent; fillMode: VideoOutput.PreserveAspectFit }
        Text { visible: mp.error !== MediaPlayer.NoError; anchors.centerIn: parent; width: parent.width - 2 * Theme.pad
               horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; text: "Can't show this file: " + mp.errorString
               color: Theme.danger; font.family: uiFont; font.pixelSize: Theme.body }
    }
    Column {
        id: below
        anchors { left: parent.left; right: parent.right; top: well.bottom; topMargin: Theme.gap }
        spacing: Theme.gap
        Row {
            spacing: Theme.gap
            Button { text: backend.pictureChoice === "" ? "Choose video…" : "Change…"; kind: backend.pictureChoice === "" ? "primary" : "normal"
                     onClicked: chooser.open() }
            Button { id: fromProject; visible: backend.pictureItems.length > 0; text: "From the project…"
                     onClicked: items.open() }
            Button { visible: backend.pictureChoice !== ""; text: "Remove"; kind: "ghost"; onClicked: backend.setPicture("") }
        }
        Row {   // where the picture starts: the song's start, or a shared marker ("logo lands"): follows the marker
            id: startRow
            visible: backend.pictureChoice !== ""
            spacing: Theme.gap; height: Theme.field
            Text { text: "Starts at"; anchors.verticalCenter: parent.verticalCenter; color: Theme.fg2
                   font.family: uiFont; font.pixelSize: Theme.body }
            ChoiceField {
                width: 170
                options: [{ value: "", label: "Start of the song" }].concat(backend.markers.map(m => ({ value: m.name, label: m.name })))
                current: backend.pictureMarker
                onPicked: (v) => backend.setPictureStart(v)
            }
        }
        Text { visible: !pc.hasVideo && backend.pictureProblem !== ""; width: parent.width; wrapMode: Text.Wrap
               color: Theme.fg4; text: backend.pictureProblem; font.family: uiFont; font.pixelSize: Theme.label }
    }
    SmallPopup {     // the project's 2D items: picking one links its newest render
        id: items
        parent: fromProject
        y: -height - 2
        width: 220; padding: Theme.grid
        background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
        contentItem: Column {
            Repeater {
                model: backend.pictureItems
                delegate: Rectangle {
                    required property var modelData
                    width: 212; height: Theme.popupRow; radius: 4
                    color: row.containsMouse ? Theme.hover : "transparent"
                    Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap - 2; anchors.verticalCenter: parent.verticalCenter
                           width: parent.width - Theme.gap; elide: Text.ElideRight
                           text: modelData.label; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont }
                    MouseArea { id: row; anchors.fill: parent; hoverEnabled: true
                                onClicked: { items.close(); backend.linkPicture(modelData.id) } }
                }
            }
        }
    }
    FileDialog {
        popupType: T.Popup.Item     // inside the window, never a window of its own (a check window's dialog drew nowhere it could be seen or clicked)
        id: chooser
        title: "Choose the video"
        nameFilters: ["Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)", "All files (*)"]
        onAccepted: { backend.setPicture(selectedFile.toString()); backend.setPictureOpen(true) }
    }
}
