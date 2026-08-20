import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / "install.sh"
UNINSTALLER = ROOT / "uninstall.sh"
COMMANDS = ("omascribe-calendar", "omascribe-meetings")


class InstallerSafetyTests(unittest.TestCase):
    def run_script(self, script, home):
        fake_bin = Path(home) / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        omarchy = fake_bin / "omarchy"
        omarchy.write_text("#!/usr/bin/env bash\nexit 0\n")
        omarchy.chmod(0o755)
        env = dict(
            os.environ,
            HOME=str(home),
            XDG_CONFIG_HOME=str(Path(home) / ".config"),
            XDG_STATE_HOME=str(Path(home) / ".local/state"),
            PATH=str(fake_bin) + os.pathsep + os.environ.get("PATH", ""),
        )
        return subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True)

    def test_installer_rejects_conflict_before_creating_any_link(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            command_dir = home / ".local/bin"
            command_dir.mkdir(parents=True)
            conflict = command_dir / "omascribe-meetings"
            conflict.write_text("belongs to another program\n")

            result = self.run_script(INSTALLER, home)

            self.assertNotEqual(0, result.returncode)
            self.assertIn("Refusing to replace existing command path", result.stderr)
            self.assertEqual("belongs to another program\n", conflict.read_text())
            self.assertFalse((command_dir / "omascribe-calendar").exists())

    def test_installer_preserves_links_owned_by_same_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            command_dir = home / ".local/bin"
            command_dir.mkdir(parents=True)
            for command in COMMANDS:
                (command_dir / command).symlink_to(ROOT / "bin" / command)

            result = self.run_script(INSTALLER, home)

            self.assertEqual(0, result.returncode, result.stderr)
            for command in COMMANDS:
                self.assertEqual(ROOT / "bin" / command, (command_dir / command).resolve())

    def test_installer_creates_both_links_on_clean_first_install(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)

            result = self.run_script(INSTALLER, home)

            self.assertEqual(0, result.returncode, result.stderr)
            for command in COMMANDS:
                link = home / ".local/bin" / command
                self.assertTrue(link.is_symlink())
                self.assertEqual(ROOT / "bin" / command, link.resolve())

    def test_installer_migrates_legacy_data_without_deleting_source(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            legacy_config = home / ".config/omarchy-meetings"
            legacy_state = home / ".local/state/omarchy-calendar"
            legacy_config.mkdir(parents=True)
            legacy_state.mkdir(parents=True)
            (legacy_config / "config.json").write_text('{"llm":{"backend":"disabled"}}\n')
            (legacy_state / "accounts.json").write_text('{"accounts":[]}\n')

            result = self.run_script(INSTALLER, home)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((home / ".config/omascribe/config.json").is_file())
            self.assertTrue((home / ".local/state/omascribe-calendar/accounts.json").is_file())
            self.assertTrue((legacy_config / "config.json").is_file())
            self.assertTrue((legacy_state / "accounts.json").is_file())
            self.assertEqual(0o600, (home / ".config/omascribe/config.json").stat().st_mode & 0o777)

    def test_installer_conflict_does_not_migrate_legacy_data(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            legacy = home / ".config/omarchy-meetings"
            legacy.mkdir(parents=True)
            (legacy / "config.json").write_text("{}\n")
            command_dir = home / ".local/bin"
            command_dir.mkdir(parents=True)
            (command_dir / "omascribe-meetings").write_text("foreign\n")

            result = self.run_script(INSTALLER, home)

            self.assertNotEqual(0, result.returncode)
            self.assertFalse((home / ".config/omascribe").exists())

    def test_installer_rejects_foreign_symlink_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            command_dir = home / ".local/bin"
            command_dir.mkdir(parents=True)
            foreign_target = home / "foreign-command"
            foreign_target.write_text("another program\n")
            conflict = command_dir / "omascribe-calendar"
            conflict.symlink_to(foreign_target)

            result = self.run_script(INSTALLER, home)

            self.assertNotEqual(0, result.returncode)
            self.assertTrue(conflict.is_symlink())
            self.assertEqual(foreign_target, conflict.resolve())
            self.assertFalse((command_dir / "omascribe-meetings").exists())

    def test_uninstaller_removes_only_links_owned_by_same_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            command_dir = home / ".local/bin"
            command_dir.mkdir(parents=True)
            (command_dir / "omascribe-calendar").symlink_to(ROOT / "bin/omascribe-calendar")
            foreign = command_dir / "omascribe-meetings"
            foreign.write_text("keep me\n")

            result = self.run_script(UNINSTALLER, home)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((command_dir / "omascribe-calendar").exists())
            self.assertEqual("keep me\n", foreign.read_text())


if __name__ == "__main__":
    unittest.main()
