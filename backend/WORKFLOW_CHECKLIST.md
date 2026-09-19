# AWARE Data and Model Workflow Checklist

This is the step-by-step plan for building a reproducible household-waste detector that is trained on VAST and exported to the iOS app.

## How to use this checklist

- Work from top to bottom. Do not begin a full training run until the data-audit phase is complete.
- Check a box only when the corresponding deliverable exists and has been reviewed.
- Codex will update completed local tasks in this file after finishing them; user decisions and manually performed remote actions remain unchecked until confirmed.
- Keep source data, checkpoints, model weights, and training outputs on VAST. Keep this local repository code-only.
- Run remote notebook cells manually after reviewing them. Codex does not access the VAST filesystem or execute remote commands.
- When asking Codex for help, return small text summaries: counts, shapes, dtypes, metrics, tracebacks, and short log excerpts. Never return credentials or tokens.

## Workspace foundation

These safeguards are already present in this local workspace:

- [x] Local code-only project structure exists.
- [x] Codex is configured for workspace writes and on-request approvals.
- [x] No Jupyter MCP, SSH, automatic remote execution, or danger-full-access mode is configured.
- [x] Local path handling uses `PROJECT_DATA_ROOT` and `PROJECT_OUTPUT_ROOT`.
- [x] Local defaults use fixtures or synthetic data rather than the VAST dataset.
- [x] The remote execution notebook is designed for manual kernel connection and review.
- [x] The supplied remote environment snapshot is recorded as informational context in `AGENTS.md`.

## Phase 0 — Protect the old work

Do this before downloading or training anything.

- [x] Revoke or rotate the Roboflow API key exposed in the old notebook.
- [x] Remove the credential from notebook history or any other copied artifact where possible.
- [x] Store any replacement credential only in the remote environment, such as `ROBOFLOW_API_KEY`; never commit it or place it in a notebook.
- [x] Preserve the previous model, metrics, and run metadata wherever they currently exist.
- [x] Label the previous result `exploratory / non-reproducible baseline` because its ten Roboflow sources cannot currently be reconstructed.
- [x] Record the old model name, class list, image size, training settings, date, metrics, and app model version.
- [x] Do not delete the old remote dataset or training outputs.

**Deliverable:** a short baseline record explaining what is known, what is unknown, and why the old result is not the primary paper result.

## Phase 1 — Define the research and product target

- [x] Draft the project specification in `SPECIFICATION.md`, with unresolved decisions explicitly marked for approval.
- [x] Write a proposed one-sentence task definition in `SPECIFICATION.md`.
- [x] Approve the proposed one-sentence task definition.
- [x] Record a recommended first-release object list: the nine provisional ontology classes, with deferred classes remaining out of scope.
- [x] Approve the original nine-class first-release object list.
- [x] Supersede it before dataset release with the eight-class ontology v2:
  battery is deferred because approved sources provide only two detection
  boxes, and no model or dataset release used ontology v1.
- [x] Supersede ontology v2 before dataset release with the seven-class
  ontology v3: plastic container is deferred because only 17 automatically
  accepted boxes remained, while the broader TACO source class mixed plastic,
  foam, molded fiber, and unclear objects. No model or dataset release used
  ontology v2.
- [x] Record the confirmed physical test matrix: iPhone XR on the latest iOS 18 release as the performance floor, plus iPad (A16) on iPadOS 27.0 Public Beta 1 as the secondary compatibility device.
- [x] Confirm the target device range and physical test-device availability.
- [x] Set provisional mobile limits for model size, latency, memory, and battery/thermal behavior:
  - Core ML package no larger than 25 MB;
  - sustained inference of at least 10 FPS and p95 latency no greater than 100 ms;
  - peak app memory no greater than 500 MB;
  - no serious or critical thermal state during a 10-minute scan;
  - sustained latency degradation no greater than 25%;
  - battery loss no greater than 5 percentage points per controlled 10-minute
    scan, with battery health and screen brightness recorded.
- [x] Document proposed detector, recycling-policy, reward, and abstention output contracts in `SPECIFICATION.md`.
- [x] Approve the layer boundaries and output contracts:
  - detector: identify a visual object class;
  - policy layer: provide jurisdiction-specific recycling advice;
  - reward layer: decide whether points should be awarded.
- [x] Defer vision-LLM fallback from the first release; uncertain detections abstain and request another view.

**Deliverable:** a one-page project specification with target classes, target device, and user-facing behavior.

## Phase 2 — Freeze a canonical ontology

Ontology v3 is frozen in `ontology.yaml`:

- [x] `plastic_bottle`
- [x] `glass_container`
- [x] `metal_can`
- [x] `cardboard`
- [x] `plastic_bag`
- [x] `disposable_cup`
- [x] `styrofoam`

Deferred after source audit:

- [x] `battery` — two TACO boxes; no Open Images V7 boxable class
- [x] `plastic_container` — 17 automatically accepted boxes; broader source
  label rejected under the approved whole-class-only mapping policy

Then write the annotation rules:

- [x] Define what counts as an instance of every class.
- [x] Define what does not count.
- [x] Decide whether loose bottle caps are a class.
- [x] Decide how attached caps are annotated.
- [x] Define rules for occlusion, truncation, damage, contamination, and multiple objects.
- [x] Define when an object is rejected as ambiguous rather than forced into a class.
- [x] Freeze the class names and numeric class order.
- [x] Never reuse a numeric class ID for a different meaning.

**Deliverable:** `ontology.yaml` plus an annotation handbook with positive and negative examples.

## Phase 3 — Inventory and approve data sources

For every source, record:

- [x] Dataset name and stable URL.
- [x] Owner or publisher.
- [x] Exact version, project/version ID, and access date.
- [x] License and required attribution.
- [x] Original class list or official versioned class-list reference.
- [x] Image and annotation counts, or an explicit planned/unrecoverable status
  for sources that do not yet have countable data.
- [x] Export format.
- [x] Preprocessing and augmentation settings.
- [x] Known limitations, such as sparse classes or incomplete labels.

Source decisions:

- [x] Use TACO v1.0 only with its dataset citation, checksum, and documented mapping.
- [x] Use Open Images V7 as the single supplemental source, with per-image license metadata and reviewed mappings.
- [x] Do not include any external Roboflow dataset in v1 or unidentified Roboflow data in any main experiment.
- [x] Use COCO only through pretrained weights unless a later supervised-data decision is approved.
- [x] Check dataset licenses separately from the Ultralytics code/model license.

**Deliverable:** `source_manifest.yaml` or `source_manifest.json` with one record per dataset version.

## Phase 4 — Keep raw data immutable on VAST

- [x] Keep each original dataset in a source- and version-specific remote location.
- [x] Do not overwrite original annotations.
- [x] Keep raw data, canonical data, audit reports, splits, and training runs in separate locations.
- [x] Set `PROJECT_DATA_ROOT` to the approved remote data root in the remote kernel.
- [x] Set `PROJECT_OUTPUT_ROOT` to the approved remote output location.
- [x] Set `PROJECT_CODE_ROOT` to the reviewed remote checkout location.
- [x] Verify these values through the reviewed notebook before processing data.
- [ ] Confirm that no dataset, checkpoint, or training output remains on the
  Mac after the newly captured smartphone test set is safely transferred to
  its approved immutable VAST location.

**Deliverable:** a documented remote directory layout and a successful read-only environment preflight.

## Phase 5 — Convert and harmonize labels

- [x] Write one adapter per approved v1 source instead of manually editing merged labels.
- [x] Preserve the original source name and original label for every annotation.
- [x] Create a mapping table with source, source class, canonical class, action, reason, and review status.
- [x] Make `safe_merge` fail closed until representative samples are approved.
- [x] Send ambiguous classes to `manual_review` or `reject`.
- [x] Never map a broad class into a narrower class without inspecting examples.
- [x] Document that missing Open Images labels are not reliable background.
- [x] Implement canonical YOLO release generation with immutable manifests and
  complete the full VAST conversion as release `aware-v1-sevenclass-seed26`.

**Deliverable:** reproducible canonical annotations and a reviewed mapping ledger.

## Phase 6 — Audit the canonical dataset

Local audit code and fixtures cover missing/corrupt images, dimensions, invalid
boxes, class IDs/order, counts, exclusions, and exact/perceptual duplicates.
The boxes below refer to running and reviewing the audit on the full VAST data.

- [x] Check that every image has the expected annotation relationship.
- [x] Check for missing files, corrupt images, invalid boxes, zero-area boxes, and out-of-range class IDs.
- [x] Count images and annotations by source, split, and canonical class.
- [x] Inspect class imbalance and rare classes.
- [ ] Render random examples with bounding boxes and class names.
- [x] Inspect every mapping marked `safe_merge` on representative samples.
- [x] Identify duplicate and near-duplicate images.
- [x] Identify source-specific annotation styles and domain bias.
- [x] Record all exclusions and fixes rather than silently deleting them.

**Deliverable:** an audit report that another person could use to understand exactly what entered the training set.

## Phase 7 — Create leakage-safe splits

Deterministic group-aware split code and leakage tests are complete locally.
The boxes below refer to the real dataset and frozen smartphone test set.

- [x] Collect or select a target-domain test set before choosing the final model.
- [x] Freeze the target test set: `records/target-test-set-v2/` (113 images,
  139 boxes, frozen 2026-09-18; supersedes v1, see its `CHANGES.md`). Keep it
  untouched during model development.
- [x] Split training and validation data by source groups and duplicate
  relationships where those relationships exist.
- [x] Run exact and perceptual duplicate checks before the split.
- [x] Verify that no image or near-duplicate appears in more than one split.
- [x] Save the immutable training and validation split manifest containing
  image IDs and dataset versions.
- [ ] Do not change the test set merely because a result is inconvenient.

**Deliverable:** immutable `train`, `val`, and target-domain `test` manifests.

## Phase 8 — Train controlled baselines

- [x] Run the local tests, metadata validation, and `python -m scripts.validate_environment` locally.
- [x] Approve and freeze the VAST recipe: 200 epochs, patience 40, batch 64, AdamW, seed 26, deterministic mode, 640 x 640, one A100.
- [x] Pass the one-epoch, 2% VAST smoke run before starting either full run.
- [x] Train YOLO26n on all approved training sources from pretrained weights
  (`e1b-yolo26n-aware-v1-seed26`, best epoch 131, validation mAP50 0.409; see
  `PAPER_NOTES.md`).
- [x] Train YOLO26s on all approved training sources from pretrained weights
  (`e2-yolo26s-aware-v1-seed26`, best epoch 168 of 200, validation mAP50
  0.423).
- [x] Select the final model before test-set evaluation: YOLO26n
  (`records/model-selection-v1.yaml`, 2026-09-19).
- [ ] Keep image size, seed, class order, evaluation code, and major settings fixed.
- [x] Record the code commit, source manifest version, split version, environment, command, and output location for every run.
- [x] Start with the standard training recipe before tuning many hyperparameters.
- [ ] Stop and repair the dataset if validation reveals label or path problems.

**Deliverable:** reproducible baseline runs with saved metrics and configuration metadata.

## Phase 9 — Run source ablations

- [ ] Train the compact TACO-only YOLO26n ablation if both primary runs finish in time.
- [ ] Compare TACO-only against TACO plus Open Images.
- [x] Keep external Roboflow training data out of v1.
- [ ] Keep the frozen target test set identical across experiments.
- [ ] Keep training settings identical where possible.
- [ ] Report dataset size as well as source composition; use matched-size comparisons if feasible.
- [ ] Compare per-class performance, not only overall mAP.

**Deliverable:** an ablation table showing whether each data source helps target-domain performance.

## Phase 10 — Analyze errors and choose behavior

- [x] Report mAP, precision, recall, and per-class AP (frozen test set v2:
  `records/target-test-evaluations-v2.yaml`).
- [x] Inspect false positives and false negatives by class (YOLO26n confusion
  matrix on test set v2; see `records/target-test-evaluations-v2.yaml`).
- [ ] Evaluate difficult conditions such as clutter, low light, occlusion, distance, and unusual viewpoints.
- [ ] Measure confidence calibration or define a conservative confidence threshold.
- [ ] Add an abstain/“please try again” behavior for uncertain predictions.
- [ ] Measure recycling-guidance correctness separately from detector accuracy.
- [ ] Document known failure cases and classes that should be removed or merged.

**Deliverable:** an error-analysis report and a justified class/threshold decision.

## Phase 11 — Export and validate on mobile

- [x] Export the selected PyTorch model to Core ML (YOLO26n 4.8 MB and
  YOLO26s 19 MB FP16 packages; the app model is chosen after both are measured
  on the iPhone).
- [x] Test the exported model on a fixed image set against the server-side model
  (`records/coreml-parity-v1.yaml`).
- [ ] Verify class order, labels, confidence values, coordinates, and box filtering.
- [x] Test FP16 first (accepted 2026-09-19; FP32 not exported).
- [ ] Test INT8 only if the accuracy change is acceptable.
- [ ] Measure model size, latency, memory, and thermal behavior on a physical iPhone.
- [ ] Replace broad substring-based Swift label matching with an explicit label-to-policy table.
- [ ] Test unknown labels and low-confidence predictions safely.

**Deliverable:** a versioned Core ML model, mobile benchmark, and verified Swift integration.

## Phase 12 — Prepare the paper and release record

- [ ] Write the dataset construction method and ontology rules.
- [ ] Include the complete source, version, license, and attribution table.
- [ ] Describe exclusions, rejected mappings, deduplication, and split strategy.
- [ ] Report all baseline and ablation results.
- [ ] Report per-class metrics and mobile deployment measurements.
- [ ] Record model architecture, input size, training settings, seed, and software versions.
- [ ] Create a dataset card and model card with limitations.
- [ ] Confirm that no credentials, private paths, datasets, checkpoints, or generated outputs are committed.
- [ ] Resolve Ultralytics and dataset licensing before public or commercial distribution.

**Deliverable:** a reproducibility package containing code, configurations, manifests, evaluation scripts, and paper-ready tables.

## Repeat this small checklist for every remote run

- [ ] Review every notebook cell before execution.
- [ ] Confirm the working directory and environment variables.
- [ ] Confirm the operation is read-only or writes only to the approved output root.
- [ ] Confirm that no shell command uploads, downloads, deletes, or changes server configuration.
- [ ] Run a small sample or validation step before a full job.
- [ ] Return only the relevant text output to Codex.
- [ ] Record the run ID, configuration, data version, and result.

## Immediate next action

Two independent tracks run in parallel.

**Training (VAST, unblocked).** TACO v1.0 was acquired from the authors' GitHub
tag `1.0` after the Zenodo transfer was stopped (`VAST_RUNBOOK.md` Gate 2), and
release `aware-v1-sevenclass-seed26` (TACO plus the Open Images subset) and the
batch-16 smoke run have both passed. The next action is the read-only
`scripts.validate_environment` preflight, then full YOLO26n, then full YOLO26s,
with the shared vLLM service paused. Batch 64 has not run since `/dev/shm` was
raised to 8 GB; if it fails, lowering it for both models is already approved.
Training does not depend on the target test set.

**Target test set (frozen 2026-09-18).** Use v2:
`records/target-test-set-v2/target_test_manifest.json` pins 113 lossless PNGs
derived from the original HEICs (orientation applied; original hashes in
`test_set/frozen_v1/heic_provenance.json`) and 139 boxes in ontology class
order. v2 replaced v1 after a second visual review, before any evaluation. No
further changes are allowed once a model has been evaluated on it. The
single-object `styrofoam` class is an accepted limitation.

Full training remains on VAST. The unidentified legacy merge remains preserved
but excluded.
