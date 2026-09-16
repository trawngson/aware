# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

Two largely independent projects share this repo:

- **iOS app** (repo root): SwiftUI app `awareapp` (iOS 18.4, Swift 5) that detects waste on-device with an Ultralytics YOLO Core ML model and shows recycling guidance. Tabs: Home, Scan, Gallery, plus a first-launch onboarding sheet.
- **`backend/`**: a Python dataset and training pipeline (TACO + Open Images → a frozen 7-class ontology → YOLO training → Core ML export). Recent commits are almost all here. Real data and training live on a remote VAST GPU server; this Mac holds only code, metadata, and tiny fixtures.

`test_set/` holds target-domain test-set labeling work (MakeSense labels, `review_returned_labels.py`). `demo/` and `output/` are untracked media and PDFs.

## Commands

### iOS app (run from repo root)

```bash
xcodebuild -resolvePackageDependencies -project awareapp.xcodeproj
xcodebuild -project awareapp.xcodeproj -scheme awareapp -configuration Debug \
  -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.4' build
xcodebuild -project awareapp.xcodeproj -scheme awareapp \
  -destination 'platform=iOS Simulator,name=iPhone 16,OS=18.4' test
# Single test: add -only-testing:awareappTests/awareappTests/example
#          or  -only-testing:awareappUITests/awareappUITests/testExample
```

There is no SwiftLint, formatter, or Makefile; use compiler diagnostics. The simulator has no camera stream, so the camera and live inference must be tested on a physical device. The test targets contain only Xcode-generated scaffolding.

### Backend (run from `backend/`)

```bash
python3 -m unittest discover -s tests          # full suite (61 tests, <1s, fixtures only)
python3 -m unittest tests.test_project_paths    # one module
python3 -m unittest tests.test_pipeline.MappingAndAdapterTests.test_mapping_ledger_is_valid  # one test
python3 -m scripts.validate_metadata            # ontology / manifest / training config
python3 -m scripts.validate_environment         # read-only preflight, required before training
```

There is no requirements file. Third-party imports are `yaml`, `PIL`, and (VAST-only) `torch` and `ultralytics`. `scripts.prepare_dataset`, `scripts.download_open_images_training`, `scripts.train_vast`, and `scripts.export_coreml` are **VAST-only**: never run them locally.

## iOS app architecture

- `awareappApp.swift` → `ContentView`, which owns the root `TabView` and uses `@AppStorage("hasSeenOnboarding")` to decide whether to show onboarding. `NavigationManager.shared` (a `@MainActor` singleton) drives tab switches between features.
- **Scan flow:** `ScanTabView` embeds `Components/CleanYOLOCamera`, a `UIViewRepresentable` around `YOLOView` that loads the bundled model `aware` (`aware.mlpackage`). Detections are filtered by confidence and trimmed to the top 3. A stable, high-confidence detection triggers a timer and navigates to `ScanResultsView`. Leaving the tab pauses inference and cancels the timers. `ScanResultsView` maps the label through `Models/ItemInfo` to guidance and points, and "Add to Gallery" creates a post in `GalleryStore`, then switches tabs.
- `GalleryStore.shared` holds all gallery state in memory only: no persistence, accounts, or backend sync. Home, insights, and leaderboard data are hard-coded demo values inside the views.
- **YOLO code comes from two sources:** the remote SPM `YOLO` package (Ultralytics `main`) provides `YOLOView`, `YOLOResult`, and related types, and `UltralyticsYOLO/` is a local copy of the sources pulled in through a filesystem-synchronized group. They are not interchangeable. Before changing detection behavior, decide which one (or the app adapter) the change belongs in. Other SPM dependencies are `OnboardingKit` and `Expandable`.
- The project uses filesystem-synchronized groups, so new Swift files under the source directories join the target automatically. `NSCameraUsageDescription` comes from the build settings and must be preserved.
- `Models/ItemInfo.swift` currently maps labels with substring checks (`contains("plastic")`, `contains("can")`, …), so e.g. `plastic_bag` gets bottle guidance, and its categories don't match the 7 backend classes. `backend/SPECIFICATION.md` §5.3 and §13 require an explicit canonical-label→policy table, kept separate from the detector, from a policy layer, and from a reward layer that awards at most once per scan event. Follow that spec when changing this logic.

## Backend architecture

The pipeline is metadata-driven and fail-closed. It is governed by versioned YAML files at the `backend/` root, validated against `schemas/*.schema.json`:

- `ontology.yaml`: frozen `aware-ontology-v3` with 7 classes (`plastic_bottle, glass_container, metal_can, cardboard, plastic_bag, disposable_cup, styrofoam`). **Numeric IDs are never reordered or reused**, and changes are recorded as errata or retirement records in `records/`. `unknown`/`abstain` are runtime outcomes, not classes.
- `source_manifest.yaml`: the approved sources (`taco-v1.0`, `open-images-v7-waste-subset`), with pinned URLs and versions.
- `mapping_ledger.yaml`: each source class gets an action (`keep | safe_merge | manual_review | reject`) and a `review_status`. Broad source classes are never auto-mapped to narrower canonical ones. Only approved mappings are included. Tests assert the approved decisions, so changing a mapping means updating the tests too.
- `configs/training/v1_controlled.yaml`: the approved training recipe, validated by `src/training_config.py`.

Data flow in `scripts/prepare_dataset.py`:
`src/adapters.py` (TACO COCO JSON / Open Images CSV → `canonical_data` records, keeping original and mapped labels) → `mappings.py` (apply the ledger) → `box_policy.py` (minimum box size at the 640px view; undersized boxes are held back) → `audit.py` (boxes finite and in bounds, valid class IDs) → `release.py` (exact and perceptual hashing via `dedup.py`) → `splitting.py` (group-aware splits and leakage checks) → an immutable YOLO release under `PROJECT_OUTPUT_ROOT/datasets/<release_id>` that refuses to overwrite an existing release. `image_files.py` applies EXIF orientation without modifying raw files. Open Images has its own gated stages: `open_images_preflight` (metadata only) → `open_images_review` (visual review sheets) → `open_images_training_selection` → `open_images_acquisition` (resumable, integrity-checked). `parity.py` checks server-vs-Core ML output parity after export.

**Paths:** all path resolution goes through `src/project_paths.py`, which reads `PROJECT_CODE_ROOT`, `PROJECT_DATA_ROOT`, and `PROJECT_OUTPUT_ROOT`. Locally these default to `tests/fixtures` and `outputs`. Use `require_path_within` for any user-supplied path, and never hard-code machine-specific or remote paths.

`SPECIFICATION.md` is the authoritative spec, organized as acceptance gates 0–8. `WORKFLOW_CHECKLIST.md` and `PAPER_PRETRAINING_CHECKLIST.md` track phase progress, and `VAST_RUNBOOK.md` and `SETUP.md` cover remote execution.

## Rules from `backend/AGENTS.md` (these apply to Claude as well)

- **Never access VAST directly.** Do not use SSH, scp, rsync, a VAST CLI, a Jupyter API, or an MCP server; do not use `sudo`; never write hostnames, Jupyter URLs, tokens, or private paths into any file. The developer runs remote cells by hand in VS Code (`notebooks/remote_execution.ipynb`). Do not download datasets, weights, or outputs to the Mac.
- Keep tests small and deterministic, running only on `tests/fixtures` or synthetic data. Never add large binaries.
- Treat the user as project supervisor: before a **major** decision or task (ontology, source, or mapping approvals, recipe changes), present the options, evidence, and tradeoffs, and wait for an explicit decision. Ask before any destructive local operation.
- **Git:** branch names must not contain `codex`, `ai`, or any other assistant identifier. **Do not add AI or assistant attribution or `Co-Authored-By` trailers** to commits or PRs unless the user explicitly asks.

## Instructions for the user (from root `AGENTS.md`)

For any VAST, server, notebook, dataset, training, export, or deployment operation, give the user explicit numbered steps suitable for a high-school senior:
- Put commands in copyable code blocks and show the expected result for each step.
- Give one VAST operation at a time and wait for its output before giving the next.
- Prefix every one-line command with `cd /mnt/data/Son/notebook/AWARE &&`.
- Pass `PROJECT_CODE_ROOT`, `PROJECT_DATA_ROOT`, and `PROJECT_OUTPUT_ROOT` inline to each Python process, because they don't persist between terminals.
- Embed checksum and other machine-checkable verification in the commands so they abort on mismatch. Never ask the user to compare output by eye.
- Print progress during long silent operations.
- Put artifacts the user needs to see in a visible folder such as `server_outputs/`, never in a dot-directory.

## Paper

For any request about the AWARE paper, first read `PAPER.md` and the canonical Google Doc it links, which is the source of truth. Use `backend/PAPER_NOTES.md` as supporting context, and point out any conflicts rather than silently resolving them.
