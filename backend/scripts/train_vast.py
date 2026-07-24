"""Run one reviewed YOLO26 training job manually on VAST.

The command requires an existing weight file and an immutable dataset release.
It has no download path, refuses local defaults, and never overwrites a run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from src.experiment_records import validate_experiment_record
from src.metadata_validation import (
    EXPECTED_CLASSES,
    EXPECTED_ONTOLOGY_VERSION,
    EXPECTED_SOURCE_MANIFEST_VERSION,
    load_yaml_mapping,
)
from src.project_paths import PathConfigurationError, ProjectPaths, require_path_within
from src.training_config import APPROVED_MODELS, training_arguments, validate_training_config
from src.validation import validate_environment
from src.splitting import missing_split_classes


RUN_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True, help="Existing .pt file under a remote project root")
    parser.add_argument("--dataset", required=True, help="dataset.yaml inside PROJECT_OUTPUT_ROOT")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--code-revision", required=True, help="Reviewed Git commit identifier")
    parser.add_argument("--smoke", action="store_true", help="Run the approved one-epoch 2 percent smoke test")
    return parser.parse_args()


def _existing_weights(value: str, paths: ProjectPaths) -> Path:
    for root in (paths.data_root, paths.output_root):
        try:
            candidate = require_path_within(value, root)
        except PathConfigurationError:
            continue
        if candidate.is_file() and candidate.suffix == ".pt":
            if candidate.name not in APPROVED_MODELS:
                raise ValueError(f"weight filename must be one of {APPROVED_MODELS}")
            return candidate
    raise ValueError("weights must be an existing approved .pt file under a remote data/output root")


def _validate_dataset_release(dataset_yaml: Path) -> tuple[str, dict[str, Any]]:
    document = load_yaml_mapping(dataset_yaml)
    if "download" in document:
        raise ValueError("dataset.yaml must not contain a download action")
    if "train" not in document or "val" not in document:
        raise ValueError("dataset.yaml must define train and val splits")
    configured_root = document.get("path")
    if (
        not isinstance(configured_root, str)
        or Path(configured_root).expanduser().resolve() != dataset_yaml.parent.resolve()
    ):
        raise ValueError("dataset.yaml path must resolve to its immutable release directory")
    for split_name in ("train", "val"):
        split_directory = require_path_within(document[split_name], dataset_yaml.parent)
        if not split_directory.is_dir():
            raise ValueError(f"dataset {split_name} split is not a directory")
    names = document.get("names")
    if isinstance(names, dict):
        ordered_names = tuple(names[index] for index in sorted(names))
    elif isinstance(names, list):
        ordered_names = tuple(names)
    else:
        raise ValueError("dataset.yaml names must be a list or numeric mapping")
    if ordered_names != EXPECTED_CLASSES:
        raise ValueError(f"dataset label order mismatch: {ordered_names}")

    manifests = dataset_yaml.parent / "manifests"
    audit_path = manifests / "audit_report.json"
    split_path = manifests / "split_manifest.json"
    if not audit_path.is_file() or not split_path.is_file():
        raise ValueError("dataset release is missing its audit or split manifest")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    if audit.get("ok") is not True:
        raise ValueError("dataset audit did not pass")
    if split.get("seed") != 26:
        raise ValueError("dataset split seed must equal the approved seed 26")
    if split.get("leakage_violations") != []:
        raise ValueError("dataset split contains leakage violations")
    distribution = split.get("distribution")
    if not isinstance(distribution, dict):
        raise ValueError("split manifest must record its distribution")
    coverage_failures = missing_split_classes(
        distribution,
        required_splits=("train", "val"),
        required_classes=EXPECTED_CLASSES,
    )
    if coverage_failures:
        raise ValueError(
            "dataset split class coverage failed: "
            + "; ".join(coverage_failures)
        )
    split_version = split.get("split_version")
    if not isinstance(split_version, str) or not split_version.strip():
        raise ValueError("split manifest must record split_version")
    return split_version, document


def _write_record(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if not RUN_PATTERN.fullmatch(args.run_id):
        raise ValueError("run ID must use lowercase letters, digits, dot, dash, or underscore")
    if not args.code_revision.strip() or "replace-before-run" in args.code_revision:
        raise ValueError("code revision must be recorded before training")

    paths = ProjectPaths.from_environment()
    paths.assert_expected_working_directory()
    preflight = validate_environment(paths, require_data=True, require_output=True)
    print(preflight.render())
    if not preflight.ok:
        return 2

    config_path = paths.project_root / "configs" / "training" / "v1_controlled.yaml"
    config = load_yaml_mapping(config_path)
    config_result = validate_training_config(config)
    print(config_result.render("training configuration"))
    if not config_result.ok:
        return 2

    weights = _existing_weights(args.weights, paths)
    dataset_yaml = require_path_within(args.dataset, paths.output_root)
    if not dataset_yaml.is_file() or dataset_yaml.name != "dataset.yaml":
        raise ValueError("dataset must be an existing dataset.yaml under PROJECT_OUTPUT_ROOT")
    split_version, _ = _validate_dataset_release(dataset_yaml)

    run_name = f"{args.run_id}-smoke" if args.smoke else args.run_id
    run_directory = require_path_within(Path("runs") / run_name, paths.output_root, must_exist=False)
    if run_directory.exists():
        raise FileExistsError(f"refusing to overwrite run: {run_directory}")
    plan_directory = require_path_within("run_plans", paths.output_root, must_exist=False)
    plan_directory.mkdir(parents=True, exist_ok=True)
    record_path = plan_directory / f"{run_name}.json"
    if record_path.exists():
        raise FileExistsError(f"refusing to overwrite run record: {record_path}")

    train_args = training_arguments(config, smoke=args.smoke)
    record: dict[str, Any] = {
        "schema_version": "1.0",
        "run_id": run_name,
        "run_kind": "smoke" if args.smoke else "full",
        "status": "running",
        "model": weights.name,
        "ontology_version": EXPECTED_ONTOLOGY_VERSION,
        "source_manifest_version": EXPECTED_SOURCE_MANIFEST_VERSION,
        "split_version": split_version,
        "code_revision": args.code_revision,
        "training": {
            "image_size": train_args["imgsz"],
            "seed": train_args["seed"],
            "deterministic": train_args["deterministic"],
            "epochs": train_args["epochs"],
            "patience": train_args["patience"],
            "batch": train_args["batch"],
            "optimizer": train_args["optimizer"],
            "initial_learning_rate": train_args["lr0"],
            "config_file": "configs/training/v1_controlled.yaml",
            "arguments": train_args,
        },
        "dataset_release": dataset_yaml.parent.name,
        "environment": {
            "execution": "VAST remote Jupyter kernel",
            "python_version": None,
            "ultralytics_version": None,
            "torch_version": None,
            "cuda_version": None,
            "gpu": None,
        },
        "outputs": {"location": f"${{PROJECT_OUTPUT_ROOT}}/runs/{run_name}"},
        "metrics": {},
    }
    record_result = validate_experiment_record(record)
    if not record_result.ok:
        raise ValueError(record_result.render("experiment record"))
    _write_record(record_path, record)

    from ultralytics import YOLO
    import torch

    record["environment"].update(
        {
            "python_version": sys.version.split()[0],
            "ultralytics_version": __import__("ultralytics").__version__,
            "torch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }
    )
    if not torch.cuda.is_available() or "A100" not in str(record["environment"]["gpu"]):
        record["status"] = "failed"
        record["failure"] = "approved NVIDIA A100 device 0 was not available"
        _write_record(record_path, record)
        raise RuntimeError(record["failure"])

    started = time.monotonic()
    try:
        result = YOLO(str(weights)).train(
            data=str(dataset_yaml),
            project=str(paths.output_root / "runs"),
            name=run_name,
            exist_ok=False,
            device=0,
            **train_args,
        )
    except Exception as error:
        record["status"] = "failed"
        record["training_duration_seconds"] = round(time.monotonic() - started, 3)
        record["failure"] = f"{type(error).__name__}: {error}"
        _write_record(record_path, record)
        raise

    record["status"] = "completed"
    record["training_duration_seconds"] = round(time.monotonic() - started, 3)
    raw_metrics = getattr(result, "results_dict", {})
    record["metrics"] = {
        key: float(value) if hasattr(value, "__float__") else value
        for key, value in raw_metrics.items()
    }
    _write_record(record_path, record)
    print(f"completed: {run_name}")
    print(f"record: {record_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
