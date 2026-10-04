# Retain the stdlib unittest runner used by the repository.

import json
import tempfile
import unittest
from pathlib import Path

from bump_version import MANIFESTS, bump, read_version


class BumpVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def write(self, codex: str, claude: str, hermes: str | None = None) -> None:
        for name, version in zip(MANIFESTS, (codex, claude, hermes or codex), strict=True):
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            if file.suffix == ".yaml":
                file.write_text(f"name: zstack\nversion: {version}\nlicense: MIT\n")
            else:
                file.write_text(f'{{\n  "name": "zstack",\n  "version": "{version}",\n  "agents": ["./a.md"]\n}}\n')

    def versions(self) -> list[object]:
        return [read_version(self.root / name) for name in MANIFESTS]

    def test_bumps_all_manifests_and_keeps_layout(self) -> None:
        self.write("0.1.9", "0.1.9")
        self.assertEqual(bump(self.root, "patch"), "0.1.10")
        self.assertEqual(self.versions(), ["0.1.10"] * 3)
        self.assertEqual(bump(self.root, "minor"), "0.2.0")
        self.assertEqual(self.versions(), ["0.2.0"] * 3)
        self.assertIn('  "agents": ["./a.md"]\n', (self.root / MANIFESTS[1]).read_text())
        self.assertEqual((self.root / "plugin.yaml").read_text(), "name: zstack\nversion: 0.2.0\nlicense: MIT\n")

    def test_rejects_hermes_drift_without_writing(self) -> None:
        self.write("0.1.0", "0.1.0", "0.2.0")
        with self.assertRaisesRegex(ValueError, "versions differ"):
            bump(self.root, "minor")
        self.assertEqual(self.versions(), ["0.1.0", "0.1.0", "0.2.0"])

    def test_missing_yaml_version_field_does_not_partially_bump(self) -> None:
        self.write("0.1.0", "0.1.0")
        (self.root / "plugin.yaml").write_text(json.dumps({"version": "0.1.0"}))
        with self.assertRaisesRegex(ValueError, "No version field"):
            bump(self.root, "patch")
        self.assertEqual(self.versions(), ["0.1.0"] * 3)

    def test_rejects_drift_non_v0_and_unknown_part_without_writing(self) -> None:
        for codex, claude, part in (
            ("0.1.0", "0.2.0", "patch"),
            ("1.0.0", "1.0.0", "patch"),
            ("0.1.0", "0.1.0", "major"),
        ):
            with self.subTest(codex=codex, claude=claude, part=part):
                self.write(codex, claude)
                with self.assertRaises(ValueError):
                    bump(self.root, part)
                self.assertEqual(self.versions(), [codex, claude, codex])


if __name__ == "__main__":
    unittest.main()
