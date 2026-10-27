# Workstation setup

For a running **Debian 13 (trixie), amd64 KDE system**. Review the selected
components before installing. Run from your own desktop account through sudo;
the script resolves your home from the account database, not root's environment.

```bash
bash setup.sh --personal --dry-run
sudo bash setup.sh --personal
sudo bash setup.sh --work
sudo bash setup.sh --personal --only=folders,date-locale,panel,shortcuts
sudo bash setup.sh --work --without-latex --yes
```

Work defaults exclude Signal, QGIS, Wine, Therion/Survex, and personal Git identity.
Spotify stays enabled. Signal and QGIS cannot be enabled in work mode. Other
`--with-NAME` and `--without-NAME` flags override defaults, regardless of their
position. `--only=NAME,NAME` starts with just those components; overrides still
apply. See `--help` for the component list. Disabling a component skips its setup;
it does not uninstall software, undo configuration, or delete existing Git settings.

System packages, repositories, keyd, zram, and systemd services run as root.
Personal installers, Git settings, folders, Python, and KDE settings run as the
sudo caller. Each component installs its runtime prerequisites even if `base`
is disabled. Common bootstrap tools are always installed. Package installation
is interactive unless `--yes` is supplied; uv/pip installation and the Anaconda
batch installer run without package confirmation prompts.

The script stops on failure. Rerun the same command after resolving the error.
System config files and edited user files receive a `.before-system-setup`
backup on their first change. Repeated package installation may update packages;
versions are not universally locked. Existing Anaconda is reused. Anaconda and
Prince download versions are pinned in `setup.sh`; update them deliberately.
Existing unsupported or broken third-party apt repositories can prevent the
initial `apt-get update` and must be repaired first.

## Python and terminals

Scientific packages (NumPy, SciPy, Matplotlib, pandas, ipympl, gdsfactory) use
**uv's `~/.venvs/base`**, with Python 3.12 when creating a new environment.
The system Python and conda base are not modified by pip. The `python-packages`
component requires `uv` to be enabled, or already installed at `~/.local/bin/uv`.
The managed `.bashrc` block activates the environment in new interactive Bash
terminals unless another virtualenv or conda environment is active. Existing
unrelated `.bashrc` content is preserved. No interactive startup file is sourced
by the root installer.

```bash
source ~/.venvs/base/bin/activate  # use immediately in the current terminal
uv pip list --python ~/.venvs/base/bin/python
deactivate
```

uv-created environments need not contain pip. Anaconda remains a separate optional component at `~/anaconda3`.
When scientific Python is configured, automatic activation of conda base is
disabled so it does not compete with uv. Explicit `conda activate NAME` remains
available after opening a new terminal.

## Desktop and folders

Folder setup renames Desktop, Documents, Downloads, and Pictures to lowercase.
It refuses ambiguous source/destination collisions before moving any directories.
Videos, Templates, Public, and Music are removed only when empty; populated
folders remain intact. Their XDG entries point at the home directory to prevent
recreation. Unknown user-directory entries and comments are preserved.

Panel setup replaces the bottom task manager's pins with Dolphin, Konsole,
QGIS (personal and enabled), Firefox, VSCode (enabled), and Spotify (enabled).
Firefox is assumed to come with the KDE installation; Firefox ESR and Firefox
launcher names are supported. No Zed pin is added. A panel config backup is saved.
If no suitable bottom panel exists, the helper reports that and retains its
startup entry; it does not create a panel or change its layout.

KDE window shortcuts are Win+Up to maximize, Win+Down to minimize,
Win+Shift+arrows to move to a monitor in that direction, and Win+Left/Right to
tile. Ctrl+Alt+F opens Dolphin. Competing default window bindings are cleared.
Calculator and activity-switching bindings are not migrated; other shortcuts
remain unchanged.
A failed assignment attempts to restore the previous bindings. This component
migrates the requested window bindings and Dolphin launcher, not every
application shortcut.

Panel and shortcut helpers apply to a running KDE session when available;
otherwise a one-time autostart entry applies them at login and removes itself
only after success. The date locale is English (Canada), which this system's Qt
and glibc both format as `yyyy-mm-dd`. Other regional formats are preserved;
log out and back in for the date locale to apply.

The keyd config intentionally swaps Caps Lock/left Control and maps global
Shift+Space to underscore. zram uses lz4, 50% of RAM on demand, and swap priority
100. Debian's supplied systemd-oomd policy is retained. New zram settings take
effect on reboot if the service is already active; setup does not swap off a
busy device.

## Checks

These checks do not install software or alter live desktop settings:

```bash
bash -n setup.sh setup-user.sh kde-panel.sh
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m unittest discover -s tests
```

Shortcut tests require Debian's `python3-dbus` and `python3-pyqt6`. Tests use
temporary homes and mocked desktop/installer services; a full fresh-system
installation is not exercised by them.

## Porting to another distribution or release

Search the scripts and `qgis.sources` for `PORTABILITY` comments before adapting
this to Ubuntu or a later Debian release. The OS/architecture guard deliberately
rejects those hosts. The comments identify repository suite and vendor URL pins,
Debian-specific package names, amd64-only downloads, the Debian 13 Prince build,
systemd/zram implementation choices, Bash startup configuration, and Plasma 6
APIs/tools. Changing the OS guard alone is insufficient.
