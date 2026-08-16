import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Headless singleton: polls status and keeps a heartbeat. All real
// work happens in bin/omameet-meetings — never in QML, because
// this runs inside the long-lived omarchy-shell process.
Item {
  id: root

  property int pollIntervalSec: 15
  // Named meetingState: Item already defines a built-in `state`.
  property string meetingState: "idle"          // idle | armed | recording | processing | error
  property string detail: ""
  property bool paused: false

  // Absolute path — `omarchy plugin add <git-url>` runs no install hooks, so the
  // helper may not be on PATH.
  readonly property string helper:
      Qt.resolvedUrl("bin/omameet-meetings").toString().replace("file://", "")

  Process {
    id: statusProc
    command: [root.helper, "status", "--json"]
    stdout: StdioCollector {
      onStreamFinished: {
        try {
          var data = JSON.parse(this.text)
          root.paused = data.paused === true
          if (data.orphaned) { root.meetingState = "error"; root.detail = "orphaned recording" }
          else if (data.recording) { root.meetingState = "recording"; root.detail = data.session ? data.session.title : "" }
          else if (root.paused) { root.meetingState = "idle"; root.detail = "paused" }
          else { root.meetingState = "idle"; root.detail = "" }
        } catch (e) {
          root.meetingState = "error"
          root.detail = "helper unavailable"
        }
      }
    }
  }

  Process { id: heartbeatProc; command: [root.helper, "heartbeat"] }

  Timer {
    interval: Math.max(15, root.pollIntervalSec) * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: {
      if (!statusProc.running) statusProc.running = true
      if (!heartbeatProc.running) heartbeatProc.running = true
    }
  }
}
