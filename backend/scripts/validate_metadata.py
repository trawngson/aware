"""Validate repository ontology and source metadata without touching datasets."""

from __future__ import annotations

import sys

from src.metadata_validation import (
    load_yaml_mapping,
    validate_ontology,
    validate_source_manifest,
)
from src.project_paths import ProjectPaths
from src.training_config import validate_training_config


def main() -> int:
    paths = ProjectPaths.from_environment()
    ontology = load_yaml_mapping(paths.project_root / "ontology.yaml")
    manifest = load_yaml_mapping(paths.project_root / "source_manifest.yaml")
    training_config = load_yaml_mapping(
        paths.project_root / "configs" / "training" / "v1_controlled.yaml"
    )

    ontology_result = validate_ontology(ontology)
    manifest_result = validate_source_manifest(
        manifest,
        ontology_version=ontology.get("ontology_version"),
    )
    training_result = validate_training_config(training_config)
    print(ontology_result.render("ontology"))
    print(manifest_result.render("source manifest"))
    print(training_result.render("training configuration"))
    return 0 if ontology_result.ok and manifest_result.ok and training_result.ok else 2


if __name__ == "__main__":
    sys.exit(main())
