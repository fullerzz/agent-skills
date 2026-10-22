---
name: statechart
description: "Turn TLA+ models into readable statecharts and counterexample paths, generate model skeletons from charts, or compare code-derived models with a specification. Use explicitly for /statechart; render with Mermaid or Pele."
disable-model-invocation: true
---

# Statechart

The chart shows what an app's user sees. A PM reads it to decide whether that behavior is right. Label each state with what is on the screen, such as "Paying". Label each step with what the user does or sees happen, such as "tap Pay" or "the charge goes through". Keep variable and action names out of labels. The scripts call this user the reader, as in `readerActions` and reader steps.

Resolve this entrypoint to its real installed directory and follow the [native host contract](../z-mode/references/native-hosts.md). Set `STATECHART_DIR` to that absolute directory, then run `node "$STATECHART_DIR/scripts/statechart.mjs" --help`. Work in an owned scratch folder outside the target repository; copy the input and its required modules there. Commands write model files beside the input and replace only their generated output folder. Skeleton generation refuses occupied files or symlinks; choose a new module name to regenerate. Mapping `.mjs` files execute JavaScript: review them as code before loading. This skill authorizes scoped verification artifacts, not product fixes, global installation, commits, publication, messages, or tracker writes.

Requires Node, Java 11+, and `TLA2TOOLS` pointing to a local [tla2tools.jar](https://github.com/tlaplus/tlaplus/releases). `JAVA` optionally selects the Java binary. Read [rendering](references/rendering.md) for Mermaid PNG and Pele SVG prerequisites and commands. Missing tools or unfinished runs are blocked evidence, never passes.

The value parser refuses integers outside JavaScript's safe integer range and function keys that collide when represented as object keys. Such inputs are unsupported evidence, not chartable states; do not round or rename values to force a pass.

Mappings receive sequences and sets as arrays, records and functions as objects, and model values as `{ modelValue: "Foo" }`. Internal keys retain value kinds, typed function domains, and set membership order independence, including when comparing projected models. Unrecognized value syntax stops the run instead of becoming an ambiguous string.

## Pick the direction

Use `from-spec` when a TLA+ model exists or the code is concrete enough to model. Use `from-chart` when there is no model and the PM should agree on the behavior before anyone writes or changes the code.

If the code already has a TLA+ spec, start from a copy of that spec. Add the variables the user sees, and keep the spec's existing invariants. To audit the code against that spec, make the copy model what the code does, and pass the spec unchanged as `--against`. In a new spec, tie every variable and action to code that a reviewer can open, and take its name from that code. Make each action one indivisible step in the code.

## Spec to chart

1. Choose the chart's states. When the PM cares about something the screen does not show, such as a second charge while the screen still says "Paying", name the state "Paying, charged twice". Start with few states, and split a state only when the split separates two bugs.
2. Write each rule the PM agrees to as one invariant, with the PM's sentence as its comment. For a rule that applies once everything settles, define `Settled == ~ENABLED System`, where `System` is the disjunction of the actions the user does not take. Record each broken rule as a model counterexample pending code reproduction. Never weaken a rule to make the chart pass.
3. Run `from-spec`, then fill in the mapping file it writes. Put the labels in `state` and `step`, and list the user's actions in `readerActions` by action name. When two bugs end on the same screen through different code paths, add `cause` and make it name the code path. To color the states by what the PM cares about, such as "Toast shown", return that group from `group`. The legend names the groups, and states that break a rule still get a red border.
4. If there is an open fix, model it from the code and pass that model as `--fixed`.
5. Render each chart with `--png` (Mermaid), `--pele` (SVG), or both, and inspect every rendered diagram. Check that each numbered path reads in order. If a label reads like code, fix `state` or `step` and run the command again.
6. Before calling a finding an actual software bug, reproduce its story against the real code in an isolated test or live repro, one step per model action. Retain the source identity, exact command, observed result, and code paths. A plausible trace or model-only mutation is not reproduction. If it cannot reproduce, label it unconfirmed, investigate correspondence, correct demonstrated model errors, and rerun without weakening the rule. Missing access or tooling leaves reproduction blocked.

## Chart to spec

1. Draw the chart the PM agrees to. Use one region for each thing that changes independently, such as the connection and the sync badge. Add one `%% never` line per rule, with the PM's sentence. Draw "the app closes" as an edge to the state the user sees next.
2. Run `from-chart`. If a rule breaks, report a design-level counterexample for the reader to review; there is no implementation bug claim before code exists.
3. Add the real code's guards and variables to the spec that `from-chart` wrote, and run `from-chart` again. For each difference it prints, establish code correspondence and reproduction before asking the reader whether the requirement or implementation should change. `--against` compares model behavior; it is not a proof that arbitrary source code refines the specification.

## Hand off

Give the reader the rendered PNG or SVG and Mermaid source of each chart. Add one line per finding with the broken rule, numbered steps, reproduction evidence or blocker, and whether a fix was checked in the model and in real code. The scripts use `bug-N` filenames and model-derived colors; those labels and colors do not establish a confirmed implementation bug or fix. Take every count you quote from `summary.json`. Attach `stories.md` and the command that regenerates everything. State source identity, bounds, assumptions, excluded behavior, and what the model leaves out. Timers and guard labels are explanatory text unless the model explicitly checks them.
