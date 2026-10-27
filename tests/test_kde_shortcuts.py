"""Run with /usr/bin/python3 -m unittest discover -s tests."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("shortcuts", Path(__file__).resolve().parents[1] / "kde-shortcuts.py")
shortcuts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shortcuts)


class FakeAccel:
    def __init__(self):
        self.values = {}
        self.missing = None
        self.conflict = None
        self.calls = []

    def allActionsForComponent(self, component):
        if component[0] == "org.kde.dolphin.desktop":
            return [] if self.missing == "Dolphin" else [[component[0], "_launch", "Dolphin", "Open Dolphin"]]
        return [["kwin", action, "KWin", action] for action in shortcuts.BINDINGS if action != self.missing]

    def setForeignShortcutKeys(self, action, keys):
        self.calls.append(action[1])
        self.values[action[1]] = [] if action[1] == self.conflict and keys == shortcuts.keys('Meta+Down') else keys

    def shortcutKeys(self, action):
        return self.values.get(action[1], [])


class ShortcutTests(unittest.TestCase):
    def test_keys_and_conflicting_defaults(self):
        accel = FakeAccel()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            config = home / "kglobalshortcutsrc"
            config.write_text("original shortcuts")
            shortcuts.apply_shortcuts(accel, home)
            shortcuts.apply_shortcuts(accel, home)
            self.assertEqual(config.read_text(), "original shortcuts")
            self.assertEqual((home / "kglobalshortcutsrc.before-system-setup").read_text(), "original shortcuts")
        self.assertEqual(accel.values["_launch"], shortcuts.keys("Ctrl+Alt+F"))
        self.assertNotIn("next activity", accel.values)
        self.assertNotIn("previous activity", accel.values)
        self.assertEqual(int(accel.values["Window Minimize"][0][0][0]), 0x10000000 | 0x01000015)
        self.assertEqual(int(accel.values["Window One Screen to the Left"][0][0][0]), 0x10000000 | 0x02000000 | 0x01000012)
        for action in ["Window Quick Tile Top", "Window Quick Tile Bottom", "Window to Next Screen", "Window to Previous Screen"]:
            self.assertEqual(accel.values[action], [])
        self.assertLess(accel.calls.index("Window Quick Tile Top"), accel.calls.index("Window Maximize"))

    def test_missing_actions_prevent_changes(self):
        accel = FakeAccel()
        accel.missing = "Window Minimize"
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(RuntimeError, "unavailable"):
            shortcuts.apply_shortcuts(accel, Path(tmp))
        self.assertEqual(accel.calls, [])

    def test_missing_dolphin_prevents_partial_changes(self):
        accel = FakeAccel()
        accel.missing = "Dolphin"
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(RuntimeError, "Dolphin"):
            shortcuts.apply_shortcuts(accel, Path(tmp))
        self.assertEqual(accel.calls, [])

    def test_conflict_is_reported(self):
        accel = FakeAccel()
        accel.conflict = "Window Minimize"
        accel.values['Window Maximize'] = shortcuts.keys('Meta+F10')
        accel.values['Window Minimize'] = shortcuts.keys('Meta+PgDown')
        previous = dict(accel.values)
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(RuntimeError, "conflicts"):
            shortcuts.apply_shortcuts(accel, Path(tmp))
        for action, keys in previous.items():
            self.assertEqual(accel.values[action], keys)


if __name__ == "__main__":
    unittest.main()
