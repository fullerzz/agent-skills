import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { findTlc, parseValue } from "../lib.mjs";
import { state, group } from "../model/OutputFolder.map.mjs";

const scripts = fileURLToPath(new URL("../", import.meta.url));
const run = (dir, script, ...args) => spawnSync(process.execPath, [join(scripts, script), ...args], {
  cwd: dir, encoding: "utf8", timeout: 120_000,
});
const scratch = (t) => {
  const dir = mkdtempSync(join(tmpdir(), "statechart review "));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  return dir;
};
let skip;
try { findTlc(); } catch { skip = "TLA2TOOLS required"; }
const chart = "stateDiagram-v2\n  [*] --> A\n  A --> B : go\n";
const generate = (dir, text = chart) => {
  writeFileSync(join(dir, "flow.mmd"), text);
  return run(dir, "chart-to-tla.mjs", "flow.mmd", "--module", "Flow");
};

test("unsafe TLC integers and colliding function keys cannot silently change a state", () => {
  assert.equal(parseValue("9007199254740991"), Number.MAX_SAFE_INTEGER);
  for (const value of ["9007199254740993", "-9007199254740993", "<<9007199254740993>>"])
    assert.throws(() => parseValue(value), /integer.*safe range/);
  assert.throws(() => parseValue('(1 :> "number" @@ "1" :> "string")'), /function keys.*collide/);
  const fn = parseValue('("__proto__" :> 1 @@ "constructor" :> 2)');
  assert.equal(Object.hasOwn(fn, "__proto__"), true);
  assert.equal(fn.__proto__, 1);
});

test("TLA keywords in chart labels generate executable actions", { skip }, (t) => {
  const dir = scratch(t);
  const text = "stateDiagram-v2\n  [*] --> A\n" +
    ["IF", "IN", "LET", "CASE", "NEW", "TRUE", "BOOLEAN"].map((s) => `  A --> B : ${s}`).join("\n");
  assert.equal(generate(dir, text).status, 0);
  const result = run(dir, "statechart.mjs", "from-chart", "flow.mmd");
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("never names cannot collide with generated state-set operators", (t) => {
  const dir = scratch(t);
  const result = generate(dir, chart + "  %% never mainStates: B\n");
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /mainStates.*already used/);
  assert.equal(existsSync(join(dir, "Flow.tla")), false);
});

test("state-set operators cannot collide with earlier region variables", { skip }, (t) => {
  const dir = scratch(t);
  const text = `stateDiagram-v2
  state Both {
    state "Main States" as First {
      [*] --> A
      A --> B : move
    }
    --
    state Main {
      [*] --> X
      X --> Y : move
    }
  }
  [*] --> Both
`;
  assert.equal(generate(dir, text).status, 0);
  const result = run(dir, "statechart.mjs", "from-chart", "flow.mmd");
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test("from-chart reports a missing mapping as unfinished work", { skip }, (t) => {
  const dir = scratch(t);
  assert.equal(generate(dir).status, 0);
  rmSync(join(dir, "Flow.map.mjs"));
  const result = run(dir, "statechart.mjs", "from-chart", "flow.mmd");
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stderr, /Flow.map.mjs.*from-spec/);
  assert.doesNotMatch(result.stderr, /ERR_MODULE_NOT_FOUND/);
});

test("mapping scaffolds refuse dangling symlinks", { skip }, (t) => {
  const dir = scratch(t);
  assert.equal(generate(dir).status, 0);
  rmSync(join(dir, "Flow.map.mjs"));
  symlinkSync(join(dir, "outside.mjs"), join(dir, "Flow.map.mjs"));
  const result = run(dir, "statechart.mjs", "from-spec", "Flow.tla");
  assert.equal(result.status, 2, result.stderr);
  assert.equal(existsSync(join(dir, "outside.mjs")), false);
  assert.match(result.stderr, /occupied/);
});

test("reruns preserve foreign TLC files and generated-name directories", { skip }, (t) => {
  const dir = scratch(t);
  assert.equal(generate(dir).status, 0);
  const args = ["from-spec", "Flow.tla"];
  assert.equal(run(dir, "statechart.mjs", ...args).status, 0);
  const out = join(dir, "Flow-statechart");
  for (const relative of ["tlc/notes.txt", "tlc/nested/notes.txt", "chart.png/notes.txt"]) {
    const file = join(out, relative);
    mkdirSync(join(file, ".."), { recursive: true });
    writeFileSync(file, "retained evidence");
    const result = run(dir, "statechart.mjs", ...args);
    assert.equal(result.status, 2, result.stderr);
    assert.equal(readFileSync(file, "utf8"), "retained evidence");
    rmSync(file);
    if (relative.includes("nested")) rmSync(join(out, "tlc/nested"), { recursive: true });
    if (relative.startsWith("chart.png")) rmSync(join(out, "chart.png"), { recursive: true });
  }
});

test("comparison charts keep second-model labels for shared endpoints and explain region fallback", (t) => {
  const dir = scratch(t);
  const dot = (action) => `strict digraph DiskGraph {\n1 [label="x = 0",style = filled]\n2 [label="x = 1"]\n1 -> 2 [label="${action}"];\n}\n`;
  writeFileSync(join(dir, "now.dot"), dot("Save"));
  writeFileSync(join(dir, "other.dot"), dot("Confirm"));
  writeFileSync(join(dir, "map.mjs"), 'export const state = v => v.x ? "Saved" : "Draft";\nexport const step = a => a;\n');
  const result = run(dir, "tlc-to-chart.mjs", "--dot", "now.dot", "--against-dot", "other.dot", "--map", "map.mjs", "--regions", "--highlight", "0", "--out", "chart.mmd");
  assert.equal(result.status, 0, result.stderr);
  const drawn = readFileSync(join(dir, "chart.mmd"), "utf8");
  assert.match(drawn, /Save/);
  assert.match(drawn, /in the spec, Confirm/);
  assert.match(result.stderr, /regions: not drawn.*context: progress/);
  const covered = run(dir, "tlc-to-chart.mjs", "--dot", "now.dot", "--against-dot", "other.dot", "--map", "map.mjs", "--cover", "--highlight", "0", "--out", "covered.mmd");
  assert.equal(covered.status, 0, covered.stderr);
  assert.match(readFileSync(join(dir, "covered.mmd"), "utf8"), /in the spec, Confirm/);
  writeFileSync(join(dir, "now.dot"), 'strict digraph DiskGraph {\n1 [label="x = 0",style = filled]\n}\n');
  writeFileSync(join(dir, "map.mjs"), 'export const state = v => v.x ? "Saved" : "Draft";\nexport const step = () => "";\n');
  const unlabeled = run(dir, "tlc-to-chart.mjs", "--dot", "now.dot", "--against-dot", "other.dot", "--map", "map.mjs", "--highlight", "0", "--out", "unlabeled.mmd");
  assert.equal(unlabeled.status, 0, unlabeled.stderr);
  assert.match(readFileSync(join(dir, "unlabeled.mmd"), "utf8"), /s0 --> s1/);
});

test("output model labels orphaned TLC as running", () => {
  const v = { pc: ["orphanTlc", "idle"], aside: [], out: { exists: false } };
  assert.equal(state(v), "One run going: no folder");
  assert.equal(group(v), "Running");
});
