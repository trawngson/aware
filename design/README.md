# Smart sorting bin — physical CAD concept v3

The concept is a bin people throw into as they would with any other. The outer
wall rises above **one central tipping plate**, and a funnel inside it guides a
thrown item onto that plate. The item is identified there; the same plate then
tilts toward one of four separate quarter-circle liners. There is no mast,
canopy, rotary carrier, intake hopper or bottom-release gate. All category
plaques remain blank. The display lights up only in the demo; numbered parts do
not assign waste categories.

Two perpendicular, limited-travel horizontal hinges let the single plate tip
toward all four sectors. A single fixed-axis hinge would only tip in two
opposing directions. A cross-beam inside the head carries the plate joint; its
four arms run above the liner dividers, so none crosses a liner opening.

The rear rim rises into a console. It holds the display, which leans back 12°,
and the identification camera, which looks down at the plate at about 50°.

V3 replaces v2 because feedback on v2 was that people will throw items in, not
set them carefully on an exposed plate.

## Inspect the design

- [Offline animated 3D preview](v3/viewer.html) — open in a WebGL-capable
  browser and click **Play detection demo**. Sound begins with that click.
- [Design sheet](v3/preview.png)
- [Assembled STEP](v3/smart_bin_assembly.step) — separate named solids.
- [Exploded STEP](v3/smart_bin_exploded.step)
- [Individual STEP and STL parts](v3/parts/)
- [Geometry validation](v3/validation.json)

The viewer works offline. Drag to orbit, scroll to zoom, cut away the side
facing you, hide the shell, funnel or fill sensors, inspect the tilt joint, or
choose any of four tipping directions. Pause, resume, reset and mute controls
are included. Four additional STEP assemblies capture the final tilt toward
each numbered sub-bin.

### Water-bottle demonstration

A nine-second illustrative sequence throws an empty water bottle in over the
front rim, lets it come to rest on the level plate, scans it, displays “Water
bottle detected,” tips the plate, rolls the bottle out under the throat lip
into the selected sub-bin, and returns the plate to level. During the demo the
side of the shell, funnel and sensor pods facing the viewer is cut away so the
plate can be seen. Reset closes it again; this is a preview effect, not a
change of CAD geometry. The actual 3D screen displays ready, scanning, the
detected water bottle, its numbered destination, delivery, return to level and
ready states. It is synchronized with the animation, shows a paused status
when paused, and goes blank on reset.

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
| Footprint | 600 × 600 mm |
| Rim height (throw-in edge) | 1,050 mm |
| Overall height, top of console | 1,240 mm |
| Funnel mouth / throat diameter | 550 / 330 mm |
| Funnel wall slope | 51.8° |
| Plate diameter / thickness | 320 / 4 mm |
| Level plate top height | 780 mm |
| Plate below rim / below throat lip | 270 / 100 mm |
| Plate-to-throat radial gap | 5 mm |
| Maximum resultant plate tilt | 45° |
| Exit gap at full tilt, under the lip / under the skirt | 172.2 / 99.3 mm |
| Liner height | 508 mm |
| Nominal capacity to brim | 30.3 L per liner |
| Liner-to-shell radial clearance | 7 mm |
| Adjacent-liner gap | 6 mm |
| IR sensor window height | 880 mm |

These are editable working assumptions, not user-specified dimensions. Brim
capacity excludes bag folds and full-threshold headroom. Component colors only
distinguish geometry; materials and category colors are not fixed.

The plate sits 100 mm below the rigid throat lip, so tipping it opens a wide
exit on the low side only, toward the chosen liner. A flexible skirt of 36
strips, 14 mm wide and about 15 mm apart, hangs from the lip down to the plate
so that items do not roll off the level plate through that 100 mm gap. At full
tilt the low side opens 99.3 mm under the skirt; thicker items have to push the
strips aside. Setting `skirt_strip_count` to 0 in the parameters removes the
skirt.

## Waste path and full-bin behavior

1. Throw one item into the funnel. It comes to rest on the level plate and is
   identified there.
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
V3 has no physical intake lock: keeping the plate level stops automatic feeding
but does not prevent someone from throwing in additional waste. A production
design needs an appropriate intake flap or interlock and jam handling.

Four generic downward-facing IR distance-sensor pods sit on arms from the
throat lip, under the funnel and out of the item path, each centered over its
liner at a 215 mm radius. The illustrative full threshold is a waste surface
100 mm below the liner rim, corresponding to a 392 mm sensor-to-surface
distance. This is not a measured volume percentage.

The geometric sightline check assumes a 15° full receiver field of view. At
the full threshold that cone is about 103 mm across; the check keeps it inside
its liner and clear of the support arms. Sample only when the plate is level
and at rest; items leaving the plate fall through the sensing path. Use
repeated readings and hysteresis, and test uneven piles, reflective/transparent
items, bag folds and dirty windows. The assumed field of view is not a
specification of a selected sensor.

A candidate for evaluation is the
[ST VL53L1X IR/ToF distance sensor](https://www.st.com/en/imaging-and-photonics-solutions/vl53l1x.html).
ST documents programmable receiver regions in
[AN5191](https://www.st.com/resource/en/application_note/dm00516219-using-the-programmable-region-of-interest-roi-with-the-vl53l1x-stmicroelectronics.pdf).
The modeled 32 × 32 × 30 mm pods are generic envelopes, not verified PCB fits.
Optical windows, exact receiver settings and calibration remain to be selected.

### Other sensing options — not modeled

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

## Open points

- The console camera does not see the whole plate. The funnel's lower edge
  hides the rear 57.7 mm of the plate at surface level, about 16% of its area.
  A second or relocated camera is needed; this is undecided.
- Several items thrown together reach the plate together and would be tipped
  into one liner.
- While the plate is tipped, an item thrown in can pass its raised side (an
  opening of up to about 90 mm) into the opposite liner. An intake flap or
  interlock is needed.
- Thin items can slip through the 5 mm plate gap. Items wider than the throat,
  or thicker than the 172.2 mm gap under the rigid lip, will jam.
- The skirt is modeled as rigid strips. Its material and stiffness are not
  chosen, and strips being pushed aside by larger items is neither simulated
  nor tested.
- The funnel is open to rain.

## Service and mechanical scope

Funnel, skirt, plate, tilt joint and sensors form one head that lifts off at
the seam above the liners, which then lift out from the top. Hinge and latch
hardware, connectors, bag retention, handles and lifting aids are not modeled;
the exploded view is not a verified service procedure. Cable routing from the
console and head to the base is not modeled either. Space beneath the liner
support deck is reserved as a possible controller/power bay.

The two actuator housings reserve space; they are not selected, torque-rated
servo motors. Bearings, drive coupling, hard stops, pinch-point guarding,
cross-beam deflection, stability, fabrication tolerances and maximum item mass
remain unresolved. A 45° plate angle does not guarantee every material will
slide or roll. Surface finish, item-size limits and real-waste testing are needed.

## Source and regeneration

- [V3 editable parameters](cad/parameters_v3.json)
- [V3 CadQuery model](cad/smart_bin_v3.py)
- Shared geometric helpers in the [V1](cad/smart_bin.py) and [V2](cad/smart_bin_v2.py) sources
- [Deterministic CAD renderer](cad/render.py)
- [Animated viewer template](cad/viewer_v3_template.html)
- [Viewer logic verification](cad/verify_viewer_v3.cjs)

Python 3.12 was used in the isolated `.venv`. Install the pinned dependencies
from `requirements.txt`, then run from the project root:

```sh
.venv/bin/python cad/smart_bin_v3.py
.venv/bin/python cad/render.py --output v3
node cad/verify_viewer_v3.cjs
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
it checks the sequence, controls, cue scheduling, the camera-facing cutaway,
synchronized 3D-screen content, projected screen visibility, CAD-aligned
transforms, and that the demo bottle clears the rim, funnel, throat lip and
skirt. It does not check GPU rendering or audible playback. The viewer was also
loaded in the system WebKit engine, where the shaders compiled and every view
and the demo drew without page errors; sound was not checked.

## Previous revisions

V2 remains in [v2](v2/) and [the V2 package](smart_bin_concept_v2.zip),
which includes its own README. It has a rear mast and canopy, an 800 mm rim and
an exposed plate that items are placed on. To regenerate it:

```sh
.venv/bin/python cad/smart_bin_v2.py
.venv/bin/python cad/render.py
node cad/verify_viewer.cjs
```

## Repository bundle

This folder contains V3 and V2. The retained `cad/smart_bin.py` supplies shared
geometric helpers; the superseded V1 exports are not included.

GitHub displays the HTML source rather than running the preview. Download the
repository, then open `v3/viewer.html` locally. No hosting service or network
connection is needed.
