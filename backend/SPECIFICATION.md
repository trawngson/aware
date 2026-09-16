# AWARE Project Specification

**Version:** 0.2
**Date:** 2026-07-22
**Status:** Phase 1 complete; provisional product and mobile acceptance targets approved
**Project:** AWARE household-waste detection and recycling-assistance application

This document converts [`WORKFLOW_CHECKLIST.md`](WORKFLOW_CHECKLIST.md) into the technical and research specification for the next AWARE development cycle.

The specification is intentionally staged. A later phase must not silently override an earlier decision about class definitions, data provenance, or evaluation.

## 1. Purpose

AWARE shall detect common household waste items in ordinary smartphone images and provide an app response that may include:

- the detected item and confidence;
- recycling or disposal guidance;
- a points/reward decision;
- an abstention or retry request when the result is uncertain.

The detector will be trained on the VAST-hosted Jupyter environment and exported for on-device inference in the existing SwiftUI iOS application. Codex will work only on the local, code-only repository and will receive selected text outputs from manually reviewed remote notebook cells.

### 1.1 One-sentence task definition

> AWARE detects nine common household-waste object classes in ordinary handheld iPhone camera images, abstains when uncertain, and passes canonical detections to separate recycling-policy and reward layers.

**Decision status:** Approved by the user on 2026-07-19; this task definition is frozen for the current project cycle.

## 2. Goals

The project shall:

1. Produce a reproducible, provenance-traceable household-waste detection dataset.
2. Resolve incompatible source taxonomies through an explicit canonical ontology.
3. Measure whether each approved data source improves performance on target-domain images.
4. Train an efficient YOLO26 detection model suitable for Core ML and mobile deployment.
5. Separate visual detection from recycling-policy and reward logic.
6. Provide paper-ready dataset, training, evaluation, licensing, and deployment records.

## 3. Non-goals

The first version shall not attempt to:

- recognize every possible form of waste;
- infer all local or municipal recycling rules directly from pixels;
- treat an uncertain prediction as a confirmed recycling decision;
- download the large VAST dataset, checkpoints, or training outputs to the Mac;
- provide Codex with direct access to the VAST server;
- configure SSH, Jupyter MCP, unrestricted remote shell access, sudo, services, firewalls, or new ports;
- use the previous unidentified multi-dataset merge as the primary paper dataset.

## 4. Operating and safety constraints

### 4.1 Local workspace

Codex may work only inside the local backend project directory. Local defaults shall use fixtures or small synthetic data. Code shall use relative paths or environment variables rather than machine-specific absolute paths.

The following environment variables define runtime locations:

- `PROJECT_CODE_ROOT`: optional code root visible to the execution environment;
- `PROJECT_DATA_ROOT`: dataset root;
- `PROJECT_OUTPUT_ROOT`: generated reports, runs, and approved outputs.

Their remote values must never be committed to source, configuration, notebooks, or documentation.

### 4.2 Remote execution

The remote Jupyter kernel is the only execution bridge to the VAST environment. The developer shall:

- connect to the existing Jupyter server manually in VS Code;
- review every notebook cell before execution;
- run only approved, visible operations;
- confirm the working directory and environment variables before processing;
- return small text diagnostics to Codex when debugging.

Codex shall not access the server directly, execute remote commands, upload or download files automatically, delete remote files, or perform destructive cleanup.

### 4.3 Credentials and sensitive information

Credentials, tokens, usernames, private server paths, and private URLs shall not appear in committed files or notebook cells. Any API credential required by a manually run remote process must be provided through the remote environment and must not be printed.

The previous exposed Roboflow credential must remain revoked or rotated. The old notebook is not an approved credential store.

## 5. Phase 1 product decisions

The choices in this section form the Phase 1 decision set. Each choice carries an explicit status so that dataset selection cannot silently define the product before the user approves it.

### 5.1 Target device range

The confirmed physical test matrix is:

- **iPhone XR running the latest available iOS 18 release:** primary phone and performance-floor device;
- **iPad (A16) running iPadOS 27.0 Public Beta 1:** secondary device for iPad compatibility and behavior on a newer processor and beta operating system.

The deployment target is therefore **iPhone XR or newer within the app's supported iOS range**, with iPad support evaluated separately on the A16 iPad. Performance acceptance must pass on the iPhone XR. Results from the iPadOS 27 beta must be labeled as beta-OS results and reported separately so beta-specific behavior does not obscure the stable iOS 18 measurement.

**Decision status:** Approved by the user on 2026-07-19; both physical devices are available for eventual testing.

#### 5.1.1 Provisional iPhone XR mobile limits

The following limits are the first-release acceptance targets for a controlled,
continuous 10-minute scan on the iPhone XR performance-floor device:

- the exported Core ML package is no larger than **25 MB**;
- sustained inference is at least **10 FPS**, with **p95 latency no greater than
  100 ms**;
- peak app memory is no greater than **500 MB**;
- the device does not enter a **serious** or **critical** thermal state;
- sustained latency degradation from the initial measured baseline is no more
  than **25%**; and
- battery loss is no more than **5 percentage points** during the scan, with
  battery health and screen brightness recorded alongside the result.

The benchmark record must also identify the app/model version, device and OS,
starting battery percentage, power state, ambient conditions where practical,
and the measurement method. These are provisional engineering gates: results
may motivate an explicitly reviewed revision, but a failing result must not be
silently accepted or hidden by changing the test procedure.

**Decision status:** Approved as provisional limits on 2026-07-22. Phase 1 is
complete.

### 5.2 First-release object classes

The first backend release uses seven classes:

1. `plastic_bottle`
2. `glass_container`
3. `metal_can`
4. `cardboard`
5. `plastic_bag`
6. `disposable_cup`
7. `styrofoam`

Loose bottle caps, plastic cutlery, straws, toothbrushes, organics, and a generic `other` class remain deferred. An attached cap is part of a `plastic_bottle`; a loose cap is rejected from this ontology. `unknown` and `abstain` remain runtime outcomes rather than training classes.

**Decision status:** The original nine-class scope was approved on 2026-07-19.
It was explicitly superseded on 2026-07-23 before any dataset or model release.
Battery is deferred because TACO supplies only two boxes and Open Images V7 has
no boxable Battery detection class. Plastic container was also deferred before
dataset release: only 17 automatically accepted TACO boxes remained, and the
broader Disposable food container source class mixed plastic, foam, molded
fiber, and materially unclear examples.

### 5.3 Layer boundaries and outputs

The detector output shall be separate from the app policy output.

#### Detector output

For each inference event, the detector adapter shall provide:

- result state: `detections`, `no_detection`, or `inference_error`;
- zero or more detections containing canonical class name, confidence score, and normalized bounding-box coordinates;
- model version and ontology version;
- frame or inference identifier needed to associate the result with the captured image.

The detector may return multiple objects. It shall not emit recycling instructions, disposal categories, jurisdiction decisions, or points. `uncertain` is produced by the application decision gate from confidence, stability, object size, image quality, or class ambiguity; it is not a learned class.

#### Recycling-policy output

The policy layer shall accept a canonical label and an explicit jurisdiction/policy version. It shall return:

- policy state: `guidance_available`, `confirmation_required`, or `unsupported`;
- display name;
- material/category;
- disposal or recycling guidance;
- jurisdiction, policy source, and policy version;
- any user confirmation needed, such as checking the cup material or local acceptance rules;
- reward eligibility, without directly mutating the user's point balance.

The policy table shall not rely on broad substring matching such as treating every label containing `plastic` or `bottle` as a plastic bottle.

If a canonical label or jurisdiction is unsupported, the safe result is generic guidance or a request to check local rules, not a guessed recycling instruction.

#### Reward output and behavior

The reward layer shall accept the application decision-gate result, the policy result, and the user's confirmation state. It shall return:

- reward state: `eligible`, `ineligible`, `already_awarded`, or `confirmation_required`;
- point value;
- a stable reason code;
- the scan event identifier used to prevent awarding the same event twice.

Points shall be awarded at most once per scan event and only after an accepted, stable detection, an eligible policy result, and explicit user confirmation. `uncertain`, `no_detection`, `inference_error`, unsupported-policy, and cancelled results receive zero points. Point values belong to versioned reward configuration, never to model labels or confidence values. Production abuse controls and cross-event duplicate policy remain a later product decision.

#### Abstention

The app shall be able to respond with “uncertain,” “try another view,” or equivalent when confidence, object size, image quality, or class ambiguity is inadequate. An uncertain prediction shall not automatically receive points.

**Decision status for Section 5.3:** Approved by the user on 2026-07-19; these layer boundaries and output contracts are frozen for the current project cycle.

### 5.4 Vision-LLM fallback

The first release shall not use a vision-enabled LLM as an automatic or optional fallback. When the detector is uncertain or returns no detection, the app shall abstain and ask the user to try another view.

The detector interface may remain extensible so a separately evaluated, explicitly user-initiated fallback can be considered in a later project cycle. Any future fallback must preserve the canonical ontology and deterministic policy/reward boundaries; it must not generate recycling policy or award points directly.

**Decision status:** Approved by the user on 2026-07-19; vision-LLM fallback is deferred from the first release.

## 6. Frozen canonical ontology v3

The seven-class list, numeric order, and annotation rules are frozen in
[`ontology.yaml`](ontology.yaml). Human-facing guidance is recorded in
[`ANNOTATION_HANDBOOK.md`](ANNOTATION_HANDBOOK.md). Numeric IDs must never be
reordered or reused for a different meaning.

| ID | Canonical class | Definition | Initial policy |
|---:|---|---|---|
| 0 | `plastic_bottle` | Rigid plastic bottle, such as a beverage or personal-care bottle | Treat attached cap as part of the bottle; do not create a separate cap box |
| 1 | `glass_container` | Glass bottle or jar intended as a household container | Exclude drinking glasses unless separately approved |
| 2 | `metal_can` | Aluminum or steel food/beverage can | Do not include arbitrary metal objects |
| 3 | `cardboard` | Cardboard box or cardboard packaging | Do not use `book` as an automatic proxy |
| 4 | `plastic_bag` | Plastic bag or flexible plastic film | Do not map all thin plastic objects here |
| 5 | `disposable_cup` | Disposable cup where the object form is visually useful | Material-specific guidance may require confirmation |
| 6 | `styrofoam` | Expanded polystyrene packaging or pieces | Define minimum visible size and fragmented-object behavior |

The following are deferred unless the application and data support them:

- `battery`;
- `plastic_container`;
- loose `plastic_bottle_cap`;
- `plastic_cutlery`;
- `straw`;
- `toothbrush`;
- `organics` or food waste;
- a generic `other` class.

`unknown` or `abstain` is a runtime behavior, not automatically a training class.

### 6.1 Annotation rules

The annotation handbook shall define:

- the visible object boundary and bounding-box policy;
- whether attached parts receive separate boxes;
- loose-cap handling;
- occlusion and truncation thresholds;
- damaged, dirty, crushed, or partially visible objects;
- multiple instances of the same class;
- objects too small to identify reliably;
- ambiguous objects that must be rejected or sent to manual review;
- whether a source with incomplete labels may be used for detection training.

No source label shall be forced into a canonical class merely to increase the dataset size.

## 7. Data-source requirements

The initial approved training-source set is intentionally limited to:

1. TACO v1.0, pinned to the official Zenodo archive and checksum.
2. A selected waste-related Open Images V7 bounding-box subset. Each selected
   image must retain author/license metadata, and broad labels require manual
   mapping review.

A newly captured smartphone-domain test set shall contain at least ten images
per class and at least 70 images total. It is evaluation-only and must be frozen
before model comparison. COCO may provide pretrained weights, but COCO images
shall not enter supervised training without separate manual relabeling and a
new source-approval decision.

No external Roboflow dataset is approved for v1. A Roboflow source may be
considered later, one version at a time, only after the user approves its exact
project/version, provenance, license, mapping, and controlled source ablation.
The unidentified Roboflow sources used in the previous experiment remain
preserved as legacy evidence and excluded from training and evaluation.

### 7.1 Source manifest

Every dataset version shall have a manifest record containing:

- source name and stable URL;
- owner/publisher;
- exact version or project/version identifier;
- access date;
- license and attribution requirements;
- original class list;
- image and annotation counts;
- source format and conversion format;
- preprocessing and augmentation settings;
- mapping-ledger version;
- known limitations;
- integrity metadata or hashes where practical.

Dataset-platform licensing and model/code licensing must be reviewed separately.

### 7.2 Remote data layout

The remote environment should keep the following logical areas separate:

```text
$PROJECT_DATA_ROOT/
├── raw/<source>/<version>/
└── captured/<capture-version>/

$PROJECT_OUTPUT_ROOT/
├── datasets/<dataset-version>/
├── audits/<audit-id>/
├── runs/<run-id>/
├── exports/<model-version>/
└── reports/<report-id>/
```

These are logical placeholders only. Private or machine-specific paths must not be written into this repository.

Raw data and original annotations are immutable. Canonical datasets, manifests,
splits, reports, runs, and exports are new versioned outputs under the approved
output root; they are never written back into the raw source tree.

## 8. Label harmonization

Each source shall be processed by a deterministic adapter. The adapter shall preserve both the original annotation and the mapped annotation metadata.

The mapping ledger shall contain at least:

```text
source
source_version
source_class
canonical_class
action
reason
review_status
```

Allowed actions are:

- `keep`: source class already matches the canonical definition;
- `safe_merge`: definitions have been reviewed and overlap;
- `manual_review`: examples require inspection before inclusion;
- `reject`: class is outside the target ontology or too ambiguous.

Initial mapping examples:

| Source label | Default action | Canonical result |
|---|---|---|
| TACO `Clear plastic bottle` | `safe_merge` after visual review | `plastic_bottle` |
| TACO `Drink can` | `safe_merge` after visual review | `metal_can` |
| TACO `Plastic bottle cap` | `reject` or deferred class | None initially |
| Roboflow `plastic bottle` | `manual_review` unless definition is exact | `plastic_bottle` only when justified |
| Roboflow `plastic container` | `reject` for v1 | Deferred target class |
| COCO `bottle` | `manual_review` or reject | Never automatically `plastic_bottle` |
| COCO `wine glass` | `reject` unless ontology expands | None initially |

Broad source classes must never be mapped automatically into narrower canonical classes. Sources with partial annotation policies must be documented and may need to be excluded from detection training.

## 9. Dataset-quality gates

The canonical dataset cannot proceed to final training until the following checks pass:

- every included image is traceable to a source and version;
- image/annotation relationships are valid;
- all boxes are finite, non-empty, and within image bounds;
- all class IDs are valid and match the frozen ontology;
- unresolved mappings are excluded or explicitly reviewed;
- class and source counts are available;
- representative labels have been visually inspected;
- exact and near-duplicate checks have been performed;
- exclusions and corrections are recorded;
- a versioned audit report exists.

An audit failure is a data-quality issue, not a reason to tune the model first.

## 10. Splitting and leakage control

The target-domain test set shall be selected before final model selection and then frozen.

Splits shall prefer group boundaries such as:

- video or image sequence;
- capture session;
- uploader or original scene;
- source-dataset grouping;
- near-duplicate cluster.

Image-level random splitting alone is insufficient when related images may share a scene or capture sequence. The split manifest shall record image IDs, source versions, group IDs where available, and the split version.

The validation set may guide training and threshold selection. The frozen target test set shall be reserved for final reporting and limited diagnostic use.

## 11. Training specification

### 11.1 Model family

The detector shall use the YOLO26 detection task initially.

- `yolo26n.pt`: mobile/latency candidate;
- `yolo26s.pt`: accuracy candidate;
- larger variants may be investigated on VAST but are not presumed deployable.

Training shall fine-tune pretrained weights rather than initialize randomly. The first baseline shall use a standard, documented training recipe before extensive hyperparameter tuning.

### 11.2 Approved controlled recipe

The v1 comparison uses the reviewed configuration in
[`configs/training/v1_controlled.yaml`](configs/training/v1_controlled.yaml):

- one NVIDIA A100 GPU on VAST, device 0;
- 640 x 640 images;
- 200 maximum epochs with early-stopping patience of 40;
- batch size 64 for both YOLO26n and YOLO26s;
- AdamW with initial learning rate 0.001;
- seed 26 and deterministic mode enabled; and
- mixed-precision training enabled.

A one-epoch, 2% smoke run must pass on VAST before a full run. If batch size 64
fails for either model, one lower batch size must be approved and used for both
models. A 300-epoch run is not part of the initial comparison; it may be added
as a separately approved experiment only if the 200-epoch curves are still
improving. Plain-language reproducibility notes and suggested paper wording are
kept in [`PAPER_NOTES.md`](PAPER_NOTES.md).

### 11.3 Controlled experiments

The initial experiment matrix shall include:

| Experiment | Training data | Purpose |
|---|---|---|
| E0 | TACO only, YOLO26n | Compact source-ablation baseline |
| E1 | TACO + selected Open Images, YOLO26n | Primary mobile-size candidate |
| E2 | TACO + selected Open Images, YOLO26s | Primary accuracy candidate |

Each experiment shall record:

- model variant;
- code revision;
- ontology version;
- source-manifest version;
- split version;
- image size;
- seed;
- training configuration;
- software and environment versions;
- remote output location;
- final and best-checkpoint metrics.

Training settings and evaluation procedures should remain fixed across source ablations. If dataset sizes differ substantially, matched-size comparisons should be added where practical.

## 12. Evaluation requirements

Each final experiment shall report:

- mAP at the selected IoU ranges;
- precision and recall;
- per-class AP, precision, and recall;
- confusion and common false-positive categories;
- performance by target-domain condition;
- confidence behavior and abstention performance;
- number of images and annotations by source;
- training and inference resource usage where relevant.

The application evaluation shall additionally report:

- recycling-guidance correctness;
- points/reward correctness;
- behavior on unknown or low-confidence predictions;
- user-facing failure cases.

Model selection shall be based on target-domain utility subject to the mobile constraints, not on aggregate validation mAP alone. The selection rule shall be written down before the final comparison.

## 13. Core ML and iOS integration

The selected model shall be exported to Core ML and validated against a fixed parity set.

Parity checks shall verify:

- class order and class names;
- input resizing and normalization;
- confidence values within an agreed tolerance;
- bounding-box coordinates;
- duplicate-box filtering behavior;
- empty and low-confidence outputs;
- preprocessing differences between server and device.

FP16 shall be tested first. INT8 may be evaluated if it provides useful mobile savings without unacceptable target-domain degradation.

The Swift app shall use an explicit canonical-label-to-policy mapping. It shall not infer policy from substring fragments. Model labels, class order, and the mapping version shall be stored with the model release record.

Mobile acceptance testing shall be performed on a physical target device and shall record:

- model file size;
- single-frame latency and sustained latency;
- memory behavior;
- thermal or throttling behavior;
- battery impact where measurable;
- camera-scene failure cases.

## 14. Notebook and remote-run requirements

The execution notebook shall:

- print hostname, Python executable, current working directory, and relevant environment status without exposing secrets;
- fail safely when the working directory is unexpected;
- verify expected code and data roots;
- enable `%autoreload`;
- import project modules from `src`;
- run a read-only validation before training;
- use small samples before full processing;
- show example training commands without automatically executing destructive shell operations;
- avoid hidden shell commands, automatic uploads, automatic downloads, and cleanup commands.

Every remote run shall follow this sequence:

1. Review the cell.
2. Confirm the kernel and working directory.
3. Confirm environment variables without printing private values.
4. Run a small read-only preflight.
5. Inspect counts or sample outputs.
6. Start the larger operation manually only after the preflight succeeds.
7. Record the run identifier, configuration, data version, and result.

## 15. Required deliverables

### Local repository

- this specification;
- workflow checklist;
- ontology definition and annotation handbook;
- source manifest template and completed approved-source records;
- mapping ledger;
- deterministic source adapters;
- dataset and label validators;
- split and leakage-audit tools;
- versioned training configurations;
- evaluation and error-analysis tools;
- safe remote execution notebook;
- model card, dataset card, and reproducibility documentation.

### VAST environment

- immutable raw source datasets;
- canonical versioned datasets;
- source and split manifests;
- audit reports;
- training runs and metrics;
- Core ML export artifacts;
- approved remote output records.

Large data, checkpoints, model weights, and generated training outputs shall remain remote.

### Paper and release record

- research question and contribution statement;
- ontology and annotation rules;
- dataset source/license/attribution table;
- data-cleaning and mapping procedure;
- leakage-safe split procedure;
- baseline and ablation tables;
- per-class and target-domain results;
- mobile benchmark;
- limitations and failure analysis;
- software, model, and dataset license review.

## 16. Acceptance gates

Progress is gated as follows:

### Gate 0 — Safety and preservation

Credentials are rotated, the old baseline is preserved and labeled exploratory, and no remote-destructive workflow is being used.

### Gate 1 — Product and ontology

The target device, user-facing behavior, class definitions, annotation rules, and class order are approved.

### Gate 2 — Source approval

Every included source has traceable provenance, version information, license information, and a mapping decision.

### Gate 3 — Canonical dataset

Source adapters produce canonical annotations without silently dropping or relabeling unresolved data.

### Gate 4 — Audit and split

The audit passes, duplicates are addressed, and train/validation/test manifests are frozen.

### Gate 5 — Baseline

Target-domain YOLO26n and YOLO26s baselines are reproducible and evaluated with recorded metadata.

### Gate 6 — Ablation and error analysis

The contribution of each source is measured and common failure modes are understood.

### Gate 7 — Mobile deployment

The selected model passes Core ML parity checks and physical-device benchmarks.

### Gate 8 — Paper and release

The methods, results, provenance, limitations, and licensing records are complete.

## 17. Open decisions

The following decisions remain intentionally open and must be resolved before the corresponding phase:

- regional recycling-policy source and supported jurisdiction;
- target-domain data collection and annotation procedure;
- whether any COCO images will be manually relabeled;
- detector accuracy and abstention thresholds;
- distribution and licensing plan for the app and paper artifacts.

## 18. Immediate next step

Ontology v3, the approved source manifest, the immutable combined dataset
release, leakage-safe training/validation split, and the 2% VAST smoke run are
complete. The next active task is a read-only VAST preflight of those artifacts
and the frozen software environment, followed by the controlled full YOLO26n
and YOLO26s runs in an exclusive A100 window. The separate smartphone-domain
test set must be collected and frozen before final model selection. Do not
train on the unidentified legacy merge or any unapproved source.
