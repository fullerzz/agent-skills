# Retain the stdlib unittest runner used by the repository.

import json
import tempfile
import unittest
from pathlib import Path

from bump_version import MANIFESTS, bump


class BumpVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def write(self, codex: str, claude: str) -> None:
        for name, version in zip(MANIFESTS, (codex, claude), strict=True):
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(f'{{\n  "name": "zstack",\n  "version": "{version}",\n  "agents": ["./a.md"]\n}}\n')

    def versions(self) -> list[str]:
        return [json.loads((self.root / name).read_text())["version"] for name in MANIFESTS]

    def test_bumps_both_manifests_and_keeps_layout(self) -> None:
        self.write("0.1.9", "0.1.9")
        self.assertEqual(bump(self.root, "patch"), "0.1.10")
        self.assertEqual(self.versions(), ["0.1.10", "0.1.10"])
        self.assertEqual(bump(self.root, "minor"), "0.2.0")
        self.assertEqual(self.versions(), ["0.2.0", "0.2.0"])
        self.assertIn('  "agents": ["./a.md"]\n', (self.root / MANIFESTS[1]).read_text())

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
                self.assertEqual(self.versions(), [codex, claude])


if __name__ == "__main__":
    unittest.main()
