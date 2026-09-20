# CO2-equivalent impact factors for the seven AWARE classes

Researched 2026-09-20. The machine-readable record is
`backend/records/impact-factors-v1.yaml` (on `main`); this document is the
prose version of the same findings.

**Status: proposed, not adopted.** No code consumes these values. The Home CO2
card and `CO2InsightsView` still show hard-coded demo numbers. Whether the app
displays any of this is a separate decision.

## What is being measured

The app's surface is "CO2 Emissions Saved", so the metric is the emissions
avoided by recycling an item instead of sending it to landfill:

```
avoided_kg_co2e = (landfilling_factor - recycling_factor) x item_mass_kg
```

Factors come from **EPA WARM v16 (December 2023)**, in metric tons CO2e per
short ton of material, negative meaning a net reduction. One short ton is
907.18474 kg.

This is *not* the item's embodied carbon. Embodied figures appear below for
contrast only, and the two must never be added into one displayed total.

## Material factors (EPA WARM v16)

| WARM material | Recycling | Landfilling | Avoided | kg CO2e/kg | Exhibit |
|---|---|---|---|---|---|
| Aluminum cans | -9.13 | 0.02 | 9.15 | **10.09** | 2-7 |
| Corrugated containers | -3.14 | 0.18 | 3.32 | **3.66** | 3-7 |
| Steel cans | -1.83 | 0.02 | 1.85 | **2.04** | 2-7 |
| PET | -1.04 | 0.02 | 1.06 | **1.17** | 5-3 |
| Mixed plastics | -0.93 | 0.02 | 0.95 | **1.05** | 5-3 |
| HDPE | -0.76 | 0.02 | 0.78 | **0.86** | 5-3 |
| Glass | -0.28 | 0.02 | 0.30 | **0.33** | 1-4 |
| LDPE | *none published* | 0.02 | — | — | 5-3 |
| Polystyrene | *none published* | 0.02 | — | — | 5-3 |

EPA describes the missing LDPE and polystyrene recycling factors as life-cycle
inventory data gaps, not as evidence that those materials are not recycled.

## Per class

| Class | Per item | Basis | Confidence |
|---|---|---|---|
| `plastic_bottle` | **12 g CO2e** (12-15 g) | 500 mL PET bottle, 10 g (range 9.9-12.7 g) | High |
| `metal_can` | **102-131 g CO2e** | Aluminium can, 12.99 g average metallic weight | High, aluminium only |
| `plastic_bag` | **7 g CO2e** | HDPE carrier bag, 8.12 g | Moderate |
| `glass_container` | — | 0.33 kg CO2e/kg | Per-kilogram only |
| `cardboard` | — | 3.66 kg CO2e/kg | Per-kilogram only |
| `disposable_cup` | — | — | Omitted |
| `styrofoam` | — | — | Omitted |

**`plastic_bottle`** — Cross-checked against an independent source: Gironi and
Piemonte (2010), via the NIH life-cycle review, give 11.4 g CO2e prevented per
500 mL bottle recycled, within 3% of the 11.7 g derived from WARM. Embodied
carbon for contrast is roughly 80-90 g per bottle, cradle-to-gate.

**`metal_can`** — WARM gives 131 g for a 12.99 g can. The Aluminum Association's
own sensitivity analysis gives -1.02 kg CO2e per 1,000 cans per percentage point
of end-of-life recycling rate, which is 102 g per can moving from 0% to 100%
recycling. Two independent methods landing at 102 and 131 g makes this the
best-supported class. Embodied carbon is 77.1 g cradle-to-gate at 73% recycled
content, or 96.8 g cradle-to-grave. Caveat: the class also admits steel food
tins (2.04 kg CO2e/kg), no citable average mass was found for those, and the
detector cannot tell the two apart.

**`plastic_bag`** — The weakest of the three. WARM's HDPE factor is derived from
rigid blow-moulded containers rather than film, and WARM has no LDPE film factor
at all. Embodied carbon is 19.2 g per bag, from the UK Environment Agency's 2011
figure of 1.578 kg CO2 eq per functional unit divided by a reference flow of
82.14 bags. That 1.578 kg number is widely misquoted online as a per-bag value;
it is not.

**`glass_container` and `cardboard`** — The per-kilogram factors are sound, but
item mass is not. Glass containers run from about 200 g (beer bottle) to 500 g
(wine bottle), a 2.5x spread, which is 66-165 g CO2e. Corrugated packaging runs
from about 200 g to over 1 kg, a 5x spread, which is 730 g to 3.7 kg CO2e.
Cardboard has the second-highest per-kilogram value of all seven classes, so it
is the class most worth revisiting if object size can ever be estimated from the
bounding box.

**`disposable_cup`** — Omitted. The class is deliberately material-neutral
(paper, plastic, foam). Van der Harst and Potting (2013), comparing ten
disposable-cup LCAs, found a 20x ratio between the highest and lowest published
climate figure for paper cups alone, and no cup material consistently better
than another. WARM has no factor for PE-coated paper cups or for polystyrene.

**`styrofoam`** — Omitted. WARM publishes no polystyrene recycling factor, and
expanded-polystyrene item mass varies by more than an order of magnitude across
trays, blocks, and clamshells. Both halves of the calculation are missing.

## What this constrains, for design

- Three of seven classes carry a per-item number, two carry a per-kilogram
  factor only, and two carry nothing. A per-scan CO2 figure covering all seven
  classes cannot be sourced today. One limited to bottles, cans, and bags can.
- The values differ by two orders of magnitude between classes, from 7 g for a
  bag to 131 g for a can. Any visual treatment needs to survive that range.
- A displayed total assumes the item actually reaches recycling. Detection alone
  does not establish that, so any total is an upper bound on real effect and
  should not be worded as a fact about the user's impact.
- WARM is US-average in grid mix, transport distance, and recycling practice.
  That sits awkwardly against the app's Hanoi-specific policy layer
  (`hanoi-2026.1`), and the basis has to be stated wherever a number appears.

## Sources

- [WARM Version 16, Containers, Packaging and Non-Durable Goods Materials](https://www.epa.gov/system/files/documents/2023-12/warm_containers_packaging_and_non-durable_goods_materials_v16_dec.pdf) — US EPA, 2023. Exhibits 1-4 (glass), 2-7 (metals), 3-7 (paper), 5-3 (plastics).
- [Frequent Questions about the Waste Reduction Model](https://www.epa.gov/waste-reduction-model/frequent-questions-about-waste-reduction-model) — US EPA. LDPE and polystyrene recycling factors are LCI data gaps.
- [Life Cycle Assessment of the Aluminum Beverage Can](https://www.aluminum.org/sites/default/files/2021-10/2021AluminumCanLCAReportFullVersion.pdf) — The Aluminum Association (study by Sphera), 2021. 12.99 g per can; 77.1 and 96.8 kg CO2e per 1,000 cans; recycling-rate sensitivity.
- [Life Cycle Assessment of Supermarket Carrier Bags](https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/291023/scho0711buan-e-e.pdf) — UK Environment Agency (SC030148), 2011. Table 3.1 (8.12 g bag, 82.14 reference flow); Table 5.1 (1.578 kg CO2 eq).
- [Life Cycle Environmental Impact of PET Water Bottles](https://nems.nih.gov/Documents/PETWaterBottlesEnvironmentalImpact.pdf) — US National Institutes of Health. 0.0114 kg CO2e prevented per 500 mL bottle recycled, citing Gironi and Piemonte (2010).
- [A critical comparison of ten disposable cup LCAs](https://www.sciencedirect.com/science/article/abs/pii/S0195925513000747) — van der Harst and Potting, *Environmental Impact Assessment Review* 43, 86-96, 2013.
- [Single-use beverage cups and their alternatives](https://www.lifecycleinitiative.org/wp-content/uploads/2021/02/UNEP_-LCA-Beverage-Cups-Report_Web.pdf) — UNEP Life Cycle Initiative, 2021.
