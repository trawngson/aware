from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.project_paths import (
    PathConfigurationError,
    ProjectPaths,
    UnexpectedWorkingDirectory,
    require_path_within,
)
from src.validation import validate_environment


class ProjectPathsTests(unittest.TestCase):
    def test_defaults_are_relative_to_the_local_project_root(self) -> None:
        paths = ProjectPaths.from_environment(environ={})

        self.assertEqual(paths.data_root, paths.project_root / "tests/fixtures")
        self.assertEqual(paths.output_root, paths.project_root / "outputs")

    def test_environment_can_supply_runtime_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            paths = ProjectPaths.from_environment(
                project_root=project_root,
                environ={
                    "PROJECT_DATA_ROOT": str(project_root / "runtime-data"),
                    "PROJECT_OUTPUT_ROOT": "runtime-outputs",
                },
            )

        self.assertEqual(paths.project_root, project_root.resolve())
        self.assertEqual(paths.data_root, (project_root / "runtime-data").resolve())
        self.assertEqual(paths.output_root, (project_root / "runtime-outputs").resolve())

    def test_unexpected_working_directory_fails_closed(self) -> None:
        paths = ProjectPaths.from_environment(environ={})

        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(UnexpectedWorkingDirectory):
                paths.assert_expected_working_directory(temp_dir)

    def test_required_child_path_cannot_escape_runtime_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(PathConfigurationError):
                require_path_within("../escape", temp_dir, must_exist=False)

    def test_overlapping_data_and_output_roots_fail_preflight(self) -> None:
        paths = ProjectPaths.from_environment(
            environ={"PROJECT_OUTPUT_ROOT": "tests/fixtures/generated"}
        )

        report = validate_environment(paths, cwd=paths.project_root)

        self.assertFalse(report.ok)
        self.assertIn("data/output separation", report.render())


if __name__ == "__main__":
    unittest.main()
