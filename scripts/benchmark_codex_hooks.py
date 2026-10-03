# /// script
# requires-python = ">=3.11"
# ///
"""Compare complete hook commands against a Git revision using warm AB/BA pairs."""

import argparse
import json
import os
from pathlib import Path
import statistics
import shlex
import subprocess
import tempfile
import time


def benchmark(baseline, pairs):
    root = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory(prefix="zstack hook benchmark ") as temporary:
        variants = {}
        for label in ("before", "after"):
            package = Path(temporary) / label
            (package / "hooks").mkdir(parents=True)
            def read_resource(relative):
                return (
                    subprocess.check_output(
                        ["git", "show", f"{baseline}:{relative}"], cwd=root
                    ) if label == "before" else (root / relative).read_bytes()
                )
            config = read_resource("hooks/hooks.json")
            (package / "hooks/hooks.json").write_bytes(config)
            command = json.loads(config)["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            # Historical baselines may use a different hook filename.
            helper = next(part.removeprefix("${PLUGIN_ROOT}/") for part in shlex.split(command) if part.startswith("${PLUGIN_ROOT}/"))
            (package / helper).write_bytes(read_resource(helper))
            data = package / "data"
            (data / "z-mode").mkdir(parents=True)
            variants[label] = (command, data, dict(os.environ, PLUGIN_ROOT=str(package), PLUGIN_DATA=str(data)))

        results = {}
        for scenario in ("inactive", "active", "clear"):
            samples = {label: [] for label in variants}

            def run(label):
                command, data, env = variants[label]
                state = data / "z-mode/benchmark.json"
                if scenario == "inactive":
                    state.unlink(missing_ok=True)
                else:
                    state.write_text('{"active":true}')
                event = json.dumps({"hook_event_name": "SessionStart", "source": "clear" if scenario == "clear" else "startup", "session_id": "benchmark"})
                started = time.perf_counter_ns()
                result = subprocess.run(command, shell=True, input=event, text=True, capture_output=True, env=env, cwd=temporary, check=True)
                elapsed = (time.perf_counter_ns() - started) / 1_000_000
                output = json.loads(result.stdout)["hookSpecificOutput"]
                assert output["hookEventName"] == "SessionStart"
                context = output["additionalContext"]
                assert ("was explicitly enabled" in context) == (scenario == "active")
                assert "Enable: " in context and "Disable: " in context
                if scenario == "clear":
                    assert not state.exists()
                return elapsed

            # Independently warm both commands, including their interpreter imports.
            for _ in range(2):
                for label in variants:
                    run(label)
            for pair in range(pairs):
                for label in (("before", "after") if pair % 2 == 0 else ("after", "before")):
                    samples[label].append(run(label))
            results[scenario] = {
                label: {"runs": len(values), "median_ms": statistics.median(values), "min_ms": min(values), "max_ms": max(values), "samples_ms": values}
                for label, values in samples.items()
            }
        return {"baseline": baseline, "order": "alternating AB/BA; two warmups per side per scenario", "failures": 0, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", help="Git revision containing the baseline hook")
    parser.add_argument("--pairs", type=int, default=20)
    args = parser.parse_args()
    if args.pairs < 6 or args.pairs % 2:
        parser.error("--pairs must be an even number of at least 6")
    print(json.dumps(benchmark(args.baseline, args.pairs), indent=2))
