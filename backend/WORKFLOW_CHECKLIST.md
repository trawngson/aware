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
- [x] Approve the nine-class first-release object list, with deferred classes remaining out of scope for now.
- [x] Record the confirmed physical test matrix: iPhone XR on the latest iOS 18 release as the performance floor, plus iPad (A16) on iPadOS 27.0 Public Beta 1 as the secondary compatibility device.
- [x] Confirm the target device range and physical test-device availability.
- [ ] Set provisional mobile limits for model size, latency, memory, and battery/thermal behavior.
- [x] Document proposed detector, recycling-policy, reward, and abstention output contracts in `SPECIFICATION.md`.
- [x] Approve the layer boundaries and output contracts:
  - detector: identify a visual object class;
  - policy layer: provide jurisdiction-specific recycling advice;
  - reward layer: decide whether points should be awarded.
- [x] Defer vision-LLM fallback from the first release; uncertain detections abstain and request another view.

**Deliverable:** a one-page project specification with target classes, target device, and user-facing behavior.

## Phase 2 — Freeze a canonical ontology

Start with a small, useful taxonomy. A candidate first version is:

- [ ] `plastic_bottle`
- [ ] `glass_container`
- [ ] `metal_can`
- [ ] `cardboard`
- [ ] `plastic_container`
- [ ] `plastic_bag`
- [ ] `disposable_cup`
- [ ] `battery`
- [ ] `styrofoam`

Then write the annotation rules:

- [ ] Define what counts as an instance of every class.
- [ ] Define what does not count.
- [ ] Decide whether loose bottle caps are a class.
- [ ] Decide how attached caps are annotated.
- [ ] Define rules for occlusion, truncation, damage, contamination, and multiple objects.
- [ ] Define when an object is rejected as ambiguous rather than forced into a class.
- [ ] Freeze the class names and numeric class order.
- [ ] Never reuse a numeric class ID for a different meaning.

**Deliverable:** `ontology.yaml` plus an annotation handbook with positive and negative examples.

## Phase 3 — Inventory and approve data sources

For every source, record:

- [ ] Dataset name and stable URL.
- [ ] Owner or publisher.
- [ ] Exact version, project/version ID, and access date.
- [ ] License and required attribution.
- [ ] Original class list.
- [ ] Image and annotation counts.
- [ ] Export format.
- [ ] Preprocessing and augmentation settings.
- [ ] Known limitations, such as sparse classes or incomplete labels.

Source decisions:

- [ ] Use TACO only with its dataset citation and documented class mapping.
- [ ] Use only one or two initially curated Roboflow projects with recoverable provenance and acceptable licenses.
- [ ] Do not include unidentified Roboflow datasets in the main experiment.
- [ ] Use COCO primarily through pretrained weights; manually relabel any COCO images used as final supervised data.
- [ ] Check dataset licenses separately from the Ultralytics code/model license.

**Deliverable:** `source_manifest.yaml` or `source_manifest.json` with one record per dataset version.

## Phase 4 — Keep raw data immutable on VAST

- [ ] Keep each original dataset in a source- and version-specific remote location.
- [ ] Do not overwrite original annotations.
- [ ] Keep raw data, canonical data, audit reports, splits, and training runs in separate locations.
- [ ] Set `PROJECT_DATA_ROOT` to the existing remote data root in the remote kernel only.
- [ ] Set `PROJECT_OUTPUT_ROOT` to an approved remote output location.
- [ ] Set `PROJECT_CODE_ROOT` only if the remote checkout location is known.
- [ ] Verify these values through the reviewed notebook before processing data.
- [ ] Confirm that no dataset, checkpoint, or training output is being copied to the Mac.

**Deliverable:** a documented remote directory layout and a successful read-only environment preflight.

## Phase 5 — Convert and harmonize labels

- [ ] Write one adapter per source instead of manually editing merged labels.
- [ ] Preserve the original source name and original label for every annotation.
- [ ] Create a mapping table with `source`, `source_version`, `source_class`, `canonical_class`, `action`, and `reason`.
- [ ] Use `safe_merge` only when class definitions truly overlap.
- [ ] Send ambiguous classes to `manual_review` or `reject`.
- [ ] Never map a broad class into a narrower class without inspecting examples.
- [ ] Do not treat missing labels from a partially annotated source as reliable background.
- [ ] Convert approved data into one canonical format and generate a versioned training configuration.

**Deliverable:** reproducible canonical annotations and a reviewed mapping ledger.

## Phase 6 — Audit the canonical dataset

- [ ] Check that every image has the expected annotation relationship.
- [ ] Check for missing files, corrupt images, invalid boxes, zero-area boxes, and out-of-range class IDs.
- [ ] Count images and annotations by source, split, and canonical class.
- [ ] Inspect class imbalance and rare classes.
- [ ] Render random examples with bounding boxes and class names.
- [ ] Inspect every mapping marked `safe_merge` on representative samples.
- [ ] Identify duplicate and near-duplicate images.
- [ ] Identify source-specific annotation styles and domain bias.
- [ ] Record all exclusions and fixes rather than silently deleting them.

**Deliverable:** an audit report that another person could use to understand exactly what entered the training set.

## Phase 7 — Create leakage-safe splits

- [ ] Collect or select a target-domain test set before choosing the final model.
- [ ] Keep the target test set frozen and untouched during model development.
- [ ] Split by video, capture session, uploader, scene, or source group when those relationships exist.
- [ ] Run exact and perceptual duplicate checks before the split.
- [ ] Verify that no image or near-duplicate appears in more than one split.
- [ ] Save a split manifest containing image IDs and dataset versions.
- [ ] Do not change the test set merely because a result is inconvenient.

**Deliverable:** immutable `train`, `val`, and target-domain `test` manifests.

## Phase 8 — Train controlled baselines

- [ ] Run the local validation tests and `python -m scripts.validate_environment` locally.
- [ ] Train a target-domain-only YOLO26n baseline from pretrained weights.
- [ ] Train a target-domain-only YOLO26s baseline from pretrained weights.
- [ ] Keep image size, seed, class order, evaluation code, and major settings fixed.
- [ ] Record the code commit, source manifest version, split version, environment, command, and output location for every run.
- [ ] Start with the standard training recipe before tuning many hyperparameters.
- [ ] Stop and repair the dataset if validation reveals label or path problems.

**Deliverable:** reproducible baseline runs with saved metrics and configuration metadata.

## Phase 9 — Run source ablations

- [ ] Train on target-domain data only.
- [ ] Train on target-domain data plus TACO.
- [ ] Train on target-domain data plus curated Roboflow data.
- [ ] Train on all approved sources.
- [ ] Keep the frozen target test set identical across experiments.
- [ ] Keep training settings identical where possible.
- [ ] Report dataset size as well as source composition; use matched-size comparisons if feasible.
- [ ] Compare per-class performance, not only overall mAP.

**Deliverable:** an ablation table showing whether each data source helps target-domain performance.

## Phase 10 — Analyze errors and choose behavior

- [ ] Report mAP, precision, recall, and per-class AP.
- [ ] Inspect false positives and false negatives by class.
- [ ] Evaluate difficult conditions such as clutter, low light, occlusion, distance, and unusual viewpoints.
- [ ] Measure confidence calibration or define a conservative confidence threshold.
- [ ] Add an abstain/“please try again” behavior for uncertain predictions.
- [ ] Measure recycling-guidance correctness separately from detector accuracy.
- [ ] Document known failure cases and classes that should be removed or merged.

**Deliverable:** an error-analysis report and a justified class/threshold decision.

## Phase 11 — Export and validate on mobile

- [ ] Export the selected PyTorch model to Core ML.
- [ ] Test the exported model on a fixed image set against the server-side model.
- [ ] Verify class order, labels, confidence values, coordinates, and box filtering.
- [ ] Test FP16 first.
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

Define and approve provisional mobile limits for model size, latency, memory, and battery/thermal behavior. The task definition, physical test matrix, nine-class first-release scope, and detector/policy/reward contracts are confirmed. Do not select additional datasets or begin Phase 2 implementation until the remaining Phase 1 limits are confirmed.
