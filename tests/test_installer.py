import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / "install.sh"
UNINSTALLER = ROOT / "uninstall.sh"
COMMANDS = ("omameet-calendar", "omameet-meetings")


class InstallerSafetyTests(unittest.TestCase):
    def run_script(self, script, home):
        fake_bin = Path(home) / "fake-bin"
        fake_bin.mkdir(exist_ok=True)
        omarchy = fake_bin / "omarchy"
        omarchy.write_text("#!/usr/bin/env bash\nexit 0\n")
        omarchy.chmod(0o755)
        env = dict(os.environ, HOME=str(home), PATH=str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
        return subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True)

    def test_installer_rejects_conflict_before_creating_any_link(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            command_dir = home / ".local/bin"
            command_dir.mkdir(parents=True)
            conflict = command_dir / "omameet-meetings"
            conflict.write_text("belongs to another program\n")

            result = self.run_script(INSTALLER, home)

            self.assertNotEqual(0, result.returncode)
            self.assertIn("Refusing to replace existing command path", result.stderr)
            self.assertEqual("belongs to another program\n", conflict.read_text())
            self.assertFalse((command_dir / "omameet-calendar").exists())

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

    def test_installer_rejects_foreign_symlink_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            command_dir = home / ".local/bin"
            command_dir.mkdir(parents=True)
            foreign_target = home / "foreign-command"
            foreign_target.write_text("another program\n")
            conflict = command_dir / "omameet-calendar"
            conflict.symlink_to(foreign_target)

            result = self.run_script(INSTALLER, home)

            self.assertNotEqual(0, result.returncode)
            self.assertTrue(conflict.is_symlink())
            self.assertEqual(foreign_target, conflict.resolve())
            self.assertFalse((command_dir / "omameet-meetings").exists())

    def test_uninstaller_removes_only_links_owned_by_same_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            command_dir = home / ".local/bin"
            command_dir.mkdir(parents=True)
            (command_dir / "omameet-calendar").symlink_to(ROOT / "bin/omameet-calendar")
            foreign = command_dir / "omameet-meetings"
            foreign.write_text("keep me\n")

            result = self.run_script(UNINSTALLER, home)

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((command_dir / "omameet-calendar").exists())
            self.assertEqual("keep me\n", foreign.read_text())


if __name__ == "__main__":
    unittest.main()
