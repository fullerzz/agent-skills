# Retain the stdlib unittest runner used by the repository.

"""Exercise explicit Codex mode controls without personal configuration."""

import contextlib
import errno
import io
import json
import os
import re
import runpy
import shlex
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "hooks/session_start.py"
# Controls name the base interpreter even when the hook runs inside a virtual environment.
INTERPRETER = os.path.realpath(getattr(sys, "_base_executable", None) or sys.executable)


class CodexHooksTests(unittest.TestCase):
    def test_shared_renderer_matches_native_wrapper_without_side_effects(self) -> None:
        render = runpy.run_path(str(HELPER))["build_context"]
        for active in (False, True):
            if active:
                self.control("enable")
            for source in ("startup", "resume", "compact", "fork"):
                with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(io.StringIO()) as output:
                    context, error = render("codex", "session-a", str(self.data), source)
                self.assertEqual(output.getvalue(), "")
                self.assertIsNone(error)
                self.assertEqual(
                    context, json.loads(self.hook(source=source))["hookSpecificOutput"]["additionalContext"]
                )
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stdout(io.StringIO()) as output:
            context, error = render("hermes", "session-a", str(self.data), "resume")
        self.assertIn("--host=hermes", context)
        self.assertIn("was explicitly enabled", context)
        self.assertIsNone(error)
        self.assertEqual(output.getvalue(), "")
        with patch.dict(os.environ, self.env, clear=True):
            context, error = render("hermes", "session-a", str(self.data), "clear")
        self.assertIn("No stored", context)
        self.assertIsNone(error)
        self.assertFalse((self.data / "z-mode/session-a.json").exists())
        for host, session, directory, source in (
            ("unknown", "session", str(self.data), "startup"),
            ("hermes", "../escape", str(self.data), "startup"),
            ("hermes", "session", "relative", "startup"),
            ("hermes", "session", str(self.data), "unknown"),
        ):
            with self.assertRaises(ValueError):
                render(host, session, directory, source)

    def test_only_session_hooks_remain(self) -> None:
        for filename in ("codex.json", "hooks.json"):
            hooks = json.loads((ROOT / "hooks" / filename).read_text())["hooks"]
            self.assertEqual(set(hooks), {"SessionStart"})
            self.assertEqual(len(hooks["SessionStart"][0]["hooks"]), 1)

    def test_legacy_recording_setting_has_no_effect(self) -> None:
        baseline = self.hook()
        self.env["ZSTACK_XRAY"] = "1"
        self.assertEqual(self.hook(), baseline)
        self.control("enable")
        self.assertIn("was explicitly enabled", self.hook(source="resume"))
        self.assertEqual(list(self.data.iterdir()), [self.data / "z-mode"])
        self.control("disable")
        self.assertIn("No stored", self.hook(source="resume"))
        self.assertEqual(list(self.data.iterdir()), [self.data / "z-mode"])
        self.assertEqual(list((self.data / "z-mode").iterdir()), [])

    def test_shell_serialization_preserves_apostrophes_and_metacharacters(self) -> None:
        serialize = runpy.run_path(str(HELPER))["control_command"]
        arguments = ["uv", "C:\\Users\\O'Neil\\plugin $root `literal`\\session_start.py", "--data-dir", "C:\\O'Neil"]
        self.assertEqual(shlex.split(serialize(arguments, "posix")), arguments)
        powershell = serialize(arguments, "powershell")
        self.assertEqual(
            powershell,
            "& 'uv' 'C:\\Users\\O''Neil\\plugin $root `literal`\\session_start.py' '--data-dir' 'C:\\O''Neil'",
        )
        self.assertEqual(
            serialize(["uv", "C:\\\u2018O\u2019Neil"], "powershell"), "& 'uv' 'C:\\\u2018\u2018O\u2019\u2019Neil'"
        )

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="zstack hook ")
        self.addCleanup(self.directory.cleanup)
        self.data = Path(self.directory.name).resolve()
        inherited = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("CLAUDE_PLUGIN_") and key != "ZSTACK_XRAY"
        }
        self.env = dict(
            inherited,
            PLUGIN_ROOT=str(ROOT),
            PLUGIN_DATA=str(self.data),
            CODEX_HOME=str(self.data / "codex"),
            CLAUDE_CONFIG_DIR=str(self.data / "claude"),
            HOME=str(self.data),
        )

    def hook(self, session: str = "session-a", source: str = "startup", host: str = "codex") -> str:
        env = self.env | ({"CLAUDE_PLUGIN_DATA": str(self.data)} if host == "claude" else {})
        result = subprocess.run(  # noqa: S603 - Trusted fixture/manifest commands.
            [sys.executable, "-I", "-S", str(HELPER), f"--host={host}"],
            input=json.dumps(
                {
                    "hook_event_name": "SessionStart",
                    "source": source,
                    "session_id": session,
                }
            ),
            text=True,
            capture_output=True,
            check=True,
            env=env,
        )
        self.assertEqual(result.stderr, "")
        return result.stdout

    def control(self, action: str, session: str = "session-a", check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - Fixed interpreter and local helper.
            [
                sys.executable,
                "-I",
                "-S",
                str(HELPER),
                action,
                "--host=codex",
                f"--session-id={session}",
                "--data-dir",
                str(self.data),
            ],
            text=True,
            capture_output=True,
            check=check,
            env=self.env,
        )

    @staticmethod
    def command(context: str, action: str, shell: str = "POSIX sh") -> str:
        template = next(
            line.split(": ", 1)[1] for line in context.splitlines() if line.startswith(f"{shell} control: ")
        )
        head, _, tail = template.rpartition("ACTION")
        return head + action + tail

    def test_configured_command_and_emitted_controls(self) -> None:
        (self.data / "uv.toml").write_text("invalid TOML [")
        marker = self.data / "site-loaded"
        (self.data / "sitecustomize.py").write_text(f"open({str(marker)!r}, 'w').close()\n")
        self.env["PYTHONPATH"] = str(self.data)
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        group = json.loads((ROOT / manifest["hooks"]).read_text())["hooks"]["SessionStart"][0]
        self.env["CLAUDE_PLUGIN_ROOT"] = str(self.data / "unrelated-plugin")
        self.env["CLAUDE_PLUGIN_DATA"] = str(self.data / "unrelated-data")
        for source in ("startup", "resume", "compact", "clear", "fork"):
            self.assertIsNotNone(re.fullmatch(group["matcher"], source))
        result = subprocess.run(  # noqa: S602 - Trusted fixture/manifest commands.
            group["hooks"][0]["command"],
            shell=True,
            input=json.dumps({"hook_event_name": "SessionStart", "source": "startup", "session_id": "session-a"}),
            text=True,
            capture_output=True,
            check=True,
            cwd=self.data,
            env=self.env,
        )
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "SessionStart")
        context = output["additionalContext"]
        commands = {action: self.command(context, action.lower()) for action in ("Enable", "Disable")}
        for action in ("Enable", "Disable"):
            # Exercise shell quoting in commands emitted by our local trusted hook.
            subprocess.run(commands[action], shell=True, check=True, env=self.env, cwd=self.data)  # noqa: S602
            active = "was explicitly enabled" in self.hook()
            self.assertEqual(active, action == "Enable")
            self.assertFalse(marker.exists())

    def test_action_in_paths_is_preserved_by_final_argument_replacement(self) -> None:
        helper = self.data / "ACTION plugin" / "session_start.py"
        helper.parent.mkdir()
        helper.write_bytes(HELPER.read_bytes())
        data = self.data / "ACTION data"
        functions = runpy.run_path(str(helper))
        context, _ = functions["build_context"]("codex", "ACTION-session", str(data), "startup")
        self.assertIn("replace only the final argument ACTION", context)
        self.assertIn("leave all other arguments unchanged", context)
        for action, expected in (
            ("enable", (True, "native")),
            ("herdr", (True, "herdr")),
            ("native", (True, "native")),
            ("disable", (False, "native")),
        ):
            argv = shlex.split(self.command(context, action))
            self.assertIn(str(helper), argv)
            self.assertEqual(argv[-3:], ["--data-dir", str(data), action])
            self.assertEqual(
                self.command(context, action, "PowerShell"), functions["control_command"](argv, "powershell")
            )
            subprocess.run(  # noqa: S603 - Isolated copied helper and generated arguments.
                [sys.executable, *argv[argv.index("-I") :]], check=True, env=self.env
            )
            self.assertEqual(functions["read_state"](functions["state_path"](str(data), "ACTION-session")), expected)

    def test_configured_command_uses_claude_plugin_variables(self) -> None:
        plugin_root = self.data / "Claude's plugin $root `literal`"
        (plugin_root / "hooks").mkdir(parents=True)
        (plugin_root / "hooks/session_start.py").write_bytes(HELPER.read_bytes())
        env = {key: value for key, value in self.env.items() if key not in ("PLUGIN_ROOT", "PLUGIN_DATA")}
        env |= {
            "CLAUDE_PLUGIN_ROOT": str(plugin_root),
            "CLAUDE_PLUGIN_DATA": str(self.data),
            "PLUGIN_DATA": "unrelated-relative",
        }
        group = json.loads((ROOT / "hooks/hooks.json").read_text())["hooks"]["SessionStart"][0]
        for source in ("startup", "resume", "compact", "clear", "fork"):
            self.assertIsNotNone(re.fullmatch(group["matcher"], source))
        hook = group["hooks"][0]
        # Model Claude's documented exec-form placeholder substitution, without a shell.
        command = [hook["command"], *(arg.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root)) for arg in hook["args"])]
        for inherited_data in ("unrelated-relative", str(self.data / "unrelated-absolute")):
            env["PLUGIN_DATA"] = inherited_data
            result = subprocess.run(  # noqa: S603 - Trusted fixture/manifest commands.
                command,
                input=json.dumps({"hook_event_name": "SessionStart", "source": "startup", "session_id": "claude-a"}),
                text=True,
                capture_output=True,
                check=True,
                cwd=self.data,
                env=env,
            )
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            enable = self.command(context, "enable")
            self.assertEqual(shlex.split(enable)[-2:], [str(self.data), "enable"])
            self.assertIn(f"PowerShell control: & '{INTERPRETER}'", context)
            self.assertTrue(self.command(context, "disable", "PowerShell").endswith(" 'disable'"))
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        enable = self.command(context, "enable")
        self.assertIn(str((plugin_root / "hooks/session_start.py").resolve()), shlex.split(enable))
        subprocess.run(enable, shell=True, check=True, env=env, cwd=self.data)  # noqa: S602
        self.assertTrue((self.data / "z-mode/claude-a.json").is_file())

    def test_emitted_controls_accept_leading_hyphen_session_ids(self) -> None:
        for session in ("-session", "--session-id", "-"):
            with self.subTest(session=session):
                context = json.loads(self.hook(session=session))["hookSpecificOutput"]["additionalContext"]
                commands = {action: self.command(context, action.lower()) for action in ("Enable", "Disable")}
                for action in ("Enable", "Disable"):
                    subprocess.run(commands[action], shell=True, check=True, env=self.env, cwd=self.data)  # noqa: S602
                    self.assertEqual("was explicitly enabled" in self.hook(session=session), action == "Enable")

    def test_fork_controls_are_fresh_and_do_not_change_parent_state(self) -> None:
        self.control("enable", session="parent")
        context = json.loads(self.hook(session="child", source="fork"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("No stored", context)
        self.assertIn("supersede any controls inherited", context)
        self.assertIn("Parent activation does not activate a fork", context)
        commands = {action: self.command(context, action.lower()) for action in ("Enable", "Disable")}
        for action in ("Enable", "Disable"):
            self.assertIn("--session-id=child", commands[action])
            self.assertNotIn("parent", commands[action])
            subprocess.run(commands[action], shell=True, check=True, env=self.env, cwd=self.data)  # noqa: S602
            self.assertEqual(
                "was explicitly enabled" in self.hook(session="child", source="resume"), action == "Enable"
            )
            self.assertIn("was explicitly enabled", self.hook(session="parent", source="resume"))

    def test_disabled_default_session_isolation_and_clear(self) -> None:
        self.assertIn("No stored", self.hook())
        self.assertEqual(list(self.data.iterdir()), [])
        self.control("enable")
        for source in ("startup", "resume", "compact"):
            self.assertIn("was explicitly enabled", self.hook(source=source))
            self.assertIn("No stored", self.hook(session="session-b", source=source))
        self.assertIn("No stored", self.hook(source="clear"))
        self.assertIn("No stored", self.hook(source="resume"))
        self.control("disable")

    def test_execution_selection_is_independent_and_mode_stop_clears_both(self) -> None:
        state = self.data / "z-mode/session-a.json"
        marker = self.data / "z-mode/session-a.herdr"
        self.control("herdr")
        self.assertFalse(state.exists())
        self.assertTrue(marker.is_file())
        self.control("enable")
        self.assertEqual(json.loads(state.read_text()), {"active": True})
        for source in ("startup", "resume", "compact"):
            context = json.loads(self.hook(source=source))["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Herdr execution was explicitly enabled", context)
            self.assertIn("z-mode was explicitly enabled", context)
        self.control("native")
        self.assertEqual(json.loads(state.read_text()), {"active": True})
        self.assertFalse(marker.exists())
        self.control("herdr")
        self.control("disable")
        self.assertEqual(list(state.parent.iterdir()), [])
        context = json.loads(self.hook())["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("Herdr execution was explicitly enabled", context)
        self.control("herdr")
        self.control("native")
        self.assertEqual(list(state.parent.iterdir()), [])

    def test_herdr_routes_to_host_companion_without_inheriting_environment_activation(self) -> None:
        codex_skill = self.data / "codex/plugins/cache/market/herdr-zstack/0.1.0/skills/hc-workflow/SKILL.md"
        claude_root = self.data / "companion source"
        claude_skill = claude_root / "skills/hc-workflow/SKILL.md"
        for skill in (codex_skill, claude_skill):
            skill.parent.mkdir(parents=True)
            skill.write_text("Native hc companion fixture")
        registry = self.data / "claude/plugins/installed_plugins.json"
        registry.parent.mkdir(parents=True)
        registry.write_text(json.dumps({"plugins": {"herdr-zstack@local": [{"installPath": str(claude_root)}]}}))
        for host, skill in (("codex", codex_skill), ("claude", claude_skill)):
            for signals in ({"HC_TERMINAL_ID": "t16"}, {"HERDR_ENV": "1"}, {}):
                env = {key: value for key, value in self.env.items() if not key.startswith(("HC_", "HERDR_"))}
                with self.subTest(host=host, signals=signals), patch.dict(self.env, env | signals, clear=True):
                    context = json.loads(self.hook(session="fresh", host=host))["hookSpecificOutput"][
                        "additionalContext"
                    ]
                    self.assertIn("Herdr execution is not enabled", context)
                    self.control("herdr")
                    context = json.loads(self.hook(host=host))["hookSpecificOutput"]["additionalContext"]
                    self.assertIn(str(skill), context)
                    self.assertIn("herdr-zstack:hc-workflow", context)
                    self.assertIn("read-only preflight passes", context)
                    self.assertNotIn("skills/herdr-workflow/", context)
                    self.assertNotIn("--session-id=session-a", context.split("Read ")[-1])
                    self.control("native")

    def test_missing_or_ambiguous_companion_reports_gap_without_legacy_fallback(self) -> None:
        self.control("herdr")
        for versions in ((), ("0.1.0", "0.2.0")):
            for version in versions:
                skill = self.data / f"codex/plugins/cache/market/herdr-zstack/{version}/skills/hc-workflow/SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text("fixture")
            context = json.loads(self.hook())["hookSpecificOutput"]["additionalContext"]
            self.assertIn("Capability gap: herdr-zstack:hc-workflow is missing or ambiguous", context)
            self.assertIn("No legacy Herdr fallback", context)
            self.assertNotIn("skills/herdr-workflow/", context)
        self.assertTrue((self.data / "z-mode/session-a.herdr").is_file())

    def test_claude_directory_marketplace_resolves_live_source_and_invalid_registry_fails_closed(self) -> None:
        resolve = runpy.run_path(str(HELPER))["companion_skill"]
        base = self.data / "claude/plugins"
        base.mkdir(parents=True)
        source = self.data / "live source"
        skill = source / "skills/hc-workflow/SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("fixture")
        registry = base / "installed_plugins.json"
        registry.write_text(json.dumps({"plugins": {"herdr-zstack@local": [{"installPath": "/stale/cache"}]}}))
        (base / "known_marketplaces.json").write_text(
            json.dumps({"local": {"source": {"source": "directory", "path": str(source)}}})
        )
        with patch.dict(os.environ, self.env, clear=True):
            self.assertEqual(resolve("claude"), str(skill))
            self.assertIsNone(resolve("codex"))
            for value in ("invalid", "[]", '{"plugins":null}', '{"plugins":{"herdr-zstack@local":[null]}}'):
                registry.write_text(value)
                self.assertIsNone(resolve("claude"))

    def test_parallel_mode_and_execution_controls_both_persist(self) -> None:
        for _ in range(10):
            processes = [
                subprocess.Popen(  # noqa: S603 - Fixed interpreter and local helper.
                    [sys.executable, "-I", "-S", str(HELPER), action, "--session-id=race", "--data-dir", str(self.data)]
                )
                for action in ("enable", "herdr")
            ]
            self.assertEqual([process.wait() for process in processes], [0, 0])
            context = json.loads(self.hook(session="race"))["hookSpecificOutput"]["additionalContext"]
            self.assertIn("z-mode was explicitly enabled", context)
            self.assertIn("Herdr execution was explicitly enabled", context)
            self.control("disable", session="race")

    def test_style_switch_disable_is_scoped_to_active_mode(self) -> None:
        context = json.loads(self.hook())["hookSpecificOutput"]["additionalContext"]
        self.assertIn("When active z-mode stops or yields to another style, run Disable", context)
        self.assertIn("Herdr selected without z-mode stays until Native", context)

    def test_real_install_paths_keep_full_controls_within_codex_limit(self) -> None:
        render = runpy.run_path(str(HELPER))["build_context"]
        data = self.data / ("plugins/data/zstack-zstack-local-" + "x" * 80)
        session = "019a2b3c-4d5e-6f70-8192-a3b4c5d6e7f8"
        runpy.run_path(str(HELPER))["set_active"](runpy.run_path(str(HELPER))["state_path"](str(data), session), True)
        subprocess.run(  # noqa: S603 - Fixed interpreter and local helper.
            [sys.executable, "-I", "-S", str(HELPER), "herdr", f"--session-id={session}", "--data-dir", str(data)],
            check=True,
        )
        skill = self.data / "codex/plugins/cache/market/herdr-zstack/0.1.0/skills/hc-workflow/SKILL.md"
        with patch.dict(os.environ, self.env, clear=True):
            for present in (False, True):
                if present:
                    skill.parent.mkdir(parents=True)
                    skill.write_text("fixture")
                context, _ = render("codex", session, str(data), "resume")
                self.assertLess(len(context), 4000)
                self.assertIn("Herdr execution was explicitly enabled", context)

    def test_execution_controls_are_scoped_and_roundtrip_from_hook(self) -> None:
        self.control("enable", session="parent")
        self.control("herdr", session="parent")
        context = json.loads(self.hook(session="child", source="fork"))["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("Herdr execution was explicitly enabled", context)
        for label in ("Herdr", "Native"):
            argv = shlex.split(self.command(context, label.lower()))
            self.assertIn("--session-id=child", argv)
            subprocess.run(  # noqa: S603 - Trusted emitted command; isolated data root.
                [sys.executable, *argv[argv.index("-I") :]], check=True, capture_output=True, env=self.env
            )
            self.assertEqual("Herdr execution was explicitly enabled" in self.hook(session="child"), label == "Herdr")
            self.assertIn("Herdr execution was explicitly enabled", self.hook(session="parent"))
        self.assertIn(f"PowerShell control: & '{INTERPRETER}'", context)
        self.hook(session="parent", source="clear")
        self.assertEqual(list((self.data / "z-mode").iterdir()), [])

    def test_legacy_and_invalid_execution_state_default_to_native(self) -> None:
        state = self.data / "z-mode/session-a.json"
        state.parent.mkdir()
        for value in ({"active": True}, {"active": True, "execution": "unexpected"}, {"execution": True}):
            state.write_text(json.dumps(value))
            context = json.loads(self.hook())["hookSpecificOutput"]["additionalContext"]
            self.assertNotIn("Herdr execution was explicitly enabled", context)
            self.assertEqual("z-mode was explicitly enabled" in context, value.get("active") is True)

    def test_legacy_json_herdr_preference_survives_upgrade_and_native_clears_it(self) -> None:
        state = self.data / "z-mode/session-a.json"
        marker = self.data / "z-mode/session-a.herdr"
        state.parent.mkdir()
        state.write_text(json.dumps({"active": True, "execution": "herdr"}))
        context = json.loads(self.hook(source="resume"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("z-mode was explicitly enabled", context)
        self.assertIn("Herdr execution was explicitly enabled", context)
        self.control("enable")
        self.assertEqual(json.loads(state.read_text()), {"active": True})
        self.assertTrue(marker.is_file())
        state.write_text(json.dumps({"active": True, "execution": "herdr"}))
        marker.unlink()
        self.control("native")
        self.assertEqual(json.loads(state.read_text()), {"active": True})
        self.assertFalse(marker.exists())
        self.assertNotIn("Herdr execution was explicitly enabled", self.hook(source="resume"))
        state.write_text(json.dumps({"active": False, "execution": "herdr"}))
        self.control("herdr")
        self.assertEqual(list(state.parent.iterdir()), [marker])
        self.assertIn("No stored z-mode activation", self.hook(source="resume"))

    def test_failed_execution_selection_preserves_prior_state_and_reports_failure(self) -> None:
        functions = runpy.run_path(str(HELPER))
        path = str(self.data / "z-mode/session-a.json")
        functions["set_active"](path, True)
        with patch("builtins.open", side_effect=PermissionError("fixture")), self.assertRaises(PermissionError):
            functions["set_execution"](path, "herdr")
        self.assertEqual(json.loads(Path(path).read_text()), {"active": True})
        self.assertEqual(list(Path(path).parent.iterdir()), [Path(path)])
        Path(path).parent.joinpath("session-a.herdr").mkdir()
        result = self.control("native", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("state not changed", result.stderr)

    @unittest.skipIf(os.name != "posix" or os.geteuid() == 0, "needs POSIX permissions that bind the current user")
    def test_blocked_state_write_names_the_sandbox_remedy(self) -> None:
        # Claude Code's Bash sandbox write-protects plugin data; a read-only directory produces the same denial.
        directory = self.data / "z-mode"
        directory.mkdir()
        directory.chmod(0o500)
        self.addCleanup(directory.chmod, 0o700)
        for action in ("enable", "herdr"):
            result = self.control(action, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("state not changed", result.stderr)
            self.assertIn("follow this session's z-mode guidance for blocked controls", result.stderr)
            self.assertNotIn("outside the sandbox", result.stderr)
        self.assertEqual(list(directory.iterdir()), [])
        corrupt = self.control("enable", session="../outside", check=False)
        self.assertNotIn("sandbox", corrupt.stderr)

    def test_only_sandbox_like_write_errors_point_to_the_guidance(self) -> None:
        # Seatbelt raises EPERM and bubblewrap EROFS; other write failures are not a sandbox remedy.
        main = runpy.run_path(str(HELPER))["main"]
        argv = ["session_start.py", "enable", "--session-id=session-a", "--data-dir", str(self.data)]
        for code in (errno.EPERM, errno.EACCES, errno.EROFS, errno.EISDIR, errno.ENOSPC):
            with (
                self.subTest(errno=errno.errorcode[code]),
                patch.object(sys, "argv", argv),
                patch("os.makedirs", side_effect=OSError(code, os.strerror(code))),
                contextlib.redirect_stderr(io.StringIO()) as stderr,
                self.assertRaises(SystemExit) as exit_,
            ):
                main()
            self.assertEqual(exit_.exception.code, 1)
            self.assertIn("state not changed", stderr.getvalue())
            self.assertEqual("blocked controls" in stderr.getvalue(), code in (errno.EPERM, errno.EACCES, errno.EROFS))
        self.assertEqual(list(self.data.iterdir()), [])

    @unittest.skipIf(os.name != "posix", "uses POSIX venv layout")
    def test_controls_ignore_an_interpreter_planted_in_the_working_directory(self) -> None:
        # uv run would pick a .venv in the working directory, which a sandboxed command can later overwrite.
        for symlinks in (True, False):
            with self.subTest(symlinks=symlinks):
                planted = self.data / f"project-{symlinks}/.venv"
                venv.EnvBuilder(symlinks=symlinks, with_pip=False).create(planted)
                interpreter = planted / "bin/python"
                self.assertEqual(interpreter.is_symlink(), symlinks)
                result = subprocess.run(  # noqa: S603 - Isolated fixture interpreter and local helper.
                    [str(interpreter), "-I", "-S", str(HELPER), "--host=codex"],
                    input=json.dumps(
                        {"hook_event_name": "SessionStart", "source": "startup", "session_id": "session-a"}
                    ),
                    text=True,
                    capture_output=True,
                    check=True,
                    cwd=planted.parent,
                    env=self.env,
                )
                context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                argv = shlex.split(self.command(context, "enable"))
                self.assertEqual(argv[0], INTERPRETER)
                self.assertFalse(Path(argv[0]).is_relative_to(self.data))
                powershell = self.command(context, "enable", "PowerShell")
                self.assertTrue(powershell.startswith(f"& '{argv[0]}' '-I' '-S' "))
                subprocess.run(argv, check=True, cwd=planted.parent, env=self.env)  # noqa: S603 - Emitted control.
                self.assertTrue((self.data / "z-mode/session-a.json").is_file())
                self.control("disable")

    def test_context_explains_persistence_under_a_sandbox(self) -> None:
        render = runpy.run_path(str(HELPER))["build_context"]
        for host, direct in (("claude", "with the ! prefix or outside Claude Code"), ("codex", "outside the agent")):
            context, _ = render(host, "session-a", str(self.data), "startup")
            self.assertIn("If a sandbox blocks a control", context)
            self.assertIn("request one unsandboxed rerun through the host's permission flow", context)
            self.assertIn("stop retrying controls this session", context)
            self.assertIn(f"give the user the command to run {direct}", context)
            self.assertIn("a blocked Disable leaves stored activation", context)

    def test_invalid_identity_and_corrupt_state_fail_inactive(self) -> None:
        for session in ("../outside", "x/y", "x; touch outside", "", "x" * 129):
            self.assertEqual(self.hook(session=session), "")
            self.assertNotEqual(self.control("enable", session=session, check=False).returncode, 0)
        self.assertEqual(list(self.data.iterdir()), [])
        state = self.data / "z-mode/session-a.json"
        state.parent.mkdir()
        for value in ("invalid", "[]", '{"active":"true"}', "null"):
            state.write_text(value)
            self.assertIn("No stored", self.hook(source="compact"))

    def test_clear_reports_state_removal_failure(self) -> None:
        state = self.data / "z-mode/session-a.json"
        state.mkdir(parents=True)
        output = json.loads(self.hook(source="clear"))
        self.assertIn("could not be removed", output["systemMessage"])
        self.assertIn("inactive for this cleared context", output["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("No stored", output["hookSpecificOutput"]["additionalContext"])
        self.assertIn("stale stored activation", output["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
