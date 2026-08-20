import importlib.machinery
import importlib.util
import unittest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


def load_module():
    path = Path(__file__).parents[1] / "bin" / "omascribe-calendar"
    loader = importlib.machinery.SourceFileLoader("omarchy_calendar", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class CalendarTests(unittest.TestCase):
    def test_legacy_keyring_token_is_migrated_to_omascribe_namespace(self):
        calendar = load_module()
        calls = []

        def fake_run(argv, **kwargs):
            calls.append((argv, kwargs.get("input")))
            if argv[1] == "lookup" and "omarchy-calendar" in argv:
                return type("Result", (), {"returncode": 0, "stdout": "legacy-token\n"})()
            if argv[1] == "lookup":
                return type("Result", (), {"returncode": 1, "stdout": ""})()
            return type("Result", (), {"returncode": 0, "stdout": ""})()

        with patch.object(calendar.subprocess, "run", side_effect=fake_run):
            self.assertEqual("legacy-token", calendar.load_token("account-1"))

        self.assertIn("omascribe-calendar", calls[0][0])
        self.assertIn("omarchy-calendar", calls[1][0])
        self.assertEqual("legacy-token", calls[2][1])

    def test_ical_parses_folded_text_and_meeting_link(self):
        calendar = load_module()
        feed = {"id": "work", "name": "Work", "source": "file:///unused"}
        text = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
UID:standup\r
DTSTART:20260819T130000Z\r
DTEND:20260819T133000Z\r
SUMMARY:Team stand\r
 up\r
DESCRIPTION:Join https://meet.google.com/abc-defg-hij\r
END:VEVENT\r
END:VCALENDAR\r
"""
        original = calendar.read_ical_source
        calendar.read_ical_source = lambda _: text
        try:
            events = calendar.ical_events(feed, calendar.date(2026, 8, 19))
        finally:
            calendar.read_ical_source = original
        self.assertEqual(events[0]["title"], "Team standup")
        self.assertEqual(events[0]["joinUrl"], "https://meet.google.com/abc-defg-hij")
        self.assertEqual(events[0]["calendarLabel"], "Work")

    def test_ical_all_day_and_exdate(self):
        calendar = load_module()
        text = """BEGIN:VCALENDAR
BEGIN:VEVENT
UID:holiday
DTSTART;VALUE=DATE:20260819
DTEND;VALUE=DATE:20260820
SUMMARY:Holiday
END:VEVENT
BEGIN:VEVENT
UID:daily
DTSTART:20260817T090000
DTEND:20260817T093000
RRULE:FREQ=DAILY;COUNT=4
EXDATE:20260819T090000
SUMMARY:Daily
END:VEVENT
END:VCALENDAR
"""
        original = calendar.read_ical_source
        calendar.read_ical_source = lambda _: text
        try:
            events = calendar.ical_events(
                {"id": "one", "name": "Personal", "source": "file:///unused"},
                calendar.date(2026, 8, 19))
        finally:
            calendar.read_ical_source = original
        self.assertEqual([event["title"] for event in events], ["Holiday"])
        self.assertTrue(events[0]["allDay"])

    def test_ical_weekly_byday(self):
        calendar = load_module()
        raw = calendar.parse_ical("""BEGIN:VCALENDAR
BEGIN:VEVENT
UID:class
DTSTART:20260817T100000
DTEND:20260817T110000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4
SUMMARY:Class
END:VEVENT
END:VCALENDAR
""")[0]
        zone = calendar.datetime.now().astimezone().tzinfo
        starts = calendar.recurrence_starts(
            raw,
            calendar.datetime(2026, 8, 19, tzinfo=zone),
            calendar.datetime(2026, 8, 20, tzinfo=zone))
        self.assertTrue(any(value.date() == calendar.date(2026, 8, 19) for value in starts))

    def test_feed_add_rejects_insecure_http(self):
        calendar = load_module()
        with self.assertRaisesRegex(ValueError, "https"):
            calendar.add_feed("http://example.com/calendar.ics", "Work")

    def test_feed_add_rejects_file_url(self):
        calendar = load_module()
        with self.assertRaisesRegex(ValueError, "local .ics path"):
            calendar.add_feed("file:///etc/passwd", "Unsafe")

    def test_feed_add_rejects_private_and_local_hosts(self):
        calendar = load_module()
        for url in ("https://127.0.0.1/calendar.ics",
                    "https://169.254.169.254/calendar.ics",
                    "https://10.0.0.5/calendar.ics"):
            with self.assertRaisesRegex(ValueError, "private or local"):
                calendar.validate_remote_calendar_url(url)

    def test_feed_fetch_connects_to_the_exact_validated_ip(self):
        calendar = load_module()
        raw_socket = object()
        wrapped_socket = object()
        tls_hosts = []

        class Context:
            def wrap_socket(self, sock, *, server_hostname):
                if sock is not raw_socket:
                    raise AssertionError("TLS did not wrap the pinned socket")
                tls_hosts.append(server_hostname)
                return wrapped_socket

        connection = calendar.PinnedHTTPSConnection(
            "calendar.example", 443, "93.184.216.34")
        connection._context = Context()
        with patch.object(calendar.socket, "create_connection", return_value=raw_socket) as connect:
            connection.connect()

        connect.assert_called_once_with(("93.184.216.34", 443), 20, None)
        self.assertIs(connection.sock, wrapped_socket)
        self.assertEqual(tls_hosts, ["calendar.example"])

    def test_feed_redirect_cannot_change_origin(self):
        calendar = load_module()

        class Response:
            status = 302
            def getheader(self, _name):
                return "https://attacker.example/feed.ics"

        class Connection:
            def request(self, *_args, **_kwargs):
                pass
            def getresponse(self):
                return Response()
            def close(self):
                pass

        def resolve(url):
            return calendar.urllib.parse.urlparse(url), ("93.184.216.34",)

        with patch.object(calendar, "resolve_public_https_url", side_effect=resolve), \
                patch.object(calendar, "PinnedHTTPSConnection", return_value=Connection()):
            with self.assertRaisesRegex(ValueError, "changed origin"):
                calendar.fetch_public_https("https://calendar.example/feed.ics", {})

    def test_feed_fetch_passes_resolved_ip_to_pinned_connection(self):
        calendar = load_module()
        calls = []

        class Response:
            status = 200
            def getheader(self, _name):
                return None
            def read(self, _limit):
                return b"BEGIN:VCALENDAR\nEND:VCALENDAR\n"

        class Connection:
            def request(self, method, path, headers):
                calls.append((method, path, headers))
            def getresponse(self):
                return Response()
            def close(self):
                pass

        def factory(host, port, pinned_ip, *, timeout):
            calls.append((host, port, pinned_ip, timeout))
            return Connection()

        resolved = (calendar.urllib.parse.urlparse(
            "https://calendar.example/feed.ics?private=1"), ("93.184.216.34",))
        with patch.object(calendar, "resolve_public_https_url", return_value=resolved), \
                patch.object(calendar, "PinnedHTTPSConnection", side_effect=factory):
            data = calendar.fetch_public_https(
                "https://calendar.example/feed.ics?private=1", {"Accept": "text/calendar"})

        self.assertTrue(data.startswith(b"BEGIN:VCALENDAR"))
        self.assertEqual(calls[0], ("calendar.example", 443, "93.184.216.34", 20))
        self.assertEqual(calls[1][0:2], ("GET", "/feed.ics?private=1"))

    def test_feed_preferences_are_stored_with_private_permissions(self):
        calendar = load_module()
        with tempfile.TemporaryDirectory() as directory:
            calendar.STATE = Path(directory)
            calendar.FEEDS_FILE = calendar.STATE / "feeds.json"
            calendar.CACHE_DIR = calendar.STATE / "cache"
            source = Path(directory) / "calendar.ics"
            source.write_text("BEGIN:VCALENDAR\nEND:VCALENDAR\n")
            item = calendar.add_feed(str(source), "Personal")
            self.assertEqual(calendar.feeds()[0]["name"], "Personal")
            self.assertEqual(calendar.FEEDS_FILE.stat().st_mode & 0o777, 0o600)
            calendar.update_feed(item["id"], enabled=False)
            self.assertFalse(calendar.feeds()[0]["enabled"])

    def test_meeting_url_prefers_structured_video(self):
        calendar = load_module()
        event = {
            "hangoutLink": "https://meet.google.com/fallback",
            "conferenceData": {"entryPoints": [{"entryPointType": "video", "uri": "https://meet.google.com/preferred"}]},
        }
        self.assertEqual(calendar.meeting_url(event), "https://meet.google.com/preferred")

    def test_meeting_url_falls_back_to_description(self):
        calendar = load_module()
        event = {"description": "Join us at https://meet.google.com/abc-defg-hij for the call."}
        self.assertEqual(calendar.meeting_url(event), "https://meet.google.com/abc-defg-hij")

    def test_meeting_url_rejects_lookalike_domains(self):
        calendar = load_module()
        for host in ("evilzoom.us", "notwebex.com", "zoom.us.attacker.example"):
            event = {"description": f"Join https://{host}/meeting"}
            self.assertEqual(calendar.meeting_url(event), "", host)
        self.assertEqual(
            calendar.meeting_url({"description": "Join https://acme.zoom.us/meeting"}),
            "https://acme.zoom.us/meeting")

    def test_normalize_all_day(self):
        calendar = load_module()
        event = {"id": "1", "summary": "Holiday", "start": {"date": "2026-08-15"}, "end": {"date": "2026-08-16"}, "_calendar": {"id": "primary", "label": "Work"}}
        output = calendar.normalize(event, {"id": "a", "email": "me@example.com"}, datetime.now().astimezone())
        self.assertTrue(output["allDay"])
        self.assertEqual(output["timeLabel"], "All day")

    def test_calendar_visibility_defaults_on_and_persists_by_account(self):
        calendar = load_module()
        with tempfile.TemporaryDirectory() as directory:
            calendar.STATE = Path(directory)
            calendar.PREFERENCES_FILE = calendar.STATE / "preferences.json"
            self.assertTrue(calendar.calendar_enabled("account-a", "school"))
            calendar.set_calendar_enabled("account-a", "school", False)
            self.assertFalse(calendar.calendar_enabled("account-a", "school"))
            self.assertTrue(calendar.calendar_enabled("account-b", "school"))

    def test_calendar_priority_defaults_normal_and_persists(self):
        calendar = load_module()
        with tempfile.TemporaryDirectory() as directory:
            calendar.STATE = Path(directory)
            calendar.PREFERENCES_FILE = calendar.STATE / "preferences.json"
            self.assertEqual(calendar.calendar_priority("account-a", "family"), "normal")
            calendar.set_calendar_priority("account-a", "family", "family")
            self.assertEqual(calendar.calendar_priority("account-a", "family"), "family")
            self.assertEqual(calendar.calendar_priority("account-b", "family"), "normal")

    def test_overlap_layout_assigns_parallel_columns(self):
        calendar = load_module()
        events = [
            {"start": "2026-08-15T09:00:00-04:00", "end": "2026-08-15T10:00:00-04:00", "allDay": False},
            {"start": "2026-08-15T09:30:00-04:00", "end": "2026-08-15T10:30:00-04:00", "allDay": False},
            {"start": "2026-08-15T11:00:00-04:00", "end": "2026-08-15T12:00:00-04:00", "allDay": False},
        ]
        calendar.apply_overlap_layout(events)
        self.assertEqual((events[0]["overlapColumn"], events[0]["overlapColumns"]), (0, 2))
        self.assertEqual((events[1]["overlapColumn"], events[1]["overlapColumns"]), (1, 2))
        self.assertEqual((events[2]["overlapColumn"], events[2]["overlapColumns"]), (0, 1))

    def test_agenda_cache_round_trip(self):
        calendar = load_module()
        with tempfile.TemporaryDirectory() as directory:
            calendar.STATE = Path(directory)
            calendar.CACHE_DIR = calendar.STATE / "agenda-cache"
            day = calendar.date(2026, 8, 15)
            payload = {"date": "2026-08-15", "events": [{"id": "one"}], "errors": []}
            calendar.write_cached_agenda(day, payload)
            self.assertEqual(calendar.read_cached_agenda(day), payload)


class AttendeeTest(unittest.TestCase):
    """Attendees/organizer must survive normalization.

    Downstream consumers (acp.meetings) map voices to real people using this
    data; dropping it silently degrades speaker attribution.
    """

    def normalized(self, event):
        calendar = load_module()
        now = calendar.datetime.now().astimezone()
        base = {"id": "e1", "summary": "Sync",
                "start": {"dateTime": "2026-08-21T14:00:00-04:00"},
                "end": {"dateTime": "2026-08-21T15:00:00-04:00"}}
        base.update(event)
        return calendar.normalize(base, {"id": "acct", "email": "me@example.com"}, now)

    def test_attendees_are_preserved(self):
        result = self.normalized({"attendees": [
            {"email": "sidd@ayon.com", "displayName": "Sidd", "responseStatus": "accepted"},
            {"email": "me@example.com", "self": True, "organizer": True,
             "responseStatus": "accepted"},
        ]})
        self.assertEqual(len(result["attendees"]), 2)
        self.assertEqual(result["guestCount"], 2)
        sidd = [a for a in result["attendees"] if a["email"] == "sidd@ayon.com"][0]
        self.assertEqual(sidd["displayName"], "Sidd")
        self.assertEqual(sidd["responseStatus"], "accepted")

    def test_self_and_organizer_flags_kept(self):
        result = self.normalized({"attendees": [
            {"email": "me@example.com", "self": True, "organizer": True}]})
        me = result["attendees"][0]
        self.assertTrue(me.get("self"))
        self.assertTrue(me.get("organizer"))

    def test_optional_and_resource_flags_kept(self):
        result = self.normalized({"attendees": [
            {"email": "room@ayon.com", "resource": True},
            {"email": "maybe@ayon.com", "optional": True}]})
        flags = {a["email"]: a for a in result["attendees"]}
        self.assertTrue(flags["room@ayon.com"].get("resource"))
        self.assertTrue(flags["maybe@ayon.com"].get("optional"))

    def test_display_name_falls_back_to_email_local_part(self):
        result = self.normalized({"attendees": [{"email": "noname@ayon.com"}]})
        self.assertEqual(result["attendees"][0]["displayName"], "noname")

    def test_organizer_and_description_preserved(self):
        result = self.normalized({
            "organizer": {"email": "boss@ayon.com", "displayName": "Boss"},
            "description": "agenda here", "location": "Room 2"})
        self.assertEqual(result["organizer"]["email"], "boss@ayon.com")
        self.assertEqual(result["description"], "agenda here")
        self.assertEqual(result["location"], "Room 2")

    def test_recurrence_and_status_preserved(self):
        result = self.normalized({"recurringEventId": "rec123", "status": "cancelled"})
        self.assertEqual(result["recurringEventId"], "rec123")
        self.assertEqual(result["status"], "cancelled")

    def test_no_attendees_yields_empty_list_not_missing_key(self):
        result = self.normalized({})
        self.assertEqual(result["attendees"], [])
        self.assertEqual(result["guestCount"], 0)

    def test_existing_fields_unchanged(self):
        """The patch is additive — nothing the widget relies on may change."""
        result = self.normalized({})
        for key in ("id", "title", "start", "end", "timeLabel", "allDay", "isNow",
                    "accountId", "accountLabel", "calendarId", "calendarLabel",
                    "priority", "color", "joinUrl", "htmlLink"):
            self.assertIn(key, result, f"existing field {key} must not be dropped")


if __name__ == "__main__":
    unittest.main()
