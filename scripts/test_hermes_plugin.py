"""Exercise the directory entrypoint against Hermes' documented registration boundary."""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent


def load_plugin(entrypoint: Path) -> ModuleType:
    name = "zstack_hermes_fixture_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(name, entrypoint)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Hermes plugin fixture")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for loaded in list(sys.modules):
            if loaded == name or loaded.startswith(name + "."):
                del sys.modules[loaded]
    return module


class Registry:
    """Only declarative skill/hook registration is available at plugin load."""

    def __init__(self) -> None:
        self.skills: dict[str, Path] = {}
        self.hooks: dict[str, Callable[..., object]] = {}

    def register_hook(self, name: str, callback: Callable[..., object]) -> None:
        if name in self.hooks:
            raise ValueError(f"Duplicate hook: {name}")
        self.hooks[name] = callback

    def register_skill(self, name: str, path: Path) -> None:
        if name in self.skills or ":" in name or not path.is_file():
            raise ValueError(f"Invalid or duplicate skill: {name}")
        self.skills[name] = path


class HermesPluginTests(unittest.TestCase):
    def test_registers_every_shared_skill_with_resources_from_another_cwd(self) -> None:
        registry = Registry()
        with tempfile.TemporaryDirectory(prefix="zstack hermes ") as scratch:
            package = Path(scratch).resolve() / "plugin with spaces"
            package.mkdir()
            shutil.copy2(ROOT / "__init__.py", package)
            shutil.copytree(ROOT / "hooks", package / "hooks", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(ROOT / "skills", package / "skills", ignore=shutil.ignore_patterns("__pycache__"))
            other = Path(scratch).resolve() / "target repo"
            other.mkdir()
            previous = Path.cwd()
            try:
                os.chdir(other)
                load_plugin(package / "__init__.py").register(registry)
                self.assertEqual(Path.cwd(), other)
            finally:
                os.chdir(previous)
            expected = sorted(path.name for path in (ROOT / "skills").iterdir() if (path / "SKILL.md").is_file())
            self.assertEqual(list(registry.skills), expected)
            self.assertIn("xray-session", registry.skills)
            self.assertIn("pre_llm_call", registry.hooks)
            self.assertIn("on_session_reset", registry.hooks)
            mode = registry.skills["z-mode"].parent
            self.assertTrue((mode / "references/native-hosts.md").is_file())
            self.assertTrue((mode / "playbooks/feature.md").is_file())
            self.assertTrue((mode / "scripts/check_plan.py").is_file())
            self.assertEqual((mode / "../how/SKILL.md").resolve(), registry.skills["how"])

    def test_symlinked_entrypoint_and_non_skill_entries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zstack hermes ") as scratch:
            package = Path(scratch).resolve() / "source"
            package.mkdir()
            shutil.copy2(ROOT / "__init__.py", package)
            shutil.copytree(ROOT / "hooks", package / "hooks", ignore=shutil.ignore_patterns("__pycache__"))
            skills = package / "skills"
            (skills / "valid").mkdir(parents=True)
            (skills / "valid/SKILL.md").write_text("shared instructions", encoding="utf-8")
            (skills / "empty").mkdir()
            (skills / "directory/SKILL.md").mkdir(parents=True)
            (skills / "README.md").write_text("not a skill", encoding="utf-8")
            link = Path(scratch) / "installed"
            link.symlink_to(package, target_is_directory=True)
            registry = Registry()
            load_plugin(link / "__init__.py").register(registry)
            self.assertEqual(registry.skills, {"valid": package / "skills/valid/SKILL.md"})

    def test_missing_shared_tree_fails_registration(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            entrypoint = Path(scratch) / "__init__.py"
            shutil.copy2(ROOT / "__init__.py", entrypoint)
            shutil.copytree(ROOT / "hooks", Path(scratch) / "hooks", ignore=shutil.ignore_patterns("__pycache__"))
            with self.assertRaises(FileNotFoundError):
                load_plugin(entrypoint).register(Registry())


if __name__ == "__main__":
    unittest.main()
