// What LLM mode asks the model (see llm.h). Kept apart so the native tests and
// scripts/llm_latency.py send exactly the same text.
//
// The model only lists the items it sees; routing-v1 (routing.h) still picks
// the stream, as it does for the detection server's boxes. Only the first
// seven labels are v4 classes. Every other label (drink_carton, can, ...,
// other) is not, so routing-v1 sends the plate to other, as it would for an
// item with no class. Naming those items gives the model a place for them
// instead of the nearest bin class, and shows how often each one comes.
#pragma once

// Bin-class wording follows backend/physical_bin/ontology-v4.yaml.
constexpr char LLM_INSTRUCTIONS[] = R"(You sort waste for a recycling bin in a school in Hanoi. The photo looks down at the bin's plate. List each separate item on the plate with its label. An empty plate has no items.
Labels:
- paper: writing, printing or notebook paper, flat or crumpled; paper bags; small paperboard boxes. Not tissues, paper cups or drink cartons.
- plastic_bottle: a plastic drink bottle with a neck narrower than its body. Its cap and label are part of it.
- paper_cup: a single-use paper drinking cup, with its lid, film, sleeve or straw.
- plastic_container: a rigid or semi-rigid single-use plastic food or drink container that is not a bottle: dessert cups, cake, salad and fruit boxes, plastic milk-tea and coffee cups, loose rigid lids.
- plastic_cutlery: a single-use plastic spoon, fork or knife.
- tissue: a facial tissue, napkin, paper towel or wet wipe.
- food_wrapper: flexible plastic or foil-lined packaging: snack and candy bags, bread wrappers, carrier bags, cling film, cutlery sleeves.
- drink_carton: a milk or juice carton of paperboard laminated with plastic or foil, with its straw.
- food_waste: food scraps, fruit peels, leftover rice or noodles, bones.
- foam_container: a foam (styrofoam) box, cup or tray.
- can: a metal drink or food can.
- straw: a loose drinking straw.
- wooden_utensil: wooden or bamboo chopsticks, skewers or ice-cream sticks.
- pen: a pen, marker, highlighter or pencil.
- face_mask: a disposable face mask.
- glass: a glass bottle, jar or piece of glass.
- hazard: a battery, power bank, vape, lighter or electronic device.
- other: anything else, or an item you cannot identify.)";

// The reply's shape: {"items": [{"label": ...}, ...]}. strict makes the
// model keep to it.
constexpr char LLM_SCHEMA[] = R"({"type":"object","additionalProperties":false,"required":["items"],"properties":{"items":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["label"],"properties":{"label":{"type":"string","enum":["paper","plastic_bottle","paper_cup","plastic_container","plastic_cutlery","tissue","food_wrapper","drink_carton","food_waste","foam_container","can","straw","wooden_utensil","pen","face_mask","glass","hazard","other"]}}}}}})";
