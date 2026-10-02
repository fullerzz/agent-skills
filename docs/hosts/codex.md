# Use this library in Codex

From the library checkout run `uv run scripts/install.py --host codex`, inspect the preview, then repeat with `--apply`. Add `--project "/path/to/project"` for project installation. Empty `--home` or `--project` values are rejected before any writes.

Personal skills link into `~/.agents/skills/<name>`; project skills into `.agents/skills/<name>`. Personal agents copy into `$CODEX_HOME/agents/` (default `~/.codex/agents/`); project agents into `.codex/agents/`. An explicit `--home` uses that root's `.codex` for isolated testing. These are separate discovery locations.

Start a new session. Select a skill with `$how`, `$poteto-mode`, or the skill picker. Use a small read-only prompt and verify the host loaded the intended source. Explicit-only skills have `agents/openai.yaml` with `policy.allow_implicit_invocation: false`.

Native roles are `poteto-agent` and `comment-sicko`. They use standalone TOML with name, description, and developer_instructions. Model overrides are omitted to inherit native defaults. The comment reviewer uses read-only sandboxing. If custom agents or delegation are disabled, use the disclosed built-in/direct fallback.

Project agent discovery requires a trusted project and enabled native agents. Confirm those settings through Codex's native trust flow; installation does not grant trust. On the tested CLI 0.160.0, delegated runs needed a persistent session: `exec --ephemeral` failed child rollout creation. See the validation record for this version-specific limit.

For requested overrides, edit native agent model and model_reasoning_effort fields supported by your version, keeping them separate. User-modified copies are preserved; a later installer run reports the collision. The installer does not enable agents, change permissions, or rewrite your configuration.

Resources resolve from the real installed skill file; Git commands stay in the target project. A read-only review does not authorize edits, messages, or PRs. Resume a named session with `codex resume <id>`, or use a saved task handoff when native history is unavailable.

See current [skills documentation](https://learn.chatgpt.com/docs/build-skills), [native subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), and [local validation results](../validation.md). Documented discovery is distinct from behavior proven by this checkout's tests.
