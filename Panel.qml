import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "acp.omameet"
  ipcTarget: "acp.omameet"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null
  readonly property var barIdentity: hostWidget || root
  property var settings: ({})
  property var agenda: ({ date: "", events: [], accounts: [], errors: [] })
  property var calendars: []
  property bool showingCalendars: false
  property string errorText: ""
  property bool loading: false
  property bool refreshQueued: false
  property bool queuedForceRefresh: false
  property double nowMs: Date.now()
  property string selectedDate: todayKey()
  property bool recording: false
  property string recordingTitle: ""
  property string sourceName: ""
  property string sourceUrl: ""

  readonly property string calendarHelper:
      Qt.resolvedUrl("bin/omameet-calendar").toString().replace("file://", "")
  readonly property string meetingsHelper:
      Qt.resolvedUrl("bin/omameet-meetings").toString().replace("file://", "")

  readonly property color foreground: Color.popups.text
  readonly property color muted: Color.muted
  readonly property color accent: Color.accent
  readonly property color urgent: Color.urgent
  readonly property int refreshIntervalSec: Math.max(60, Number(settings.refreshIntervalSec || 300))
  readonly property string tooltip: recording ? ("Recording — " + recordingTitle) : nextEventText()
  readonly property int startHour: 7
  readonly property int endHour: 19
  readonly property int hourHeight: Style.space(64)
  readonly property int timeGutter: Style.space(66)
  readonly property int timelineHeight: (endHour - startHour) * hourHeight
  readonly property var priorityOrder: ["normal", "family", "work", "informational"]

  function alpha(color, amount) { return Qt.rgba(color.r, color.g, color.b, amount) }
  function todayKey() {
    var value = new Date()
    return value.getFullYear() + "-" + String(value.getMonth() + 1).padStart(2, "0") + "-" + String(value.getDate()).padStart(2, "0")
  }
  function dateObject() {
    var value = new Date(selectedDate + "T12:00:00")
    return isNaN(value.getTime()) ? new Date() : value
  }
  function dateTitle() {
    var value = dateObject()
    return selectedDate === todayKey() ? "Today" : value.toLocaleDateString(Qt.locale(), "dddd")
  }
  function dateSubtitle() { return dateObject().toLocaleDateString(Qt.locale(), "MMMM d, yyyy") }
  function shiftDay(amount) {
    var value = dateObject()
    value.setDate(value.getDate() + amount)
    selectedDate = value.getFullYear() + "-" + String(value.getMonth() + 1).padStart(2, "0") + "-" + String(value.getDate()).padStart(2, "0")
    refresh(false)
  }
  function goToday() { selectedDate = todayKey(); refresh(false) }
  function open() { showingCalendars = false; root.controller.show(); refresh(false) }
  function openSettings() { showingCalendars = true; root.controller.show(); loadCalendars() }
  function close() { root.controller.hide() }
  function toggle() { if (root.opened) close(); else open() }
  function refresh(force) {
    force = force === true
    if (agendaProcess.running) {
      refreshQueued = true
      queuedForceRefresh = queuedForceRefresh || force
      return
    }
    loading = true
    errorText = ""
    agendaProcess.command = [calendarHelper, "agenda", "--date", selectedDate, "--json"]
    if (force) agendaProcess.command.push("--refresh")
    agendaProcess.running = true
  }
  function applyAgenda(value) {
    loading = false
    try {
      var payload = JSON.parse(String(value || "{}"))
      if (payload.date === selectedDate) {
        agenda = payload
        if (agenda.errors && agenda.errors.length)
          errorText = agenda.errors.map(function(e) { return e.message || "Calendar sync failed" }).join(" · ")
        Qt.callLater(scrollToNow)
        if (!prefetchProcess.running) {
          prefetchProcess.command = [calendarHelper, "prefetch", "--date", selectedDate, "--days", "2"]
          prefetchProcess.running = true
        }
      }
    } catch (e) { errorText = "Could not read calendar data" }
  }
  function loadCalendars() { if (!calendarListProcess.running) calendarListProcess.running = true }
  function addIcalSource() {
    var value = sourceUrl.trim()
    if (!value || addSourceProcess.running) return
    addSourceProcess.command = [calendarHelper, "source", "add", value]
    if (sourceName.trim()) addSourceProcess.command.push("--name", sourceName.trim())
    addSourceProcess.running = true
  }
  function applyCalendars(value) {
    try {
      var payload = JSON.parse(String(value || "{}"))
      calendars = payload.calendars || []
      if (payload.errors && payload.errors.length)
        errorText = payload.errors.map(function(e) { return e.message || "Could not list calendars" }).join(" · ")
    } catch (e) { errorText = "Could not read calendar settings" }
  }
  function updateCalendar(index, field, value) {
    var updated = calendars.slice()
    var row = {}
    for (var key in updated[index]) row[key] = updated[index][key]
    row[field] = value
    updated[index] = row
    calendars = updated
    return row
  }
  function toggleCalendar(index) {
    if (settingsProcess.running || index < 0 || index >= calendars.length) return
    var row = updateCalendar(index, "enabled", !calendars[index].enabled)
    settingsProcess.command = [calendarHelper, "calendar", "set", row.accountId, row.calendarId, row.enabled ? "true" : "false"]
    settingsProcess.running = true
  }
  function cyclePriority(index) {
    if (settingsProcess.running || index < 0 || index >= calendars.length) return
    var current = priorityOrder.indexOf(calendars[index].priority || "normal")
    var next = priorityOrder[(current + 1) % priorityOrder.length]
    var row = updateCalendar(index, "priority", next)
    settingsProcess.command = [calendarHelper, "calendar", "priority", row.accountId, row.calendarId, next]
    settingsProcess.running = true
  }
  function setAccountVisible(accountId, enabled) {
    if (settingsProcess.running) return
    var command = [calendarHelper, "calendar", "set-account", accountId, enabled ? "true" : "false"]
    var updated = calendars.slice()
    for (var i = 0; i < updated.length; i++) {
      if (updated[i].accountId !== accountId) continue
      var row = {}
      for (var key in updated[i]) row[key] = updated[i][key]
      row.enabled = enabled
      updated[i] = row
      command.push(row.calendarId)
    }
    calendars = updated
    settingsProcess.command = command
    settingsProcess.running = true
  }
  function openUrl(url) {
    if (!/^https:\/\//.test(String(url || ""))) return
    openProcess.command = ["xdg-open", url]
    openProcess.running = true
  }
  function joinMeeting(event) {
    if (!event || !/^https:\/\//.test(String(event.joinUrl || "")) || joinProcess.running) return
    joinProcess.command = [meetingsHelper, "join", "--title", event.title || "Meeting",
                           "--url", event.joinUrl, "--event-json", JSON.stringify(event)]
    joinProcess.running = true
  }
  function eventsWhere(kind) {
    var output = []
    var items = agenda.events || []
    for (var i = 0; i < items.length; i++) {
      var event = items[i]
      var start = new Date(event.start)
      var end = new Date(event.end)
      var startMinute = start.getHours() * 60 + start.getMinutes()
      var endMinute = end.getHours() * 60 + end.getMinutes()
      if (kind === "allDay" && event.allDay) output.push(event)
      else if (!event.allDay && kind === "before" && startMinute < startHour * 60) output.push(event)
      else if (!event.allDay && kind === "after" && startMinute >= endHour * 60) output.push(event)
      else if (!event.allDay && kind === "timeline" && endMinute > startHour * 60 && startMinute < endHour * 60) output.push(event)
    }
    return output
  }
  function minutes(value) { var date = new Date(value); return date.getHours() * 60 + date.getMinutes() }
  function timelineY(event) { return Math.max(0, minutes(event.start) - startHour * 60) * hourHeight / 60 }
  function timelineEventHeight(event) {
    var visibleStart = Math.max(startHour * 60, minutes(event.start))
    var visibleEnd = Math.min(endHour * 60, minutes(event.end))
    return Math.max(Style.space(28), (visibleEnd - visibleStart) * hourHeight / 60 - Style.spacing.xs)
  }
  function timeRange(event) {
    if (event.allDay) return "All day"
    var start = new Date(event.start)
    var end = new Date(event.end)
    return start.toLocaleTimeString(Qt.locale(), "h:mm AP") + "–" + end.toLocaleTimeString(Qt.locale(), "h:mm AP")
  }
  function nextEventText() {
    var events = agenda.events || []
    for (var i = 0; i < events.length; i++)
      if (!events[i].allDay && new Date(events[i].end).getTime() > nowMs) return events[i].timeLabel + "  " + events[i].title
    return "No more events today"
  }
  function eventEnded(event) { return new Date(event.end).getTime() <= nowMs }
  function eventText(event) { return eventEnded(event) ? muted : foreground }
  function priorityLabel(value) {
    if (value === "informational") return "Info"
    return String(value || "normal").charAt(0).toUpperCase() + String(value || "normal").slice(1)
  }
  function eventFill(event) {
    if (eventEnded(event)) return alpha(muted, 0.045)
    if (event.priority === "family") return Style.selectedFillFor(accent, accent, urgent)
    if (event.priority === "work") return Style.selectedFillFor(foreground, accent, urgent)
    if (event.priority === "informational") return alpha(muted, 0.05)
    return Style.normalFillFor(foreground, accent, urgent)
  }
  function eventMarker(event) {
    if (eventEnded(event)) return alpha(muted, 0.55)
    if (new Date(event.start).getTime() <= nowMs && nowMs < new Date(event.end).getTime()) return urgent
    if (event.priority === "family") return accent
    if (event.priority === "work") return foreground
    if (event.priority === "informational") return muted
    return accent
  }
  function scrollToNow() {
    if (selectedDate !== todayKey() || showingCalendars) return
    var now = new Date(nowMs)
    var minute = now.getHours() * 60 + now.getMinutes()
    if (minute < startHour * 60 || minute >= endHour * 60) return
    var target = timelineContainer.y + (minute - startHour * 60) * hourHeight / 60 - Style.space(150)
    panelScroll.contentY = Math.max(0, Math.min(target, panelScroll.contentHeight - panelScroll.height))
  }

  Process {
    id: agendaProcess
    command: [root.calendarHelper, "agenda", "--date", root.selectedDate, "--json"]
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.applyAgenda(text) }
    onExited: function(code) {
      root.loading = false
      if (code !== 0 && root.errorText === "") root.errorText = "Calendar refresh failed"
      if (root.refreshQueued) {
        var force = root.queuedForceRefresh
        root.refreshQueued = false
        root.queuedForceRefresh = false
        Qt.callLater(function() { root.refresh(force) })
      }
    }
  }
  Process { id: openProcess }
  Process { id: joinProcess; onExited: function(code) { if (code !== 0) root.errorText = "Could not join and start recording"; root.refreshRecording() } }
  Process {
    id: recordingStatusProcess
    command: [root.meetingsHelper, "status", "--json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          var payload = JSON.parse(text)
          root.recording = payload.recording === true
          root.recordingTitle = payload.session ? (payload.session.title || "Meeting") : ""
        } catch (e) { root.recording = false; root.recordingTitle = "" }
      }
    }
  }
  function refreshRecording() { if (!recordingStatusProcess.running) recordingStatusProcess.running = true }
  Process { id: prefetchProcess }
  Process {
    id: calendarListProcess
    command: [root.calendarHelper, "calendar", "list"]
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.applyCalendars(text) }
  }
  Process {
    id: settingsProcess
    onExited: function(code) {
      if (code === 0) root.refresh(true)
      else { root.errorText = "Could not save calendar settings"; root.loadCalendars() }
    }
  }
  Process {
    id: addAccountProcess
    command: [root.calendarHelper, "account", "add"]
    onExited: function(code) {
      if (code === 0) { root.loadCalendars(); root.refresh(true) }
      else root.errorText = "Could not add Google account"
    }
  }
  Process {
    id: addSourceProcess
    onExited: function(code) {
      if (code === 0) {
        root.sourceName = ""
        root.sourceUrl = ""
        root.loadCalendars()
        root.refresh(true)
      } else root.errorText = "Could not add iCalendar source — check the URL and try again"
    }
  }
  Timer { interval: root.refreshIntervalSec * 1000; repeat: true; running: true; triggeredOnStart: true; onTriggered: root.refresh(true) }
  Timer { interval: 30000; repeat: true; running: true; onTriggered: root.nowMs = Date.now() }
  Timer { interval: 5000; repeat: true; running: true; triggeredOnStart: true; onTriggered: root.refreshRecording() }

  IpcHandler {
    target: root.ipcTarget
    function open(): void { root.open() }
    function close(): void { root.close() }
    function toggle(): void { root.toggle() }
    function refresh(): void { root.refresh(true) }
  }

  KeyboardPanel {
    id: popup
    anchorItem: root.anchorItem
    owner: root.barIdentity
    bar: root.bar
    open: root.opened
    centerOnBar: true
    contentWidth: popup.fittedContentWidth(Style.space(520))
    contentHeight: popup.fittedContentHeight(Style.space(650))

    Column {
      id: panelLayout
      anchors.fill: parent
      spacing: 0

      Item {
        id: panelHeader
        width: parent.width
        height: Style.space(92)
        Button { visible: !root.showingCalendars; anchors.left: parent.left; anchors.leftMargin: Style.spacing.panelPadding; anchors.verticalCenter: parent.verticalCenter; text: "‹"; tooltipText: "Previous day"; foreground: root.foreground; accent: root.accent; onClicked: root.shiftDay(-1) }
        Column {
          visible: !root.showingCalendars
          anchors.centerIn: parent
          spacing: Style.spacing.xs
          Text { anchors.horizontalCenter: parent.horizontalCenter; text: root.dateTitle(); color: root.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true }
          Text { anchors.horizontalCenter: parent.horizontalCenter; text: root.dateSubtitle(); color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall }
        }
        Row {
          visible: !root.showingCalendars
          anchors.right: parent.right
          anchors.rightMargin: Style.spacing.panelPadding
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.spacing.sm
          Button { visible: root.selectedDate !== root.todayKey(); text: "Today"; foreground: root.foreground; accent: root.accent; onClicked: root.goToday() }
          Button { text: root.loading ? "Refreshing…" : "Refresh"; tooltipText: "Fetch the latest events"; foreground: root.foreground; accent: root.accent; onClicked: root.refresh(true) }
          Button { text: "›"; tooltipText: "Next day"; foreground: root.foreground; accent: root.accent; onClicked: root.shiftDay(1) }
        }
        Row {
          visible: root.showingCalendars
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.leftMargin: Style.spacing.panelPadding
          anchors.rightMargin: Style.spacing.panelPadding
          anchors.verticalCenter: parent.verticalCenter
          spacing: Style.spacing.sm
          Text { width: parent.width - addAccountButton.width - doneButton.width - parent.spacing * 2; anchors.verticalCenter: parent.verticalCenter; text: "Calendars"; color: root.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true; elide: Text.ElideRight }
          Button { id: addAccountButton; anchors.verticalCenter: parent.verticalCenter; text: addAccountProcess.running ? "Connecting…" : "Google"; tooltipText: "Connect a Google Calendar account"; foreground: root.foreground; accent: root.accent; enabled: !addAccountProcess.running; bordered: true; onClicked: addAccountProcess.running = true }
          Button { id: doneButton; anchors.verticalCenter: parent.verticalCenter; text: "Done"; foreground: root.foreground; accent: root.accent; selected: true; onClicked: { root.showingCalendars = false; root.refresh(false); Qt.callLater(root.scrollToNow) } }
        }
      }

      PanelSeparator { id: headerSeparator; foreground: root.foreground }

      Flickable {
        id: panelScroll
        width: parent.width
        height: parent.height - panelHeader.height - headerSeparator.height
        contentWidth: width
        contentHeight: content.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
          id: content
          width: panelScroll.width
          spacing: 0

        Column {
          visible: root.showingCalendars
          width: parent.width
          spacing: Style.spacing.sm
          topPadding: Style.spacing.xxl
          bottomPadding: Style.spacing.xxl
          Text { width: parent.width; leftPadding: Style.spacing.panelPadding; rightPadding: Style.spacing.panelPadding; bottomPadding: Style.spacing.sm; text: "Add a private iCalendar subscription — no Google Cloud project required"; color: root.foreground; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall; wrapMode: Text.Wrap }
          Row {
            width: parent.width
            leftPadding: Style.spacing.panelPadding
            rightPadding: Style.spacing.panelPadding
            spacing: Style.spacing.sm
            TextField { id: sourceNameField; width: Style.space(120); placeholderText: "Name"; text: root.sourceName; foreground: root.foreground; accent: root.accent; onTextChanged: root.sourceName = text }
            TextField { id: sourceUrlField; width: parent.width - sourceNameField.width - addSourceButton.width - parent.spacing * 2 - parent.leftPadding - parent.rightPadding; placeholderText: "https://…/calendar.ics"; text: root.sourceUrl; foreground: root.foreground; accent: root.accent; onTextChanged: root.sourceUrl = text; onAccepted: root.addIcalSource() }
            Button { id: addSourceButton; text: addSourceProcess.running ? "Adding…" : "Add"; foreground: root.foreground; accent: root.accent; selected: root.sourceUrl.trim() !== ""; enabled: root.sourceUrl.trim() !== "" && !addSourceProcess.running; onClicked: root.addIcalSource() }
          }
          Text { width: parent.width; leftPadding: Style.spacing.panelPadding; rightPadding: Style.spacing.panelPadding; topPadding: Style.spacing.md; bottomPadding: Style.spacing.md; text: "Use the secret subscription URL from Google Calendar, iCloud, Fastmail, Outlook, or another calendar provider. OmaMeet stores it locally with private permissions."; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption; wrapMode: Text.Wrap }
          PanelSeparator { width: parent.width; foreground: root.foreground }
          Text { width: parent.width; leftPadding: Style.spacing.panelPadding; topPadding: Style.spacing.lg; bottomPadding: Style.spacing.md; text: "Choose visibility and cycle each calendar's priority"; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption }
          Repeater {
            model: root.calendars
            delegate: Item {
              required property var modelData
              required property int index
              readonly property bool accountStart: index === 0 || root.calendars[index - 1].accountId !== modelData.accountId
              width: content.width
              height: (accountStart ? Style.space(42) : 0) + Style.space(62)
              Row {
                visible: parent.accountStart
                height: parent.accountStart ? Style.space(42) : 0
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: Style.spacing.panelPadding
                anchors.rightMargin: Style.spacing.panelPadding
                spacing: Style.spacing.sm
                Text { anchors.verticalCenter: parent.verticalCenter; width: parent.width - showAll.width - hideAll.width - parent.spacing * 2; text: modelData.accountLabel; color: root.foreground; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall; font.bold: true; elide: Text.ElideRight }
                Button { id: showAll; anchors.verticalCenter: parent.verticalCenter; text: "Show all"; foreground: root.foreground; accent: root.accent; onClicked: root.setAccountVisible(modelData.accountId, true) }
                Button { id: hideAll; anchors.verticalCenter: parent.verticalCenter; text: "Hide all"; foreground: root.foreground; accent: root.accent; onClicked: root.setAccountVisible(modelData.accountId, false) }
              }
              Toggle {
                anchors.left: parent.left
                anchors.right: priorityButton.left
                anchors.leftMargin: Style.spacing.panelPadding
                anchors.rightMargin: Style.spacing.md
                anchors.bottom: parent.bottom
                height: Style.space(58)
                label: modelData.calendarLabel
                description: modelData.primary ? "Primary calendar" : ""
                checked: modelData.enabled
                foreground: root.foreground
                accent: root.accent
                onClicked: root.toggleCalendar(index)
              }
              Button {
                id: priorityButton
                anchors.right: parent.right
                anchors.rightMargin: Style.spacing.panelPadding
                anchors.bottom: parent.bottom
                anchors.bottomMargin: Style.spacing.md
                text: root.priorityLabel(modelData.priority)
                tooltipText: "Priority: click to change"
                foreground: root.foreground
                accent: root.accent
                bordered: true
                onClicked: root.cyclePriority(index)
              }
            }
          }
        }

        Column {
          visible: !root.showingCalendars
          width: parent.width
          spacing: 0

          Item {
            visible: root.errorText !== ""
            width: parent.width
            height: visible ? errorLabel.implicitHeight + Style.spacing.xxl * 2 : 0
            Text { id: errorLabel; anchors.left: parent.left; anchors.right: parent.right; anchors.margins: Style.spacing.panelPadding; anchors.verticalCenter: parent.verticalCenter; text: root.errorText; color: root.urgent; font.family: Style.font.family; font.pixelSize: Style.font.bodySmall; wrapMode: Text.Wrap }
          }

          Column {
            visible: root.eventsWhere("allDay").length > 0
            width: parent.width
            topPadding: Style.spacing.xl
            bottomPadding: Style.spacing.xl
            spacing: Style.spacing.sm
            Text { leftPadding: Style.spacing.panelPadding; text: "ALL DAY"; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption; font.bold: true; font.letterSpacing: 1 }
            Repeater {
              model: root.eventsWhere("allDay")
              delegate: Rectangle {
                required property var modelData
                width: parent.width - Style.spacing.panelPadding * 2
                height: Style.space(36)
                anchors.horizontalCenter: parent.horizontalCenter
                radius: Style.cornerRadius
                color: root.eventFill(modelData)
                Rectangle { width: Style.space(3); height: parent.height; color: root.eventMarker(modelData); radius: width / 2 }
                Text { anchors.left: parent.left; anchors.leftMargin: Style.spacing.xl; anchors.right: parent.right; anchors.rightMargin: Style.spacing.md; anchors.verticalCenter: parent.verticalCenter; text: modelData.title + "  ·  " + modelData.calendarLabel; color: root.eventText(modelData); font.family: Style.font.family; font.pixelSize: Style.font.bodySmall; elide: Text.ElideRight }
                TapHandler { onTapped: root.openUrl(modelData.htmlLink) }
              }
            }
          }

          CompactEvents { title: "BEFORE 7 AM"; events: root.eventsWhere("before") }

          Item {
            id: timelineContainer
            width: parent.width
            height: root.timelineHeight

            Repeater {
              model: root.endHour - root.startHour + 1
              delegate: Item {
                required property int index
                width: timelineContainer.width
                height: 1
                y: index * root.hourHeight
                Rectangle { anchors.left: parent.left; anchors.leftMargin: root.timeGutter; anchors.right: parent.right; height: 1; color: root.alpha(root.foreground, 0.1) }
                Text { anchors.left: parent.left; anchors.leftMargin: Style.spacing.panelPadding; anchors.verticalCenter: parent.verticalCenter; text: String((root.startHour + index - 1) % 12 + 1) + ((root.startHour + index) < 12 ? " AM" : " PM"); color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption }
              }
            }

            Rectangle {
              id: currentLine
              visible: root.selectedDate === root.todayKey() && (new Date(root.nowMs).getHours() * 60 + new Date(root.nowMs).getMinutes()) >= root.startHour * 60 && (new Date(root.nowMs).getHours() * 60 + new Date(root.nowMs).getMinutes()) <= root.endHour * 60
              anchors.left: parent.left
              anchors.leftMargin: root.timeGutter - Style.space(4)
              anchors.right: parent.right
              height: Style.space(2)
              y: ((new Date(root.nowMs).getHours() * 60 + new Date(root.nowMs).getMinutes()) - root.startHour * 60) * root.hourHeight / 60
              color: root.urgent
              z: 20
              Rectangle { width: Style.space(8); height: width; radius: width / 2; color: root.urgent; anchors.right: parent.left; anchors.verticalCenter: parent.verticalCenter }
            }

            Repeater {
              model: root.eventsWhere("timeline")
              delegate: Rectangle {
                required property var modelData
                readonly property int columns: Math.max(1, Number(modelData.overlapColumns || 1))
                readonly property int column: Math.max(0, Number(modelData.overlapColumn || 0))
                readonly property real availableWidth: timelineContainer.width - root.timeGutter - Style.spacing.panelPadding
                x: root.timeGutter + column * availableWidth / columns + Style.spacing.xs
                y: root.timelineY(modelData)
                width: availableWidth / columns - Style.spacing.sm
                height: root.timelineEventHeight(modelData)
                radius: Style.cornerRadius
                color: root.eventFill(modelData)
                border.width: modelData.priority === "informational" ? Style.normalBorderWidth : 0
                border.color: root.alpha(root.eventMarker(modelData), Style.normalBorderAlpha)
                opacity: root.eventEnded(modelData) ? 0.72 : 1
                z: root.eventEnded(modelData) ? 4 : modelData.priority === "family" ? 8 : modelData.priority === "work" ? 7 : modelData.priority === "normal" ? 6 : 5
                Rectangle { width: Style.space(3); anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; radius: width / 2; color: root.eventMarker(modelData) }
                Column {
                  anchors.fill: parent
                  anchors.leftMargin: Style.spacing.xl
                  anchors.rightMargin: joinButton.visible ? joinButton.width + Style.spacing.sm : Style.spacing.md
                  anchors.topMargin: Style.spacing.sm
                  clip: true
                  Text { width: parent.width; text: modelData.title; color: root.eventText(modelData); font.family: Style.font.family; font.pixelSize: Style.font.bodySmall; font.bold: !root.eventEnded(modelData) && (modelData.priority === "family" || modelData.priority === "work"); elide: Text.ElideRight }
                  Text { width: parent.width; visible: parent.parent.height >= Style.space(44); text: root.timeRange(modelData) + "  ·  " + modelData.calendarLabel; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption; elide: Text.ElideRight }
                }
                Button { id: joinButton; visible: !!modelData.joinUrl && !root.eventEnded(modelData); anchors.right: parent.right; anchors.rightMargin: Style.spacing.xs; anchors.verticalCenter: parent.verticalCenter; text: root.recording ? "Recording" : "Join"; foreground: root.foreground; accent: root.accent; selected: root.recording; enabled: !joinProcess.running && !root.recording; onClicked: root.joinMeeting(modelData) }
                HoverHandler { id: eventHover }
                TapHandler { onTapped: root.openUrl(modelData.htmlLink) }
              }
            }
          }

          CompactEvents { title: "AFTER 7 PM"; events: root.eventsWhere("after") }

          Item {
            visible: !root.loading && root.errorText === "" && (!root.agenda.events || root.agenda.events.length === 0)
            width: parent.width
            height: visible ? Style.space(150) : 0
            Column { anchors.centerIn: parent; spacing: Style.spacing.md; Text { anchors.horizontalCenter: parent.horizontalCenter; text: "✓"; color: root.accent; font.pixelSize: Style.font.displayLarge } Text { anchors.horizontalCenter: parent.horizontalCenter; text: root.agenda.accounts && root.agenda.accounts.length ? "Your day is clear" : "Add a calendar to begin"; color: root.foreground; font.family: Style.font.family; font.pixelSize: Style.font.title; font.bold: true } }
          }
        }
        }
      }
    }
  }

  component CompactEvents: Column {
    id: compact
    required property string title
    required property var events
    visible: events.length > 0
    width: parent ? parent.width : 0
    topPadding: Style.spacing.xl
    bottomPadding: Style.spacing.xl
    spacing: Style.spacing.sm
    Text { leftPadding: Style.spacing.panelPadding; text: compact.title; color: root.muted; font.family: Style.font.family; font.pixelSize: Style.font.caption; font.bold: true; font.letterSpacing: 1 }
    Repeater {
      model: compact.events
      delegate: Rectangle {
        required property var modelData
        width: compact.width - Style.spacing.panelPadding * 2
        height: Style.space(38)
        anchors.horizontalCenter: parent.horizontalCenter
        radius: Style.cornerRadius
        color: root.eventFill(modelData)
        Rectangle { width: Style.space(3); height: parent.height; radius: width / 2; color: root.eventMarker(modelData) }
        Text { anchors.left: parent.left; anchors.leftMargin: Style.spacing.xl; anchors.right: parent.right; anchors.rightMargin: Style.spacing.md; anchors.verticalCenter: parent.verticalCenter; text: root.timeRange(modelData) + "  " + modelData.title; color: root.eventText(modelData); font.family: Style.font.family; font.pixelSize: Style.font.bodySmall; elide: Text.ElideRight }
        TapHandler { onTapped: root.openUrl(modelData.htmlLink) }
      }
    }
  }
}
