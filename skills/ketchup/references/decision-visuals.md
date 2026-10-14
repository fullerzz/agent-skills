# Decision visuals

Adapted from HumanLayer's [show-me](https://github.com/humanlayer/skills/blob/653b6411c1f70c275a18e37673b042ff99f67ceb/plugins/show-me/skills/show-me/SKILL.md) under the [MIT license](HUMANLAYER-LICENSE.txt). This bundled reference requires no installed show-me skill. Apply it within ketchup's read-only, chat-only boundary.

Choose the smallest view that makes the user's decision clear. Put it next to the decision lines it supports; retain only the calls, files, states, and boundaries needed to compare the options. One useful comparison is better than an inventory of diagrams. Ketchup's box, word, and voice limits apply to every view; link sources rather than spelling them out.

| Decision concerns | Useful view |
| --- | --- |
| Visible UI or layout change | Existing captured before/after screenshots or video, with state labels and source references |
| Costs, measurements, status, or tradeoffs | Current/option columns in a table; include units for known numbers, link sources, and mark unknown values |
| Code or behavior change | A small actual diff, or a clearly labeled proposed diff or pseudocode sketch |
| Runtime ownership or ordering | A call tree or Mermaid flow/sequence diagram, with current and proposed paths distinguished |
| Component or file responsibility | A shallow component/file tree, or a tree diff showing the affected boundaries |

For multiple options, use one current-state column beside the option columns. When no current state is known, compare options and say the baseline is unavailable. A diff can encode before/after with removed/added lines; label the sides of sequential diagrams when the host cannot show them side by side. Use plain text or Markdown tables when Mermaid or image rendering is unavailable, and disclose a rendering gap that hides relevant detail.

Separate observed results from proposals. A sketch explains a proposed shape; it is not evidence that code ran or a UI was captured. Do not infer a screenshot from source code, generate a screen you did not capture, invent measurements, or construct a guessed artifact URL. Include only existing, relevant artifacts safe to display; omit secrets and sensitive details.

If only one captured state exists, show it with its label and say the other capture is missing. You may explain known proposed behavior in a table, but do not present it as a captured after-state. If no useful comparison can be grounded, state the missing evidence plainly and give the decision lines and one line naming the options without a visual. Never start work, install a tool, or request broader access just to fill the gap.

HumanLayer's standalone skill also writes and opens focused HTML artifacts. Ketchup does not adopt that path: compose inline tables, diffs, pseudocode, trees, and diagrams from existing evidence, or reuse artifacts already available. Do not launch a browser or app to render a visual, write an HTML file, or call another skill whose workflow exceeds these boundaries.
