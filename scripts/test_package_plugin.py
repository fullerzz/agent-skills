# Retain the stdlib unittest runner used by the repository.

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from package_plugin import git_output, package


def track(root: Path) -> None:
    for arguments in (("init", "-q"), ("config", "core.excludesFile", "/dev/null"), ("add", "--all")):
        git_output(root, *arguments)


class PackagePluginTests(unittest.TestCase):
    def test_codex_agents_are_bundled_with_working_tree_contents(self) -> None:
        source = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (".codex-plugin/plugin.json", "LICENSE", "hooks/codex.json", "skills/z-mode/SKILL.md"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, target)
            shutil.copytree(source / "agents", root / "agents")
            track(root)
            agent = root / "agents/codex/z-agent.toml"
            agent.write_text(agent.read_text() + "\n# working tree modification\n")
            (root / "agents/codex/personal.toml").write_text("private")
            staged = package(root)
            for agent in (root / "agents/codex").glob("*.toml"):
                if agent.name != "personal.toml":
                    self.assertEqual((staged / agent.relative_to(root)).read_bytes(), agent.read_bytes())
            self.assertFalse((staged / "agents/codex/personal.toml").exists())

    def test_ketchup_bundles_visual_guidance_attribution_and_policy(self) -> None:
        source = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (".codex-plugin/plugin.json", "LICENSE", "hooks/codex.json"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source / name, target)
            shutil.copytree(source / "skills/ketchup", root / "skills/ketchup")
            shutil.copytree(source / "agents", root / "agents")
            track(root)
            staged = package(root)
            for name in (
                "SKILL.md",
                "agents/openai.yaml",
                "references/decision-visuals.md",
                "references/HUMANLAYER-LICENSE.txt",
            ):
                with self.subTest(resource=name):
                    self.assertEqual(
                        (staged / "skills/ketchup" / name).read_bytes(),
                        (source / "skills/ketchup" / name).read_bytes(),
                    )
            self.assertEqual((staged / "LICENSE").read_bytes(), (source / "LICENSE").read_bytes())

    def test_resources_dependencies_and_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (
                ".codex-plugin/plugin.json",
                "LICENSE",
                "agents/codex/z-agent.toml",
                "skills/z-mode/SKILL.md",
                "skills/z-mode/scripts/tool.ts",
                "skills/z-mode/scripts/package.json",
                "hooks/hooks.json",
                "hooks/session_start.py",
                "skills/z-mode/scripts/node_modules/dependency.js",
                "skills/z-mode/__pycache__/module.pyc",
                "skills/z-mode/nested/.git/config",
                "skills/z-mode/debug.log",
                "skills/z-mode/module.pyc",
            ):
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(name)
            (root / "skills/z-mode/tool-link.ts").symlink_to("scripts/tool.ts")
            track(root)
            (root / "skills/z-mode/.env").write_text("SECRET=personal")
            (root / ".git/info/exclude").write_text("hooks/ignored-personal.json\n")
            (root / "hooks/ignored-personal.json").write_text("private")
            (root / "hooks/credentials.json").write_text('{"token":"personal"}')
            (root / "hooks/session_start.py").write_text("working tree modification")
            staged = package(root)
            self.assertEqual((staged / "skills/z-mode/tool-link.ts").read_text(), "skills/z-mode/scripts/tool.ts")
            self.assertTrue((staged / "skills/z-mode/scripts/package.json").exists())
            self.assertTrue((staged / "hooks/session_start.py").exists())
            self.assertFalse((staged / ".git").exists())
            for name in ("nested/.git", "debug.log", "module.pyc", ".env"):
                self.assertFalse((staged / "skills/z-mode" / name).exists())
            self.assertFalse((staged / "hooks/credentials.json").exists())
            self.assertFalse((staged / "hooks/ignored-personal.json").exists())
            self.assertEqual((staged / "hooks/session_start.py").read_text(), "working tree modification")
            self.assertFalse((staged / "skills/z-mode/scripts/node_modules").exists())
            self.assertFalse((staged / "skills/z-mode/__pycache__").exists())
            (staged / "stale").write_text("old")
            package(root)
            self.assertFalse((staged / "stale").exists())

    def test_refuses_symlinked_destination_and_external_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (".codex-plugin/plugin.json", "LICENSE"):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(name)
            (root / "skills").mkdir()
            (root / "hooks").mkdir()
            (root / "hooks/hooks.json").write_text("{}")
            (root / "agents").mkdir()
            (root / "agents/z-agent.toml").write_text("agent")
            (root / "outside").write_text("preserve")
            (root / "skills/escape").symlink_to("../outside")
            track(root)
            with self.assertRaisesRegex(ValueError, "omitted or indirect resource: skills/escape"):
                package(root)
            (root / "skills/escape").unlink()
            (root / "dist").symlink_to(root / "skills")
            with self.assertRaisesRegex(ValueError, "symlinked dist/zstack"):
                package(root)
            self.assertEqual((root / "outside").read_text(), "preserve")

    def test_wrong_types_omitted_symlink_route_and_no_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                package(root)
            for name in (
                ".codex-plugin/plugin.json",
                "LICENSE",
                "skills/tool.txt",
                "hooks/hooks.json",
                "agents/z-agent.toml",
            ):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            track(root)
            staged = package(root)
            (staged / "sentinel").write_text("preserve")
            (root / "hooks").rename(root / "saved-hooks")
            (root / "hooks").write_text("wrong type")
            with self.assertRaises(ValueError):
                package(root)
            self.assertEqual((staged / "sentinel").read_text(), "preserve")
            (root / "hooks").unlink()
            (root / "saved-hooks").rename(root / "hooks")
            (root / "LICENSE").unlink()
            (root / "LICENSE").mkdir()
            with self.assertRaises(ValueError):
                package(root)
            (root / "LICENSE").rmdir()
            (root / "LICENSE").write_text("MIT")
            (root / "skills/link").symlink_to("debug.log")
            (root / "skills/debug.log").symlink_to("tool.txt")
            track(root)
            with self.assertRaises(ValueError):
                package(root)

    def test_lexical_routes_parent_symlinks_and_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in (
                ".codex-plugin/plugin.json",
                "LICENSE",
                "skills/sub/tool.txt",
                "hooks/hooks.json",
                "agents/z-agent.toml",
            ):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(name)
            (root / "scratch").mkdir()
            (root / "skills/link").symlink_to("../scratch/../skills/sub/tool.txt")
            track(root)
            with self.assertRaisesRegex(ValueError, "omitted or indirect resource: skills/link"):
                package(root)
            (root / "skills/link").unlink()
            git_output(root, "rm", "--cached", "--", "skills/link")
            (root / "skills/sub").rename(root / "scratch/sub")
            (root / "skills/sub").symlink_to("../scratch/sub")
            with self.assertRaisesRegex(ValueError, "symlinked parent: skills/sub/tool.txt"):
                package(root)
            with self.assertRaisesRegex(ValueError, "Git repository root"):
                package(root / "scratch")


if __name__ == "__main__":
    unittest.main()
