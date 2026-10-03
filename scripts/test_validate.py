import tempfile
import json
import unittest
from pathlib import Path

from validate import frontmatter, load_yaml, validate


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for relative in (
            "skills/z-mode/scripts/check-plan.mjs",
            "skills/z-mode/scripts/worktree-audit.sh",
            "skills/z-mode/scripts/worktree-audit.mjs",
            "skills/z-mode/scripts/watch-pr/watch-pr",
            "skills/z-mode/scripts/orch/orch.ts",
            "skills/show-me-your-work/scripts/log.sh",
        ):
            self.write(relative, "").chmod(0o755)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_valid_repository_and_yaml_12_boolean_policy(self):
        self.write(
            "skills/on/SKILL.md",
            "---\nname: on\ndescription: |\n  A multiline description.\ndisable-model-invocation: true\n---\n[resource](file%20name.txt)\n",
        )
        self.write("skills/on/file name.txt", "resource")
        self.write(
            "skills/on/agents/openai.yaml",
            "policy:\n  allow_implicit_invocation: false\n",
        )
        self.write(
            "agents/codex/reviewer.toml",
            'name = "reviewer"\ndescription = "Review code"\ndeveloper_instructions = "Check changes"\n',
        )
        self.write(
            "agents/claude/reviewer.md",
            "---\nname: reviewer\ndescription: Review code\nmodel: inherit\n---\n",
        )
        self.assertEqual(validate(self.root), (1, []))
        self.write(
            "skills/on/agents/openai.yaml",
            "policy:\n  allow_implicit_invocation: off\n",
        )
        self.assertIn(
            "skills/on/SKILL.md: Explicit-only Codex policy missing",
            validate(self.root)[1],
        )

    def test_reports_structural_failures_and_ignores_fenced_links(self):
        self.write(
            "skills/example/SKILL.md",
            "---\nname: example\ndescription: Example\nextra: true\ndisable-model-invocation: yes\n---\n[missing](absent.txt)\n```md\n[example](not-real.txt)\n```\n/loop\ntrailing \n",
        )
        self.write(
            "skills/duplicate/SKILL.md",
            "---\nname: example\ndescription: Duplicate\n---\n",
        )
        self.write("broken.yaml", "a: [\n")
        self.write("agents/codex/bad.toml", 'name = "wrong"\n')
        self.write(".cursor-plugin/retired.txt", "")
        (self.root / "skills/show-me-your-work/scripts/log.sh").chmod(0o644)
        count, failures = validate(self.root)
        self.assertEqual(count, 1)
        for message in (
            "Unsupported shared metadata: extra",
            "Invocation flag must be boolean",
            "Broken local link: absent.txt",
            "Trailing whitespace",
            "Active unsupported host instruction",
            "Duplicate skill name",
            "Name must match directory",
            "Missing description",
            "Missing developer_instructions",
            "Agent name mismatch",
            "Helper not executable",
            "Retired content remains",
        ):
            self.assertTrue(any(message in failure for failure in failures), message)
        self.assertTrue(any(failure.startswith("broken.yaml:") for failure in failures))
        self.assertFalse(any("not-real.txt" in failure for failure in failures))

    def test_rejects_legacy_and_renamed_model_markers_in_active_markdown(self):
        for marker in ("pstack-models.mdc", "zstack-models.mdc"):
            for relative in (
                "skills/example/reference.md",
                "agents/claude/reviewer.md",
                "docs/guide/setup.md",
            ):
                with self.subTest(marker=marker, file=relative):
                    file = self.write(
                        relative,
                        "---\nname: reviewer\ndescription: Review code\nmodel: inherit\n---\n"
                        f"Use {marker} for model routing.\n",
                    )
                    self.assertIn(
                        f"{relative}: Active unsupported host instruction",
                        validate(self.root)[1],
                    )
                    file.unlink()

    def test_bad_metadata_missing_entrypoints_and_helpers_are_failures(self):
        file = self.write(
            "skills/example/SKILL.md", "---\nname: Example\ndescription: Example\n---\n"
        )
        with self.assertRaisesRegex(ValueError, "Invalid identifier"):
            frontmatter(file)
        file.write_text("No frontmatter\n")
        (self.root / "skills/z-mode/scripts/check-plan.mjs").unlink()
        (self.root / "skills/show-me-your-work/scripts/log.sh").unlink()
        count, failures = validate(self.root)
        self.assertEqual(count, 0)
        self.assertIn("skills/example/SKILL.md: Missing YAML frontmatter", failures)
        self.assertIn("scripts/check-plan.mjs: Missing tool entrypoint", failures)
        self.assertTrue(
            any(
                failure.startswith("skills/show-me-your-work/scripts/log.sh:")
                for failure in failures
            )
        )

    def test_codex_read_only_activation_preserves_claude_policy(self):
        for name in ("how", "why"):
            self.write(f"skills/{name}/SKILL.md", f"---\nname: {name}\ndescription: Explain code\ndisable-model-invocation: true\n---\n")
            self.write(f"skills/{name}/agents/openai.yaml", "policy:\n  allow_implicit_invocation: true\n")
        self.assertEqual(validate(self.root), (2, []))
        self.write("skills/how/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        self.assertIn("skills/how/SKILL.md: Read-only Codex implicit policy missing", validate(self.root)[1])

    def test_generated_plugin_does_not_duplicate_source_skills(self):
        text = "---\nname: example\ndescription: Explain code\n---\n"
        self.write("skills/example/SKILL.md", text)
        self.write("dist/zstack/skills/example/SKILL.md", text)
        self.assertEqual(validate(self.root), (1, []))

    def test_only_read_only_skills_opt_into_codex_implicit_invocation(self):
        skills = Path(__file__).resolve().parent.parent / "skills"
        implicit = set()
        for skill in skills.iterdir():
            policy_file = skill / "agents/openai.yaml"
            if policy_file.is_file():
                policy = load_yaml(policy_file.read_text())["policy"]
                if policy["allow_implicit_invocation"]:
                    implicit.add(skill.name)
        self.assertEqual(implicit, {"how", "why"})
        for name in implicit:
            self.assertIs(frontmatter(skills / name / "SKILL.md")["disable-model-invocation"], True)

    def test_native_plugin_requires_packaged_hook_and_license(self):
        manifest = {
            "skills": "./skills/",
            "name": "zstack", "version": "0.1.0",
            "hooks": "./hooks/hooks.json",
        }
        self.write(".codex-plugin/plugin.json", json.dumps(manifest))
        self.assertIn(".codex-plugin/plugin.json: Missing bundled hook configuration", validate(self.root)[1])
        self.write("hooks/hooks.json", '{"hooks": {}}')
        self.write("LICENSE", "MIT")
        self.assertEqual(validate(self.root), (0, []))
        manifest["hooks"] = "../outside.json"
        self.write(".codex-plugin/plugin.json", json.dumps(manifest))
        self.assertIn(".codex-plugin/plugin.json: Missing bundled hook configuration", validate(self.root)[1])


if __name__ == "__main__":
    unittest.main()
