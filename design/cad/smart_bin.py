"""Parametric concept CAD, millimetres. No waste-category names are assigned.

Run from the project root: .venv/bin/python cad/smart_bin.py
STEP contains separate named solid components; the Python + JSON retain parameters.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / ".cache"))
import cadquery as cq


@dataclass
class Part:
    name: str
    shape: cq.Shape
    color: tuple[float, float, float]
    group: str
    explode: tuple[float, float, float] = (0, 0, 0)
    description: str = ""


def box(w, d, h, center, radius=0):
    wp = cq.Workplane("XY").box(w, d, h)
    if radius:
        wp = wp.edges("|Y").fillet(radius)
    return wp.translate(center).val()


def tube(ro, ri, z, h):
    wp = cq.Workplane("XY").circle(ro)
    if ri:
        wp = wp.circle(ri)
    return wp.extrude(h).translate((0, 0, z)).val()


def sector(ro, ri, side_offset, z, h):
    """True circular quarter-annulus with straight walls offset from both axes."""
    extent = ro + 5
    quadrant = box(extent, extent, h + 2,
                   (side_offset + extent / 2, side_offset + extent / 2,
                    z + h / 2))
    return tube(ro, ri, z, h).intersect(quadrant).clean()


def build(p):
    radius = p["body_diameter_mm"] / 2
    rim = p["rim_height_mm"]
    top = p["overall_height_mm"]
    liner_z = p["liner_bottom_mm"]
    wall = p["liner_wall_mm"]
    liner_ro = radius - p["shell_wall_mm"] - p["liner_radial_clearance_mm"]
    liner_ri = p["liner_inner_radius_mm"]
    gap = p["sector_gap_mm"] / 2
    lip_z = rim - p["lip_height_mm"]
    mast_r = p["mast_outer_radius_mm"]
    canopy_z = top - p["canopy_thickness_mm"]
    mast_z = rim - p["mast_insertion_mm"]
    dz = rim + p["display_center_above_rim_mm"]
    sz = rim + p["sensor_center_above_rim_mm"]

    assert len(p["category_labels"]) == 4 and not any(p["category_labels"]), \
        "This revision deliberately has four blank category labels."
    assert liner_ro > liner_ri + 80
    assert liner_ri > p["core_radius_mm"]
    assert liner_z + p["liner_floor_mm"] < lip_z < rim
    assert canopy_z > dz + p["display_height_mm"] / 2 + 25
    assert sz + p["sensor_size_mm"] / 2 < dz - p["display_height_mm"] / 2
    assert mast_r > p["mast_wall_mm"]
    assert p["canopy_diameter_mm"] >= p["body_diameter_mm"]

    parts = []

    def add(name, shape, color, group, explode=(0, 0, 0), description=""):
        parts.append(Part(name, shape.clean(), color, group, explode, description))

    charcoal = (0.19, 0.23, 0.26)
    light = (0.79, 0.81, 0.81)
    metal = (0.61, 0.66, 0.69)
    glass = (0.07, 0.11, 0.14)

    add("outer_shell", tube(radius, radius - p["shell_wall_mm"], 24, rim - 24),
        light, "shell", (0, 0, -70), "Cylindrical outer shell; open at top")
    add("bottom_plinth", tube(radius, 0, 8, 16), charcoal, "base", (0, 0, -120),
        "Bottom closure / ballast envelope")
    add("liner_support_deck", tube(radius - p["shell_wall_mm"], 0, liner_z - 8, 8),
        metal, "base", (0, 0, -50), "Common support floor below four liners")
    foot_pos = radius * 0.6
    for i, (x, y) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1)), 1):
        add(f"foot_{i}", tube(25, 0, 0, 8).translate((x * foot_pos, y * foot_pos, 0)),
            charcoal, "base", (0, 0, -140), "Foot envelope")

    # One liner master, rotated into four separate compartments. Pocket does not
    # perforate any wall: the liners have closed sides and bottoms, open tops.
    outer = sector(liner_ro, liner_ri, gap, liner_z, rim - liner_z)
    lower_void = sector(liner_ro - wall, liner_ri + wall, gap + wall,
                        liner_z + p["liner_floor_mm"],
                        lip_z - liner_z - p["liner_floor_mm"])
    upper_void = sector(liner_ro - p["lip_width_mm"],
                        liner_ri + p["lip_width_mm"], gap + p["lip_width_mm"],
                        lip_z, p["lip_height_mm"] + 1)
    cavity = lower_void.fuse(upper_void).clean()
    liner = outer.cut(cavity).clean()
    capacity_l = outer.intersect(cavity).Volume() / 1e6
    liner_colors = [(0.87, 0.88, 0.86), (0.77, 0.80, 0.79),
                    (0.82, 0.84, 0.83), (0.71, 0.75, 0.75)]
    label_radius = liner_ro - p["lip_width_mm"] / 2
    # Narrow blank plaques on the flat, thickened rim; no named or color-coded
    # categories. A technical component index exists only in the CAD hierarchy.
    plaque = box(44, 5, 1.5, (0, label_radius, rim + .75))
    for i in range(4):
        angle = i * 90
        theta = math.radians(angle + 45)
        offset = (185 * math.cos(theta), 185 * math.sin(theta), 100)
        add(f"sub_bin_{i + 1}", liner.rotate((0, 0, 0), (0, 0, 1), angle),
            liner_colors[i], "liners", offset, "Removable hollow quarter-circle liner")
        add(f"blank_label_{i + 1}", plaque.rotate((0, 0, 0), (0, 0, 1), angle - 45),
            (0.92, 0.93, 0.92), "labels", offset, "Blank category plaque")

    # Fixed hub + stop shelf; tower inserts only 80 mm, so the whole tower can
    # be lifted out before the full-height liners are extracted.
    core = tube(p["core_radius_mm"], mast_r + 2, liner_z, rim - liner_z)
    collar = tube(p["core_radius_mm"] + 4, mast_r, rim, 8)
    stop = tube(p["core_radius_mm"], mast_r - p["mast_wall_mm"] - 2, mast_z - 8, 8)
    lock_bore = cq.Solid.makeCylinder(3.2, 2 * (p["core_radius_mm"] + 6),
                                     cq.Vector(-p["core_radius_mm"] - 6, 0, rim - 20),
                                     cq.Vector(1, 0, 0))
    hub = core.fuse(collar, stop).cut(lock_bore).clean()
    add("fixed_central_socket", hub, charcoal, "hub", (0, 0, 0),
        "Fixed hub with insertion stop and transverse retention-pin bore")
    mast = tube(mast_r, mast_r - p["mast_wall_mm"], mast_z, canopy_z - mast_z)
    mast = mast.cut(lock_bore)
    tower_offset = (0, 0, 250)
    add("removable_hollow_mast", mast, metal, "tower", tower_offset,
        "Hollow central mast; 80 mm removable socket insertion")

    def mount(name, z, h, rear_y):
        ring = tube(mast_r + 6, mast_r, z - h / 2, h)
        bridge = box(42, abs(rear_y) - mast_r + 1, h,
                     (0, (rear_y - mast_r + 1) / 2, z))
        bracket = ring.fuse(bridge).cut(tube(mast_r, 0, z - h / 2 - 1, h + 2))
        add(name, bracket, metal, "tower", tower_offset,
            "Concept clamp / standoff envelope")

    dw, dh, dd = (p["display_width_mm"], p["display_height_mm"],
                  p["display_depth_mm"])
    display_rear = -mast_r - 8
    display_y = display_rear - dd / 2
    display_front = display_rear - dd
    housing = box(dw, dd, dh, (0, display_y, dz), 8)
    pocket = box(dw - 8, dd - 8, dh - 8, (0, display_y, dz), 4)
    window = box(dw - 28, 10, dh - 32, (0, display_front + 2, dz), 4)
    add("display_housing", housing.cut(pocket.fuse(window)), charcoal, "tower",
        tower_offset, "Hollow display envelope; actual display hardware remains unspecified")
    add("blank_display_face", box(dw - 28, 2, dh - 32,
                                  (0, display_front + 1, dz), 4),
        glass, "tower", tower_offset, "Blank screen placeholder")
    mount("display_mount", dz, 50, display_rear)

    ss, sd = p["sensor_size_mm"], p["sensor_depth_mm"]
    sensor_rear = -mast_r - 7
    sensor_y = sensor_rear - sd / 2
    sensor_front = sensor_rear - sd
    housing = box(ss, sd, ss, (0, sensor_y, sz), 6)
    pocket = box(ss - 8, sd - 8, ss - 8, (0, sensor_y, sz), 3)
    lens_radius = ss * .175
    lens_bore = cq.Solid.makeCylinder(lens_radius, 7,
                                      cq.Vector(0, sensor_front - 1, sz), cq.Vector(0, 1, 0))
    add("sensor_housing", housing.cut(pocket.fuse(lens_bore)), charcoal, "tower",
        tower_offset, "Hollow camera / sensor envelope, positioned below screen")
    add("sensor_lens_placeholder",
        cq.Solid.makeCylinder(lens_radius - .2, 2,
                              cq.Vector(0, sensor_front - 1, sz), cq.Vector(0, 1, 0)),
        glass, "tower", tower_offset, "Optical envelope only; sensor type and field of view TBD")
    mount("sensor_mount", sz, 40, sensor_rear)

    canopy_radius = p["canopy_diameter_mm"] / 2
    canopy = cq.Workplane("XY").circle(canopy_radius).extrude(p["canopy_thickness_mm"])
    canopy = canopy.edges().fillet(2).translate((0, 0, canopy_z)).val()
    recess = tube(canopy_radius - 10, mast_r + 12, canopy_z - 1,
                  p["canopy_thickness_mm"] - 3)
    add("canopy", canopy.cut(recess), light, "tower", (0, 0, 340),
        "Shallow overhead canopy with underside pocket and central mast land")

    # Automatic-routing concept: a single front-central intake loads a closed
    # carrier at the park angle (-90 degrees). The carrier rotates around the
    # mast to a quarter-bin center, then its bottom gate releases the item.
    # Drives, bearings, hinges and hardware are envelopes, not selected parts.
    carrier_r = p["routing_carrier_radius_mm"]
    cw = p["routing_carrier_tangential_width_mm"]
    cd = p["routing_carrier_radial_depth_mm"]
    ch = p["routing_carrier_height_mm"]
    carrier_z = rim + p["routing_carrier_floor_above_rim_mm"]
    intake_z = rim + p["intake_bottom_above_rim_mm"]
    intake_h = p["intake_height_mm"]
    assert carrier_z + ch + 10 < intake_z
    assert intake_z + intake_h < dz - dh / 2
    assert math.hypot(carrier_r + cd / 2, cw / 2) < liner_ro
    assert (carrier_r - (cd - 6) / 2 - (cw - 6) / 2) / math.sqrt(2) > gap + p["lip_width_mm"]
    assert carrier_r - cd / 2 > liner_ri + p["lip_width_mm"]
    routing_offset = (0, 0, 190)
    intake_outer = (cq.Workplane("XY", origin=(0, -carrier_r, intake_z))
                    .rect(cw, cd).workplane(offset=intake_h)
                    .rect(cw + 60, cd + 40).loft()).val()
    intake_void = (cq.Workplane("XY", origin=(0, -carrier_r, intake_z - 1))
                   .rect(cw - 6, cd - 6).workplane(offset=intake_h + 2)
                   .rect(cw + 54, cd + 34).loft()).val()
    optical_port = box(60, 60, 36, (0, -carrier_r + cd / 2 + 12, sz))
    intake = intake_outer.cut(intake_void.fuse(optical_port))
    add("single_intake_hopper", intake, metal, "routing_fixed", routing_offset,
        "One intake above rotary carrier, with camera observation port")
    add("intake_holding_gate", box(cw - 6, cd - 6, 3,
                                    (0, -carrier_r, intake_z + 1.5)),
        charcoal, "routing_fixed", routing_offset,
        "Closed holding gate; actuator and hinge details TBD")
    support_top = intake_z
    support_h = 15
    rear = -carrier_r + cd / 2
    support_ring = tube(mast_r + 10, mast_r, support_top - support_h, support_h)
    support_plate = box(cw + 20, abs(rear) - mast_r + 5, support_h,
                        (0, (rear - mast_r + 5) / 2, support_top - support_h / 2))
    support = support_ring.fuse(support_plate).cut(
        tube(mast_r, 0, support_top - support_h - 1, support_h + 2))
    add("intake_support", support, metal, "routing_fixed", routing_offset,
        "Fixed intake standoff connected to removable mast")
    add("stationary_bearing_land", tube(44, mast_r, rim + 8, 4), metal,
        "routing_fixed", routing_offset, "Concept axial bearing support")
    add("rotor_bearing_envelope", tube(90, mast_r + 2, rim + 12, 12), charcoal,
        "routing_rotating", routing_offset, "Indexed rotor / bearing and drive envelope")
    arm = box(50, abs(rear) - 40, 16,
              (0, (rear - 40) / 2, rim + 32))
    add("rotary_carrier_arm", arm, metal, "routing_rotating", routing_offset,
        "Arm couples rotor to carrier at 180 mm radius")
    carrier = box(cw, cd, ch, (0, -carrier_r, carrier_z + ch / 2))
    carrier = carrier.cut(box(cw - 6, cd - 6, ch + 2,
                              (0, -carrier_r, carrier_z + ch / 2)))
    add("rotating_item_carrier", carrier, charcoal, "routing_rotating", routing_offset,
        "Hollow single-item carrier shown at the front loading/park position")
    add("carrier_bottom_gate", box(cw - 6, cd - 6, 3,
                                    (0, -carrier_r, carrier_z + 1.5)),
        metal, "routing_rotating", routing_offset,
        "Bottom-release gate, kept closed until an eligible bin is selected")
    motor = tube(75, mast_r + 2, rim + 40, 75)
    add("index_drive_envelope", motor, charcoal, "routing_fixed", routing_offset,
        "Reserved motor / transmission / mounting space; hardware not selected")

    # Four IR/ToF envelopes, one over the middle of each quarter-bin. They move
    # with the tower during service. No particular sensor PCB has been selected.
    pod_w = p["fill_sensor_housing_width_mm"]
    pod_h = p["fill_sensor_housing_height_mm"]
    pod_top = top - 4
    pod_bottom = pod_top - pod_h
    for i in range(4):
        theta = math.radians(45 + i * 90)
        sx = p["fill_sensor_radial_position_mm"] * math.cos(theta)
        sy = p["fill_sensor_radial_position_mm"] * math.sin(theta)
        outer = box(pod_w, pod_w, pod_h, (sx, sy, pod_top - pod_h / 2))
        pocket = box(pod_w - 6, pod_w - 6, pod_h - 6,
                     (sx, sy, pod_top - pod_h / 2))
        aperture = cq.Solid.makeCylinder(6, 8, cq.Vector(sx, sy, pod_bottom - 1),
                                         cq.Vector(0, 0, 1))
        pod = outer.cut(pocket.fuse(aperture))
        add(f"fill_sensor_housing_{i + 1}", pod, charcoal, "fill_sensors",
            (0, 0, 340), "Downward-facing IR distance-sensor enclosure envelope")
        window = cq.Solid.makeCylinder(5.8, 2, cq.Vector(sx, sy, pod_bottom),
                                      cq.Vector(0, 0, 1))
        add(f"fill_sensor_window_{i + 1}", window, glass, "fill_sensors",
            (0, 0, 340), "IR-transmissive window placeholder; material TBD")

    metrics = {
        "units": "mm",
        "body_diameter_mm": 2 * radius,
        "canopy_diameter_mm": 2 * canopy_radius,
        "rim_height_mm": rim,
        "overall_height_mm": top,
        "liner_height_mm": rim - liner_z,
        "nominal_brim_capacity_per_liner_l": round(capacity_l, 2),
        "nominal_total_brim_capacity_l": round(4 * capacity_l, 2),
        "liner_shell_radial_clearance_mm": p["liner_radial_clearance_mm"],
        "liner_hub_radial_clearance_mm": liner_ri - p["core_radius_mm"],
        "adjacent_liner_gap_mm": p["sector_gap_mm"],
        "mast_insertion_mm": p["mast_insertion_mm"],
        "rim_to_canopy_underside_mm": canopy_z - rim,
        "fill_sensor_count": 4,
        "waste_entry": "Single intake with holding gate and indexed rotary carrier",
        "carrier_park_angle_degrees": -90,
        "carrier_destination_angles_degrees": [45, 135, 225, 315],
        "intake_top_height_mm": intake_z + intake_h,
        "carrier_opening_mm": [cw - 6, cd - 6],
        "fill_sensor_window_height_mm": pod_bottom,
        "fill_sensor_to_empty_floor_mm": pod_bottom - liner_z - p["liner_floor_mm"],
        "provisional_full_level_mm": rim - p["full_level_below_rim_mm"],
        "provisional_full_distance_threshold_mm": pod_bottom - rim + p["full_level_below_rim_mm"],
        "category_labels": p["category_labels"],
        "status": "Concept geometry; dimensions and hardware are provisional"
    }
    return parts, metrics


def validate(parts):
    results = []
    for part in parts:
        solids = part.shape.Solids()
        valid = part.shape.isValid()
        volume = part.shape.Volume()
        if not valid or len(solids) != 1 or volume <= 0:
            raise ValueError(f"Invalid part: {part.name}; valid={valid}, solids={len(solids)}")
        results.append({"name": part.name, "valid": valid, "solid_count": len(solids),
                        "volume_mm3": round(volume, 3)})
    collisions = []
    # Shared faces are intentional mating surfaces. Positive overlap is not.
    for i, a in enumerate(parts):
        ab = a.shape.BoundingBox()
        for b in parts[i + 1:]:
            bb = b.shape.BoundingBox()
            if any(min(getattr(ab, f"{axis}max"), getattr(bb, f"{axis}max")) -
                   max(getattr(ab, f"{axis}min"), getattr(bb, f"{axis}min")) < 1e-5
                   for axis in "xyz"):
                continue
            overlap = a.shape.intersect(b.shape).Volume()
            if overlap > .01:
                collisions.append({"a": a.name, "b": b.name,
                                   "overlap_mm3": round(overlap, 3)})
    if collisions:
        raise ValueError(f"Assembly intersections: {collisions}")
    return {"parts": results, "positive_volume_intersections": collisions,
            "checks": ["Every part is a valid single B-rep solid",
                       "No component pair has positive-volume overlap",
                       "Four separate liners and four blank category plaques"]}


def export(parts, metrics, output):
    output.mkdir(parents=True, exist_ok=True)
    assembly = cq.Assembly(name="smart_bin_concept_v1")
    exploded = cq.Assembly(name="smart_bin_exploded_v1")
    for part in parts:
        assembly.add(part.shape, name=part.name, color=cq.Color(*part.color))
        exploded.add(part.shape.translate(part.explode), name=part.name,
                     color=cq.Color(*part.color))
    assembly.export(str(output / "smart_bin_assembly.step"))
    exploded.export(str(output / "smart_bin_exploded.step"))
    routing_checks = []
    for destination, angle in enumerate(metrics["carrier_destination_angles_degrees"], 1):
        rotated_parts = []
        route = cq.Assembly(name=f"smart_bin_route_to_sub_bin_{destination}")
        for part in parts:
            shape = part.shape
            if part.group == "routing_rotating":
                shape = shape.rotate((0, 0, 0), (0, 0, 1), angle + 90)
            rotated_parts.append(Part(part.name, shape, part.color, part.group))
            route.add(shape, name=part.name, color=cq.Color(*part.color))
        validate(rotated_parts)
        route.export(str(output / f"route_to_sub_bin_{destination}.step"))
        routing_checks.append({"destination": destination, "angle_degrees": angle,
                               "positive_volume_intersections": []})
    # A reusable single liner and one STL per distinct component are convenient
    # for prototyping. STLs use mm coordinates and do not carry a formal unit tag.
    part_dir = output / "parts"
    part_dir.mkdir(exist_ok=True)
    for part in parts:
        cq.exporters.export(part.shape, str(part_dir / f"{part.name}.step"))
        cq.exporters.export(part.shape, str(part_dir / f"{part.name}.stl"),
                            tolerance=.15, angularTolerance=.08)
    mesh_data = []
    for part in parts:
        vertices, triangles = part.shape.tessellate(.8, .15)
        mesh_data.append({"name": part.name, "group": part.group,
                          "color": part.color, "explode": part.explode,
                          "vertices": [[round(v.x, 4), round(v.y, 4), round(v.z, 4)]
                                       for v in vertices], "triangles": triangles})
    (output / "mesh.json").write_text(json.dumps(mesh_data, separators=(",", ":")))
    (output / "dimensions.json").write_text(json.dumps(metrics, indent=2) + "\n")
    with (output / "components.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["component", "quantity", "description", "category_text"])
        for part in parts:
            writer.writerow([part.name, 1, part.description, ""])
    # Re-import the assembled STEP and verify exported solid count + volume.
    imported = cq.importers.importStep(str(output / "smart_bin_assembly.step"))
    imported_solids = imported.solids().vals()
    expected_volume = sum(part.shape.Volume() for part in parts)
    actual_volume = sum(s.Volume() for s in imported_solids)
    # STEP translations of fillets may change volume by a few mm³; use a small
    # relative tolerance (1e-6) as well as an absolute floor of 1 mm³.
    if (len(imported_solids) != len(parts) or
            abs(actual_volume - expected_volume) > max(1, expected_volume * 1e-6)):
        raise ValueError(f"STEP round-trip failed: {len(imported_solids)}/{len(parts)} "
                         f"solids, volume error {abs(actual_volume - expected_volume)} mm³")
    return {"roundtrip_solid_count": len(imported_solids),
            "roundtrip_volume_error_mm3": round(abs(actual_volume - expected_volume), 6),
            "roundtrip_relative_volume_error": abs(actual_volume - expected_volume) / expected_volume,
            "indexed_routing_position_checks": routing_checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, default=ROOT / "cad/parameters.json")
    parser.add_argument("--output", type=Path, default=ROOT / "designs/v1")
    args = parser.parse_args()
    parameters = json.loads(args.parameters.read_text())
    print("Building the four-compartment concept…", flush=True)
    parts, metrics = build(parameters)
    print(f"Validating {len(parts)} separate components…", flush=True)
    report = validate(parts)
    print("Exporting STEP, individual parts and preview meshes…", flush=True)
    report.update(export(parts, metrics, args.output))
    report["cadquery_version"] = cq.__version__
    (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(metrics, indent=2))
    print(f"STEP round-trip valid: {report['roundtrip_solid_count']} solids", flush=True)


if __name__ == "__main__":
    main()
