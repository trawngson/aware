<a id="readme-top"></a>
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]


<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/trawngson/aware">
    <img src="https://i.postimg.cc/8CGwknJM/App-Icon-ios-marketing.png" alt="Logo" width="160" height="160">
  </a>

<h3 align="center">AWARE (AI Waste-sorting and Recycling Enhancement)</h3>

  <p align="center">
    Recycling made simple. Point your camera at an item, get the sorting answer offline, and earn your streak.
    <br />
    <br />
    <a href="#getting-started">Getting Started</a>
    ·
    <a href="https://github.com/trawngson/aware/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/trawngson/aware/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>


<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about-the-project">About The Project</a></li>
    <li><a href="#features">Features</a></li>
    <li><a href="#built-with">Built With</a></li>
    <li><a href="#repository-layout">Repository Layout</a></li>
    <li><a href="#how-detection-works-on-device">How Detection Works On Device</a></li>
    <li><a href="#the-shipped-model">The Shipped Model</a></li>
    <li>
      <a href="#the-training-pipeline-backend">The Training Pipeline (backend/)</a>
      <ul>
        <li><a href="#governing-documents">Governing documents</a></li>
        <li><a href="#ontology-v3">Ontology v3</a></li>
        <li><a href="#approved-data-sources">Approved data sources</a></li>
        <li><a href="#pipeline-stages">Pipeline stages</a></li>
        <li><a href="#command-reference">Command reference</a></li>
        <li><a href="#environment-variables-and-profiles">Environment variables and profiles</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#run-the-ios-app">Run the iOS app</a></li>
        <li><a href="#run-the-backend-locally">Run the backend locally</a></li>
      </ul>
    </li>
    <li><a href="#project-status">Project Status</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>


<!-- ABOUT THE PROJECT -->
## About The Project
<p align="center">
<img src="https://i.postimg.cc/zX1kFc7d/Clean-Shot-2026-06-10-at-12-12-06-2x.png" alt="Login (Dark)" width="200"/>
<img src="https://i.postimg.cc/tTxhh3xb/Clean-Shot-2026-06-10-at-12-14-00-2x.png" alt="Login (Light)" width="200"/>
<img src="https://i.postimg.cc/26Z44QZf/Clean-Shot-2026-06-10-at-12-14-17-2x.png" alt="Homepage" width="200"/>
<img src="https://i.postimg.cc/k5ZQ61Bg/Clean-Shot-2026-06-10-at-12-14-23-2x.png" alt="Log" width="200"/>
</p>

**AWARE** is a native iOS application that classifies household waste from a live camera
feed and tells you how to dispose of it. Detection runs **entirely on device** through a
Core ML export of an Ultralytics YOLO model — there is no inference server, no upload of
camera frames, and the Scan tab works with the network off.

Around that core, the app adds the parts that make sorting a habit rather than a lookup:
a dashboard with streaks and weekly comparisons, waste and CO₂ insights, a leaderboard,
and a community gallery where a scan can be posted as an upcycling idea.

The repository holds two halves that are developed together but run in completely
different places:

| Half | Location | Language | Runs on |
| --- | --- | --- | --- |
| The app | `awareapp/`, `UltralyticsYOLO/`, `aware.mlpackage` | Swift / SwiftUI | iPhone and iPad (iOS 18.4+) |
| The dataset and training pipeline | `backend/` | Python 3.11+ | A remote GPU host (VAST), never the phone |

The `backend/` half is not a web API. It is an auditable data pipeline: every class, every
source dataset, and every source-label-to-AWARE-class mapping is written down, reviewed,
and frozen in version-controlled YAML before a single image is downloaded or a single
epoch is trained.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Features

### 📷 Scan
* Real-time object detection over the camera preview, offline, via Core ML + Vision.
* The Ultralytics debug overlay is hidden behind a custom viewfinder (`CleanYOLOCamera`),
  so the user sees a clean pulsing frame instead of raw boxes.
* **Two ways to confirm a detection**: an immediate confirm above `0.75` confidence, or a
  detection that stays stable on the same label for `1.0 s` above the `0.40` display
  threshold. This avoids the flicker of a label changing every frame.
* The confirmed frame is captured clean (no overlays) and carried into the result screen.
* The result screen shows the item name, category, leaf points, an expandable description,
  and numbered disposal instructions.

### 🏠 Home
* Welcome header with leaf-point balance and avatar.
* Dashboard cards: items scanned, weekly streak, weekly comparison, community impact,
  recent activity, and a rotating environmental fact.
* **Waste insights** and **CO₂ insights** screens with hand-rolled SwiftUI charts —
  donut, bar, and line — over weekly/monthly series.
* **Leaderboard** and a user options screen.

### 🖼 Gallery
* A feed of upcycling ideas with likes, saves, and replies, backed by an observable
  `GalleryStore`.
* **Scan → Gallery hand-off**: "Add to Gallery" on a scan result pushes the captured
  image and item name into the composer and switches tabs, with the composer pre-expanded.

### 👋 Onboarding
* A first-launch sheet (OnboardingKit + PageView), gated on an `@AppStorage`
  `hasSeenOnboarding` flag.

> **Note on data**: the Home, Insights, Gallery, and Leaderboard screens currently render
> from in-memory sample data (`SampleData`, `GalleryPost.sample`) and reset on launch.
> There is no account system, backend service, or persistence layer yet — see
> [Project Status](#project-status).

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Built With

* [![Swift][Swift]][Swift-url]
* [![SwiftUI][SwiftUI]][SwiftUI-url]
* [![CoreML][CoreML]][CoreML-url]
* [![YOLO][YOLO]][YOLO-url]
* [![Python][Python]][Python-url]

Swift package dependencies (resolved automatically by Xcode via SPM):

| Package | Version | Used for |
| --- | --- | --- |
| [ultralytics/yolo-ios-app](https://github.com/ultralytics/yolo-ios-app) | `main` | `YOLOView`, camera capture, NMS, result types |
| [danielsaidi/OnboardingKit](https://github.com/danielsaidi/OnboardingKit) | 9.1.0 | First-launch onboarding flow |
| [ryanashcraft/Expandable](https://github.com/ryanashcraft/Expandable) | 1.0.0 | Expandable item descriptions |
| [danielsaidi/PageView](https://github.com/danielsaidi/PageView) | 0.2.0 | Transitive via OnboardingKit — paged onboarding screens |
| [weichsel/ZIPFoundation](https://github.com/weichsel/ZIPFoundation) | 0.9.20 | Transitive via the YOLO package — model download/unpack |

`UltralyticsYOLO/` is a vendored copy of the Ultralytics Swift sources (AGPL-3.0) kept in
tree so the camera view can be patched locally.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Repository Layout

```text
aware/
├── awareapp/                       # The SwiftUI application
│   ├── awareappApp.swift           #   @main entry point
│   ├── ContentView.swift           #   Root TabView: Home / Scan / Gallery
│   ├── NavigationManager.swift     #   Shared cross-tab navigation (singleton)
│   ├── Assets.xcassets/            #   App icon, sample and project images
│   └── Views/
│       ├── Scan/                   #   Camera, detection, result screen
│       │   ├── ScanTabView.swift   #     Detection state machine and thresholds
│       │   ├── ScanResultsView.swift
│       │   ├── Models/             #     YOLODetection, ItemInfo, LabelMappings
│       │   └── Components/         #     CleanYOLOCamera, PulsingViewfinder, cards
│       ├── Home/                   #   Dashboard, Insights, Leaderboard, UserOptions
│       ├── Gallery/                #   Feed, composer, post cards, GalleryStore
│       └── Onboarding/
├── UltralyticsYOLO/                # Vendored Ultralytics Swift package (AGPL-3.0)
├── aware.mlpackage/                # The shipped Core ML detector (~19 MB, FP16)
├── awareapp.xcodeproj/             # Xcode project, schemes, SPM pins
├── awareappTests/ awareappUITests/ # XCTest targets (currently scaffolding)
└── backend/                        # Dataset governance and training pipeline
    ├── ontology.yaml               #   Frozen class definitions (aware-ontology-v3)
    ├── source_manifest.yaml        #   Approved sources, licenses, limitations
    ├── mapping_ledger.yaml         #   Source label → AWARE class decisions
    ├── schemas/                    #   JSON Schemas for the three documents above
    ├── configs/                    #   local.toml, vast.example.toml, training recipe
    ├── records/                    #   Experiment record template and retirements
    ├── scripts/                    #   Manually-run entry points (see command table)
    ├── src/                        #   Library modules used by the scripts
    ├── notebooks/                  #   Remote read-only preflight notebook
    └── tests/                      #   ~60 pytest cases over the pipeline
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## How Detection Works On Device

```text
AVCaptureSession ──▶ YOLOView (vendored Ultralytics)
                      │  Core ML request on aware.mlpackage, 640×640, end-to-end NMS
                      ▼
                  YOLOResult ──▶ CleanYOLOCamera.onDetection
                                   │  filter conf > 0.40, keep the top box
                                   ▼
                              ScanTabView state machine
                                   ├─ conf ≥ 0.75            ──▶ confirm immediately
                                   └─ same label for ≥ 1.0 s ──▶ confirm
                                   ▼
                          captureCurrentFrame() (clean, overlay-free)
                                   ▼
                    ScanResultsView ──▶ ItemInfo.info(for:) ──▶ name, category,
                                        leaf points, description, instructions
                                   └──▶ "Add to Gallery" ──▶ GalleryStore + tab switch
```

The tuning constants live at the top of `awareapp/Views/Scan/ScanTabView.swift`:

| Constant | Value | Meaning |
| --- | --- | --- |
| `confidenceThreshold` | `0.40` | Below this a detection is ignored entirely |
| `autoConfirmThreshold` | `0.75` | At or above this the result screen opens at once |
| `stableDetectionDuration` | `1.0 s` | How long a mid-confidence label must hold |

The camera session is paused whenever the Scan tab is inactive or the result screen is
open, so the app does not hold the camera or drain battery in the background.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## The Shipped Model

`aware.mlpackage` is the detector currently bundled with the app.

| Property | Value |
| --- | --- |
| Architecture | Ultralytics **YOLO26s**, detection task |
| Export | Core ML, FP16, `batch=1`, `nms=False`, `end2end=True` |
| Input | `image`, 640 × 640 × 3, stride 32 |
| Package size | ~19 MB |
| Converted | 2026-04-15 with coremltools 9.0 from `torch 2.9.0+cu128` |
| Trained on | `awarev5-1/data.yaml` (the legacy exploratory merge) |
| Classes (13) | `battery`, `disposable cup`, `glass`, `metal can`, `organics`, `plastic bag`, `plastic bottle`, `plastic bottle cap`, `plastic container`, `plastic cutlery`, `straw`, `styrofoam`, `toothbrush` |
| License | AGPL-3.0 (Ultralytics) |

> ⚠️ **This model predates the governed pipeline.** Its 13 labels come from the legacy
> merge recorded in `source_manifest.yaml` as `legacy-unidentified-merge-v5.1` — a source
> whose exact projects, versions, licenses, and splits are *unrecoverable*, which is why
> it is marked `excluded` and preserved only as non-reproducible evidence. The reviewed
> ontology below (7 classes) is what the next release trains against, and
> `awareapp/Views/Scan/Models/LabelMappings.swift` still maps the 13 legacy labels. Expect
> the label set to change when the v3 model lands.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## The Training Pipeline (`backend/`)

The pipeline is built around one rule: **nothing enters training that has not been written
down and approved first.** Scripts are run manually, raw data is immutable, releases are
never overwritten, and every stage is reproducible from the committed YAML.

### Governing documents

| File | Version | What it fixes |
| --- | --- | --- |
| `ontology.yaml` | `aware-ontology-v3` (frozen 2026-07-23) | Class IDs, definitions, positive/negative examples, and the global annotation rules for occlusion, truncation, damage, contamination, piles, ambiguity, and minimum visibility |
| `source_manifest.yaml` | `aware-sources-v3` | Every dataset with its owner, pinned URL/commit, license and verification status, checksums, expected bytes, counts, and known limitations |
| `mapping_ledger.yaml` | `aware-mappings-v3` | Each source class routed to `safe_merge`, `manual_review`, or `reject`, with a written reason and a review status |
| `configs/training/v1_controlled.yaml` | `aware-yolo26-v1-controlled` | The approved hyperparameters, the smoke-test recipe, and the two models to compare |
| `records/experiment.template.yaml` | — | The record every training run must fill in (code revision, split version, versions, metrics, checkpoint hash, resource usage) |

All three of the first documents are machine-validated against `schemas/*.schema.json`
before use, and IDs are contiguous from zero and never reused.

### Ontology v3

Seven classes, chosen because each one can be told apart from the others by looking at it:

| ID | Class | Definition |
| --- | --- | --- |
| 0 | `plastic_bottle` | A rigid plastic bottle with a neck narrower than its body |
| 1 | `glass_container` | A glass bottle or jar made to hold household contents |
| 2 | `metal_can` | An aluminum or steel food, beverage, or household product can |
| 3 | `cardboard` | Corrugated or paperboard box material and recognizable packaging made from it |
| 4 | `plastic_bag` | A flexible plastic carrier bag, produce bag, pouch, or film bag |
| 5 | `disposable_cup` | A single-use drinking cup of paper, plastic, or foam |
| 6 | `styrofoam` | Expanded polystyrene foam packaging, foodware, or identifiable pieces |

`unknown`, `abstain`, and `no_detection` are **runtime outcomes, not classes** — the model
is never trained to predict them.

Two classes were deliberately dropped rather than trained badly, and the reasons are
recorded in `records/ontology-v*-retirement.yaml`:

* **battery** — TACO provides only two boxes.
* **plastic_container** — its narrow approved mapping yielded only 17 accepted boxes, and
  merging the broader "Disposable food container" class would have mixed plastic, foam,
  molded fiber, and unclear examples.

### Approved data sources

| Source | Role | Status | Notes |
| --- | --- | --- | --- |
| **TACO v1.0** (pinned commit `ad8a693`) | training | approved, raw files verified | CC BY 4.0 · 1,500 images / 4,784 annotations · outdoor litter domain |
| **Open Images V7** (waste subset) | training | approved for acquisition | Only `Plastic bag → plastic_bag` and `Tin can → metal_can` are accepted; `Bottle` and `Box` were **rejected** as materially ambiguous |
| **aware-smartphone-test-v1** | target test | planned | A new, frozen, handheld-domain test set — ≥ 10 images per class, ≥ 70 total, no augmentation, never trained on |
| **legacy-unidentified-merge-v5.1** | legacy evidence | excluded | Unrecoverable provenance; kept only as a non-reproducible baseline |

### Pipeline stages

```text
 metadata validation ──▶ preflight ──▶ mapping review ──▶ selection ──▶ acquisition
        (YAML)            (no pixels)   (contact sheets)   (metadata)     (pixels)
                                                                            │
                                                                            ▼
   Core ML export ◀── training ◀── immutable release ◀── split ◀── adapt + audit
     (+ parity)       (VAST GPU)     (YOLO layout)    (group-aware)  (canonical records)
```

1. **Validate metadata** — ontology, manifest, ledger, and training config are checked
   before anything else runs.
2. **Preflight** (`src/open_images_preflight.py`) — downloads *only* official CSV metadata
   and builds a bounded, seeded sample so class decisions can be made without pixels.
3. **Mapping review** (`src/mapping_review.py`, `src/open_images_review.py`) — renders
   deterministic contact sheets (seed 26) so each candidate source class is accepted or
   rejected by eye, and the verdict is written back to the ledger.
4. **Selection** (`src/open_images_training_selection.py`) — picks the approved training
   rows from official metadata, still without downloading images.
5. **Acquisition** (`src/open_images_acquisition.py`) — resumable, retrying, MD5/ETag-
   verified download of exactly the selected pixels into a read-only raw directory.
6. **Adaptation** (`src/adapters.py`) — TACO COCO polygons and Open Images CSV rows are
   converted into one canonical, source-traceable record type (`src/canonical_data.py`),
   applying the ledger, the box policy, and the Open Images attribute rejections.
7. **Box policy** (`src/box_policy.py`) — reproduces the ontology's minimum-size rule at
   the letterboxed 640 px training view; undersized boxes are held for review, not silently
   trained.
8. **Audit and dedup** (`src/audit.py`, `src/dedup.py`) — read-only checks plus SHA-256
   exact and dHash perceptual duplicate grouping.
9. **Split** (`src/splitting.py`) — deterministic **group-aware** train/val/test assignment
   using connected duplicate groups, with explicit leakage detection, per-class
   distribution summaries, and a missing-class check.
10. **Release** (`src/release.py`) — writes an immutable YOLO-layout dataset release with
    per-image hashes; existing releases are never overwritten.
11. **Train** (`scripts/train_vast.py`) — one reviewed YOLO26 run: 640 px, 200 epochs,
    patience 40, batch 64, AdamW, `lr0 = 0.001`, seed 26, deterministic, AMP, with a
    1-epoch / 2 % smoke test first. `yolo26n` and `yolo26s` are compared under identical
    settings; going to 300 epochs requires new approval.
12. **Export and verify** (`scripts/export_coreml.py`, `src/parity.py`) — FP16 Core ML
    export capped at 25 MB, with label-order validation and IoU-based server-to-Core-ML
    prediction parity checks.

### Command reference

Every command is run manually, from `backend/`, and is read-only unless stated otherwise.

| Command | What it does |
| --- | --- |
| `python -m scripts.validate_environment` | Non-destructive preflight: resolves the three roots, creates nothing, touches no network |
| `python -m scripts.validate_metadata` | Validates `ontology.yaml`, `source_manifest.yaml`, and the training config |
| `python -m scripts.preflight_open_images` | Downloads official Open Images metadata and prepares the class review |
| `python -m scripts.create_open_images_mapping_review` | Builds bounded Open Images review sheets from an approved preflight |
| `python -m scripts.create_taco_mapping_review --review-id … --annotations … --images …` | Builds deterministic TACO contact sheets for proposed mappings |
| `python -m scripts.select_open_images_training` | Selects approved training rows from official metadata (no pixels) |
| `python -m scripts.download_open_images_training` | Acquires the selected pixels with retries and integrity checks |
| `python -m scripts.prepare_dataset` | **Writes** a new immutable canonical YOLO release under `PROJECT_OUTPUT_ROOT/datasets` |
| `python -m scripts.train_vast` | **Writes** one reviewed training run; refuses local defaults and never overwrites a run |
| `python -m scripts.export_coreml` | **Writes** one FP16 Core ML export from a selected checkpoint |
| `python -m pytest` | Runs the pipeline test suite |

### Environment variables and profiles

Paths are never hard-coded. `src/project_paths.py` resolves three variables and fails
closed if execution is rooted anywhere but the configured code root:

| Variable | Default (local) | Purpose |
| --- | --- | --- |
| `PROJECT_CODE_ROOT` | the `backend/` directory | Where the code lives; the working directory must match it exactly |
| `PROJECT_DATA_ROOT` | `tests/fixtures` | Read-only raw data |
| `PROJECT_OUTPUT_ROOT` | `outputs` | The only writable location |

Every path argument passed to a script is resolved with `require_path_within(...)`, so a
path that escapes its declared root is rejected instead of followed.

Two profiles ship with the repo: `configs/local.toml` (fixtures only, validation-only,
8 samples) and `configs/vast.example.toml` (a placeholder template containing no server,
username, or token). On the GPU host, training runs inside a locked-down kernel launched
by `scripts/aware_isolated_kernel.sh` — a root-owned launcher that bubblewraps the
filesystem, drops to an unprivileged UID/GID, clears capabilities, sets `no_new_privs`,
and only then starts Python.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- GETTING STARTED -->
## Getting Started

### Supported Devices
AWARE currently supports:
- iOS 18.4+
- iPadOS 18.4+ (`TARGETED_DEVICE_FAMILY = 1,2`)

A **physical device** is required for the Scan tab — the Simulator has no camera.

### Run the iOS app

#### Prerequisites

| Requirement | Version |
| --- | --- |
| macOS | 14.0 (Sonoma) or later |
| Xcode | 16.3 or later (needs the iOS 18.4 SDK) |
| Swift | 5.0 language mode or later |
| Apple ID | Any free account works for signing a development build |

#### Installation & setup

**1. Clone the repository**

```bash
git clone https://github.com/trawngson/aware.git
cd aware
```

**2. Open the project in Xcode**

```bash
open awareapp.xcodeproj
```

**3. Let Swift Package Manager resolve**

Xcode resolves the five pinned packages listed in
[Built With](#built-with) on first open. Wait for the process to finish before building
(*File ▸ Packages ▸ Resolve Package Versions* if it does not start on its own).

**4. Set your signing team**

Select the `awareapp` target ▸ *Signing & Capabilities* ▸ choose your team. The bundle ID
`net.nctson.awareapp` is already taken, so change it to something of your own.

#### Running the application
1. Pick a run destination in the scheme dropdown — a connected iPhone or iPad for the full
   experience, or a Simulator if you only need Home and Gallery.
2. Press <kbd>⌘</kbd> + <kbd>R</kbd> to build and run.
3. Grant the camera permission when prompted, then open the **Scan** tab.
4. Press <kbd>⌘</kbd> + <kbd>⇧</kbd> + <kbd>C</kbd> to open the debug console for detection
   logs.

### Run the backend locally

The local profile is deliberately tiny: it points at the checked-in fixtures, writes only
to `outputs/`, and never reaches the network.

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install pyyaml pillow pytest         # core, review sheets, tests

python -m scripts.validate_environment   # resolve and check the three roots
python -m scripts.validate_metadata      # validate ontology, manifest, training config
python -m pytest                         # run the pipeline test suite
```

Acquisition, dataset preparation, training, and export additionally need outbound network
access (the download paths use only the standard library — there is no `requests`
dependency) plus `ultralytics` and `torch`, which are imported lazily and only by
`scripts/train_vast.py` and `scripts/export_coreml.py`, an NVIDIA A100-class GPU, and the
remote roots configured as above. Those stages are **not** meant to run on a laptop.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Project Status

| Area | State |
| --- | --- |
| On-device detection | ✅ Working, offline, with the legacy 13-class model |
| App UI (Home / Scan / Gallery / Onboarding) | ✅ Implemented |
| App data | ⚠️ Sample data in memory; no persistence, accounts, or sync yet |
| App tests | ⚠️ XCTest targets are scaffolding only |
| Ontology, manifest, mapping ledger (v3) | ✅ Frozen and reviewed |
| TACO mapping review | ✅ Complete |
| Open Images acquisition | 🔄 Selection verified; subset inventory pending |
| Smartphone-domain test set | 📋 Planned, not yet captured |
| v3 model training and Core ML release | 📋 Approved recipe, not yet run end to end |

The README describes what is in the repository today. Anything marked 🔄 or 📋 above is not
finished, and the shipped model is still the legacy one.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- CONTRIBUTING -->
## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

When your change touches `backend/`, please keep the governance rules intact: update the
relevant YAML document *and* its schema validation in the same pull request, keep raw data
immutable, never overwrite an existing release, and run `python -m pytest` from `backend/`
before opening the PR.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/trawngson/aware/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=trawngson/aware" alt="contrib.rocks image" />
</a>



<!-- LICENSE -->
## License

The AWARE application code is intended to be distributed under the MIT License.

> ⚠️ No `LICENSE` file has been committed to this repository yet, so the terms above are a
> statement of intent rather than an effective grant. Please add one before relying on it.

Third-party terms that apply regardless:

* **`UltralyticsYOLO/`** — Ultralytics YOLO Swift sources, **AGPL-3.0**
  (see <https://ultralytics.com/license> for commercial licensing).
* **`aware.mlpackage`** — exported from an Ultralytics model and declares **AGPL-3.0**.
* **TACO** — CC BY 4.0, attribution required.
* **Open Images V7** — CC BY 4.0 annotations; images listed as CC BY 2.0, with per-image
  attribution that must be preserved.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTACT -->
## Contact

Truong Son - contact@truongson.me

Project Link: [https://github.com/trawngson/aware](https://github.com/trawngson/aware)

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

* [TACO — Trash Annotations in Context](http://tacodataset.org/) by Pedro F. Proença and Pedro Simões
* [Open Images V7](https://storage.googleapis.com/openimages/web/index.html) by Google LLC and the credited image authors
* [Ultralytics YOLO](https://docs.ultralytics.com/) and the [iOS Swift package](https://github.com/ultralytics/yolo-ios-app)
* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/trawngson/aware.svg?style=for-the-badge
[contributors-url]: https://github.com/trawngson/aware/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/trawngson/aware.svg?style=for-the-badge
[forks-url]: https://github.com/trawngson/aware/network/members
[stars-shield]: https://img.shields.io/github/stars/trawngson/aware.svg?style=for-the-badge
[stars-url]: https://github.com/trawngson/aware/stargazers
[issues-shield]: https://img.shields.io/github/issues/trawngson/aware.svg?style=for-the-badge
[issues-url]: https://github.com/trawngson/aware/issues
[license-shield]: https://img.shields.io/github/license/trawngson/aware.svg?style=for-the-badge
[license-url]: https://github.com/trawngson/aware/blob/main/LICENSE.txt
[Swift]: https://img.shields.io/badge/Swift-F05138?style=flat&logo=swift&logoColor=white
[Swift-url]: https://developer.apple.com/swift/
[SwiftUI]: https://img.shields.io/badge/SwiftUI-0071E3?style=flat&logo=swift&logoColor=white
[SwiftUI-url]: https://developer.apple.com/xcode/swiftui/
[CoreML]: https://img.shields.io/badge/Core%20ML-000000?style=flat&logo=apple&logoColor=white
[CoreML-url]: https://developer.apple.com/documentation/coreml
[YOLO]: https://img.shields.io/badge/YOLO26-FFCC00?style=flat&logo=python&logoColor=black
[YOLO-url]: https://docs.ultralytics.com/
[Python]: https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white
[Python-url]: https://www.python.org/
