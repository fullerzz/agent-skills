# /// script
# requires-python = ">=3.11"
# ///
"""Compare complete hook commands against a Git revision using warm AB/BA pairs."""

import argparse
import json
import os
import shlex
import statistics
import subprocess
import tempfile
import time
from pathlib import Path


def run_variant(variant: tuple[str, Path, dict[str, str]], scenario: str, temporary: str) -> float:
    command, data, env = variant
    state = data / "z-mode/benchmark.json"
    if scenario == "inactive":
        state.unlink(missing_ok=True)
    else:
        state.write_text('{"active":true}')
    event = json.dumps(
        {
            "hook_event_name": "SessionStart",
            "source": "clear" if scenario == "clear" else "startup",
            "session_id": "benchmark",
        }
    )
    started = time.perf_counter_ns()
    result = subprocess.run(  # noqa: S602 - Benchmark the trusted manifest shell command.
        command, shell=True, input=event, text=True, capture_output=True, env=env, cwd=temporary, check=True
    )
    elapsed = (time.perf_counter_ns() - started) / 1_000_000
    output = json.loads(result.stdout)["hookSpecificOutput"]
    if output["hookEventName"] != "SessionStart":
        raise ValueError("Hook returned the wrong event")
    context = output["additionalContext"]
    if ("was explicitly enabled" in context) != (scenario == "active"):
        raise ValueError("Hook returned the wrong activation state")
    if "Enable: " not in context or "Disable: " not in context:
        raise ValueError("Hook omitted mode controls")
    if scenario == "clear" and state.exists():
        raise ValueError("Clear did not remove mode state")
    return elapsed


def benchmark(baseline: str, pairs: int) -> dict[str, object]:
    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="zstack hook benchmark ") as temporary:
        variants = {}
        for label in ("before", "after"):
            package = Path(temporary) / label
            (package / "hooks").mkdir(parents=True)

            def read_resource(relative: str, label: str = label) -> bytes:
                return (
                    subprocess.check_output(  # noqa: S603 - User-selected Git baseline, no shell.
                        ["git", "show", f"{baseline}:{relative}"],  # noqa: S607
                        cwd=root,
                    )
                    if label == "before"
                    else (root / relative).read_bytes()
                )

            manifest = json.loads(read_resource(".codex-plugin/plugin.json"))
            config = read_resource(manifest["hooks"])
            command = json.loads(config)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            # Historical baselines may use a different hook filename or root expression.
            helper = next(
                part.rpartition("}/")[2] for part in shlex.split(command) if "PLUGIN_ROOT" in part and "}/" in part
            )
            (package / helper).write_bytes(read_resource(helper))
            data = package / "data"
            (data / "z-mode").mkdir(parents=True)
            inherited = {key: value for key, value in os.environ.items() if not key.startswith("CLAUDE_PLUGIN_")}
            variants[label] = (command, data, dict(inherited, PLUGIN_ROOT=str(package), PLUGIN_DATA=str(data)))

        results = {}
        for scenario in ("inactive", "active", "clear"):
            samples: dict[str, list[float]] = {label: [] for label in variants}

            # Independently warm both commands, including their interpreter imports.
            for _ in range(2):
                for label in variants:
                    run_variant(variants[label], scenario, temporary)
            for pair in range(pairs):
                for label in ("before", "after") if pair % 2 == 0 else ("after", "before"):
                    samples[label].append(run_variant(variants[label], scenario, temporary))
            results[scenario] = {
                label: {
                    "runs": len(values),
                    "median_ms": statistics.median(values),
                    "min_ms": min(values),
                    "max_ms": max(values),
                    "samples_ms": values,
                }
                for label, values in samples.items()
            }
        return {
            "baseline": baseline,
            "order": "alternating AB/BA; two warmups per side per scenario",
            "failures": 0,
            "results": results,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="Git revision containing the baseline hook")
    parser.add_argument("--pairs", type=int, default=20)
    args = parser.parse_args()
    if args.pairs < 6 or args.pairs % 2:
        parser.error("--pairs must be an even number of at least 6")
    print(json.dumps(benchmark(args.baseline, args.pairs), indent=2))
