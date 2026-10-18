# Retain the stdlib unittest runner used by the repository.

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from validate import frontmatter, load_yaml, markdown_prose, validate, validate_catalog


class ValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("plugin.yaml", "name: zstack\nversion: 0.1.0\nlicense: MIT\n")
        self.write("__init__.py", "")
        self.write("LICENSE", "MIT")
        for resource in ("hooks/hermes.py", "hooks/session_start.py"):
            self.write(resource, "")
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

    def test_catalog_counts_follow_the_tree_and_deduplicate_native_roles(self) -> None:
        self.write("skills/example/SKILL.md", "")
        self.write("skills/principle-example/SKILL.md", "")
        self.write("skills/z-mode/playbooks/example.md", "")
        for host, suffix in (("codex", "toml"), ("claude", "md")):
            self.write(f"agents/{host}/reviewer.{suffix}", "")
            self.write(f"agents/{host}/worker.{suffix}", "")
        self.write("README.md", "2 skills, 1 engineering principles, 1 workflow playbooks, two native agent roles.\n")
        self.write("docs/index.md", "details: 2 skills, 1 engineering principles, and 1 workflow playbooks.\n")
        failures = []
        validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
        self.assertEqual(failures, [])
        self.write("README.md", "3 skills, 2 engineering principles, 2 workflow playbooks, 3 native agent roles.\n")
        validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
        self.assertEqual(len(failures), 4)
        self.assertTrue(all("Catalog says" in failure for failure in failures))
        self.write("docs/index.md", "details: 99 skills.\n")
        failures.clear()
        validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
        self.assertIn("docs/index.md: Catalog says 99 skills, but the tree has 2", failures)

    def test_catalog_checks_current_source_links_without_policing_examples_or_history(self) -> None:
        source = "https://github.com/fullerzz/agent-skills/blob/main/"
        self.write("skills/example/SKILL.md", "")
        self.write("docs/reference/workflow-skills.md", f"[source]({source}skills/example/SKILL.md#example)\n")
        self.write("README.md", f"```md\n99 skills\n[example]({source}absent.md)\n```\n")
        self.write("docs/guide/example.md", "Three workflow playbooks cover this subset.\n")
        self.write("docs/provenance.md", f"99 skills previously. [old]({source}retired.md)\n")
        self.write("docs/reference/other.md", "[external](https://github.com/other/repo/blob/main/absent.md)\n")
        failures = []
        validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
        self.assertEqual(failures, [])
        (self.root / "skills/example/SKILL.md").unlink()
        validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
        self.assertEqual(
            failures, ["docs/reference/workflow-skills.md: Broken current-source link: skills/example/SKILL.md"]
        )

    def test_source_links_parse_query_fragment_and_encoded_path(self) -> None:
        source = "https://github.com/fullerzz/agent-skills/blob/main/"
        self.write("skills/file name.md", "")
        self.write("README.md", f"[source]({source}skills/file%20name.md?plain=1#heading)\n")
        failures: list[str] = []
        validate_catalog(self.root, lambda file, message: failures.append(message))
        self.assertEqual(failures, [])

    def test_source_links_with_optional_titles_check_only_the_destination(self) -> None:
        source = "https://github.com/fullerzz/agent-skills/blob/main/"
        self.write("exists.md", "")
        failures: list[str] = []
        for title in (
            '"source"',
            "'source'",
            "(source)",
            r'"a \"quoted\" source"',
            r"'a \'quoted\' source'",
            r"(a \) source)",
        ):
            with self.subTest(title=title):
                self.write(
                    "README.md",
                    f"[valid]({source}exists.md?plain=1#heading {title})\n"
                    f"[missing]({source}absent.md?plain=1#heading {title})\n",
                )
                failures.clear()
                validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
                expected = ["README.md: Broken current-source link: absent.md"]
                self.assertEqual(failures, expected)
                self.assertEqual(validate(self.root), (0, expected))

    def test_angle_source_destinations_are_checked(self) -> None:
        source = "https://github.com/fullerzz/agent-skills/blob/main/"
        self.write("file (name).md", "")
        failures: list[str] = []
        for spacing, title in (("", ""), (" ", ' "source"'), ("\n", r' "a \"quoted\" source"')):
            with self.subTest(spacing=spacing, title=title):
                self.write(
                    "README.md",
                    f"[valid]({spacing}<{source}file%20(name).md?plain=1#heading>{title}{spacing})\n"
                    f"[missing]({spacing}<{source}absent(name).md?plain=1#heading>{title}{spacing})\n",
                )
                failures.clear()
                validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
                expected = ["README.md: Broken current-source link: absent(name).md"]
                self.assertEqual(failures, expected)
                self.assertEqual(validate(self.root), (0, expected))

    def test_angle_source_decoding_failure_keeps_later_links(self) -> None:
        source = "https://github.com/fullerzz/agent-skills/blob/main/"
        for path in ("%FF.md", "%00.md"):
            with self.subTest(path=path):
                self.write(
                    "README.md", f'[invalid](<{source}{path}?plain=1#heading> "source")\n[later](<{source}later.md>)\n'
                )
                expected = [
                    f"README.md: Broken current-source link: {path}",
                    "README.md: Broken current-source link: later.md",
                ]
                self.assertEqual(validate(self.root), (0, expected))

    def test_invalid_encoded_source_paths_fail_without_skipping_later_links(self) -> None:
        source = "https://github.com/fullerzz/agent-skills/blob/main/"
        self.write("\ufffd.md", "")
        failures: list[str] = []
        for path in ("%FF.md", "%00.md"):
            with self.subTest(path=path):
                self.write("README.md", f"[invalid]({source}{path})\n[later]({source}later.md)\n")
                failures.clear()
                validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
                expected = [
                    f"README.md: Broken current-source link: {path}",
                    "README.md: Broken current-source link: later.md",
                ]
                self.assertEqual(failures, expected)
                self.assertEqual(validate(self.root), (0, expected))

    def test_source_path_resolution_errors_do_not_skip_later_links(self) -> None:
        source = "https://github.com/fullerzz/agent-skills/blob/main/"
        self.write("README.md", f"[invalid]({source}invalid.md)\n[later]({source}later.md)\n")
        original_resolve = Path.resolve
        failures: list[str] = []
        for error in (OSError("resolution failed"), ValueError("invalid path")):
            with self.subTest(error=error):

                def resolve(path: Path, strict: bool = False, error: OSError | ValueError = error) -> Path:
                    if path.name == "invalid.md":
                        raise error
                    return original_resolve(path, strict=strict)

                with patch.object(Path, "resolve", resolve):
                    failures.clear()
                    validate_catalog(self.root, lambda file, message: failures.append(f"{file}: {message}"))
                    expected = [
                        "README.md: Broken current-source link: invalid.md",
                        "README.md: Broken current-source link: later.md",
                    ]
                    self.assertEqual(failures, expected)
                    self.assertEqual(validate(self.root), (0, expected))

    def test_source_links_reject_existing_targets_outside_checkout(self) -> None:
        source = "https://github.com/fullerzz/agent-skills/blob/main/"
        failures: list[str] = []
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "exists.md"
            external.write_text("external")
            (self.root / "escape.md").symlink_to(external)
            for path in (
                str(external),
                str(external).replace("/", "%2F"),
                f"../{Path(outside).name}/exists.md",
                "escape.md",
            ):
                with self.subTest(path=path):
                    self.write("README.md", f"[source]({source}{path})\n")
                    failures.clear()
                    validate_catalog(self.root, lambda file, message: failures.append(message))
                    self.assertEqual(len(failures), 1)
                    self.assertIn("Broken current-source link", failures[0])

    def test_fenced_examples_allow_tildes_and_require_matching_closers(self) -> None:
        for fence in ("```", "~~~~"):
            with self.subTest(fence=fence):
                other = "~~~" if fence[0] == "`" else "```"
                text = f"before\n{fence}md\n99 skills\n{other}\n99 skills\n{fence[:-1]}\n99 skills\n{fence}\nafter\n"
                self.assertEqual(markdown_prose(text), "before\nafter\n")
        self.write(
            "README.md",
            "~~~md\n99 skills\n[source](https://github.com/fullerzz/agent-skills/blob/main/absent.md)\n~~~\n",
        )
        failures: list[str] = []
        validate_catalog(self.root, lambda file, message: failures.append(message))
        self.assertEqual(failures, [])

    def test_catalog_checks_all_small_word_counts(self) -> None:
        failures: list[str] = []
        for number, word in enumerate(
            ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"], 1
        ):
            with self.subTest(word=word):
                self.write(f"skills/example-{number}/SKILL.md", "")
                for page in ("README.md", "docs/index.md"):
                    self.write(page, f"{word} skills\n")
                failures.clear()
                validate_catalog(self.root, lambda file, message: failures.append(message))
                self.assertEqual(failures, [])
                self.write("README.md", f"{word} native agent roles\n")
                self.write("docs/index.md", f"{word} native agent roles\n")
                validate_catalog(self.root, lambda file, message: failures.append(message))
                self.assertEqual(len(failures), 2)
                self.assertTrue(all(f"Catalog says {word} native agent roles" in failure for failure in failures))

    def test_skill_slug_metadata_rejects_nonportable_names_and_lengths(self) -> None:
        for name in ("Mixed-Case", "has space", "under_score", "-leading", "trailing-", "double--dash", "x" * 65):
            with self.subTest(name=name):
                file = self.write("skills/example/SKILL.md", f"---\nname: {name}\ndescription: Example\n---\n")
                with self.assertRaisesRegex(ValueError, "Invalid identifier"):
                    frontmatter(file)

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

    def test_codex_implicit_activation_preserves_claude_policy(self) -> None:
        for name in ("how", "why", "python-best-practices"):
            self.write(
                f"skills/{name}/SKILL.md",
                f"---\nname: {name}\ndescription: Explain code\ndisable-model-invocation: true\n---\n",
            )
            self.write(f"skills/{name}/agents/openai.yaml", "policy:\n  allow_implicit_invocation: true\n")
        self.assertEqual(validate(self.root), (3, []))
        self.write("skills/python-best-practices/agents/openai.yaml", "policy:\n  allow_implicit_invocation: false\n")
        self.assertIn("skills/python-best-practices/SKILL.md: Codex implicit policy missing", validate(self.root)[1])

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

    def test_only_selected_skills_opt_into_codex_implicit_invocation(self) -> None:
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
        self.assertEqual(implicit, {"how", "why", "python-best-practices"})
        for name in implicit | {"ketchup", "in-your-own-words"}:
            self.assertIs(frontmatter(skills / name / "SKILL.md")["disable-model-invocation"], True)

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
                self.assertEqual(
                    [failure for failure in failures if not failure.startswith("plugin.yaml:")],
                    [f"{path}: Missing required Claude plugin file" for path in missing],
                )

    def test_hermes_manifest_identity_version_and_resources(self) -> None:
        self.assertEqual(validate(self.root), (0, []))
        for manifest in (
            "name: other\nversion: 0.1.0\nlicense: MIT\n",
            "name: zstack\nversion: 0.2.0\nlicense: MIT\n",
            "name: zstack\nversion: 1\nlicense: MIT\n",
            "[]\n",
        ):
            with self.subTest(manifest=manifest):
                self.write("plugin.yaml", manifest)
                self.assertIn("plugin.yaml: Invalid native plugin identity or shared version", validate(self.root)[1])
        self.write("plugin.yaml", "name: zstack\nversion: 0.1.0\nlicense: MIT\n")
        (self.root / "__init__.py").unlink()
        self.assertIn("plugin.yaml: Missing Hermes plugin resource: __init__.py", validate(self.root)[1])
        (self.root / "plugin.yaml").unlink()
        self.assertTrue(any(failure.startswith("plugin.yaml:") for failure in validate(self.root)[1]))


if __name__ == "__main__":
    unittest.main()
