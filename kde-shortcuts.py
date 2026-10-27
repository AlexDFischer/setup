#!/usr/bin/python3
"""Apply portable KWin and Dolphin shortcuts as the desktop user in a KDE session.

KDE persists these in ~/.config/kglobalshortcutsrc, [kwin] and
[services][org.kde.dolphin.desktop]. Use the live
KGlobalAccel API rather than editing a file the running daemon may overwrite.
"""
# PORTABILITY: KDE Plasma/KWin + KGlobalAccel v2 D-Bus API and PyQt6.
import os
from pathlib import Path
import shutil
import sys

import dbus
from PyQt6.QtGui import QKeySequence

# Clear the default actions that otherwise compete with these combinations.
# Directional screen moves use monitor geometry, rather than monitor numbering.
BINDINGS = {
    "Window Quick Tile Top": None,
    "Window Quick Tile Bottom": None,
    "Window to Next Screen": None,
    "Window to Previous Screen": None,
    "Window Maximize": "Meta+Up",
    "Window Minimize": "Meta+Down",
    "Window One Screen to the Left": "Meta+Shift+Left",
    "Window One Screen to the Right": "Meta+Shift+Right",
    "Window One Screen Up": "Meta+Shift+Up",
    "Window One Screen Down": "Meta+Shift+Down",
    "Window Quick Tile Left": "Meta+Left",
    "Window Quick Tile Right": "Meta+Right",
}


def keys(shortcut):
    """Serialize Qt key sequences using KGlobalAccel's a(ai) D-Bus type."""
    sequences = []
    if shortcut:
        sequence = QKeySequence(shortcut)
        combinations = dbus.Array(
            [sequence[i].toCombined() for i in range(sequence.count())], signature="i"
        )
        sequences.append(dbus.Struct((combinations,), signature="ai"))
    return dbus.Array(sequences, signature="(ai)")


def apply_shortcuts(accel, config_home):
    # Preflight all action IDs before changing anything; KWin must be running.
    actions = accel.allActionsForComponent(dbus.Array(["kwin", "", "", ""], signature="s"))
    actions = {str(action[1]): action for action in actions}
    missing = set(BINDINGS) - actions.keys()
    if missing:
        raise RuntimeError("KWin actions unavailable: " + ", ".join(sorted(missing)))
    dolphin_actions = accel.allActionsForComponent(
        dbus.Array(["org.kde.dolphin.desktop", "", "", ""], signature="s")
    )
    launch = next((action for action in dolphin_actions if str(action[1]) == "_launch"), None)
    if launch is None:
        raise RuntimeError("Dolphin launch shortcut unavailable; install Dolphin and retry after KDE login")
    actions["Open Dolphin"] = launch
    requested_bindings = {**BINDINGS, "Open Dolphin": "Ctrl+Alt+F"}
    config = config_home / "kglobalshortcutsrc"
    backup = config_home / "kglobalshortcutsrc.before-system-setup"
    if config.exists() and not backup.exists():
        shutil.copy2(config, backup)
    previous = {action: accel.shortcutKeys(actions[action]) for action in requested_bindings}
    changed = []
    try:
        for action, shortcut in requested_bindings.items():
            requested = keys(shortcut)
            changed.append(action)
            accel.setForeignShortcutKeys(actions[action], requested)
            if accel.shortcutKeys(actions[action]) != requested:
                raise RuntimeError(f"Could not assign {shortcut or 'none'} to {action}; check for shortcut conflicts")
    except Exception:
        # Avoid leaving the user with half of the requested bindings installed.
        for action in reversed(changed):
            try:
                accel.setForeignShortcutKeys(actions[action], previous[action])
            except dbus.DBusException as error:
                print(f"Could not restore {action}: {error}", file=sys.stderr)
        raise


def main():
    if os.geteuid() == 0:
        raise RuntimeError("Run this helper as the desktop user, without sudo")
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    bus = dbus.SessionBus()
    accel = dbus.Interface(
        bus.get_object("org.kde.kglobalaccel", "/kglobalaccel"), "org.kde.KGlobalAccel"
    )
    apply_shortcuts(accel, config_home)
    (config_home / "autostart/setup-kde-shortcuts.desktop").unlink(missing_ok=True)
    print("KDE window shortcuts and Ctrl+Alt+F for Dolphin configured.")


if __name__ == "__main__":
    try:
        main()
    except (dbus.DBusException, RuntimeError, OSError) as error:
        print(f"KDE shortcut setup: {error}", file=sys.stderr)
        sys.exit(1)
