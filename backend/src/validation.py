"""Read-only preflight checks for local and remote-kernel execution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .project_paths import ProjectPaths


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ValidationReport:
    checks: tuple[ValidationCheck, ...]

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def render(self) -> str:
        lines = [f"preflight: {'PASS' if self.ok else 'FAIL'}"]
        for check in self.checks:
            marker = "OK" if check.ok else "ERROR"
            lines.append(f"[{marker}] {check.name}: {check.detail}")
        return "\n".join(lines)


def validate_environment(
    paths: ProjectPaths,
    *,
    cwd: str | Path | None = None,
    require_data: bool = True,
    require_output: bool = False,
) -> ValidationReport:
    """Validate only metadata and directory boundaries; never create or scan data."""

    checks: list[ValidationCheck] = []
    project_root = paths.project_root.resolve()
    actual_cwd = Path.cwd().resolve() if cwd is None else Path(cwd).expanduser().resolve()

    checks.append(
        ValidationCheck(
            "project root",
            project_root.is_dir(),
            str(project_root),
        )
    )
    checks.append(
        ValidationCheck(
            "working directory",
            actual_cwd == project_root,
            f"expected {project_root}; got {actual_cwd}",
        )
    )

    for relative_path in ("src", "configs"):
        candidate = project_root / relative_path
        checks.append(
            ValidationCheck(
                f"project/{relative_path}",
                candidate.is_dir(),
                str(candidate),
            )
        )

    data_root = paths.data_root.resolve()
    output_root = paths.output_root.resolve()
    filesystem_root = Path(data_root.anchor).resolve()
    data_is_safe = data_root not in {project_root, filesystem_root}
    data_exists = paths.data_root.is_dir()
    checks.append(
        ValidationCheck(
            "data root",
            data_exists and data_is_safe if require_data else data_is_safe,
            f"{paths.data_root}"
            + (" (required)" if require_data else " (optional)"),
        )
    )

    output_filesystem_root = Path(output_root.anchor).resolve()
    output_is_safe = output_root not in {project_root, output_filesystem_root}
    output_exists = paths.output_root.is_dir()
    checks.append(
        ValidationCheck(
            "output root",
            output_exists and output_is_safe if require_output else output_is_safe,
            f"{paths.output_root}"
            + (" (required)" if require_output else " (not created by preflight)"),
        )
    )

    roots_are_separate = not (
        data_root == output_root
        or data_root.is_relative_to(output_root)
        or output_root.is_relative_to(data_root)
    )
    checks.append(
        ValidationCheck(
            "data/output separation",
            roots_are_separate,
            "data and output roots must not overlap",
        )
    )

    return ValidationReport(tuple(checks))
