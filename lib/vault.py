"""Vault writer: meeting.json is the source of truth, notes.md is rendered from it.

Audio deletion is irreversible, so it happens only after every success condition
is verified: transcript non-empty, notes written, meeting.json written.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path


def slugify(text: str, limit: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return (text[:limit].strip("-") or "meeting")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def frontmatter(meeting: dict, participants: list[dict], extracted: dict) -> str:
    def esc(value):
        return json.dumps(value if value is not None else "")

    people = [p.get("name") for p in participants if p.get("name")]
    lines = [
        "---",
        "type: meeting",
        "folder: Meetings",
        f"title: {esc(meeting.get('title'))}",
        f"date: {esc(((meeting.get('scheduled') or {}).get('start') or (meeting.get('actual') or {}).get('start') or '')[:10])}",
        f"start: {esc(meeting.get('actual', {}).get('start'))}",
        f"end: {esc(meeting.get('actual', {}).get('end'))}",
        f"event_id: {esc(meeting.get('event_id'))}",
        f"series_id: {esc(meeting.get('series_id'))}",
        f"platform: {esc(meeting.get('platform'))}",
        f"host: {esc(meeting.get('host_machine'))}",
        "attendees:",
    ]
    for person in people:
        lines.append(f"  - {esc(person)}")
    lines += [
        f"commitments: {len(extracted.get('commitments', []))}",
        f"decisions: {len(extracted.get('decisions', []))}",
        f"needs_review: {sum(1 for c in extracted.get('commitments', []) if c.get('needs_human'))}",
        f"last_updated: {esc(datetime.now().astimezone().date().isoformat())}",
        "generated: OmaMeet",
        "---",
        "",
    ]
    return "\n".join(lines)


def write_meeting(vault: Path, meeting: dict, participants: list[dict],
                  conflicts: list[dict], extracted: dict, transcript_md: str,
                  notes_body: str, audio_files: list[Path],
                  retain_audio: bool) -> dict:
    """Audio deletion requires the WHOLE chain to succeed — including extraction.

    A failed extraction means the meeting can be reprocessed later, which is
    impossible once the audio is gone. Deletion is irreversible; retention is not.
    """
    """Write the folder atomically-ish and return a result with verification."""
    date = (meeting.get("scheduled", {}).get("start")
            or meeting.get("actual", {}).get("start") or "")[:10]
    if not date:
        date = datetime.now().astimezone().date().isoformat()
    folder_name = f"{date}-{slugify(meeting.get('title', 'meeting'))}"
    # Ad-hoc recordings share a generic title. Without the start time, every
    # recording on the same day overwrites the previous meeting's vault files.
    if str(meeting.get("event_id") or "").startswith("adhoc_"):
        started = (meeting.get("actual", {}).get("start") or "")[11:19]
        stamp = started.replace(":", "")
        if stamp:
            folder_name = f"{date}-{stamp}-{slugify(meeting.get('title', 'meeting'))}"
    folder = vault / folder_name
    folder.mkdir(parents=True, exist_ok=True)

    contract = {
        "schema": 1,
        "generated_by": "OmaMeet",
        "generated_at": datetime.now().astimezone().isoformat(),
        "meeting": meeting,
        "participants": participants,
        "participant_conflicts": conflicts,
        "commitments": extracted.get("commitments", []),
        "decisions": extracted.get("decisions", []),
        "risks": extracted.get("risks", []),
        "questions": extracted.get("questions", []),
        "uncertain": extracted.get("uncertain", []),
        "followups": build_followups(extracted, meeting),
        "llm": extracted.get("llm", {}),
        "passes": extracted.get("passes", {}),
        "audio": {
            "deleted": False,
            "retained": retain_audio,
            "checksums": {p.name: sha256(p) for p in audio_files if p.exists()},
        },
    }

    transcript_path = folder / "transcript.md"
    notes_path = folder / "notes.md"
    contract_path = folder / "meeting.json"

    transcript_path.write_text(transcript_md)
    notes_path.write_text(frontmatter(meeting, participants, extracted) + notes_body)

    # Verify before considering deletion. Size and exit codes lie.
    written_ok = (
        transcript_path.exists() and transcript_path.stat().st_size > 0
        and notes_path.exists() and notes_path.stat().st_size > 0
        and bool(transcript_md.strip())
    )
    # Extraction must ALSO have succeeded, or the audio stays so the meeting
    # can be reprocessed once the LLM is available again.
    extraction_ok = not extracted.get("error")
    verified = written_ok and extraction_ok
    contract["verification"] = {
        "files_written": written_ok,
        "extraction_ok": extraction_ok,
        "extraction_error": extracted.get("error"),
        "safe_to_delete_audio": verified,
    }

    deleted = []
    if verified and not retain_audio:
        for audio in audio_files:
            try:
                if audio.exists():
                    audio.unlink()
                    deleted.append(audio.name)
            except OSError:
                pass
        contract["audio"]["deleted"] = bool(deleted)
        contract["audio"]["deleted_files"] = deleted

    if not verified:
        contract["audio"]["retained_reason"] = (
            extracted.get("error") or "output verification failed")
    contract_path.write_text(json.dumps(contract, indent=2) + "\n")
    return {
        "ok": written_ok,
        "dir": str(folder),
        "verified": verified,
        "extraction_ok": extraction_ok,
        "audio_deleted": deleted,
        "audio_retained": not deleted,
        "files": [p.name for p in (contract_path, notes_path, transcript_path)],
    }


def build_followups(extracted: dict, meeting: dict) -> list[dict]:
    """Drafted, never sent. Approval belongs to the human."""
    followups = []
    for commitment in extracted.get("commitments", []):
        owner = commitment.get("owner") or {}
        due = (commitment.get("due") or {}).get("value")
        if owner.get("email") and due:
            followups.append({
                "action": "email",
                "to": owner["email"],
                "when": f"{due}T09:00",
                "condition": f"if {commitment['id']} still open",
                "draft": f"Hi {owner.get('name') or ''} — following up on: "
                         f"{commitment.get('text')}. You mentioned "
                         f"\"{(commitment.get('verbatim') or '')[:120]}\".",
                "status": "draft",
                "requires_approval": True,
            })
        followups.append({
            "action": "task",
            "title": commitment.get("text"),
            "owner": owner.get("name"),
            "due": due,
            "source": commitment["id"],
            "status": "draft",
            "requires_approval": True,
        })
    return followups
