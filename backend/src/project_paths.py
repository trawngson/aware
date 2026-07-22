"""Centralized, environment-driven path handling.

The module has safe local defaults and accepts absolute paths only from the
execution environment. It never creates directories, walks a dataset, or
performs network operations.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


LOCAL_PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = Path("tests/fixtures")
DEFAULT_OUTPUT_ROOT = Path("outputs")


class PathConfigurationError(RuntimeError):
    """Raised when required project paths are missing or unsafe to use."""


class UnexpectedWorkingDirectory(PathConfigurationError):
    """Raised when execution is not rooted at the expected project directory."""


def require_path_within(
    candidate: str | os.PathLike[str] | Path,
    root: str | os.PathLike[str] | Path,
    *,
    must_exist: bool = True,
) -> Path:
    """Resolve a path and fail if it escapes the explicit runtime root."""

    resolved_root = Path(root).expanduser().resolve()
    unresolved = Path(candidate).expanduser()
    resolved_candidate = (
        unresolved.resolve()
        if unresolved.is_absolute()
        else (resolved_root / unresolved).resolve()
    )
    if resolved_candidate == resolved_root or not resolved_candidate.is_relative_to(resolved_root):
        raise PathConfigurationError(
            f"path must be a child of {resolved_root}: {resolved_candidate}"
        )
    if must_exist and not resolved_candidate.exists():
        raise PathConfigurationError(f"required path does not exist: {resolved_candidate}")
    return resolved_candidate


def _resolve_path(value: str | os.PathLike[str] | Path, project_root: Path) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (project_root / candidate).resolve()


def _path_from_environment(
    name: str,
    default: Path,
    project_root: Path,
    environ: Mapping[str, str],
) -> Path:
    raw_value = environ.get(name, "").strip()
    return _resolve_path(raw_value or default, project_root)


@dataclass(frozen=True)
class ProjectPaths:
    """Resolved paths for one execution environment.

    Relative environment values are resolved from ``project_root``. This keeps
    local code portable while allowing the remote kernel to provide absolute
    dataset and output locations at runtime.
    """

    project_root: Path
    data_root: Path
    output_root: Path

    @classmethod
    def from_environment(
        cls,
        *,
        project_root: str | os.PathLike[str] | Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> "ProjectPaths":
        env = os.environ if environ is None else environ

        if project_root is not None:
            resolved_project_root = _resolve_path(project_root, LOCAL_PROJECT_ROOT)
        else:
            configured_project_root = env.get("PROJECT_CODE_ROOT", "").strip()
            resolved_project_root = _resolve_path(
                configured_project_root or LOCAL_PROJECT_ROOT,
                LOCAL_PROJECT_ROOT,
            )

        return cls(
            project_root=resolved_project_root,
            data_root=_path_from_environment(
                "PROJECT_DATA_ROOT",
                DEFAULT_DATA_ROOT,
                resolved_project_root,
                env,
            ),
            output_root=_path_from_environment(
                "PROJECT_OUTPUT_ROOT",
                DEFAULT_OUTPUT_ROOT,
                resolved_project_root,
                env,
            ),
        )

    def assert_expected_working_directory(
        self,
        cwd: str | os.PathLike[str] | Path | None = None,
    ) -> None:
        """Fail closed unless ``cwd`` is exactly the configured code root."""

        actual = Path.cwd().resolve() if cwd is None else Path(cwd).expanduser().resolve()
        expected = self.project_root.resolve()
        if actual != expected:
            raise UnexpectedWorkingDirectory(
                "Unexpected working directory: "
                f"expected {expected}, got {actual}. "
                "Set PROJECT_CODE_ROOT in the execution environment and restart "
                "the kernel; local and remote paths are not interchangeable."
            )

    def as_dict(self) -> dict[str, str]:
        """Return resolved paths for logging without reading their contents."""

        return {
            "project_root": str(self.project_root),
            "data_root": str(self.data_root),
            "output_root": str(self.output_root),
        }
