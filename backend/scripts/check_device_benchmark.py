"""Check one on-device benchmark run file against the iPhone XR limits.

The run file comes from the app's benchmark mode (the "awareapp Benchmark"
scheme) and is copied into PROJECT_OUTPUT_ROOT/device_benchmarks/. The result is
written next to it as <run>.<protocol record>.check.json and is never
overwritten. Runs checked before v2 have results named <run>.check.json.

Usage (from backend/):
  python3 -m scripts.check_device_benchmark device_benchmarks/<run>.json [--protocol records/...yaml]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.dedup import sha256_file
from src.device_benchmark import evaluate_run
from src.metadata_validation import load_yaml_mapping
from src.project_paths import ProjectPaths, require_path_within


PROTOCOL = Path("records") / "device-benchmark-protocol-v2.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="run file, relative to PROJECT_OUTPUT_ROOT")
    parser.add_argument("--protocol", default=str(PROTOCOL), help="protocol record, relative to backend/")
    args = parser.parse_args()

    paths = ProjectPaths.from_environment()
    protocol_path = require_path_within(paths.project_root / args.protocol, paths.project_root / "records")
    protocol = load_yaml_mapping(protocol_path)
    if protocol.get("status") != "approved":
        raise SystemExit(f"{args.protocol} is {protocol.get('status')!r}; runs are scored only after it is approved")

    run_path = require_path_within(args.run, paths.output_root)
    result_path = run_path.with_name(f"{run_path.stem}.{protocol['record']}.check.json")
    if result_path.exists():
        raise SystemExit(f"refusing to overwrite {result_path}")

    run = json.loads(run_path.read_text(encoding="utf-8"))
    report = evaluate_run(run, protocol)
    print(f"protocol: {protocol['record']}")
    print(f"run: {run_path.name} ({run.get('run_id')})")
    print(f"device: {run.get('device', {}).get('machine')} iOS {run.get('device', {}).get('system_version')}")
    print(report.render())

    result = {
        "protocol": protocol["record"],
        "run_file": run_path.name,
        "run_file_sha256": sha256_file(run_path),
        "run_file_bytes": run_path.stat().st_size,
        "run_id": run.get("run_id"),
        "started_at": run.get("started_at"),
        "status": run.get("status"),
        "device": run.get("device"),
        "app": run.get("app"),
        "model": run.get("model"),
        "operator_input": run.get("operator_input"),
        **report.to_json(),
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"result: {result_path}")
    return 2 if report.verdict == "INVALID" else 0


if __name__ == "__main__":
    sys.exit(main())
