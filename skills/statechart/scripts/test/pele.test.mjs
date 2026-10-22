import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { findTlc } from "../lib.mjs";

const cli = fileURLToPath(new URL("../statechart.mjs", import.meta.url));
let skip;
try { findTlc(); } catch { skip = "TLA2TOOLS is required for renderer integration"; }

test("Pele resolves from the caller, retains partial evidence on failure, and cleans stale SVGs", { skip }, (t) => {
  const dir = mkdtempSync(join(tmpdir(), "statechart pele "));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  copyFileSync(new URL("sync.mmd", import.meta.url), join(dir, "sync.mmd"));
  const pkg = join(dir, "node_modules", "pele");
  mkdirSync(pkg, { recursive: true });
  writeFileSync(join(pkg, "package.json"), JSON.stringify({ name: "pele", type: "module", exports: "./index.mjs" }));
  const source = (body) => writeFileSync(join(pkg, "index.mjs"), `export function render(text, options) { ${body} }`);
  const run = (...flags) => spawnSync(process.execPath, [cli, "from-chart", "sync.mmd", "--expect-broken", "NeverSyncedWhileOffline", ...flags], {
    cwd: dir, env: process.env, encoding: "utf8", timeout: 120_000,
  });
  const out = (name) => join(dir, "Sync-statechart", name);
  source(`if (options.links !== false || options.images !== false || options.responsive !== false) throw Error("unsafe options");
    if (!text.includes("stateDiagram-v2")) throw Error("not a chart");
    return { svg: '<svg xmlns="http://www.w3.org/2000/svg"><text>chart</text></svg>' };`);
  let result = run("--pele");
  assert.equal(result.status, 0, result.stdout + result.stderr);
  for (const name of ["chart.svg", "bug-1.svg"]) assert.match(readFileSync(out(name), "utf8"), /<svg/);
  // Fail only the trace, after the overview has rendered.
  source(`if (text.includes("1. ")) throw Error("trace rejected"); return { svg: '<svg></svg>' };`);
  result = run("--pele");
  assert.equal(result.status, 2, result.stdout + result.stderr);
  assert.match(result.stderr, /with Pele: trace rejected/);
  assert.ok(existsSync(out("chart.svg")));
  assert.ok(!existsSync(out("bug-1.svg")));
  for (const name of ["bug-1.mmd", "stories.md", "summary.json"]) assert.ok(existsSync(out(name)));
  result = run();
  assert.equal(result.status, 0, result.stderr);
  assert.ok(!existsSync(out("chart.svg")));
  source('return { svg: "" };');
  result = run("--pele");
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stderr, /Pele returned no SVG/);
  rmSync(pkg, { recursive: true });
  result = run("--pele");
  assert.equal(result.status, 2, result.stderr);
  assert.match(result.stderr, /cannot load Pele/);
  assert.ok(existsSync(out("chart.mmd")));
});
