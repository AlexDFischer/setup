#!/usr/bin/python3
"""Repeatable changes to the invoking user's files; never run as root."""
import argparse
import errno
import os
from pathlib import Path
import shutil
import urllib.parse
import xml.etree.ElementTree as ET

RENAMED_FOLDERS = {'Desktop': 'desktop', 'Downloads': 'downloads',
                   'Documents': 'documents', 'Pictures': 'pictures'}
REMOVED_FOLDERS = ('Videos', 'Templates', 'Public', 'Music')
XBEL_NAMESPACES = {
    'bookmark': 'http://www.freedesktop.org/standards/desktop-bookmarks',
    'kdepriv': 'http://www.kde.org/kdepriv',
    'mime': 'http://www.freedesktop.org/standards/shared-mime-info',
}


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
    names = RENAMED_FOLDERS
    # Check every destination before moving anything. When both spellings exist,
    # merge the capitalized one into the lowercase one, but never overwrite a file.
    for old, new in names.items():
        source, target = home / old, home / new
        if (source.exists() and not source.is_dir()) or (target.exists() and not target.is_dir()):
            raise RuntimeError(f'Expected directories for {source} and {target}')
        if source.exists() and target.exists():
            clashes = [child.name for child in source.iterdir() if (target / child.name).exists()]
            if clashes:
                raise RuntimeError(f'Cannot merge {source} into {target}; resolve these names first: {", ".join(clashes)}')
    for old, new in names.items():
        source, target = home / old, home / new
        if source.exists() and target.exists():
            for child in source.iterdir():
                child.rename(target / child.name)
            source.rmdir()
        elif source.exists():
            source.rename(target)
        else:
            target.mkdir(exist_ok=True)
    for name in REMOVED_FOLDERS:
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


def places(home, data_home):
    """Point KDE's Places sidebar at the lowercase folders and hide removed ones.

    KDE keeps these in user-places.xbel; system entries such as Home and Trash
    are left as they are. Removed folders are hidden rather than deleted because
    KDE recreates missing system entries.
    """
    path = data_home / 'user-places.xbel'
    if not path.exists():
        print(f'Skipping KDE Places: {path} does not exist yet; rerun after the first KDE login')
        return
    for prefix, uri in XBEL_NAMESPACES.items():
        ET.register_namespace(prefix, uri)
    root = ET.fromstring(path.read_bytes())
    for bookmark in root.iter('bookmark'):
        parsed = urllib.parse.urlsplit(bookmark.get('href', ''))
        if parsed.scheme != 'file':
            continue
        target = Path(urllib.parse.unquote(parsed.path))
        if target.parent != home:
            continue
        lowered = RENAMED_FOLDERS.get(target.name, target.name)
        if lowered in RENAMED_FOLDERS.values():
            bookmark.set('href', (home / lowered).as_uri())
            bookmark.find('title').text = lowered
        elif target.name in REMOVED_FOLDERS:
            info = bookmark.find('info')
            if info is None:
                info = ET.SubElement(bookmark, 'info')
            metadata = next((m for m in info.findall('metadata') if m.get('owner') == 'http://www.kde.org'), None)
            if metadata is None:
                metadata = ET.SubElement(info, 'metadata', owner='http://www.kde.org')
            hidden = metadata.find('IsHidden')
            if hidden is None:
                hidden = ET.SubElement(metadata, 'IsHidden')
            hidden.text = 'true'
    src_href = (home / 'src').as_uri()
    if not any(b.get('href') == src_href for b in root.iter('bookmark')):
        bookmark = ET.Element('bookmark', href=src_href)
        ET.SubElement(bookmark, 'title').text = 'src'
        info = ET.SubElement(bookmark, 'info')
        freedesktop = ET.SubElement(info, 'metadata', owner='http://freedesktop.org')
        ET.SubElement(freedesktop, '{%s}icon' % XBEL_NAMESPACES['bookmark'], name='folder-development')
        kde = ET.SubElement(info, 'metadata', owner='http://www.kde.org')
        ET.SubElement(kde, 'ID').text = 'system-setup/src'
        children = list(root)
        after = [i for i, b in enumerate(children) if b.get('href') == (home / 'pictures').as_uri()]
        root.insert(after[0] + 1 if after else len(children), bookmark)
    text = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xbel>\n'
            + ET.tostring(root, encoding='unicode') + '\n')
    if text != path.read_text():
        write_file(path, text)


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
    parser.add_argument('action', choices=['folders', 'places', 'shell-path', 'base-env'])
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error('Run as the desktop user, without sudo')
    home = Path.home()
    if args.action == 'folders':
        folders(home, Path(os.environ.get('XDG_CONFIG_HOME', str(home / '.config'))))
    elif args.action == 'places':
        places(home, Path(os.environ.get('XDG_DATA_HOME', str(home / '.local/share'))))
    elif args.action == 'shell-path':
        shell_path(home)
    else:
        base_env(home)


if __name__ == '__main__':
    main()
