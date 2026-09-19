# Local-only AI project workflow

This directory is the local, code-only project workspace. The parent repository
contains the existing Swift application; do not broaden work into the parent
tree unless the user explicitly asks for a separate change there.

## Hard safety boundary

- Work only inside this local project directory.
- Never access the VAST server directly from Codex.
- Never use or configure SSH, `scp`, `rsync`, `sftp`, a VAST CLI, a Jupyter API
  client, or a Jupyter MCP server for this project.
- Never add remote hosts, Jupyter URLs, tokens, usernames, private paths, or
  credentials to source, configuration, notebooks, logs, or documentation.
- Never include or run `sudo` commands. Do not change server services,
  firewalls, sudo configuration, SSH configuration, or exposed ports.
- Never execute remote commands or delete remote files. Remote notebook cells
  are reviewed and started manually by the developer in Jupyter in Chrome only.
- Do not download or synchronize datasets, checkpoints, model weights, or
  generated training outputs to the Mac.

The project `.codex/config.toml` is deliberately offline, has no MCP servers,
and does not grant Codex remote shell access. Do not weaken those settings.

## Paths and environments

- Use relative paths for local defaults and keep path resolution in
  `src/project_paths.py`.
- Use `PROJECT_DATA_ROOT` for the dataset root and `PROJECT_OUTPUT_ROOT` for
  generated results. `PROJECT_CODE_ROOT` may identify the checked-out code root
  inside the remote kernel.
- Local defaults must use `tests/fixtures` or small synthetic data and
  `outputs`; they must never point at a remote or mounted dataset.
- The VAST environment may set the same variables to existing remote paths,
  but those values must remain outside this local repository and must not be
  copied into committed files.
- Never assume a local filesystem path matches a remote filesystem path.
  Resolve environment-specific paths at runtime and validate the working
  directory before importing or training.

## Data, tests, and generated files

- Keep tests small, deterministic, and runnable without the VAST dataset.
- Prefer synthetic samples or files under `tests/fixtures`; do not add large
  binary fixtures.
- Do not commit credentials, tokens, `.env` files, datasets, checkpoints,
  model weights, WandB state, logs, or generated outputs.
- Treat any remote data path as read-only input unless the user explicitly
  specifies an approved output location and manually reviews the operation.

## Change and verification rules

- Treat the user as the project supervisor. Before making a major project
  decision or starting a major task, present the proposed choice, relevant
  evidence, and tradeoffs, then obtain the user's explicit decision. Routine
  implementation and verification may proceed within the scope of a major task
  the user has already approved.
- Ask before destructive local operations, including deleting files,
  overwriting user data, bulk cleanup, or changing repository history.
- Make path and configuration changes in one central module rather than adding
  hard-coded machine-specific paths to training code or notebooks.
- Before training, run the read-only preflight:
  `python -m scripts.validate_environment`.
- Review every notebook cell before running it against the remote kernel.
  Never add hidden shell execution, automatic uploads, automatic downloads, or
  destructive cleanup to the notebook.

## Git and GitHub identity

- Use the repository's configured user identity for commit authorship and
  committer metadata.
- Use neutral, project-related branch names. Never include `codex`, `sol`,
  `ai`, or another assistant identifier in a branch name.
- Do not add assistant attribution, AI attribution, or assistant co-author
  trailers to commits, branches, pull requests, or push-related metadata unless
  the user explicitly requests it.
- Before publishing, verify the commit identity and remote branch name.

## Remote kernel context

A user-provided kernel snapshot confirmed Python 3.11 and the required ML
packages on VAST. Its hostname, usernames, and machine-specific paths are kept
outside the repository. The snapshot is informational only and does not
authorize direct access. Runtime code must use `PROJECT_CODE_ROOT`,
`PROJECT_DATA_ROOT`, and `PROJECT_OUTPUT_ROOT` supplied by the remote
environment.


