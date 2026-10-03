import tempfile
import unittest
from pathlib import Path

from package_plugin import package


class PackagePluginTests(unittest.TestCase):
    def test_resources_dependencies_and_rebuild(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (".codex-plugin/plugin.json", "LICENSE", "skills/z-mode/SKILL.md", "skills/z-mode/scripts/tool.ts", "skills/z-mode/scripts/package.json", "hooks/hooks.json", "hooks/session_start.py", "skills/z-mode/scripts/node_modules/dependency.js", "skills/z-mode/__pycache__/module.pyc", ".git/config"):
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(name)
            (root / "skills/z-mode/tool-link.ts").symlink_to("scripts/tool.ts")
            staged = package(root)
            self.assertEqual((staged / "skills/z-mode/tool-link.ts").read_text(), "skills/z-mode/scripts/tool.ts")
            self.assertTrue((staged / "skills/z-mode/scripts/package.json").exists())
            self.assertTrue((staged / "hooks/session_start.py").exists())
            self.assertFalse((staged / ".git").exists())
            self.assertFalse((staged / "skills/z-mode/scripts/node_modules").exists())
            self.assertFalse((staged / "skills/z-mode/__pycache__").exists())
            (staged / "stale").write_text("old")
            package(root)
            self.assertFalse((staged / "stale").exists())

    def test_refuses_symlinked_destination_and_external_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (".codex-plugin/plugin.json", "LICENSE"):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(name)
            (root / "skills").mkdir()
            (root / "hooks").mkdir()
            (root / "outside").write_text("preserve")
            (root / "skills/escape").symlink_to("../outside")
            with self.assertRaises(ValueError):
                package(root)
            (root / "skills/escape").unlink()
            (root / "dist").symlink_to(root / "skills")
            with self.assertRaises(ValueError):
                package(root)
            self.assertEqual((root / "outside").read_text(), "preserve")


if __name__ == "__main__":
    unittest.main()
