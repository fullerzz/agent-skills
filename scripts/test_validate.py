# Retain the stdlib unittest runner used by the repository.

import json
import tempfile
import unittest
from pathlib import Path

from validate import frontmatter, load_yaml, validate


class ValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write(".claude-plugin/plugin.json", json.dumps({"name": "zstack", "version": "0.1.0", "agents": []}))
        self.write(
            ".claude-plugin/marketplace.json",
            json.dumps({"name": "zstack-local", "plugins": [{"name": "zstack", "source": "./"}]}),
        )
        for relative in (
            "skills/z-mode/scripts/check_plan.py",
            "skills/z-mode/scripts/worktree-audit.sh",
            "skills/z-mode/scripts/worktree_audit.py",
            "skills/z-mode/scripts/watch-pr/watch_pr.py",
            "skills/z-mode/scripts/orch/orch.py",
            "skills/show-me-your-work/scripts/log.sh",
        ):
            self.write(relative, "").chmod(0o755)

    def write(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_valid_repository_and_yaml_12_boolean_policy(self) -> None:
        self.write(
            "skills/on/SKILL.md",
            "---\nname: on\ndescription: |\n"
            "  A multiline description.\ndisable-model-invocation: true\n---\n[resource](file%20name.txt)\n",
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
        self.write(
            ".claude-plugin/plugin.json",
            json.dumps({"name": "zstack", "version": "0.1.0", "agents": ["./agents/claude/reviewer.md"]}),
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

    def test_reports_structural_failures_and_ignores_fenced_links(self) -> None:
        self.write(
            "skills/example/SKILL.md",
            "---\nname: example\ndescription: Example\nextra: true\ndisable-model-invocation: yes\n"
            "---\n[missing](absent.txt)\n```md\n[example](not-real.txt)\n```\n/loop\ntrailing \n",
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

    def test_rejects_legacy_and_renamed_model_markers_in_active_markdown(self) -> None:
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

    def test_bad_metadata_missing_entrypoints_and_helpers_are_failures(self) -> None:
        file = self.write("skills/example/SKILL.md", "---\nname: Example\ndescription: Example\n---\n")
        with self.assertRaisesRegex(ValueError, "Invalid identifier"):
            frontmatter(file)
        file.write_text("No frontmatter\n")
        (self.root / "skills/z-mode/scripts/check_plan.py").unlink()
        (self.root / "skills/show-me-your-work/scripts/log.sh").unlink()
        count, failures = validate(self.root)
        self.assertEqual(count, 0)
        self.assertIn("skills/example/SKILL.md: Missing YAML frontmatter", failures)
        self.assertIn("scripts/check_plan.py: Missing tool entrypoint", failures)
        self.assertTrue(any(failure.startswith("skills/show-me-your-work/scripts/log.sh:") for failure in failures))

    def test_codex_read_only_activation_preserves_claude_policy(self) -> None:
        for name in ("how", "why"):
            self.write(
                f"skills/{name}/SKILL.md",
                f"---\nname: {name}\ndescription: Explain code\ndisable-model-invocation: true\n---\n",
            )
            self.write(f"skills/{name}/agents/openai.yaml", "policy:\n  allow_implicit_invocation: true\n")
        self.assertEqual(validate(self.root), (2, []))
        self.write("skills/how/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        self.assertIn("skills/how/SKILL.md: Read-only Codex implicit policy missing", validate(self.root)[1])

    def test_generated_plugin_does_not_duplicate_source_skills(self) -> None:
        text = "---\nname: example\ndescription: Explain code\n---\n"
        self.write("skills/example/SKILL.md", text)
        self.write("skills/example/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        self.write("dist/zstack/skills/example/SKILL.md", text)
        self.assertEqual(validate(self.root), (1, []))

    def test_nested_dist_resources_are_validated(self) -> None:
        self.write("dist/generated.md", "[ignored](missing.md)\n")
        self.write("skills/example/dist/reference.md", "[broken](missing.md)\n")
        self.assertEqual(validate(self.root)[1], ["skills/example/dist/reference.md: Broken local link: missing.md"])

    def test_codex_policy_required_without_shared_invocation_marker(self) -> None:
        self.write("skills/setup-zstack/SKILL.md", "---\nname: setup-zstack\ndescription: Configure host\n---\n")
        for text in (None, "{}", "policy: []", "policy: {}", "policy:\n  allow_implicit_invocation: true\n"):
            with self.subTest(policy=text):
                if text is not None:
                    self.write("skills/setup-zstack/agents/openai.yaml", text)
                self.assertIn(
                    "skills/setup-zstack/SKILL.md: Explicit-only Codex policy missing", validate(self.root)[1]
                )
        self.write("skills/setup-zstack/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        self.assertEqual(validate(self.root), (1, []))

    def test_only_read_only_skills_opt_into_codex_implicit_invocation(self) -> None:
        skills = Path(__file__).resolve().parent.parent / "skills"
        implicit = set()
        for skill in skills.iterdir():
            if not (skill / "SKILL.md").is_file():
                continue
            policy_file = skill / "agents/openai.yaml"
            policy = load_yaml(policy_file.read_text()) if policy_file.is_file() else None
            policy = policy.get("policy") if isinstance(policy, dict) else None
            if not isinstance(policy, dict) or policy.get("allow_implicit_invocation") is not False:
                implicit.add(skill.name)
        self.assertEqual(implicit, {"how", "why"})
        for name in implicit:
            self.assertIs(frontmatter(skills / name / "SKILL.md")["disable-model-invocation"], True)

    def test_xray_session_requires_explicit_invocation_on_both_hosts(self) -> None:
        relative = "skills/xray-session/SKILL.md"
        header = "---\nname: xray-session\ndescription: Inspect current session\n"
        self.write(relative, header + "disable-model-invocation: true\n---\n")
        self.write("skills/xray-session/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        self.assertEqual(validate(self.root), (1, []))
        for marker in ("", "disable-model-invocation: false\n", "disable-model-invocation: 'true'\n"):
            with self.subTest(shared_marker=marker):
                self.write(relative, header + marker + "---\n")
                self.assertIn(
                    f"{relative}: Xray session requires explicit-only shared invocation",
                    validate(self.root)[1],
                )
        self.write(relative, header + "disable-model-invocation: true\n---\n")
        for policy in (
            None,
            "{}",
            "policy:\n  allow_implicit_invocation: true\n",
            "policy:\n  allow_implicit_invocation: 'false'\n",
        ):
            with self.subTest(codex_policy=policy):
                policy_file = self.root / "skills/xray-session/agents/openai.yaml"
                if policy is None:
                    policy_file.unlink()
                else:
                    self.write("skills/xray-session/agents/openai.yaml", policy)
                self.assertIn(f"{relative}: Explicit-only Codex policy missing", validate(self.root)[1])

    def test_native_plugin_requires_packaged_hook_and_license(self) -> None:
        manifest = {
            "skills": "./skills/",
            "name": "zstack",
            "version": "0.1.0",
            "hooks": "./hooks/codex.json",
        }
        self.write(".codex-plugin/plugin.json", json.dumps(manifest))
        self.assertIn(".codex-plugin/plugin.json: Missing bundled hook configuration", validate(self.root)[1])
        self.write("hooks/codex.json", '{"hooks": {}}')
        self.write("LICENSE", "MIT")
        self.assertEqual(validate(self.root), (0, []))
        for version in ("1.0.0", "0.1", "v0.1.0"):
            with self.subTest(version=version):
                self.write(".codex-plugin/plugin.json", json.dumps({**manifest, "version": version}))
                self.assertIn(".codex-plugin/plugin.json: Invalid native plugin identity", validate(self.root)[1])
        manifest["hooks"] = "../outside.json"
        self.write(".codex-plugin/plugin.json", json.dumps(manifest))
        self.assertIn(".codex-plugin/plugin.json: Missing bundled hook configuration", validate(self.root)[1])

    def test_claude_plugin_lists_every_agent_and_matches_codex_version(self) -> None:
        self.write("agents/claude/reviewer.md", "---\nname: reviewer\ndescription: Review code\nmodel: inherit\n---\n")
        agents = ["./agents/claude/reviewer.md"]
        manifest = {"name": "zstack", "version": "0.1.0", "agents": agents}
        self.write(".claude-plugin/plugin.json", json.dumps(manifest))
        self.assertEqual(validate(self.root), (0, []))
        self.write("agents/claude/worker.md", "---\nname: worker\ndescription: Do work\nmodel: inherit\n---\n")
        self.assertIn(".claude-plugin/plugin.json: Agents must list every agents/claude file", validate(self.root)[1])
        agents.append("./agents/claude/worker.md")
        self.write(".claude-plugin/plugin.json", json.dumps(manifest))
        self.write(".codex-plugin/plugin.json", json.dumps({"name": "zstack", "version": "0.2.0"}))
        self.assertIn(".claude-plugin/plugin.json: Invalid native plugin identity", validate(self.root)[1])

    def test_claude_marketplace_exposes_documented_install_id(self) -> None:
        marketplace = {"name": "zstack-local", "plugins": [{"name": "zstack", "source": "./"}]}
        self.write(".claude-plugin/marketplace.json", json.dumps(marketplace))
        self.assertEqual(validate(self.root), (0, []))
        for broken in (
            {**marketplace, "name": "renamed"},
            {**marketplace, "plugins": [{"name": "zstack", "source": "./dist/zstack"}]},
            {"name": "zstack-local"},
        ):
            with self.subTest(marketplace=broken):
                self.write(".claude-plugin/marketplace.json", json.dumps(broken))
                self.assertTrue(validate(self.root)[1][0].startswith(".claude-plugin/marketplace.json: "))

    def test_claude_plugin_requires_manifest_and_marketplace(self) -> None:
        paths = (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json")
        for missing in ((paths[0],), (paths[1],), paths):
            with self.subTest(missing=missing):
                saved = {path: (self.root / path).read_text() for path in missing}
                for path in missing:
                    (self.root / path).unlink()
                failures = validate(self.root)[1]
                for path, content in saved.items():
                    self.write(path, content)
                self.assertEqual(failures, [f"{path}: Missing required Claude plugin file" for path in missing])


if __name__ == "__main__":
    unittest.main()
