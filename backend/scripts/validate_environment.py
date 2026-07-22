"""Run the non-destructive project preflight.

This command checks the configured code, data, and output roots. It does not
create directories, enumerate dataset contents, start training, or use a
network connection.
"""

from __future__ import annotations

import sys

from src.project_paths import ProjectPaths
from src.validation import validate_environment


def main() -> int:
    paths = ProjectPaths.from_environment()
    report = validate_environment(paths)
    print(report.render())
    print("resolved paths:")
    for name, value in paths.as_dict().items():
        print(f"  {name}: {value}")
    return 0 if report.ok else 2


if __name__ == "__main__":
    sys.exit(main())
