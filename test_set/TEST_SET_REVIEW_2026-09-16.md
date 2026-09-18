# Target-domain test set — visual review and corrections, 2026-09-16

Reviewed: reworked MakeSense labels (`drive-download-20260916T002726Z-1-001.zip`,
6 batch archives, 119 label files) against `test_set/session_1_reuploaded` and
`test_set/session_2`.

Corrected labels: `test_set/labels_corrected/` (119 files, authoritative).
The raw returned export is unmodified.

Classes visually reviewed in full: `plastic_bottle`, `disposable_cup`,
`styrofoam`.
NOT yet visually reviewed: `glass_container`, `metal_can`, `cardboard`,
`plastic_bag` (77 boxes).

## Structural validation — PASS (before and after correction)

- 119/119 accepted images have labels; 0 orphans, 0 missing.
- 139 boxes, 0 structural errors, all normalized 0..1 and within bounds.
- No box smaller than 1% of frame; median box 27% of frame.
- 16% of boxes touch an image edge (ordinary truncation).
- No `classes.txt` in the export: the integer-to-name order is not recoverable
  from the files and must be supplied and recorded externally.
- Class order verified consistent with the previous export (not a permutation).

## Correction 1 — APPLIED: EPS errata had been applied backwards

`ontology.yaml` errata 2026-07-28 (commit `bb903d1`) states, for class 6:
  - negative: "foam drinking cups, which belong to disposable_cup"
  - ambiguity: "Drinking-cup form takes precedence and maps to disposable_cup"

The relabeling round moved three MUJI cup boxes the wrong direction,
`disposable_cup` (5) -> `styrofoam` (6). The pre-rework labels were correct.
It also contradicted `IMG_1999`, the same cup product, still `disposable_cup`.

Applied: `IMG_2224` (2 boxes) and `IMG_2225` (1 box) set back to class 5.

## Correction 2 — APPLIED: bubble-tea cup labelled plastic_bottle

`IMG_2031` and `IMG_2032` show the same sealed plastic bubble-tea cup with film
lid and straw, labelled `plastic_bottle` (0). Drinking-cup form takes
precedence, and equivalent plastic cups in `IMG_2191`, `IMG_2120` and `IMG_2121`
are correctly `disposable_cup`.

Applied: `IMG_2031` and `IMG_2032` set to class 5.

## Effect of corrections

  class              boxes           images
  plastic_bottle     28 -> 26        21
  glass_container    26 -> 26        22
  metal_can          14 -> 14        14
  cardboard          29 -> 29        26
  plastic_bag        16 -> 16        15
  disposable_cup     13 -> 18        13
  styrofoam          13 -> 10        10
  TOTAL             139 -> 139

Box geometry is untouched; only four class IDs changed across four files.

## LIMITATION (for the paper) — the styrofoam class is a single object

After correction, every `styrofoam` instance in the target-domain test set comes
from one physical object. `IMG_2212` through `IMG_2221` are ten photographs of
the same expanded-polystyrene shipping box, in the same location, with the same
cloth resting on it, differing only in camera angle and distance. There are ten
images, ten boxes, and one object.

Suggested wording:

> A limitation of our target-domain test set is that the `styrofoam` class is
> not independently sampled. All ten `styrofoam` instances are photographs of a
> single expanded-polystyrene shipping box captured in one location from
> varying viewpoints. Per-class average precision for `styrofoam` therefore
> estimates the detector's response to one specific object under viewpoint
> variation, not its ability to generalize across the class. We report the
> number but do not treat it as a class-level generalization result, and we
> exclude it when comparing source ablations. The same caveat applies in weaker
> form to `metal_can` (14 instances) and `plastic_bag` (16 instances), where
> per-class AP carries wide error bars regardless of object diversity.

Why this was not fixed: additional expanded-polystyrene objects (foam trays,
takeaway boxes, packing foam) could not be sourced within the project's time
budget, and a further capture-and-label round would have delayed the work
beyond what the schedule allowed.

### Detection note worth reporting on its own

Perceptual hashing does not catch this. Running dHash at Hamming distance <= 12
over all 119 images flags only `IMG_2216`/`IMG_2217` and reports eleven
"unique scenes" for `styrofoam`. Same-object/different-viewpoint duplication is
invisible to perceptual deduplication, so `dedup.py` cannot certify test-set
object diversity. Diversity at the level of physical objects has to be tracked
at capture time, by recording an object identifier per photograph. Recommend
adding that field when the test set is frozen.

## Observation — plastic_bottle composition differs from the training sources

Of 23 `plastic_bottle` images (21 after correction), roughly 19 are soap,
hand wash, lotion and cosmetic pump dispensers (`IMG_2035`-`IMG_2046`,
`IMG_2113`-`IMG_2117`). Only about four are beverage bottles (`IMG_2085`,
`IMG_2086`, `IMG_2087`, and Listerine `IMG_2112`).

TACO is a litter dataset dominated by beverage bottles. Measured
`plastic_bottle` performance will therefore reflect a train/test domain shift
in object subtype, not only detector quality. This should be stated in the
results discussion whichever way the numbers fall.

## Box tightness — acceptable, no action

Boxes are generally tight. Boxes on hand-held objects often include the holding
hand (`IMG_2039`, `IMG_2044`, `IMG_2046`, `IMG_2113`, `IMG_2115`). This costs
IoU at the stricter thresholds of mAP@[.5:.95] but is harmless at mAP@0.5.
Not worth re-drawing.
