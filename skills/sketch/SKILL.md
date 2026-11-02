---
name: sketch
description: "Render Mermaid diagrams as inline text with Sketch for chat responses and terminals. Use when the user asks for Sketch or diagrams displayed without an image viewer."
disable-model-invocation: true
---

# Sketch

Build the diagram in Mermaid, render it with Sketch, and display the captured text inline. Sketch's CLI exposes the box-drawing renderer from the Go package `tuios.dev/sketch/text`; do not write a Go wrapper just to obtain that output.

## Render and display

1. Check `sketch --help` for the installed flags. If unavailable, report the missing dependency. When installation is authorized, use `mise use -g go:tuios.dev/sketch/cmd/sketch@latest` (requires Go 1.25+) or the user's package manager.
2. Write Mermaid source for the relationships you need to explain. Use a temporary `.mmd` file unless the user wants a saved artifact. Keep labels short and choose a diagram type that matches the information.
3. Capture stdout with explicit text format, no ANSI color, and a bounded width:

   ```sh
   sketch diagram.mmd -f text -color never -cols 80
   ```

   Sketch defaults to SVG when stdout is captured or piped. Always use `-f text` for inline diagrams; `sketch/text` is a Go package, not a shell command or CLI subcommand. `-color never` keeps escape sequences out of the response.

   Standard input works too:

   ```sh
   sketch - -f text -color never -cols 80 <<'MERMAID'
   flowchart LR
       A[Mermaid source] --> B[Sketch]
       B --> C[Inline diagram]
   MERMAID
   ```

4. Check the exit status and read the drawing. Confirm labels, arrow direction, branches, and loops match the source and the facts being explained. On parse or width errors, correct or simplify the source and rerun. Split a large diagram into focused views rather than truncating it. Do not silently omit relationships to make it fit.
5. Put the actual captured output in a fenced `text` block in the response, preserving whitespace and Unicode characters. Add a short explanation of what it shows. Do not substitute Mermaid source, manually redraw the result, or claim a failed render succeeded. If output was truncated by the tool, capture it to a file and read the complete drawing before displaying it.

## Existing Markdown and other outputs

`sketch README.md -f text -color never -cols 80` renders its Mermaid blocks. Add `-diagram 2` to select the second diagram; select a single diagram when surrounding blocks are irrelevant.

Inline text is the default for this skill. Use `-o diagram.svg` or `-o diagram.png` when the user requests an image export. Opening a Rex pane is optional and uses the installed rex skill; inline replies need no terminal integration, browser, TUIOS process, or graphics protocol.

Sources: [Sketch library and CLI](https://tuios.dev/docs/libraries/sketch), [Go text renderer](https://pkg.go.dev/tuios.dev/sketch/text).
