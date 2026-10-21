import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Dialogs
import QtMultimedia
import RostrumKit

// The project's picture in the corner of the Timeline page: the video's frame at the playhead, so sound is made
// to picture. The document's `picture` field (an agent can set it too) is a video file or a link to a 2D item of
// the project, which shows that item's newest render. Paused or scrubbing: the
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
        Text { anchors.verticalCenter: parent.verticalCenter; visible: backend.pictureChoice !== ""
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
                   wrapMode: Text.Wrap; color: Theme.fg4
                   text: backend.pictureProblem !== "" ? backend.pictureProblem : "Choose a video or a 2D item to make the sound to."
                   font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
    Row {
        anchors { left: parent.left; top: well.bottom; topMargin: Theme.gap }
        spacing: Theme.gap
        Button { text: backend.pictureChoice === "" ? "Choose video…" : "Change…"; kind: backend.pictureChoice === "" ? "primary" : "normal"
                 onClicked: chooser.open() }
        Button { id: fromProject; visible: backend.pictureItems.length > 0; text: "From the project…"
                 onClicked: items.open() }
        Button { visible: backend.pictureChoice !== ""; text: "Remove"; kind: "ghost"; onClicked: backend.setPicture("") }
    }
    QQC.Popup {     // the project's 2D items: picking one links its newest render
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
        id: chooser
        title: "Choose the video"
        nameFilters: ["Video (*.mp4 *.mov *.mkv *.webm *.avi *.m4v)", "All files (*)"]
        onAccepted: { backend.setPicture(selectedFile.toString()); backend.setPictureOpen(true) }
    }
}
