# Target test set v2 — changes from v1 (2026-09-18)

v2 supersedes v1 (`records/target-test-set-v1/`) before any model was evaluated
on either version. v1 is retained unchanged. Same frozen PNGs, same class order.

A second visual review (classes 1–4) found objects that the labeling protocol
("label every clearly identifiable object… not only the subject") required but
the returned labels omitted.

## Removed images (6)

| Image | Reason |
|---|---|
| IMG_2016, IMG_2017 | Many unlabeled shelf jars, too small or blurred to box reliably |
| IMG_2063 | Unlabeled background jars of uncertain material |
| IMG_2109, IMG_2110 | Store aisle with dozens of small unlabeled cans and cartons |
| IMG_2194 | Photographer confirmed the film was not a bag; no qualifying object remains |

## Boxes added or redrawn (4 images)

| Image | Change |
|---|---|
| IMG_2033 | plastic_bag box redrawn to cover the whole visible bag |
| IMG_2187 | plastic_bag added (bag on the cardboard box) |
| IMG_2205 | cardboard added (flattened carton, upper left); two plastic_bottle added (LaVie 5 L jugs) |
| IMG_2206 | cardboard added (flattened carton, upper left); plastic_bottle added (LaVie 5 L jug) |

Left unlabeled because the class was not clear: the LaVie display tray and the
silver bag in IMG_2205/IMG_2206.

## Result

113 images (Session 1: 84, Session 2: 29), 139 boxes: plastic_bottle 29,
glass_container 23, metal_can 14, cardboard 29, plastic_bag 16,
disposable_cup 18, styrofoam 10.
