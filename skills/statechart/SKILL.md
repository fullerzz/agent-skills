---
name: statechart
description: "Check a TLA+ model of a system that moves between states, such as a product flow, a protocol, or a service, and draw it as a Mermaid statechart with the shortest path to each state that breaks a rule. Use explicitly for /statechart; render with Pele."
disable-model-invocation: true
---

# Statechart

The chart shows how a system moves between states, in the words of the person who reads it. That person, the reader, decides whether the behavior is right.

## Run

Resolve this entrypoint to its real installed directory and follow the [native host contract](../z-mode/references/native-hosts.md). Set `STATECHART_DIR` to that absolute directory. Work in an owned scratch folder outside the target repository, and copy the spec and its required modules there. Write a TLA+ spec and its config. Then run:

```sh
"$STATECHART_DIR/scripts/statechart" SPEC.tla [--config FILE] [--view FILE] [--out DIR]
```

The launcher runs `scripts/statechart.ts` with Node 22.18–22.x or 23.6+, Bun 1.1.5+, or Deno 2+. The output folder must be new or empty; the default is `SPEC-chart` beside the spec. Exit 0 means every checked rule holds, 1 means a rule breaks, and 2 means TLC stopped with an error, a signal killed the check, or the command could not run. Only exits 0 and 1 write output.

TLC needs Java 11+. Set `TLA2TOOLS` to a local [tla2tools.jar](https://github.com/tlaplus/tlaplus/releases), and optionally `JAVA` to a Java binary. Without `TLA2TOOLS`, the command runs `mise install` for a checksum-pinned tla2tools 1.7.4 and Temurin 25, which needs the network and writes to the user's mise tool store. Ask before that first install unless the user already allowed it. Missing tools or unfinished runs are blocked evidence, never passes.

A view module executes JavaScript: review it as code before loading. This skill authorizes scoped verification artifacts, not product fixes, global installation, commits, publication, messages, or tracker writes.

## Write the spec

- If the code already has a TLA+ spec, start from a copy of it, add the variables the reader sees, and keep its existing invariants.
- Write each rule that the reader agrees to as an INVARIANT, with the reader's sentence as its comment. A rule can be about a screen, a result, a stored value, or a message. If the model has no variable for a rule, add the variable. Never weaken a rule to make it hold.
- In a model of code, tie every variable and action to code that a reviewer can open, and take its name from that code. Make each action one indivisible step in the code. Put the file and line of the code that checks each condition of an action in a comment on that condition, as in `\* pay.ts:120`.
- Write `Next` as a disjunction of the actions, such as `YouPressPlay \/ YouPressStop`. If you do not, TLC names every step `Next`.
- A state with no step out breaks `NoDeadlock`, also when it is a correct end state. When an INVARIANT or a PROPERTY already has that name, the rule is `CHECK_DEADLOCK`. Add to `Next` an action that is true only in the end states and changes nothing, such as `Done == phase \in {"paid", "failed"} /\ UNCHANGED vars`, and give it a label in `step()`.

## Pick the chart

You do the work that needs judgment: the words on each state and arrow, the phases and their colors, the title, and the report to the reader. Put your work in a view module, and give it with `--view`.

To show the reader's words, the view exports `state(vars)`. The value that `state()` returns picks the form:

- A string gives a flat chart: `export const state = (v) => (v.paid ? "Paid" : "Paying");`
- An array gives parent states: `export const state = (v) => v.main.split(".");`
- An object gives one parallel region for each key: `export const state = (v) => ({ Playback: v.playback, Volume: v.volume });`

Label each state with what the reader can see or cares about, such as "Paying" or "Lease held, write pending". Keep variable names out of labels. In `vars`, a TLA+ sequence is an object with keys from 1, so `v.pc[1]` is `pc[1]`. A set is an array, and a model value is its name. When two keys of one function read as the same object key, such as the model value `A` and the string `"A"`, the command stops rather than drop one.

The view can also export `step(action, from, to)`. It gets the TLC action name and the values before and after the step, and it returns the label of the arrow. Write each step label as the user sees it happen, such as "you press play" or "the connect fails". Do not name the code or the TLA+ action. Two actions that end the same in the chart get the same label, so that they share one arrow.

When a step can occur only in some conditions, end its label with the condition in brackets, in the reader's words, such as `you press play [while the file loads]`. In a regions chart, the command writes the condition on the other regions on the arrow, in the words of their labels, such as `[when Offline]`. Your brackets replace it, and two arrows from one state can then look the same. So in a regions chart, do not write brackets for a condition on another region. When a value that no label shows decides where a step goes, name the result in the label, such as "the roster read fails".

The view can also export these:

- `group(vars)` returns the name of a phase. Each chart state gets the color of its group. When the model states behind one chart state are in different groups, that state gets no color.
- `colors` gives each group name a color class.
- `title` is a string that the chart shows at the top.

The command calls `state()` and `group()` at most once for each model state, and `step()` at most once for each step. The chart and the report both use those answers. So make each function depend only on its arguments.

The chart does not draw a step that stays in one label. Split a label when the reader must see such a step.

Aim for about 20 arrows or fewer, because a busier chart is hard to read. First return coarser labels from `state()`. Give one label to values that act the same, and leave out a detail that the reader does not need, such as a call in flight whose return changes nothing. Keep each state of a bug path, and keep each mark. When a merge changes a `breaks` state to `mayBreak`, it hides where a rule breaks. Do not merge two states that break different rules, because the reader then cannot see which rule breaks where. If the chart is still too busy, return `null` from `step()` for the steps that the reader does not need, such as a reset that every state has, or a step whose arrow repeats what other arrows show. Obey these rules when you hide steps:

- Keep each chart state reachable by arrows from a start state.
- Keep at least one arrow out of each chart state that has a step out in the model.
- Hide all the steps of an arrow, or none of them. When you hide only some, its condition gets narrower.
- In the hand-off, say which steps the chart hides.

## Read the report

- In the chart, a state that breaks a rule has the class `breaks`. When only some model states behind it break the rule, it has the class `mayBreak`. The Legend names the rules of each mark. When two rules break, it names both on one mark, so say in the hand-off which state breaks which rule. In a regions chart, a state gets a mark when each combination of region states that includes it can break a rule. When a combination can break a rule and none of its states has a mark, each state in that combination gets a mark.
- TLC goes past a state that breaks a rule, so the chart shows the states after a bug.
- Because TLC goes past bugs, a model with no limit on its states can run without end. Keep the constants small, or add a CONSTRAINT.
- With a VIEW or a SYMMETRY, TLC counts states that it treats as the same as one state, and the chart draws that one state. An arrow can lead to it rather than to the state that the step reaches, and the report says so.
- TLC checks the rules in each state past a CONSTRAINT or an ACTION_CONSTRAINT, but it does not explore that state or check it for deadlock. When TLC's shortest path for a rule ends in such a state, the chart draws that state, and the report gives that path. The chart does not draw the other states past the bound. A deadlock in such a state does not show. TLC also checks the rules after each step that an ACTION_CONSTRAINT excludes, also when it reaches the next state another way. When TLC's shortest path for a rule ends with such a step, the chart draws that step.
- The command checks the rules with TLC on the config as written, with one worker. When a rule breaks, the command removes that rule and runs TLC again, until no rule breaks. After the first break, each run stops at 100,000 distinct states, so that a large model does not run without end. When a run reaches that bound or stops on an error, the report lists the rules that it did not check under "Rules not checked", and the chart does not mark them. A rule that is not checked can hold or break; never report it as passing. To check it, remove the rules that break from the config, or make the model smaller. The bound adds a module that changes TLC's order of the variables, so for a property TLC can find a different counterexample than a run without the bound.
- A PROPERTY that breaks on a loop shows the path into the loop and marks the states that repeat forever with `repeats`. Action labels keep their full TLC names, including qualified INSTANCE actions such as `C!Up`.
- `tlc.out` is what TLC printed on the config as written. When the chart does not show the bug path of a rule that breaks, `tlc-RULE.out` is what TLC printed for the run that found it. When TLC repeats its first warning, plain TLC prints it twice, but `tlc.out` shows it once, because TLC leaves the second copy out of the output that this command reads. That happens only when Java runs with `-XX:+UseParallelGC`, since otherwise TLC's first warning is its advice to pass that flag, which it prints once.

## Show the chart

Show `chart.mmd` to the user as a `mermaid` code block. The chart has a budget of 500 states, counted by TLC on the config as written. Above that, the chart draws only the paths to the rules that break, and when no rule breaks, the command writes no `chart.mmd`. It still checks each rule, and the report gives the state count and each bug path. To see the whole graph, make the model smaller.

Render charts with Pele. When the user asks for an image, or a chart is too large to read as text, follow [render](references/render.md). Do not use a different renderer unless the user asks for it. Inspect each rendered chart, and check that each numbered path reads in order. If a label reads like code, fix the view and run the command again with a new `--out` folder.

## Hand off

Give each chart and its Mermaid text to the person who must decide. Add one line for each finding: the rule, the reader's sentence for that rule, the path as the report numbers it, and its reproduction evidence or blocker. Take every count you quote from `report.md`. Say what the model leaves out, its bounds, and the steps the chart hides. Give the command that makes the files again, with a new `--out` folder. A `breaks` mark is a model counterexample, not a confirmed software bug.

When the model describes code, replay each bug path against the real code in an isolated test or live repro, one step for each action. Drive user or client entry points and assert observable results, rather than flags the test sets or source-text matches. Distinguish runtime proof from code-reading evidence, and record the source identity, exact command, and observed result. If a bug does not occur, think that the model is wrong until you show that it is not: label the finding unconfirmed, correct demonstrated model errors, and rerun without weakening the rule. Missing access or tooling leaves reproduction blocked.
