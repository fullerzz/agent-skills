# Authoring a skill
1. Read existing callers, metadata, resources, and invocation intent. Use installed native skill-authoring guidance when available; otherwise these steps suffice.
2. Keep one canonical folder with SKILL.md name and concise quoted description. Use kebab-case identifiers matching the folder.
3. Keep decision-changing guidance in the entrypoint; link substantial conditional procedures as resources. Avoid generic instructions.
4. Project discovery is .agents/skills for Codex or .claude/skills for Claude Code. For both, choose one canonical directory and collision-safe link the other.
5. Preserve explicit-only policy: Claude disable-model-invocation: true and Codex agents/openai.yaml policy.allow_implicit_invocation: false. Do not change a user's policy by default.
6. Resolve bundled resources from the real installed entrypoint, independently of target cwd. Validate frontmatter, names, links, and executable helpers.
7. For behavior changes run a realistic scoped scenario; subjective prose can be reviewed directly with the user. Record gaps.
Return the local artifact and validation. Authoring does not authorize installing globally, filing tickets, sending messages, committing, pushing, or opening a PR.
