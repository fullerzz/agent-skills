---
name: show-me
description: "Help the user understand the current topic visually with concise diagrams, code-shape sketches, and focused HTML artifacts. Mermaid diagrams render inline in color with Sketch."
disable-model-invocation: true
---

# Show me

Adapted from HumanLayer's [show-me](https://github.com/humanlayer/skills/blob/4d69d20f6e9b57b4fcf0d501ccfb1be961f0f329/plugins/show-me/skills/show-me/SKILL.md) under the [MIT license](references/HUMANLAYER-LICENSE.txt).

Run only when the user invokes show-me by name. If you loaded it on your own initiative, stop and answer the request normally.

Help the user understand the current topic of conversation visually. Skip the preamble and keep prose brief. Pick the smallest view that makes the key point clear.

- Show logic or an algorithm as pseudocode:

```text
on(save)
  if content is unchanged
    return cached result
  write new content
  return fresh result
```

- Show runtime control flow as a call tree:

```text
submitForm
  createSession
    persistPrompt
    launchAgent
  navigateToSession
```

- Show UI structure as a component tree, including state and module boundaries that matter:

```tsx
<SessionPage> (apps/example/src/routes/session.tsx)
  useSessionEvents()
  <SessionToolbar>
    <RunSkillButton> (packages/ui)
```

- Show file responsibility or a broad refactor as a shallow file tree:

```text
src/
├── commands/       # parses user actions
├── sessions/       # owns session state
└── transport/      # sends API requests
```

- Show component interaction, control flow, or data flow with Mermaid, rendered inline in color by Sketch. Never answer with a raw Mermaid block. Run the source through Sketch as a visible shell command; the command's colored terminal output is the diagram:

```sh
sketch - -f text -color always -cols 80 <<'MERMAID'
sequenceDiagram
    participant User
    participant UI
    participant Daemon
    User->>UI: choose command
    UI->>Daemon: send expanded prompt
    Daemon-->>UI: stream result
MERMAID
```

- Use `diff` when the point is what changes and the surrounding shape already exists. Match the diff shape to the topic.

For a component change:

```diff
 <SessionPage>
   useSessionEvents()
   <SessionToolbar>
+    <RunSkillButton />
   <SessionTimeline>
+    <SkillResultCard />
```

For a file-layout change:

```diff
 src/
 ├── commands/
+│   └── show-me.ts       # expands the slash command
 ├── sessions/
-└── transport.ts
+└── transport/
+    ├── client.ts
+    └── stream.ts
```

For a call-tree or call-stack change:

```diff
 submitForm
   createSession
     persistPrompt
+    expandSkillMention
     launchAgent
-  navigateToSession
+  navigateToSession
+    subscribeToEvents
```

For a state or control-flow change:

```diff
 on(save)
-  write content
+  if content is unchanged
+    return cached result
+  write new content
+  invalidate cache
```

- Show the whole block when most of it is new, when omitted context would hide ownership or order, or when the user needs a copyable target shape:

```ts
function expandSkill(command: string): string {
  const skillName = command.slice(1)
  return `use the ${skillName} skill`
}
```

- For a visual UI, layout, state comparison, or concept too dense for a text diagram, write one focused HTML file — a diagram, an infographic, or a short slide deck, whichever fits the point. Match the product's colors, type, spacing, and components; use real labels and data; support desktop and mobile. Then open it for the user with the platform's opener, such as `open path/to/show-me-{description}.html` on macOS or `xdg-open` on Linux. An opener runs where the agent runs, so in a remote or headless session it does not reach the user. There, deliver the file through the host's attachment or download feature. If the host has neither, give the saved path and say the file could not be opened for them.

### Rendering Mermaid with Sketch

Follow the [Sketch skill](../sketch/SKILL.md) for the missing-CLI check, installation authority, reading the drawing back against the source, and splitting a large diagram instead of truncating it. Show-me differs in one way: it renders in color, and the colored command output is the display.

- Always pass `-f text`. Sketch writes SVG when stdout is not a terminal, and an agent's shell capture is not one.
- Always pass `-color always`. The default `auto` turns color off when stdout is not a terminal or `NO_COLOR` is set.
- Keep `-cols 80` unless the user's view is known to be wider or narrower.
- Use one Sketch command per diagram, so each drawing sits next to the short text it supports.
- Never paste the colored capture into the reply. Its ANSI escape sequences do not render as color in Markdown.
- Where the user is known to see command output in full, such as Claude Code in a terminal, the colored output is the display. Refer to it instead of repeating it.
- On any other surface, assume the user may not see command output: a messaging gateway, a remote session, or a host that collapses or truncates it. The command result does not say what the user saw. There, also render the diagram with the Sketch skill's plain-text path, `-color never`, and put that drawing in a fenced `text` block in the reply.
- On a parse or width error, fix or simplify the source and rerun. Never present a failed render as the diagram.

### Guidance

Place each visual next to the short text it supports. Keep only the calls, files, props, states, and boundaries needed to answer the user's current question or the options to resolve the current discussion point.

You may use one of these, you may use several, it is unlikely you will use all of them. Use your judgement and don't overwhelm the user.
