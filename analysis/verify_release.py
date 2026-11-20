"""Verify frozen records and optionally regenerate results without changing the release."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {"P1", "P2", "P3", "P4"}
HELDOUT_FILES = (
    "heldout_trials.csv",
    "heldout_router_gpt4o.csv",
    "heldout_screening.csv",
    "heldout_deposit_profiles.csv",
    "heldout_deposit_profiles_extra.csv",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def validate_split(split, task_ids):
    """Require a nonempty, disjoint partition of the measured tasks."""
    groups = []
    for name in ("calibration", "evaluation"):
        ids = split[name]
        require(isinstance(ids, list) and ids, f"Empty or invalid {name} split")
        require(all(type(value) is int for value in ids), f"Non-integer {name} task ID")
        require(len(ids) == len(set(ids)), f"Duplicate task in {name}")
        groups.append(set(ids))
    calibration, evaluation = groups
    require(not calibration & evaluation, "Calibration/evaluation task overlap")
    require(calibration | evaluation == set(task_ids), "Split does not cover measured tasks exactly")
    return calibration, evaluation


def validate_competence(rows, ground_truth):
    """Check provider identities, task coverage and correctness against recorded answers."""
    lookup = {}
    for row in rows:
        key = int(row["task_id"]), row["provider"]
        task_id, provider = key
        require(key not in lookup, f"Duplicate provider/task record: {key}")
        require(provider in PROVIDERS, f"Unknown provider: {provider}")
        require(task_id in ground_truth, f"Unknown measured task: {task_id}")
        require(float(row["truth"]) == ground_truth[task_id], f"Ground truth mismatch: {key}")
        require(row["parsed"] in {"0", "1"}, f"Invalid provider parse flag: {key}")
        require(row["correct"] in {"0", "1"}, f"Invalid provider correctness: {key}")
        answer_correct = row["parsed"] == "1" and float(row["answer"]) == ground_truth[task_id]
        require(int(row["correct"]) == answer_correct, f"Provider answer/score mismatch: {key}")
        lookup[key] = int(row["correct"])
    tasks = {key[0] for key in lookup}
    require(bool(tasks), "No measured tasks")
    require(set(lookup) == {(task, provider) for task in tasks for provider in PROVIDERS},
            "Incomplete provider/task coverage")
    return lookup


def validate_trials(rows, allowed_tasks, competence, label):
    """Check task isolation and scores without dropping unreadable attempts."""
    require(bool(rows), f"No trials in {label}")
    readable = 0
    for number, row in enumerate(rows, 2):
        context = f"{label}:{number}"
        task_id = int(row["task_id"])
        require(task_id in allowed_tasks, f"Task outside allowed split: {context}")
        require(row["parsed"] in {"0", "1"}, f"Invalid parse flag: {context}")
        if row["parsed"] == "0":
            continue
        readable += 1
        provider = row["chosen_provider"]
        require((task_id, provider) in competence, f"Unknown provider/task: {context}")
        outcome = row.get("realised_correct", row.get("correct"))
        require(float(outcome) == competence[task_id, provider], f"Router outcome mismatch: {context}")
        if "chosen_slot" in row:
            order = row["order"].split("|")
            require(len(order) == 4 and set(order) == PROVIDERS, f"Invalid displayed order: {context}")
            slot = row["chosen_slot"]
            require(slot in ("A", "B", "C", "D"), f"Invalid chosen slot: {context}")
            require(order["ABCD".index(slot)] == provider, f"Slot/provider mismatch: {context}")
    return {"attempted": len(rows), "readable": readable}


def verify_integrity(root):
    manifest = json.loads((root / "SHA256SUMS.json").read_text(encoding="utf-8"))
    require(manifest["algorithm"] == "sha256", "Unsupported integrity algorithm")
    files = manifest["files"]
    require(bool(files), "Empty integrity manifest")
    for relative, expected in files.items():
        path = root / relative
        require(path.resolve().is_relative_to(root.resolve()), f"Manifest path escapes release: {relative}")
        require(path.is_file(), f"Missing snapshot file: {relative}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                f"Snapshot checksum mismatch: {relative}")
    return len(files)


def compare_values(actual, expected, label):
    """Compare nested JSON and CSV records, allowing only small numerical roundoff."""
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and actual.keys() == expected.keys(), f"Object keys differ: {label}")
        for key, value in expected.items():
            compare_values(actual[key], value, f"{label}.{key}")
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), f"Row count differs: {label}")
        for index, (left, right) in enumerate(zip(actual, expected)):
            compare_values(left, right, f"{label}[{index}]")
    else:
        try:
            left, right = float(actual), float(expected)
        except (TypeError, ValueError):
            require(actual == expected, f"Value differs: {label}: {actual!r} != {expected!r}")
        else:
            require(math.isfinite(left) and math.isfinite(right), f"Non-finite value: {label}")
            require(math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-9),
                    f"Numerical value differs: {label}: {actual!r} != {expected!r}")


def regenerate_results(root):
    """Execute only the offline analysis in a disposable copy, then compare all tables."""
    expected_files = sorted((root / "results").glob("*"))
    require(bool(expected_files), "No reference results")
    with tempfile.TemporaryDirectory(prefix="agent-registry-verify-") as directory:
        scratch = Path(directory)
        for name in ("analysis", "tasks", "provider_outputs", "router_decisions", "rq1"):
            shutil.copytree(root / name, scratch / name, ignore=shutil.ignore_patterns("__pycache__"))
        try:
            subprocess.run([sys.executable, str(scratch / "analysis" / "analysis.py")],
                           cwd=scratch, check=True, capture_output=True, text=True, timeout=180)
        except subprocess.CalledProcessError as error:
            raise ValueError(f"Offline analysis exited {error.returncode}: {error.stderr[-4000:]}") from error
        require({path.name for path in expected_files} == {path.name for path in (scratch / "results").iterdir()},
                "Generated result file set differs")
        for reference in expected_files:
            actual = scratch / "results" / reference.name
            if reference.suffix == ".json":
                compare_values(json.loads(actual.read_text()), json.loads(reference.read_text()), reference.name)
            elif reference.suffix == ".csv":
                compare_values(read_csv(actual), read_csv(reference), reference.name)
            else:
                raise ValueError(f"Unsupported result format: {reference.name}")
    return len(expected_files)


def verify(root=ROOT, regenerate=False):
    root = Path(root)
    integrity_count = verify_integrity(root)
    tasks = json.loads((root / "tasks" / "market_ground_truth.json").read_text())["tasks"]
    truth = {task["task_id"]: task["truth"] for task in tasks}
    require(len(truth) == len(tasks), "Duplicate ground-truth task ID")
    competence = validate_competence(read_csv(root / "provider_outputs" / "pop2_competence.csv"), truth)
    measured = {key[0] for key in competence}
    split = json.loads((root / "tasks" / "heldout_split.json").read_text())
    calibration, evaluation = validate_split(split, measured)
    trials = {name: validate_trials(read_csv(root / "router_decisions" / name), evaluation, competence, name)
              for name in HELDOUT_FILES}
    trials["burnin_trials.csv"] = validate_trials(
        read_csv(root / "router_decisions" / "burnin_trials.csv"), calibration, competence, "burnin_trials.csv")
    result = {
        "status": "passed",
        "snapshot_files_checked": integrity_count,
        "calibration_tasks": len(calibration),
        "evaluation_tasks": len(evaluation),
        "ground_truth_tasks_without_measurements": sorted(set(truth) - measured),
        "trial_checks": trials,
        "regenerated_result_files": regenerate_results(root) if regenerate else 0,
        "scope": "Released-record consistency and optional offline numerical reproduction. "
                 "Does not establish preregistration, independently validate task generation, "
                 "rerun hosted models, or establish causal real-market effects.",
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regenerate", action="store_true", help="Recompute tables in a temporary directory")
    args = parser.parse_args()
    try:
        result = verify(regenerate=args.regenerate)
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
