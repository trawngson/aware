"""Rear-mast smart bin with one plate on two bounded tilt axes. All units mm.

The two servo housings are reserved envelopes, not selected torque-rated hardware.
The V1 geometric helpers are retained; this script writes only v2 by default.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

from smart_bin import Part, ROOT, box, cq, sector, tube, validate


def cylinder(radius, length, origin, direction):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*origin), cq.Vector(*direction))


def angles(tilt_degrees, direction_degrees):
    tilt, direction = map(math.radians, (tilt_degrees, direction_degrees))
    roll = math.asin(-math.sin(tilt) * math.sin(direction))
    pitch = math.atan2(math.sin(tilt) * math.cos(direction), math.cos(tilt))
    return math.degrees(roll), math.degrees(pitch)


def posed(parts, pivot_z, roll, pitch):
    result = []
    for part in parts:
        shape = part.shape
        if part.group == "tilt_plate":
            shape = shape.rotate((0, 0, pivot_z), (1, 0, pivot_z), roll)
        if part.group in ("tilt_plate", "tilt_pitch"):
            shape = shape.rotate((0, 0, pivot_z), (0, 1, pivot_z), pitch)
        result.append(Part(part.name, shape, part.color, part.group, part.explode, part.description))
    return result


def build(p):
    radius = p["body_diameter_mm"] / 2
    rim, top = p["rim_height_mm"], p["overall_height_mm"]
    liner_z, wall = p["liner_bottom_mm"], p["liner_wall_mm"]
    ro = radius - p["shell_wall_mm"] - p["liner_radial_clearance_mm"]
    ri, gap = p["liner_inner_radius_mm"], p["sector_gap_mm"] / 2
    lip_z = rim - p["lip_height_mm"]
    mast_y, mast_r = p["rear_mast_center_y_mm"], p["mast_outer_radius_mm"]
    canopy_z = top - p["canopy_thickness_mm"]
    pivot_z = rim + p["pivot_above_rim_mm"]
    plate_z = pivot_z + p["plate_bottom_above_pivot_mm"]
    plate_r, plate_t = p["plate_radius_mm"], p["plate_thickness_mm"]
    theta = math.radians(p["maximum_plate_tilt_degrees"])
    dz = rim + p["display_center_above_rim_mm"]
    assert p["category_labels"] == ["", "", "", ""]
    assert mast_y - mast_r >= radius
    assert plate_z > rim
    assert pivot_z + p["plate_bottom_above_pivot_mm"] * math.cos(theta) - plate_r * math.sin(theta) > rim + 20
    assert plate_r + p["plate_bottom_above_pivot_mm"] * math.sin(theta) < ro

    parts = []
    metal, light = (.61, .66, .69), (.79, .81, .81)
    charcoal, glass = (.19, .23, .26), (.07, .11, .14)
    tower_explode = (0, 0, 240)

    def add(name, shape, color, group, explode=(0, 0, 0), description=""):
        parts.append(Part(name, shape.clean(), color, group, explode, description))

    add("outer_shell", tube(radius, radius - p["shell_wall_mm"], 24, rim - 24),
        light, "shell", (0, 0, -70), "Open-top cylindrical housing")
    extension_end = mast_y + 45
    plinth = tube(radius, 0, 8, 16).fuse(
        box(100, extension_end - radius + 15, 16,
            (0, (extension_end + radius - 15) / 2, 16)))
    add("plinth_with_rear_mast_base", plinth, charcoal, "base", (0, 0, -120),
        "Rear base extension anchors mast outside the four liner spaces")
    add("liner_support_deck", tube(radius - p["shell_wall_mm"], 0, liner_z - 8, 8),
        metal, "base", (0, 0, -50), "Common liner support floor")
    foot_pos = radius * .6
    foot_locations = [(foot_pos, foot_pos), (-foot_pos, foot_pos),
                      (-foot_pos, -foot_pos), (foot_pos, -foot_pos), (0, mast_y + 20)]
    for i, (x, y) in enumerate(foot_locations, 1):
        add(f"foot_{i}", tube(25, 0, 0, 8).translate((x, y, 0)), charcoal, "base",
            (0, 0, -140), "Support foot envelope")

    outer = sector(ro, ri, gap, liner_z, rim - liner_z)
    lower_void = sector(ro - wall, ri + wall, gap + wall,
                        liner_z + p["liner_floor_mm"], lip_z - liner_z - p["liner_floor_mm"])
    upper_void = sector(ro - p["lip_width_mm"], ri + p["lip_width_mm"],
                        gap + p["lip_width_mm"], lip_z, p["lip_height_mm"] + 1)
    cavity = lower_void.fuse(upper_void)
    liner = outer.cut(cavity)
    capacity = outer.intersect(cavity).Volume() / 1e6
    colors = [(.87, .88, .86), (.77, .80, .79), (.82, .84, .83), (.71, .75, .75)]
    plaque = box(44, 5, 1.5, (0, ro - p["lip_width_mm"] / 2, rim + .75))
    for i in range(4):
        a = i * 90
        phi = math.radians(a + 45)
        offset = (185 * math.cos(phi), 185 * math.sin(phi), 100)
        add(f"sub_bin_{i + 1}", liner.rotate((0, 0, 0), (0, 0, 1), a), colors[i],
            "liners", offset, "Removable quarter-circle liner extending toward the center")
        add(f"blank_label_{i + 1}", plaque.rotate((0, 0, 0), (0, 0, 1), a - 45),
            (.92, .93, .92), "labels", offset, "Blank category plaque")

    # Rear mast stays outside the housing, rather than occupying a central hub.
    flange = tube(45, mast_r, 24, 8).translate((0, mast_y, 0))
    flange = flange.cut(tube(radius, 0, 23, 10))
    for x in (-33, 33):
        flange = flange.cut(cylinder(3.2, 10, (x, mast_y, 23), (0, 0, 1)))
    add("rear_mast_mount_flange", flange, metal, "rear_support", (0, 0, 40),
        "Mast attachment flange at rear base; bolt bores reserved")
    mast = tube(mast_r, mast_r - p["mast_wall_mm"], 24, canopy_z - 24)
    add("rear_hollow_mast", mast.translate((0, mast_y, 0)), metal,
        "rear_support", tower_explode, "Back-mounted support and cable passage")
    cleat = box(80, 80, 12, (0, mast_y, canopy_z - 6)).cut(
        tube(mast_r, 0, canopy_z - 13, 14).translate((0, mast_y, 0)))
    add("rear_canopy_cleat", cleat, metal, "rear_support", tower_explode,
        "Detachable canopy support around rear mast")

    dw, dh, dd = p["display_width_mm"], p["display_height_mm"], p["display_depth_mm"]
    display_rear = mast_y - mast_r - 13
    cy = display_rear - dd / 2
    front = display_rear - dd
    housing = box(dw, dd, dh, (0, cy, dz), 8)
    pocket = box(dw - 8, dd - 8, dh - 8, (0, cy, dz), 4)
    aperture = box(dw - 28, 10, dh - 32, (0, front + 2, dz), 4)
    add("display_housing", housing.cut(pocket.fuse(aperture)), charcoal, "display",
        tower_explode, "Blank display above the rear rim, facing the user")
    add("blank_display_face", box(dw - 28, 2, dh - 32, (0, front + 1, dz), 4), glass,
        "display", tower_explode, "Blank display placeholder")
    ring = tube(mast_r + 6, mast_r, dz - 25, 50).translate((0, mast_y, 0))
    bridge = box(42, mast_y - mast_r + 1 - display_rear, 50,
                 (0, (display_rear + mast_y - mast_r + 1) / 2, dz))
    mount = ring.fuse(bridge).cut(tube(mast_r, 0, dz - 26, 52).translate((0, mast_y, 0)))
    add("rear_display_standoff", mount, metal, "display", tower_explode,
        "Rear-mast display attachment")

    cr = p["canopy_diameter_mm"] / 2
    canopy = (cq.Workplane("XY").circle(cr).extrude(p["canopy_thickness_mm"])
              .edges().fillet(2).translate((0, 0, canopy_z))).val()
    recess = tube(cr - 10, 42, canopy_z - 1, p["canopy_thickness_mm"] - 3)
    add("canopy", canopy.cut(recess), light, "canopy", (0, 0, 330),
        "Overhead canopy supported from the back")

    # Identification camera points diagonally downward at the plate's center.
    camera_y = p["camera_center_y_mm"]
    camera_z = rim + p["camera_center_above_rim_mm"]
    ss, sd = p["camera_size_mm"], p["camera_depth_mm"]
    aim = -math.degrees(math.atan2(camera_y, camera_z - plate_z - plate_t))
    camera_center = (0, camera_y, camera_z)
    def camera_pose(shape):
        return shape.rotate(camera_center, (1, camera_y, camera_z), aim)
    housing = box(ss, ss, sd, camera_center)
    pocket = box(ss - 8, ss - 8, sd - 8, camera_center)
    bore = cylinder(12, 8, (0, camera_y, camera_z - sd / 2 - 1), (0, 0, 1))
    add("identification_camera_housing", camera_pose(housing.cut(pocket.fuse(bore))),
        charcoal, "camera", (0, 0, 300), "Camera aimed at item on the single plate")
    add("camera_lens_placeholder", camera_pose(cylinder(11.8, 2,
        (0, camera_y, camera_z - sd / 2 - 1), (0, 0, 1))), glass, "camera", (0, 0, 300),
        "Camera optical window envelope")
    a = math.radians(aim)
    direction = (0, -math.sin(a), math.cos(a))
    origin = (0, camera_y + sd / 2 * direction[1], camera_z + sd / 2 * direction[2])
    length = (top - 4 - origin[2]) / direction[2] + 15
    hanger = cylinder(10, length, origin, direction)
    hanger = hanger.intersect(box(1000, 1000, top - 4, (0, 0, (top - 4) / 2)))
    add("camera_canopy_hanger", hanger, metal, "camera", (0, 0, 300),
        "Angled camera hanger to underside of canopy roof")

    # Fixed cantilever ends at the center under the plate. Main mast is at back.
    beam_top = rim + 60
    beam_depth, beam_width = 40, 60
    beam_end = mast_y - mast_r + 1
    outer_beam = box(beam_width, beam_end, beam_depth,
                     (0, beam_end / 2, beam_top - beam_depth / 2))
    inner_beam = box(beam_width - 8, beam_end + 2, beam_depth - 8,
                     (0, beam_end / 2, beam_top - beam_depth / 2))
    collar = tube(mast_r + 6, mast_r, beam_top - beam_depth, beam_depth).translate((0, mast_y, 0))
    beam = outer_beam.cut(inner_beam).fuse(collar).cut(
        tube(mast_r, 0, beam_top - beam_depth - 1, beam_depth + 2).translate((0, mast_y, 0)))
    add("rear_cantilever_plate_support", beam, metal, "tilt_fixed", (0, 0, 160),
        "Removable hollow arm from rear mast to central two-axis pivot")

    # Two perpendicular bounded hinge axes, with no vertical-axis rotary sorter.
    fork = box(80, 80, 8, (0, 0, beam_top + 4))
    for y in (-30, 30):
        fork = fork.fuse(box(16, 10, pivot_z + 6 - beam_top - 8,
                             (0, y, (pivot_z + 6 + beam_top + 8) / 2)))
    fork = fork.cut(cylinder(4.2, 80, (0, -40, pivot_z), (0, 1, 0)))
    add("fixed_tilt_yoke", fork, charcoal, "tilt_fixed", (0, 0, 170),
        "Fixed fork for the Y tilt hinge")
    cross = box(20, 20, 20, (0, 0, pivot_z)).fuse(
        cylinder(4, 70, (-35, 0, pivot_z), (1, 0, 0)),
        cylinder(4, 70, (0, -35, pivot_z), (0, 1, 0)))
    add("two_axis_cross_pin", cross, metal, "tilt_pitch", (0, 0, 180),
        "Universal joint cross: two perpendicular horizontal hinge axes")
    upper = box(80, 24, 6, (0, 0, plate_z - 3))
    for x in (-30, 30):
        upper = upper.fuse(box(12, 12, plate_z - pivot_z + 8,
                               (x, 0, (plate_z + pivot_z - 8) / 2)))
    upper = upper.cut(cylinder(4.2, 80, (-40, 0, pivot_z), (1, 0, 0)))
    add("moving_plate_yoke", upper, metal, "tilt_plate", (0, 0, 210),
        "Moving fork connecting the single plate to the X hinge")
    plate = (cq.Workplane("XY").circle(plate_r).extrude(plate_t)
             .edges().fillet(1).translate((0, 0, plate_z))).val()
    add("single_detection_and_tipping_plate", plate, (.86, .89, .88), "tilt_plate", (0, 0, 250),
        "One flat surface for both identification and tipping toward a sub-bin")
    pitch_drive = box(30, 30, 40, (0, 52, pivot_z - 20)).fuse(
        cylinder(4, 12, (0, 35, pivot_z), (0, 1, 0)))
    add("pitch_actuator_envelope", pitch_drive, charcoal, "tilt_fixed", (0, 0, 170),
        "Reserved bounded-angle tilt actuator; hardware and torque TBD")
    roll_drive = box(30, 30, 35, (52, 0, pivot_z - 17.5)).fuse(
        cylinder(4, 12, (35, 0, pivot_z), (1, 0, 0)))
    add("roll_actuator_envelope", roll_drive, charcoal, "tilt_pitch", (0, 0, 180),
        "Second bounded-angle actuator on the intermediate hinge")

    pod_w, pod_h = p["fill_sensor_housing_width_mm"], p["fill_sensor_housing_height_mm"]
    pod_top, pod_bottom = top - 4, top - 4 - pod_h
    for i in range(4):
        phi = math.radians(45 + i * 90)
        sx, sy = [p["fill_sensor_radial_position_mm"] * f(phi) for f in (math.cos, math.sin)]
        pod = box(pod_w, pod_w, pod_h, (sx, sy, pod_top - pod_h / 2))
        pocket = box(pod_w - 6, pod_w - 6, pod_h - 6, (sx, sy, pod_top - pod_h / 2))
        aperture = cylinder(6, 8, (sx, sy, pod_bottom - 1), (0, 0, 1))
        add(f"fill_sensor_housing_{i + 1}", pod.cut(pocket.fuse(aperture)), charcoal,
            "fill_sensors", (0, 0, 330), "IR distance-sensor pod above one sub-bin")
        add(f"fill_sensor_window_{i + 1}", cylinder(5.8, 2, (sx, sy, pod_bottom), (0, 0, 1)),
            glass, "fill_sensors", (0, 0, 330), "IR-transmissive window placeholder")

    fov_half = math.radians(p["fill_sensor_receiver_full_fov_degrees"] / 2)
    beam_r_at_plate = (pod_bottom - plate_z - plate_t) * math.tan(fov_half)
    assert p["fill_sensor_radial_position_mm"] - beam_r_at_plate > plate_r
    full_level = rim - p["full_level_below_rim_mm"]
    beam_r_at_full = (pod_bottom - full_level) * math.tan(fov_half)
    assert p["fill_sensor_radial_position_mm"] + beam_r_at_full < ro - wall
    metrics = {
        "revision": "v2", "units": "mm", "body_diameter_mm": radius * 2,
        "canopy_diameter_mm": cr * 2, "rim_height_mm": rim, "overall_height_mm": top,
        "footprint_width_mm": radius * 2, "footprint_depth_mm": radius + extension_end,
        "rear_mast_center_y_mm": mast_y, "liner_height_mm": rim - liner_z,
        "nominal_brim_capacity_per_liner_l": round(capacity, 2),
        "nominal_total_brim_capacity_l": round(capacity * 4, 2),
        "plate_radius_mm": plate_r, "plate_thickness_mm": plate_t,
        "plate_level_top_height_mm": plate_z + plate_t,
        "tilt_pivot_mm": [0, 0, pivot_z],
        "maximum_plate_tilt_degrees": p["maximum_plate_tilt_degrees"],
        "destination_directions_degrees": [45, 135, 225, 315],
        "fill_sensor_count": 4, "fill_sensor_radial_position_mm": p["fill_sensor_radial_position_mm"],
        "fill_sensor_window_height_mm": pod_bottom,
        "provisional_full_level_mm": full_level,
        "provisional_full_distance_threshold_mm": pod_bottom - full_level,
        "receiver_full_fov_degrees_assumed": p["fill_sensor_receiver_full_fov_degrees"],
        "level_plate_ir_beam_clearance_mm": round(p["fill_sensor_radial_position_mm"] - beam_r_at_plate - plate_r, 2),
        "category_labels": p["category_labels"],
        "demo_bottle_height_mm": p["demo_bottle_height_mm"],
        "demo_bottle_diameter_mm": p["demo_bottle_diameter_mm"],
        "status": "Concept geometry; drives, loading limits and fabrication details provisional"
    }
    return parts, metrics


def export(parts, metrics, output, names=("rear_mast_tilting_plate_v2", "rear_mast_exploded_v2")):
    output.mkdir(parents=True, exist_ok=True)
    def save_assembly(items, name, filename, exploded=False):
        assembly = cq.Assembly(name=name)
        for part in items:
            shape = part.shape.translate(part.explode) if exploded else part.shape
            assembly.add(shape, name=part.name, color=cq.Color(*part.color))
        assembly.export(str(output / filename))
    save_assembly(parts, names[0], "smart_bin_assembly.step")
    save_assembly(parts, names[1], "smart_bin_exploded.step", True)
    checks = []
    # Test intermediate travel as well as every final pose, not just endpoints.
    for destination, direction in enumerate(metrics["destination_directions_degrees"], 1):
        for fraction in (.25, .5, .75, 1.0):
            roll, pitch = angles(metrics["maximum_plate_tilt_degrees"] * fraction, direction)
            items = posed(parts, metrics["tilt_pivot_mm"][2], roll, pitch)
            validate(items)
            if fraction == 1:
                save_assembly(items, f"tilt_to_sub_bin_{destination}", f"tilt_to_sub_bin_{destination}.step")
                vertices = []
                for part in items:
                    vv, tt = part.shape.tessellate(.8, .15)
                    vertices.append({"name": part.name, "group": part.group, "color": part.color,
                                     "explode": part.explode,
                                     "vertices": [[round(v.x, 4), round(v.y, 4), round(v.z, 4)] for v in vv],
                                     "triangles": tt})
                (output / f"tilt_mesh_{destination}.json").write_text(json.dumps(vertices, separators=(",", ":")))
            checks.append({"destination": destination, "fraction": fraction,
                           "roll_degrees": round(roll, 4), "pitch_degrees": round(pitch, 4),
                           "positive_volume_intersections": []})
    meshes = []
    part_dir = output / "parts"; part_dir.mkdir(exist_ok=True)
    for part in parts:
        cq.exporters.export(part.shape, str(part_dir / f"{part.name}.step"))
        cq.exporters.export(part.shape, str(part_dir / f"{part.name}.stl"), tolerance=.15, angularTolerance=.08)
        vv, tt = part.shape.tessellate(.8, .15)
        meshes.append({"name": part.name, "group": part.group, "color": part.color,
                       "explode": part.explode,
                       "vertices": [[round(v.x, 4), round(v.y, 4), round(v.z, 4)] for v in vv],
                       "triangles": tt})
    (output / "mesh.json").write_text(json.dumps(meshes, separators=(",", ":")))
    (output / "dimensions.json").write_text(json.dumps(metrics, indent=2) + "\n")
    with (output / "components.csv").open("w", newline="") as stream:
        writer = csv.writer(stream); writer.writerow(["component", "quantity", "description", "category_text"])
        writer.writerows([[part.name, 1, part.description, ""] for part in parts])
    imported = cq.importers.importStep(str(output / "smart_bin_assembly.step")).solids().vals()
    expected = sum(part.shape.Volume() for part in parts)
    actual = sum(shape.Volume() for shape in imported)
    assert len(imported) == len(parts) and abs(actual - expected) < max(1, expected * 1e-6)
    return {"tilt_pose_checks": checks, "roundtrip_solid_count": len(imported),
            "roundtrip_relative_volume_error": abs(actual - expected) / expected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, default=ROOT / "cad/parameters_v2.json")
    parser.add_argument("--output", type=Path, default=ROOT / "v2")
    args = parser.parse_args()
    print("Building rear-mast, single-plate concept…", flush=True)
    parts, metrics = build(json.loads(args.parameters.read_text()))
    print(f"Validating {len(parts)} neutral components and 16 tilt poses…", flush=True)
    report = validate(parts)
    report.update(export(parts, metrics, args.output))
    report["cadquery_version"] = cq.__version__
    (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(metrics, indent=2)); print("STEP export and tilt checks passed.", flush=True)


if __name__ == "__main__":
    main()
