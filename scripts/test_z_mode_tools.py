"""Behavior contracts for the uv helpers; fixtures never touch personal state."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "skills/z-mode/scripts"


def executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required test executable not found: {name}")
    return path


class EntrypointTests(unittest.TestCase):
    def test_uv_launchers_work_from_a_link_in_a_separate_cwd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="helper install ") as temp:
            root = Path(temp)
            target = root / "target repo"
            target.mkdir()
            installed = root / "installed scripts"
            shutil.copytree(TOOLS, installed, ignore=shutil.ignore_patterns("node_modules", "__pycache__"))
            link = root / "watch_pr.py"
            link.symlink_to(installed / "watch-pr/watch_pr.py")
            result = subprocess.run(  # noqa: S603 - Local CLI fixtures use explicit argument vectors, never a shell.
                [executable("uv"), "run", str(link), "--help"], cwd=target, capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage:", result.stdout)
            self.assertEqual(list(target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
