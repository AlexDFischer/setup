#!/usr/bin/python3
"""Repeatable changes to the invoking user's files; never run as root."""
import argparse
import errno
import os
from pathlib import Path
import shutil


def backup(path):
    saved = path.with_name(path.name + '.before-system-setup')
    if path.exists() and not saved.exists():
        shutil.copy2(path, saved)


def write_file(path, text):
    # Preserve dotfile-manager symlinks instead of replacing them with plain files.
    if path.is_symlink():
        path = path.resolve(strict=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    temporary = path.with_name(path.name + '.system-setup.tmp')
    temporary.write_text(text)
    if path.exists():
        shutil.copymode(path, temporary)
    temporary.replace(path)


def folders(home, config_home):
    names = {'Desktop': 'desktop', 'Downloads': 'downloads',
             'Documents': 'documents', 'Pictures': 'pictures'}
    # Check every destination before moving anything. Never merge implicitly.
    for old, new in names.items():
        source, target = home / old, home / new
        if source.exists() and target.exists():
            raise RuntimeError(f'Both {source} and {target} exist; merge them manually before retrying')
        if (source.exists() and not source.is_dir()) or (target.exists() and not target.is_dir()):
            raise RuntimeError(f'Expected directories for {source} and {target}')
    for old, new in names.items():
        source, target = home / old, home / new
        if source.exists():
            source.rename(target)
        else:
            target.mkdir(exist_ok=True)
    for name in ('Videos', 'Templates', 'Public', 'Music'):
        path = home / name
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError as error:
                if error.errno not in (errno.ENOTEMPTY, errno.EEXIST):
                    raise
                print(f'Keeping nonempty directory: {path}')
    values = {'DESKTOP': 'desktop', 'DOWNLOAD': 'downloads',
              'DOCUMENTS': 'documents', 'PICTURES': 'pictures',
              'VIDEOS': '', 'TEMPLATES': '', 'PUBLICSHARE': '', 'MUSIC': ''}
    path = config_home / 'user-dirs.dirs'
    lines = path.read_text().splitlines() if path.exists() else []
    keys = {f'XDG_{name}_DIR' for name in values}
    lines = [line for line in lines if line.partition('=')[0].strip() not in keys]
    lines += [f'XDG_{name}_DIR="$HOME/{directory}"' for name, directory in values.items()]
    write_file(path, '\n'.join(lines) + '\n')


def managed_bash_block(home, name, block):
    path = home / '.bashrc'
    text = path.read_text() if path.exists() else ''
    start, end = f'# >>> system-setup {name} >>>', f'# <<< system-setup {name} <<<'
    if start in text or end in text:
        if text.count(start) != 1 or text.count(end) != 1 or text.index(start) > text.index(end):
            raise RuntimeError(f'Malformed system-setup {name} block in .bashrc')
        a, b = text.index(start), text.index(end) + len(end)
        text = text[:a] + text[b:].lstrip('\n')
    write_file(path, text.rstrip('\n') + '\n\n' + start + '\n' + block + end + '\n')


def shell_path(home):
    managed_bash_block(home, 'PATH', """case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
""")


def base_env(home):
    managed_bash_block(home, 'uv base', """# Activate only in interactive shells that do not already have an environment.
if [[ $- == *i* && -z ${VIRTUAL_ENV:-} && -z ${CONDA_PREFIX:-} && -f "$HOME/.venvs/base/bin/activate" ]]; then
    source "$HOME/.venvs/base/bin/activate"
fi
""")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['folders', 'shell-path', 'base-env'])
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Run as the desktop user, without sudo')
    home = Path.home()
    if args.action == 'folders':
        folders(home, Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config'))))
    elif args.action == 'shell-path':
        shell_path(home)
    else:
        base_env(home)


if __name__ == '__main__':
    main()
