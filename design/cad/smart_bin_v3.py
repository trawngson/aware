"""Raised-wall smart bin: thrown items funnel onto one enclosed tilting plate. All units mm.

There is no mast or canopy: display and camera sit in a console on the rear rim.
The V1 geometric helpers and V2 are retained; this script writes only v3 by default.
"""

from __future__ import annotations
import argparse
import json
import math
from pathlib import Path

from smart_bin import Part, ROOT, box, cq, sector, tube, validate
from smart_bin_v2 import cylinder, export


def revolve(profile):
    """Solid of revolution about Z from a closed (radius, z) outline."""
    return (cq.Workplane("XZ").polyline(profile).close()
            .revolve(360, (0, 0, 0), (0, 1, 0))).val()


def prism(plane, profile, length):
    """Outline drawn on a vertical plane, extruded symmetrically along its normal."""
    return cq.Workplane(plane).polyline(profile).close().extrude(length / 2, both=True).val()


def build(p):
    radius, shell_wall = p["body_diameter_mm"] / 2, p["shell_wall_mm"]
    top = p["bin_rim_height_mm"]
    liner_z, wall = p["liner_bottom_mm"], p["liner_wall_mm"]
    plate_r, plate_t = p["plate_radius_mm"], p["plate_thickness_mm"]
    plate_h = p["plate_bottom_above_pivot_mm"]
    theta = math.radians(p["maximum_plate_tilt_degrees"])
    # Heights stack downward from the rim the user throws over.
    lip_top = top - p["funnel_height_mm"]
    lip_bottom = lip_top - p["throat_lip_height_mm"]
    plate_z = lip_bottom - p["plate_below_throat_lip_mm"] - plate_t
    pivot_z = plate_z - plate_h
    rim = pivot_z - p["pivot_above_liner_rim_mm"]
    lip_z = rim - p["lip_height_mm"]
    ro = radius - shell_wall - p["liner_radial_clearance_mm"]
    ri, gap = p["liner_inner_radius_mm"], p["sector_gap_mm"] / 2
    throat_r, fw = plate_r + p["throat_clearance_mm"], p["funnel_wall_mm"]
    mouth_r, collar_t = p["funnel_mouth_radius_mm"], p["rim_collar_thickness_mm"]
    slope = p["funnel_height_mm"] / (mouth_r - throat_r)
    seat = p["head_seat_height_mm"]
    strips, skirt_r = p["skirt_strip_count"], throat_r + 1
    assert p["category_labels"] == ["", "", "", ""]
    assert rim > liner_z + 300
    assert mouth_r + fw < radius - shell_wall
    # The tilted plate must clear the skirt (or bare lip) and stay above the liner rims.
    lip_h = lip_bottom - pivot_z
    edge_r, edge_h = (skirt_r, plate_h) if strips else (throat_r, lip_h)
    assert lip_h >= plate_h
    assert math.hypot(plate_r, plate_h + plate_t) + 2 < math.hypot(edge_r, edge_h)
    assert pivot_z + plate_h * math.cos(theta) - plate_r * math.sin(theta) > rim + 20
    assert plate_r + (plate_h + plate_t) * math.sin(theta) < ro
    # Low-side gaps to the tipped plate surface: under the rigid lip, and under the skirt.
    exit_gap = throat_r * math.sin(theta) + lip_h * math.cos(theta) - plate_h - plate_t
    skirt_gap = skirt_r * math.sin(theta) + plate_h * math.cos(theta) - plate_h - plate_t
    assert min(exit_gap, skirt_gap) > p["demo_bottle_diameter_mm"] + 20

    parts = []
    metal, light = (.61, .66, .69), (.79, .81, .81)
    charcoal, glass = (.19, .23, .26), (.07, .11, .14)

    def add(name, shape, color, group, explode=(0, 0, 0), description=""):
        parts.append(Part(name, shape.clean(), color, group, explode, description))

    add("outer_shell", tube(radius, radius - shell_wall, 24, rim - 24),
        light, "shell", (0, 0, -70), "Lower cylindrical housing around the four liners")
    foot_pos = radius * .6
    foot_locations = [(foot_pos, foot_pos), (-foot_pos, foot_pos),
                      (-foot_pos, -foot_pos), (foot_pos, -foot_pos)]
    add("plinth", tube(radius, 0, 8, 16), charcoal, "base", (0, 0, -120),
        "Bottom closure / ballast envelope")
    add("liner_support_deck", tube(radius - shell_wall, 0, liner_z - 8, 8),
        metal, "base", (0, 0, -50), "Common liner support floor")
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
            (.92, .93, .92), "labels", offset, "Blank category plaque, seen with the head open")

    # Head module: everything above the liner rims lifts or hinges away as one unit.
    head = (0, 0, 300)
    add("head_seat_ring", tube(radius - 2, radius - shell_wall - 6, rim, seat), charcoal,
        "shell", head, "Recessed seat between lower housing and removable head")
    add("head_shell", tube(radius, radius - shell_wall, rim + seat, top - collar_t - rim - seat),
        light, "shell", head, "Raised outer wall enclosing funnel, plate and sensors")
    funnel = revolve([(mouth_r, top), (radius, top), (radius, top - collar_t),
                      (mouth_r + fw - collar_t / slope, top - collar_t),
                      (throat_r + fw, lip_top), (throat_r + fw, lip_bottom),
                      (throat_r, lip_bottom), (throat_r, lip_top)])
    add("intake_funnel", funnel, metal, "funnel", (0, 0, 560),
        "Rim collar, funnel and throat lip guiding thrown items onto the plate")
    if strips:
        # Flexible fringe keeps small items on the level plate; large ones push through.
        fringe = (cq.Workplane("XY").polarArray(skirt_r + 1, 0, 360, strips)
                  .rect(2, p["skirt_strip_width_mm"]).extrude(lip_bottom - plate_z)
                  .translate((0, 0, plate_z))).vals()
        add("flexible_throat_skirt", tube(skirt_r + 2, skirt_r, lip_bottom - 8, 8).fuse(*fringe),
            (.14, .15, .16), "funnel", (0, 0, 560),
            "Flexible strip fringe from throat lip to plate; material and density TBD")

    # Four arms run above the liner dividers, so no arm crosses a liner opening.
    hub_top = rim + 60
    arm_w, arm_z = p["support_arm_width_mm"], rim + 15
    ridge = [(-arm_w / 2, arm_z), (arm_w / 2, arm_z), (arm_w / 2, hub_top - 23),
             (0, hub_top - 10), (-arm_w / 2, hub_top - 23)]
    arm = prism("XZ", ridge, radius * 2)
    spider = arm.fuse(arm.rotate((0, 0, 0), (0, 0, 1), 90),
                      box(90, 90, hub_top - arm_z, (0, 0, (hub_top + arm_z) / 2)))
    spider = spider.intersect(tube(radius - shell_wall, 0, arm_z, hub_top - arm_z))
    add("plate_support_spider", spider, metal, "tilt_fixed", head,
        "Ridged cross-beam from head wall to the central two-axis pivot")

    # Two perpendicular bounded hinge axes, as in v2, now inside the head.
    fork = box(80, 80, 8, (0, 0, hub_top + 4))
    for y in (-30, 30):
        fork = fork.fuse(box(16, 10, pivot_z + 6 - hub_top - 8,
                             (0, y, (pivot_z + 6 + hub_top + 8) / 2)))
    fork = fork.cut(cylinder(4.2, 80, (0, -40, pivot_z), (0, 1, 0)))
    add("fixed_tilt_yoke", fork, charcoal, "tilt_fixed", (0, 0, 315),
        "Fixed fork for the Y tilt hinge")
    cross = box(20, 20, 20, (0, 0, pivot_z)).fuse(
        cylinder(4, 70, (-35, 0, pivot_z), (1, 0, 0)),
        cylinder(4, 70, (0, -35, pivot_z), (0, 1, 0)))
    add("two_axis_cross_pin", cross, metal, "tilt_pitch", (0, 0, 330),
        "Universal joint cross: two perpendicular horizontal hinge axes")
    upper = box(80, 24, 6, (0, 0, plate_z - 3))
    for x in (-30, 30):
        upper = upper.fuse(box(12, 12, plate_z - pivot_z + 8,
                               (x, 0, (plate_z + pivot_z - 8) / 2)))
    upper = upper.cut(cylinder(4.2, 80, (-40, 0, pivot_z), (1, 0, 0)))
    add("moving_plate_yoke", upper, metal, "tilt_plate", (0, 0, 365),
        "Moving fork connecting the single plate to the X hinge")
    plate = (cq.Workplane("XY").circle(plate_r).extrude(plate_t)
             .edges().fillet(1).translate((0, 0, plate_z))).val()
    add("single_detection_and_tipping_plate", plate, (.86, .89, .88), "tilt_plate", (0, 0, 410),
        "One flat surface closing the throat: catches, presents and tips the item")
    pitch_drive = box(30, 30, 40, (0, 52, pivot_z - 20)).fuse(
        cylinder(4, 12, (0, 35, pivot_z), (0, 1, 0)))
    add("pitch_actuator_envelope", pitch_drive, charcoal, "tilt_fixed", (0, 0, 315),
        "Reserved bounded-angle tilt actuator; hardware and torque TBD")
    roll_drive = box(30, 30, 35, (52, 0, pivot_z - 17.5)).fuse(
        cylinder(4, 12, (35, 0, pivot_z), (1, 0, 0)))
    add("roll_actuator_envelope", roll_drive, charcoal, "tilt_pitch", (0, 0, 330),
        "Second bounded-angle actuator on the intermediate hinge")

    # Fill sensors hang off the throat lip, under the funnel and out of the item path.
    pod_w, pod_h = p["fill_sensor_housing_width_mm"], p["fill_sensor_housing_height_mm"]
    sensor_r = p["fill_sensor_radial_position_mm"]
    pod_top, pod_bottom = lip_top, lip_top - pod_h
    assert pod_bottom >= lip_bottom
    assert math.hypot(sensor_r - pod_w / 2, pod_w / 2) > throat_r + fw + 10
    pod = box(pod_w, pod_w, pod_h, (sensor_r, 0, pod_top - pod_h / 2))
    pocket = box(pod_w - 6, pod_w - 6, pod_h - 6, (sensor_r, 0, pod_top - pod_h / 2))
    aperture = cylinder(6, 8, (sensor_r, 0, pod_bottom - 1), (0, 0, 1))
    pod = pod.cut(pocket.fuse(aperture))
    window = cylinder(5.8, 2, (sensor_r, 0, pod_bottom), (0, 0, 1))
    reach = sensor_r - pod_w / 2 - throat_r
    bracket = box(reach, 20, 20, (throat_r + reach / 2, 0, pod_top - pod_h / 2)).cut(
        tube(throat_r + fw, 0, pod_bottom, pod_h))
    for i in range(4):
        a = 45 + i * 90
        for name, shape, color, description in (
                ("housing", pod, charcoal, "IR distance-sensor pod above one sub-bin"),
                ("window", window, glass, "IR-transmissive window placeholder"),
                ("bracket", bracket, metal, "Sensor arm from the throat lip")):
            add(f"fill_sensor_{name}_{i + 1}", shape.rotate((0, 0, 0), (0, 0, 1), a), color,
                "fill_sensors", (0, 0, 560), description)
    fov_half = math.radians(p["fill_sensor_receiver_full_fov_degrees"] / 2)
    full_level = rim - p["full_level_below_rim_mm"]
    beam_r_at_full = (pod_bottom - full_level) * math.tan(fov_half)
    assert sensor_r + beam_r_at_full < ro - wall
    assert (sensor_r - beam_r_at_full) / math.sqrt(2) > gap + wall + arm_w / 2

    # Rear rim rises into a console: display leans back, camera chin looks down.
    console = (0, 0, 640)
    cw, ch = p["console_width_mm"], p["console_height_mm"]
    y0, lean = p["console_base_front_y_mm"], math.radians(p["display_lean_back_degrees"])
    y1, z1 = y0 - p["console_chin_forward_mm"], top + p["console_chin_height_mm"]
    y2, z2 = y1 + (top + ch - z1) * math.tan(lean), top + ch
    overall = z2
    gw, gh = p["display_face_width_mm"], p["display_face_height_mm"]
    assert math.hypot(cw / 2, y2) < radius and math.hypot(gw / 2, y2) < radius - 12
    body = prism("YZ", [(y0, top), (y1, z1), (y2, z2), (radius + 20, z2), (radius + 20, top)], cw)
    body = body.intersect(tube(radius, 0, top, ch))
    face_center = (0, (y1 + y2) / 2, (z1 + z2) / 2)
    def on_face(shape):
        return shape.rotate((0, 0, 0), (1, 0, 0), -math.degrees(lean)).translate(face_center)
    face = on_face(box(gw, 2, gh, (0, 1, 0)))
    chin_length = math.hypot(y0 - y1, z1 - top)
    aim = (0, -(z1 - top) / chin_length, -(y0 - y1) / chin_length)
    chin = (0, (y0 + y1) / 2, (top + z1) / 2)
    def along_aim(distance):
        return tuple(c + distance * a for c, a in zip(chin, aim))
    inward = tuple(-a for a in aim)
    # The plate centre must sit near the camera axis. The funnel's lower edge hides
    # a strip of the plate nearest the camera; it widens as the plate sits deeper.
    to_plate = (-chin[1], plate_z + plate_t - chin[2])
    off_axis = math.degrees(math.atan2(-to_plate[1], -to_plate[0]) - math.atan2(-aim[2], -aim[1]))
    assert abs(off_axis) < 8
    hidden = plate_r - (throat_r - (lip_top - plate_z - plate_t) * (chin[1] - throat_r) / (chin[2] - lip_top))
    body = body.cut(face).cut(cylinder(12, 7, along_aim(1), inward))
    add("display_camera_console", body, light, "display", console,
        "Raised rear rim housing the display and identification camera")
    add("blank_display_face", face, glass, "display", console, "Blank display placeholder")
    add("camera_lens_placeholder", cylinder(11.8, 2, along_aim(-4), inward), glass,
        "camera", console, "Recessed camera window aimed down at the plate")
    sw, sh = gw / 2 - 4, gh / 2 - 4
    screen = [(sx, face_center[1] - .3 * math.cos(lean) + sz * math.sin(lean),
               face_center[2] + .3 * math.sin(lean) + sz * math.cos(lean))
              for sx, sz in ((-sw, -sh), (sw, -sh), (sw, sh), (-sw, sh))]

    metrics = {
        "revision": "v3", "units": "mm",
        "body_diameter_mm": radius * 2, "rim_height_mm": top, "overall_height_mm": overall,
        "footprint_width_mm": radius * 2, "footprint_depth_mm": radius * 2,
        "liner_rim_height_mm": rim, "liner_height_mm": rim - liner_z,
        "nominal_brim_capacity_per_liner_l": round(capacity, 2),
        "nominal_total_brim_capacity_l": round(capacity * 4, 2),
        "funnel_mouth_diameter_mm": mouth_r * 2, "throat_diameter_mm": throat_r * 2,
        "funnel_slope_degrees": round(math.degrees(math.atan(slope)), 1),
        "plate_radius_mm": plate_r, "plate_thickness_mm": plate_t,
        "plate_level_top_height_mm": plate_z + plate_t,
        "plate_below_rim_mm": top - plate_z - plate_t,
        "plate_to_throat_gap_mm": p["throat_clearance_mm"],
        "plate_below_throat_lip_mm": p["plate_below_throat_lip_mm"],
        "throat_lip_bottom_height_mm": lip_bottom,
        "skirt_strip_count": strips, "skirt_bottom_height_mm": plate_z,
        "skirt_gap_at_full_tilt_mm": round(skirt_gap, 1),
        "camera_hidden_plate_edge_mm": round(max(hidden, 0), 1),
        "tilt_pivot_mm": [0, 0, pivot_z],
        "maximum_plate_tilt_degrees": p["maximum_plate_tilt_degrees"],
        "exit_gap_at_full_tilt_mm": round(exit_gap, 1),
        "destination_directions_degrees": [45, 135, 225, 315],
        "fill_sensor_count": 4, "fill_sensor_radial_position_mm": sensor_r,
        "fill_sensor_window_height_mm": pod_bottom,
        "provisional_full_level_mm": full_level,
        "provisional_full_distance_threshold_mm": pod_bottom - full_level,
        "receiver_full_fov_degrees_assumed": p["fill_sensor_receiver_full_fov_degrees"],
        "display_face_corners_mm": [[round(c, 3) for c in corner] for corner in screen],
        "category_labels": p["category_labels"],
        "demo_bottle_height_mm": p["demo_bottle_height_mm"],
        "demo_bottle_diameter_mm": p["demo_bottle_diameter_mm"],
        "demo_landing_height_mm": liner_z + p["liner_floor_mm"] + p["demo_bottle_diameter_mm"] / 2 + 5,
        "status": "Concept geometry; drives, loading limits and fabrication details provisional"
    }
    return parts, metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, default=ROOT / "cad/parameters_v3.json")
    parser.add_argument("--output", type=Path, default=ROOT / "v3")
    args = parser.parse_args()
    print("Building raised-wall, funnel-fed concept…", flush=True)
    parts, metrics = build(json.loads(args.parameters.read_text()))
    print(f"Validating {len(parts)} neutral components and 16 tilt poses…", flush=True)
    report = validate(parts)
    report.update(export(parts, metrics, args.output, ("raised_wall_funnel_v3", "raised_wall_exploded_v3")))
    report["cadquery_version"] = cq.__version__
    (args.output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(metrics, indent=2)); print("STEP export and tilt checks passed.", flush=True)


if __name__ == "__main__":
    main()
