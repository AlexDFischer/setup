import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'setup.sh'
PANEL = SCRIPT.with_name('kde-panel.sh')


class ScriptTests(unittest.TestCase):
    def run_setup(self, *args):
        return subprocess.run(['bash', str(SCRIPT), *args], text=True, capture_output=True)

    def test_profiles_and_optional_pins(self):
        for profile in ('--personal', '--work'):
            result = self.run_setup(profile, '--dry-run')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('  spotify\n', result.stdout)
            self.assertEqual('  -> QGIS\n' in result.stdout, profile == '--personal')
            result = self.run_setup(profile, '--without-qgis', '--without-vscode', '--without-spotify', '--dry-run')
            self.assertNotIn('  -> QGIS', result.stdout)
            self.assertNotIn('  -> VSCode', result.stdout)
            self.assertNotIn('  -> Spotify', result.stdout)
        result = self.run_setup('--work', '--only=folders,shell-path', '--dry-run')
        self.assertEqual(result.stdout, 'Profile: work\n  folders\n  shell-path\n')

    def test_invalid_flags_and_forbidden_work_apps(self):
        for args in [(), ('--personal', '--work'), ('--work', '--with-qgis'), ('--work', '--only=signal'), ('--work', '--with-unknown')]:
            self.assertNotEqual(self.run_setup(*args, '--dry-run').returncode, 0)

    def test_failed_download_does_not_run_installer_or_later_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'executed'
            # Real shell failure semantics; no network or install commands run.
            code = '''source "$1"
curl() { printf 'touch "%s"\\n' "$2"; return 22; }
download example "$2/installer"
bash "$2/installer"
touch "$2/executed"
'''
            result = subprocess.run(['bash', '-c', code, 'test', str(SCRIPT), tmp], capture_output=True)
            self.assertEqual(result.returncode, 22)
            self.assertFalse(marker.exists())

    def test_failed_key_does_not_write_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'target'
            code = '''source "$1"
work_directory=$2
download() { echo invalid > "$2"; }
gpg() { return 2; }
install_key example "$2/target"
touch "$2/later"
'''
            result = subprocess.run(['bash', '-c', code, 'test', str(SCRIPT), tmp], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target.exists())
            self.assertFalse((Path(tmp) / 'later').exists())

    def test_panel_receives_selected_apps_and_retries_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / 'qdbus6'
            fake.write_text('#!/bin/bash\nprintf "%s" "$4" > "$CAPTURE"\necho "${MOCK_RESULT:-setup-panel-ok}"\n')
            fake.chmod(0o755)
            startup = root / '.config/autostart/setup-kde-panel.desktop'
            startup.parent.mkdir(parents=True)
            env = dict(os.environ, HOME=tmp, XDG_CONFIG_HOME=str(root/'.config'), XDG_DATA_HOME=str(root/'.local/share'), PATH=f'{root}:/usr/bin:/bin', CAPTURE=str(root/'script'))
            for profile, selected in [('personal', True), ('work', False)]:
                startup.write_text('queued')
                subprocess.run(['bash', str(PANEL), profile, '1', '0', '1'], env=env, capture_output=True, check=True)
                js = (root / 'script').read_text()
                self.assertEqual('applications:org.qgis.qgis.desktop' in js, selected)
                self.assertNotIn('applications:code.desktop', js)
                self.assertIn('applications:spotify.desktop', js)
                self.assertNotIn('zed', js.lower())
                self.assertFalse(startup.exists())
            startup.write_text('queued')
            result = subprocess.run(['bash', str(PANEL), 'work'], env=dict(env, MOCK_RESULT='setup-panel-no-task-manager'), capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(startup.exists())

    def test_configs_keep_first_backup_and_replace_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'source').write_text('updated')
            (root / 'target').write_text('original')
            code = '\n'.join(['source "$1"', 'install_config "$2/source" "$2/target"', 'install_config "$2/source" "$2/target"'])
            subprocess.run(['bash', '-c', code, 'test', str(SCRIPT), tmp], check=True)
            self.assertEqual((root / 'target').read_text(), 'updated')
            self.assertEqual((root / 'target.before-system-setup').read_text(), 'original')

    def test_queued_desktop_entry_with_spaced_home(self):
        with tempfile.TemporaryDirectory(prefix='setup user ') as tmp:
            code = r'''source "$1"
script_directory=$(dirname "$1")
setup_home=$2; setup_uid=999999
as_user() { env HOME="$setup_home" XDG_CONFIG_HOME="$setup_home/.config" "$@"; }
queue_desktop_task panel kde-panel.sh work 0 1 1
'''
            subprocess.run(['bash', '-c', code, 'test', str(SCRIPT), tmp], check=True, capture_output=True)
            entry = Path(tmp) / '.config/autostart/setup-kde-panel.desktop'
            self.assertIn('"work" "0" "1" "1"', entry.read_text())
            subprocess.run(['desktop-file-validate', str(entry)], check=True)
