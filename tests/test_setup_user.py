"""Privilege-boundary tests; no account changes or installations."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'setup-user.sh'


class SetupUserTests(unittest.TestCase):
    def shell(self, script, *args, env=None):
        return subprocess.run(['bash', '-c', 'source "$1"; shift; ' + script,
                               'test', str(HELPER), *args], env=env,
                              text=True, capture_output=True)

    def test_rejects_root_and_missing_sudo_user(self):
        for user in ('', 'root', 'nonexistent-setup-test-user'):
            p = self.shell('init_setup_user', env=dict(os.environ, SUDO_USER=user))
            self.assertNotEqual(p.returncode, 0)

    def test_resolves_passwd_home_not_inherited_home(self):
        script = '''
getent() { printf '%s\\n' 'desktop:x:1234:1234:Desktop:/tmp:/bin/bash'; }
id() { printf '%s\\n' desktop; }
init_setup_user || exit
printf '%s|%s|%s' "$setup_user" "$setup_home" "$setup_uid"
'''
        p = self.shell(script, env=dict(os.environ, SUDO_USER='desktop', HOME='/root'))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout, 'desktop|/tmp|1234')

    def test_user_runner_environment_cwd_and_argument_quoting(self):
        with tempfile.TemporaryDirectory(prefix='setup user ') as home:
            script = '''
setup_user=desktop; setup_home=$1; setup_uid=1234
# Mock only privilege switching; execute the real env and shell wrapper.
runuser() {
    [[ "$1" == -u && "$2" == desktop && "$3" == -- ]] || return 99
    shift 3
    "$@"
}
as_user /usr/bin/python3 -c 'import os,sys,json; print(json.dumps([os.getcwd(),dict(os.environ),sys.argv[1:]]))' 'space value' '$(false)'
'''
            p = self.shell(script, home, env=dict(os.environ, HOME='/root',
                            XDG_CONFIG_HOME='/root/.config', PYTHONPATH='/root/python',
                            CONDA_PREFIX='/root/conda', BASH_ENV='/nonexistent'))
            self.assertEqual(p.returncode, 0, p.stderr)
            cwd, env, args = json.loads(p.stdout)
            self.assertEqual(cwd, home)
            self.assertEqual(env['HOME'], home)
            self.assertEqual(env['XDG_CONFIG_HOME'], home + '/.config')
            self.assertNotIn('PYTHONPATH', env)
            self.assertNotIn('CONDA_PREFIX', env)
            self.assertNotIn('BASH_ENV', env)
            self.assertEqual(args, ['space value', '$(false)'])
