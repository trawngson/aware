# Smart sorting bin — physical CAD concept v2

The revised concept uses a **rear-mounted mast and one central tipping plate**.
An item rests on that plate for identification; the same plate tilts toward one
of four separate quarter-circle liners. There is no rotary carrier, second
container, intake hopper or bottom-release gate. All category plaques remain
blank. The display lights up only in the demo; numbered parts do not assign
waste categories.

Two perpendicular, limited-travel horizontal hinges let the single plate tip
toward all four sectors. A single fixed-axis hinge would only tip in two
opposing directions. The rear mast supports the plate joint through a removable
cantilever; it no longer occupies the center of the liners.

## Inspect the design

- [Offline animated 3D preview](v2/viewer.html) — open in a WebGL-capable
  browser and click **Play detection demo**. Sound begins with that click.
- [Design sheet](v2/preview.png)
- [Assembled STEP](v2/smart_bin_assembly.step) — separate named solids.
- [Exploded STEP](v2/smart_bin_exploded.step)
- [Individual STEP and STL parts](v2/parts/)
- [Geometry validation](v2/validation.json)

The viewer works offline. Drag to orbit, scroll to zoom, hide the shell/canopy,
inspect the tilt joint, or choose any of four tipping directions. Pause, resume,
reset and mute controls are included. Four additional STEP assemblies capture
the final tilt toward each numbered sub-bin.

### Water-bottle demonstration

A nine-second illustrative sequence places an empty water bottle sideways on the
level plate, scans it, displays “Water bottle detected,” tips the plate, rolls
the bottle into the selected sub-bin, and returns the plate to level. The
canopy stays visible but becomes transparent during the demo so the mechanism
can be seen through it. Reset restores its opaque appearance; this is a preview
effect, not a change of CAD material. The actual 3D
screen displays loading, scanning, the detected water bottle, its numbered
destination, delivery, return to level and ready states. It is synchronized
with the animation, shows a paused status when paused, and goes blank on reset.

The selected bin is only an example route; the default is sub-bin 4. It does
not assign a bottle to any currently undecided category. Detection chimes,
soft synthetic actuator cues and a landing cue are generated locally using
Web Audio; no external audio assets or network requests are needed.

This is a scripted visualization, not computer-vision inference, live sensor
output or a rigid-body simulation. STEP/STL display geometry is unchanged;
screen content is generated locally for the HTML demo, not engraved in CAD.

## Provisional geometry

| Parameter | Value |
|---|---:|
| Cylindrical body diameter | 600 mm |
| Body / rear-base footprint | 600 × 670 mm |
| Bin rim height | 800 mm |
| Overall height | 1,300 mm |
| Canopy diameter | 660 mm |
| Rear mast center, behind bin center | 325 mm |
| Liner height | 720 mm |
| Nominal capacity to brim | 43.09 L per liner |
| Plate diameter / thickness | 280 / 4 mm |
| Level plate top height | 979 mm |
| Maximum resultant plate tilt | 38° |
| Liner-to-shell radial clearance | 7 mm |
| Adjacent-liner gap | 6 mm |
| IR sensor window height | 1,266 mm |

These are editable working assumptions, not user-specified dimensions. Brim
capacity excludes bag folds and full-threshold headroom. Component colors only
distinguish geometry; materials and category colors are not fixed.

## Waste path and full-bin behavior

1. Place one item on the level plate for identification.
2. Confirm the intended sub-bin is available. If it is full or its fill reading
   is unavailable, keep the plate level and request service. Do not redirect an
   item to a different category to bypass a full destination.
3. Tilt toward that sector, deliver the item, then return to level.
4. A confirmed full reading makes the destination unavailable and should send a
   personnel notification identifying the sub-bin. If all bins are unavailable,
   suspend sorting and show an out-of-service message.
5. After bag replacement, verify an empty reading and explicitly clear that
   bin's service state before accepting it again.

This is the intended control sequence; firmware, real detection, notifications
and full-bin simulation are not implemented. No messages were sent to personnel.
V2 has no physical intake lock: keeping the plate level stops automatic feeding
but does not prevent someone from placing additional waste on it. A production
design needs an appropriate intake/access interlock and jam handling.

Four generic downward-facing IR distance-sensor pods sit beneath the canopy,
each centered over its liner at a 190 mm radius. The illustrative full threshold
is a waste surface 100 mm below the rim, corresponding to a 566 mm sensor-to-
surface distance. This is not a measured volume percentage.

The geometric sightline check assumes a 15° full receiver field of view. At
the level plate it leaves approximately 12.22 mm radial clearance. Sample only
when the plate is level and empty; moving items or the tipped plate can obstruct
measurements. Use repeated readings and hysteresis, and test uneven piles,
reflective/transparent items, bag folds and dirty windows. The assumed field of
view is not a specification of a selected sensor.

A candidate for evaluation is the
[ST VL53L1X IR/ToF distance sensor](https://www.st.com/en/imaging-and-photonics-solutions/vl53l1x.html).
ST documents programmable receiver regions in
[AN5191](https://www.st.com/resource/en/application_note/dm00516219-using-the-programmable-region-of-interest-roi-with-the-vl53l1x-stmicroelectronics.pdf).
The modeled 32 × 32 × 30 mm pods are generic envelopes, not verified PCB fits.
Optical windows, exact receiver settings and calibration remain to be selected.

### Lidless sensing option — not yet modeled

If the canopy is removed, mount the four level sensors on small fixed over-rim
brackets or rear-mast arms instead. Position each sensor above the bag fold,
aimed through its open mouth rather than through its lined side wall. A bag
retaining collar must keep loose folds out of the sensing path. Brackets need
clearance from the plate, falling items and liner-removal path.

A multizone ToF sensor is a candidate to evaluate for uneven waste surfaces;
[ST's VL53L5CX datasheet](https://www.st.com/resource/en/datasheet/vl53l5cx.pdf)
documents 4×4/8×8 distance zones and waste-bin content monitoring as an application.
Its wider field of view requires a new placement/zone-selection check; the
current 15° sightline assumptions do not automatically apply. Actual bags,
black/transparent waste, ambient light and dirty windows still need testing.

Optional independently supported weighing platforms under each liner can add
an overweight limit without optical interference from the bag. Weight alone
does not establish fullness by volume: a bin of empty bottles can be full but
light. Take stable level readings between deliveries, require sustained
threshold readings, and treat a blocked/invalid sensor as unavailable rather
than empty. This is a proposed architecture, not implemented hardware or firmware.

## Service and mechanical scope

The rear mast is hollow for cables and attaches to a rear extension of the base.
The downward-aimed identification camera attaches beneath the canopy; the blank
display attaches to the rear mast above the rim. Space beneath the liner support
deck is reserved as a possible controller/power bay.

For top removal of the liners, disconnect power and remove the canopy/sensor
assembly and the cantilever/plate module. The rear mast can stay in place.
Exact quick-release hardware, connectors, bag retention, handles and lifting
aids are not yet detailed; the exploded view is not a verified service procedure.

The two actuator housings reserve space; they are not selected, torque-rated
servo motors. Bearings, drive coupling, hard stops, pinch-point guarding,
cantilever deflection, stability, fabrication tolerances and maximum item mass
remain unresolved. A 38° plate angle does not guarantee every material will
slide or roll. Surface finish, item-size limits and real-waste testing are needed.

## Source and regeneration

- [V2 editable parameters](cad/parameters_v2.json)
- [V2 CadQuery model](cad/smart_bin_v2.py)
- [Shared geometric helpers in V1 source](cad/smart_bin.py)
- [Deterministic CAD renderer](cad/render.py)
- [Animated viewer template](cad/viewer_v2_template.html)
- [Viewer logic verification](cad/verify_viewer.cjs)

Python 3.12 was used in the isolated `.venv`. Install the pinned dependencies
from `requirements.txt`, then run from the project root:

```sh
.venv/bin/python cad/smart_bin_v2.py
.venv/bin/python cad/render.py
node cad/verify_viewer.cjs
```

STEP exports are in millimetres, using
[CadQuery's assembly exporter](https://cadquery.readthedocs.io/en/latest/importexport.html).
The Python and JSON are the parametric source; imported STEP does not preserve
a native feature tree. STL coordinates are millimetres, but STL does not encode
units. Native browser WebGL and Web Audio are used; the HTML has no CDN dependency.

Validation checks 41 positive-volume single-solid B-reps, component overlaps
in neutral and 16 sampled tilt poses, and STEP round-trip solid count and volume.
It does not certify continuous motion or a functioning prototype. The viewer
test executes the actual application logic with DOM/WebGL/audio test doubles;
it checks the sequence, controls, cue scheduling, synchronized 3D-screen content,
projected screen visibility and CAD-aligned transforms,
not GPU rendering or audible playback. No browser connection was available for
end-to-end playback verification in this environment.


## Repository bundle

This folder contains V2 only. The retained `cad/smart_bin.py` supplies shared
geometric helpers; the superseded V1 exports are not included.

GitHub displays the HTML source rather than running the preview. Download the
repository or [V2 package](smart_bin_concept_v2.zip), then open
`v2/viewer.html` locally. No hosting service or network connection is needed.
