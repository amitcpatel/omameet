# OmaMeet release status

Last updated: 2026-08-19

## Current state

- Product name: **OmaMeet — AI Meeting Notes**
- Plugin ID: `acp.omameet`
- Public repository: <https://github.com/amitcpatel/omameet>
- Marketplace submission: <https://github.com/HANCORE-linux/omarchy-plugin-marketplace/issues/788>
- Marketplace state: open, validated, awaiting manual security review
- Marketplace-reviewed version: `0.3.1`
- Marketplace-reviewed commit: `3b5c532`
- Local installed version on the development machine: `0.3.0`
- Prepared update version: `0.3.2`
- Prepared update branch: `remove-watchdog-v0.3.2`
- Prepared code and preview commit: `037ae4d`

Do not open a second marketplace submission. Continue with issue #788.

## What is already released

- `v0.3.0`: first marketplace-ready implementation
- `v0.3.1`: product positioning updated to **OmaMeet — AI Meeting Notes**
- GitHub release: <https://github.com/amitcpatel/omameet/releases/tag/v0.3.1>

The `main` branch currently remains on v0.3.1 while marketplace review is in
progress.

## What is staged for v0.3.2

The branch `remove-watchdog-v0.3.2` contains:

- complete removal of the legacy watchdog command and notification;
- complete removal of the legacy systemd timer installer;
- the native Omarchy service as the only automatic meeting detector;
- a regression test confirming `watchdog` and `install-timers` are absent;
- the approved root marketplace image at `preview.png`;
- version updates in `manifest.json`, `bin/omameet-meetings`, and the README.

Relevant commits:

- `805f2a5` — Remove legacy watchdog notifications and timers
- `037ae4d` — Add marketplace preview for OmaMeet

The preview is an authentic capture of the native v0.3.2 panel using synthetic
events. It is 832 × 1086, contains no private calendar data, and was approved by
the project owner.

## Verification completed

On v0.3.2:

- `omarchy plugin validate .` passes;
- all 96 unit and contract tests pass;
- Python source compiles;
- installer and removal shell scripts pass `bash -n`;
- `git diff --check` passes;
- the legacy watchdog unit was disabled and removed from the development
  machine;
- `systemctl --user status omarchy-meetings-watchdog.timer` reports that the
  unit cannot be found.

`qmllint` is not installed on the development machine. The actual v0.3.2 panel
was instead loaded in the running Omarchy shell and captured successfully.

## Marketplace review notes

Submission #788 passed repository and Quattro compatibility validation at
commit `3b5c532`. The automated security baseline found no security findings,
but requested manual review for:

- the optional installer/removal scripts; and
- user-service management, including the isolated `systemd-run --user` meeting
  processing job.

The original validation also reported that v0.3.1 had no root preview. The
approved `preview.png` is staged in v0.3.2 and will resolve that on revalidation.

## Resume after marketplace approval

1. Confirm issue #788 is approved and the plugin appears in the marketplace.
2. Check out and update the prepared branch:

   ```bash
   git switch remove-watchdog-v0.3.2
   git pull --ff-only
   ```

3. Re-run release validation:

   ```bash
   omarchy plugin validate .
   python3 -m unittest discover -s tests -v
   python3 -m py_compile bin/omameet-calendar bin/omameet-meetings lib/*.py
   bash -n install.sh uninstall.sh
   git diff --check
   ```

4. Merge v0.3.2 into `main` and push:

   ```bash
   git switch main
   git pull --ff-only
   git merge --ff-only remove-watchdog-v0.3.2
   git push origin main
   ```

5. Tag and publish v0.3.2:

   ```bash
   git tag -a v0.3.2 -m "OmaMeet 0.3.2"
   git push origin v0.3.2
   gh release create v0.3.2 \
     --repo amitcpatel/omameet \
     --title "OmaMeet 0.3.2 — AI Meeting Notes" \
     --notes "Removes the legacy watchdog and timer installer, keeps the native Omarchy service as the sole detector, and adds the marketplace preview."
   ```

6. Edit the existing marketplace issue #788 to trigger validation against the
   new `main` commit. Do not create a duplicate issue.
7. Confirm the new validation comment detects `preview.png`, reports v0.3.2,
   and references the expected commit.
8. Update the locally installed plugin only after the release is published:

   ```bash
   omarchy plugin update acp.omameet
   ```

9. Verify the installed manifest and helper both report v0.3.2, then exercise
   panel open/close, calendar refresh, iCalendar setup, and a manual recording
   start/stop.

## Product principles

- If OmaMeet does not add clear value to Omarchy, do not ship it.
- Keep Google Cloud optional; iCalendar must remain the low-friction path.
- Calendar time alone must never start a recording.
- Avoid noisy health notifications. Surface actionable failures in context.
- Preserve private calendar URLs, recordings, transcripts, and notes.
- Prefer the native Omarchy plugin lifecycle over separate background timers.
- Do not over-engineer, but do not cut release-quality corners.
