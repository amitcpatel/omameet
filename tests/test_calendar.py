import importlib.machinery
import importlib.util
import contextlib
import io
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

    def test_only_google_calendar_sources_are_exposed(self):
        calendar = load_module()
        removed = (
            "FEEDS_FILE", "feeds", "add_feed", "remove_feed", "read_ical_source",
            "parse_ical", "ical_events", "fetch_public_https",
        )
        for name in removed:
            self.assertFalse(hasattr(calendar, name), name)

        with patch.object(calendar.sys, "argv", ["omascribe-calendar", "source", "list"]), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaisesRegex(SystemExit, "2"):
                calendar.main()

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
