import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('setup_home', Path(__file__).resolve().parents[1] / 'setup-home.py')
home_setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(home_setup)


class HomeTests(unittest.TestCase):
    def test_folder_rerun_preserves_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / 'Documents').mkdir()
            (home / 'Documents/report').write_text('keep')
            (home / 'Music').mkdir()
            (home / 'Music/song').write_text('keep')
            (home / 'Videos').mkdir()
            config = home / '.config'
            config.mkdir()
            (config / 'user-dirs.dirs').write_text('# keep this comment\n')
            home_setup.folders(home, config)
            home_setup.folders(home, config)
            self.assertEqual((home / 'documents/report').read_text(), 'keep')
            self.assertEqual((home / 'Music/song').read_text(), 'keep')
            self.assertFalse((home / 'Videos').exists())
            self.assertTrue((home / 'pictures').is_dir())
            text = (config / 'user-dirs.dirs').read_text()
            self.assertIn('XDG_MUSIC_DIR="$HOME/"', text)
            self.assertIn('# keep this comment', text)

    def test_conflicts_fail_before_any_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            for name in ('Desktop', 'Documents', 'documents'):
                (home / name).mkdir()
            with self.assertRaisesRegex(RuntimeError, 'merge them manually'):
                home_setup.folders(home, home / '.config')
            self.assertTrue((home / 'Desktop').exists())
            self.assertFalse((home / 'desktop').exists())

    def test_shell_blocks_preserve_config_and_do_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            path = home / '.bashrc'
            path.write_text('export MY_SETTING=keep\n')
            for _ in range(2):
                home_setup.shell_path(home)
                home_setup.base_env(home)
            self.assertEqual(path.read_text().count('# >>> system-setup PATH >>>'), 1)
            self.assertEqual(path.read_text().count('# >>> system-setup uv base >>>'), 1)
            self.assertIn('export MY_SETTING=keep', path.read_text())
            self.assertEqual((home / '.bashrc.before-system-setup').read_text(), 'export MY_SETTING=keep\n')
            subprocess.run(['bash', '-n', str(path)], check=True)

    def test_autoactivation_only_when_appropriate(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            activate = home / '.venvs/base/bin/activate'
            activate.parent.mkdir(parents=True)
            activate.write_text('export VIRTUAL_ENV="$HOME/.venvs/base"\n')
            home_setup.base_env(home)
            for interactive, active_name in [(False, None), (True, None), (True, 'VIRTUAL_ENV'), (True, 'CONDA_PREFIX')]:
                env = {'HOME': tmp, 'PATH': '/usr/bin:/bin'}
                if active_name:
                    env[active_name] = '/already-active'
                command = ['bash', '--noprofile', '--norc']
                if interactive:
                    command.append('-i')
                command += ['-c', 'source "$HOME/.bashrc"; printf "%s" "${VIRTUAL_ENV:-}"']
                result = subprocess.run(command, env=env, text=True, capture_output=True, check=True)
                expected = '/already-active' if active_name == 'VIRTUAL_ENV' else (str(activate.parent.parent) if interactive and not active_name else '')
                self.assertEqual(result.stdout, expected)

    def test_shell_symlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            real = home / 'dotfiles-bashrc'
            real.write_text('export EXISTING=1\n')
            (home / '.bashrc').symlink_to(real)
            home_setup.shell_path(home)
            self.assertTrue((home / '.bashrc').is_symlink())
            self.assertIn('export EXISTING=1', real.read_text())
