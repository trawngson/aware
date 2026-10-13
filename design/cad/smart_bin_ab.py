"""Buildable prototype options A (220 L drum) and B (aluminium frame + four bins). Units mm.

Both bodies carry the same head: funnel, soft skirt, 320 mm aluminium tipping plate on a
two-axis joint driven by two DS3218 servos through GT2 2:1 belts, a 47 degree stop ring, an
IMU on the plate yoke and four fill sensors. The head hangs from one deck ring and stands on
its joint beam when lifted out. A rear console holds the ESP32-S3, the TFT and an LED strip,
with the camera hidden under its chin.
Only V1 geometric helpers are imported; this script writes design/ab/ only.
"""

from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path

from smart_bin import Part, ROOT, box, cq, tube, validate

DIRECTIONS = (45, 135, 225, 315)


def cylinder(radius, length, origin, direction):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*origin), cq.Vector(*direction))


def revolve(profile):
    """Solid of revolution about Z from a closed (radius, z) outline."""
    return (cq.Workplane("XZ").polyline(profile).close()
            .revolve(360, (0, 0, 0), (0, 1, 0))).val()


def angles(tilt_degrees, direction_degrees):
    """Yaw, then tilt about the hinge (X at zero yaw), that tips the plate toward a direction.

    A positive tilt tips the plate toward -Y. Tilting both ways keeps the yaw within +/-90 degrees,
    so the four diagonal bins need only +/-45 degrees of yaw.
    """
    yaw = (direction_degrees - 270 + 180) % 360 - 180
    tilt = tilt_degrees
    if abs(yaw) > 90:
        yaw = (direction_degrees - 90 + 180) % 360 - 180
        tilt = -tilt_degrees
    return yaw, tilt


def posed(parts, pivot_z, yaw, tilt):
    result = []
    for part in parts:
        shape = part.shape
        if part.group == "tilt_plate":
            shape = shape.rotate((0, 0, pivot_z), (1, 0, pivot_z), tilt)
        if part.group in ("tilt_plate", "yaw"):
            shape = shape.rotate((0, 0, 0), (0, 0, 1), yaw)
        result.append(Part(part.name, shape, part.color, part.group, part.explode, part.description))
    return result


def belt_center_distance(loop, big_r, small_r):
    """Centre distance for a closed belt of given pitch length (open-belt formula, solved)."""
    lo, hi = big_r + small_r, loop / 2
    for _ in range(60):
        c = (lo + hi) / 2
        phi = math.acos((big_r - small_r) / c)
        length = 2 * c * math.sin(phi) + 2 * big_r * (math.pi - phi) + 2 * small_r * phi
        lo, hi = (c, hi) if length < loop else (lo, c)
    return (lo + hi) / 2


def belt_loop(to3d, extrude, big_r, small_r, center_z, c, gap=.3, thickness=1.2):
    """Closed belt ring around a big pulley at center_z and a small one c below it."""
    phi = math.acos((big_r - small_r) / c)

    def wire(offset):
        rb, rs = big_r + offset, small_r + offset
        n1, n2 = (math.sin(phi), -math.cos(phi)), (-math.sin(phi), -math.cos(phi))
        pt = lambda center, r, n: to3d(center[0] + r * n[0], center[1] + r * n[1])
        cb, cs = (0, center_z), (0, center_z - c)
        edges = [cq.Edge.makeThreePointArc(pt(cb, rb, n1), to3d(0, center_z + rb), pt(cb, rb, n2)),
                 cq.Edge.makeLine(pt(cb, rb, n2), pt(cs, rs, n2)),
                 cq.Edge.makeThreePointArc(pt(cs, rs, n2), to3d(0, center_z - c - rs), pt(cs, rs, n1)),
                 cq.Edge.makeLine(pt(cs, rs, n1), pt(cb, rb, n1))]
        return cq.Wire.assembleEdges(edges)

    face = cq.Face.makeFromWires(wire(gap + thickness), [wire(gap)])
    return cq.Solid.extrudeLinear(face, cq.Vector(*extrude))


def head(p, add):
    """Shared head module. Returns geometry facts used by the bodies and checks."""
    top = p["rim_height_mm"]
    deck_z, deck_t = p["head_deck_height_mm"], p["deck_thickness_mm"]
    deck_ro, deck_ri = p["deck_outer_radius_mm"], p["deck_inner_radius_mm"]
    plate_r, plate_t = p["plate_radius_mm"], p["plate_thickness_mm"]
    plate_h = p["plate_bottom_above_pivot_mm"]
    lip_top = top - p["funnel_height_mm"]
    lip_bottom = lip_top - p["throat_lip_height_mm"]
    plate_z = lip_bottom - p["plate_below_throat_lip_mm"] - plate_t
    pivot = plate_z - plate_h
    spider_top = pivot - p["spider_top_below_pivot_mm"]
    spider_bottom = spider_top - p["spider_height_mm"]
    throat_r, fw = plate_r + p["throat_clearance_mm"], p["funnel_wall_mm"]
    mouth_r, collar_t = p["funnel_mouth_radius_mm"], p["rim_collar_thickness_mm"]
    slope = p["funnel_height_mm"] / (mouth_r - throat_r)
    shell_top = top - collar_t
    theta = math.radians(p["maximum_plate_tilt_degrees"])
    strips, skirt_r = p["skirt_strip_count"], throat_r + 1
    metal, light, charcoal = (.61, .66, .69), (.86, .88, .87), (.19, .23, .26)
    pp, servo_blue, glass = (.90, .92, .89), (.12, .32, .58), (.07, .11, .14)
    lift = (0, 0, 450)
    brain_lift = (0, 0, 520)
    rubber = (.08, .08, .08)

    # The same tilted-plate clearances as v3: skirt, lip, and the low edge above the liners.
    lip_h = lip_bottom - pivot
    assert math.hypot(plate_r, plate_h + plate_t) + 2 < math.hypot(skirt_r, plate_h)
    exit_gap = throat_r * math.sin(theta) + lip_h * math.cos(theta) - plate_h - plate_t
    skirt_gap = skirt_r * math.sin(theta) + plate_h * math.cos(theta) - plate_h - plate_t
    assert min(exit_gap, skirt_gap) > p["item_diameter_mm"] + 20
    low_edge_z = pivot + plate_h * math.cos(theta) - plate_r * math.sin(theta)
    assert low_edge_z > spider_top + 20

    # Deck ring: the one interface every body must carry at deck_z.
    add("head_deck", tube(deck_ro, deck_ri, deck_z, deck_t), metal, "head", lift,
        "Head deck ring carrying all head loads; rests on the body at the deck height",
        "laser", "Aluminium sheet 3 mm")
    pin_r = p["orientation_pin_radius_mm"]
    add("orientation_pin", cylinder(3, 15, (0, pin_r, deck_z - 15), (0, 0, 1)), metal, "head", lift,
        "Single pin at the rear of the deck; the head seats in one orientation only", "buy",
        "Steel dowel 6 x 25")
    ring_ro, ring_w = p["locating_ring_outer_radius_mm"], p["locating_ring_wall_mm"]
    add("head_locating_ring", tube(ring_ro, ring_ro - ring_w, deck_z - p["locating_ring_depth_mm"],
                                   p["locating_ring_depth_mm"]),
        charcoal, "head", lift, "Spigot under the deck that centres the head in the body",
        "laser", "PP sheet 3 mm, rolled and riveted")
    shell_w = p["head_shell_wall_mm"]
    add("head_shell_ring", tube(deck_ro, deck_ro - shell_w, deck_z + deck_t, shell_top - deck_z - deck_t),
        light, "head", lift, "Raised wall between deck and funnel collar",
        "laser", "Aluminium composite 3 mm, rolled")
    funnel = revolve([(mouth_r, top), (deck_ro, top), (deck_ro, shell_top),
                      (mouth_r + fw - collar_t / slope, shell_top),
                      (throat_r + fw, lip_top), (throat_r + fw, lip_bottom),
                      (throat_r, lip_bottom), (throat_r, lip_top)])
    add("intake_funnel", funnel, (.78, .81, .80), "head", lift,
        "Collar, cone and throat lip; cone, collar and lip band are cut flat and riveted",
        "laser", "PP sheet 2 mm")
    fringe = (cq.Workplane("XY").polarArray(skirt_r + 1, 0, 360, strips)
              .rect(2, p["skirt_strip_width_mm"]).extrude(lip_bottom - plate_z)
              .translate((0, 0, plate_z))).vals()
    add("flexible_throat_skirt", tube(skirt_r + 2, skirt_r, lip_bottom - 8, 8).fuse(*fringe),
        (.14, .15, .16), "head", lift, "Flexible strip fringe under the throat lip",
        "laser", "Soft PVC strip curtain 2 mm")

    # Hangers on the four axes run above the dividers, never over a bin opening.
    hs, hr, reach = p["hanger_size_mm"], p["hanger_radius_mm"], p["spider_reach_mm"]
    assert math.hypot(hr + hs / 2, hs / 2) < ring_ro - ring_w
    for i, a in enumerate((0, 90, 180, 270), 1):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        add(f"hanger_{i}", box(hs, hs, deck_z - spider_top, (hr * c, hr * s, (deck_z + spider_top) / 2)),
            metal, "head", lift, "Square aluminium tube hanging the joint beam from the deck",
            "cut", "Aluminium square tube 30 x 30 x 2")
    sw = p["spider_width_mm"]
    spider = box(reach * 2, sw, spider_top - spider_bottom, (0, 0, (spider_top + spider_bottom) / 2)).fuse(
        box(sw, reach * 2, spider_top - spider_bottom, (0, 0, (spider_top + spider_bottom) / 2)),
        box(90, 90, spider_top - spider_bottom, (0, 0, (spider_top + spider_bottom) / 2)))
    add("joint_beam", spider, metal, "head", lift,
        "Cross beam carrying the joint; its arms lie above the bin dividers",
        "cut", "Aluminium rectangular tube 40 x 30 x 2, two pieces crossed and bolted through a 3 mm plate")
    for i, a in enumerate((0, 90, 180, 270), 1):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        add(f"spider_foot_{i}", box(30, 30, 1.5, ((reach - 15) * c, (reach - 15) * s, spider_bottom - .75)),
            rubber, "head", lift, "Rubber foot under a beam end: the head stands on it when lifted out",
            "buy", "Rubber pad 30 x 30 x 1.5, self-adhesive")

    # Option D drive. A small yaw servo turns the tilt stage toward the bin, then one hinge tilts
    # the plate. The hinge sits just under the plate, near its centre of gravity, and two pillow
    # blocks carry the plate, so the tilt servo only supplies torque through a GT2 2:1 belt.
    big_r = p["pulley_large_teeth"] * 2 / math.pi / 2
    small_r = p["pulley_small_teeth"] * 2 / math.pi / 2
    c = belt_center_distance(p["belt_loop_length_mm"], big_r, small_r)
    shaft_z = pivot - c
    bw, bore = p["belt_width_mm"], 4.05
    s_len, s_wid, s_hgt = p["servo_body_mm"]
    from_top = p["servo_shaft_from_top_mm"]
    belt_x, block_x = p["tilt_belt_plane_x_mm"], p["hinge_block_x_mm"]
    ring_x = lambda ro, ri, x0, length, z: cylinder(ro, length, (x0, 0, z), (1, 0, 0)).cut(
        cylinder(ri, length, (x0, 0, z), (1, 0, 0)))
    ring_z = lambda ro, ri, z0, h: tube(ro, ri, z0, h)
    servo_blue = (.12, .32, .58)

    # Fixed yaw support on the beam hub: back plate, two bearing arms and the yaw servo shelf.
    st = p["yaw_stack_mm"]
    shelf_z, arm_lo, arm_hi = st["servo_shelf_z_offset"], st["lower_arm_z_offset"], st["upper_arm_z_offset"]
    z_of = lambda off: spider_top + off
    bracket = box(5, 32, z_of(arm_hi) + 5 - spider_top, (-42.5, 0, (spider_top + z_of(arm_hi) + 5) / 2))
    for z0 in (z_of(arm_lo), z_of(arm_hi)):
        bracket = bracket.fuse(box(72, 32, 5, (-4, 0, z0 + 2.5)).cut(cylinder(5, 5, (0, 0, z0), (0, 0, 1))))
    bracket = bracket.fuse(box(62, 32, 4, (-9, 0, z_of(shelf_z) + 2)).cut(
        cylinder(3.5, 4, (0, 0, z_of(shelf_z)), (0, 0, 1))))
    add("yaw_bracket", bracket, charcoal, "tilt_fixed", lift,
        "Fixed C-bracket on the beam hub: two arms for the yaw bearings and a shelf for the yaw servo",
        "print", "PETG, 60 % infill (or bent aluminium 3 mm)")
    for name, z0 in (("lower", z_of(arm_lo) + 5), ("upper", z_of(arm_hi) + 5)):
        brg = box(60, 30, 4, (0, 0, z0 + 2)).fuse(cylinder(11, 12, (0, 0, z0), (0, 0, 1))).cut(
            cylinder(bore, 12, (0, 0, z0), (0, 0, 1)))
        add(f"yaw_bearing_{name}", brg, (.55, .58, .60), "tilt_fixed", lift,
            "Flanged bearing for the vertical yaw shaft", "buy", "Flanged pillow block KFL08, bore 8 mm")
    y_len, y_wid, y_hgt = p["yaw_servo_body_mm"]
    y_top = z_of(shelf_z)
    yaw_servo = box(y_len, y_wid, y_hgt, (y_len / 2 - 6, 0, y_top - y_hgt / 2)).fuse(
        box(32.5, y_wid, 2.5, (y_len / 2 - 6, 0, y_top - 6)),
        cylinder(2.4, 8, (0, 0, y_top), (0, 0, 1)))
    add("yaw_servo", yaw_servo, servo_blue, "tilt_fixed", lift,
        "MG90S turning the tilt stage plus or minus 45 degrees toward the bin", "buy", "MG90S, metal gears")

    # Yaw stage: coupling, vertical shaft, collar, platform, hinge posts and blocks, tilt servo.
    plat_bot = pivot - p["yaw_platform_below_pivot_mm"]
    plat_top = plat_bot + 5
    upper_top = z_of(arm_hi) + 5 + 12
    assert upper_top + 8 <= plat_bot, "collar fits between the upper bearing and the platform"
    add("yaw_coupling", ring_z(9.5, bore, y_top + 4, 12), metal, "yaw", lift,
        "Flexible coupling from the yaw servo spline to the 8 mm shaft", "buy", "Flexible coupling 5 x 8 mm")
    add("yaw_shaft", cylinder(4, plat_bot - (y_top + 10), (0, 0, y_top + 10), (0, 0, 1)), metal, "yaw", lift,
        "Vertical yaw shaft in the two flanged bearings", "cut", "Stainless 304 rod 8 mm")
    add("yaw_collar", ring_z(8, bore, plat_bot - 8, 8), metal, "yaw", lift,
        "Shaft collar resting on the upper bearing: carries the stage weight", "buy", "Shaft collar 8 mm")
    half_y = p["yaw_platform_half_y_mm"]
    add("yaw_platform", box(2 * (block_x + 15), 2 * half_y, 5, (0, 0, plat_bot + 2.5)), charcoal, "yaw", lift,
        "Turning platform carrying the hinge posts, the tilt servo and the stop pads", "laser",
        "Aluminium sheet 4 mm")
    block_base = pivot - 15
    for i, x in enumerate((-block_x, block_x), 1):
        add(f"hinge_post_{i}", box(13, 30, block_base - plat_top, (x, 0, (block_base + plat_top) / 2)), metal,
            "yaw", lift, "Post from the platform to a hinge pillow block", "cut", "Aluminium flat bar 30 x 13")
        blk = box(13, 55, 5, (x, 0, block_base + 2.5)).fuse(ring_x(14, bore, x - 6.5, 13, pivot)).cut(
            cylinder(bore, 13, (x - 6.5, 0, pivot), (1, 0, 0)))
        add(f"hinge_block_{i}", blk, (.55, .58, .60), "yaw", lift,
            "Horizontal pillow block carrying the hinge shaft; takes the plate load off the servo", "buy",
            "Pillow block KP08, bore 8 mm")
    face = belt_x - 1
    body_y0 = -from_top
    tilt_servo = box(s_hgt, s_len, s_wid, (face - s_hgt / 2, body_y0 + s_len / 2, shaft_z)).fuse(
        box(2.5, 54, s_wid, (face - 12, body_y0 + s_len / 2, shaft_z)),
        cylinder(2.5, 7, (face, 0, shaft_z), (1, 0, 0)))
    add("tilt_servo", tilt_servo, servo_blue, "yaw", lift,
        "MG996R driving the hinge through the 2:1 belt", "buy", "MG996R, metal gears")
    ear_x = face - 12 + 1.25
    srv_bracket = box(5, 68, shaft_z + s_wid / 2 + 6 - plat_top,
                      (ear_x + 2.5, body_y0 + s_len / 2, (shaft_z + s_wid / 2 + 6 + plat_top) / 2)).cut(
        box(5, s_len, s_wid, (ear_x + 2.5, body_y0 + s_len / 2, shaft_z)))
    add("tilt_servo_bracket", srv_bracket, charcoal, "yaw", lift,
        "Bracket the MG996R ears bolt to; slotted holes set the belt tension", "print", "PETG, 60 % infill")
    add("tilt_pulley_small", cylinder(small_r - .25, bw, (belt_x, 0, shaft_z), (1, 0, 0)).cut(
        cylinder(2.6, bw, (belt_x, 0, shaft_z), (1, 0, 0))), metal, "yaw", lift,
        "GT2 20-tooth pulley on the MG996R (3D-printed adapter to the horn)", "buy", "GT2 20T, 6 mm belt")
    add("tilt_belt", belt_loop(lambda a, z: cq.Vector(belt_x, a, z), (bw, 0, 0), big_r, small_r, pivot, c),
        (.1, .1, .1), "yaw", lift, "GT2 closed belt, hinge axis", "buy",
        f"GT2 closed loop {p['belt_loop_length_mm']:.0f} mm")

    # Hard stop on the turning platform, so it always sits under the edge that goes down: at the stop
    # angle the plate lands on rubber, and a heavy drop loads the yaw bearings, not the servo gears.
    stop = math.radians(p["tilt_stop_degrees"])
    pad_y, pad_hw = p["tilt_stop_pad_y_mm"], 6
    pad_top = pivot + plate_h / math.cos(stop) - (pad_y + pad_hw) * math.tan(stop)
    clear_at_max = pivot + plate_h / math.cos(theta) - (pad_y + pad_hw) - pad_top
    assert clear_at_max > 4, "plate must clear the stop pads at the working tilt"
    assert pad_y + pad_hw <= half_y
    for i, y in enumerate((-pad_y, pad_y), 1):
        add(f"tilt_stop_pad_{i}", box(24, 2 * pad_hw, pad_top - plat_top, (0, y, (pad_top + plat_top) / 2)),
            rubber, "yaw", lift, f"Stop pad: the plate lands on it at {p['tilt_stop_degrees']:.0f} degrees",
            "print", "PETG block with a rubber bumper on top")

    # Tilt stage: hinge shaft, collars, lugs under the plate, large pulley, plate and IMU.
    shaft_len = 2 * (block_x + 15)
    add("hinge_shaft", cylinder(4, shaft_len, (-shaft_len / 2, 0, pivot), (1, 0, 0)), metal, "tilt_plate", lift,
        "Hinge shaft 22 mm under the plate surface, turning in the two pillow blocks", "cut",
        "Stainless 304 rod 8 mm")
    for i, x in enumerate((-block_x - 6.5 - 8, block_x + 6.5), 1):
        add(f"hinge_collar_{i}", ring_x(8, bore, x, 8, pivot), metal, "tilt_plate", lift,
            "Shaft collar holding the hinge shaft in place", "buy", "Shaft collar 8 mm")
    lug_x = p["plate_lug_x_mm"]
    holes = [(x, y) for x in (-lug_x, lug_x) for y in (-12, 12)]
    for i, x in enumerate((-lug_x, lug_x), 1):
        lug = box(6, 24, plate_z - 4 - (pivot - 10), (x, 0, (plate_z - 4 + pivot - 10) / 2)).fuse(
            box(20, 40, 4, (x, 0, plate_z - 2))).cut(cylinder(bore, 6, (x - 3, 0, pivot), (1, 0, 0)))
        for hx, hy in holes:
            lug = lug.cut(cylinder(2.2, 4, (hx, hy, plate_z - 4), (0, 0, 1)))
        add(f"plate_lug_{i}", lug, charcoal, "tilt_plate", lift,
            "Lug under the plate, clamped to the hinge shaft", "print", "PETG, 60 % infill")
    add("tilt_pulley_large", cylinder(big_r - .25, bw, (belt_x, 0, pivot), (1, 0, 0)).cut(
        cylinder(bore, bw, (belt_x, 0, pivot), (1, 0, 0))), metal, "tilt_plate", lift,
        "GT2 40-tooth pulley clamped to the hinge shaft", "buy", "GT2 40T, 8 mm bore (check: some are 5 mm)")
    plate = (cq.Workplane("XY").circle(plate_r).extrude(plate_t).edges().fillet(min(1, plate_t / 3))
             .translate((0, 0, plate_z))).val()
    for x, y in holes:
        plate = plate.cut(cylinder(2.2, plate_t, (x, y, plate_z), (0, 0, 1)))
    add("tipping_plate", plate, pp, "tilt_plate", lift,
        "320 mm tipping plate bolted to the two lugs; does not melt under a hot ember", "laser",
        "Aluminium sheet 1.5 mm, matt grey powder coat")
    add("tilt_imu", box(21, 16, 3, (0, 30, plate_z - 1.5)), (.10, .35, .20), "tilt_plate", lift,
        "IMU under the plate: true tilt angle for jam detection and homing after a power cut",
        "buy", "MPU-6050 (GY-521)")

    # Fill sensors hang off the throat lip, under the funnel and out of the item path.
    pod_w, pod_h = p["fill_sensor_housing_width_mm"], p["fill_sensor_housing_height_mm"]
    sensor_r = p["fill_sensor_radial_position_mm"]
    pod_top, pod_bottom = lip_top, lip_top - pod_h
    pod = box(pod_w, pod_w, pod_h, (sensor_r, 0, pod_top - pod_h / 2))
    pod = pod.cut(box(pod_w - 6, pod_w - 6, pod_h - 6, (sensor_r, 0, pod_top - pod_h / 2)).fuse(
        cylinder(6, 8, (sensor_r, 0, pod_bottom - 1), (0, 0, 1))))
    reach_s = sensor_r - pod_w / 2 - throat_r
    bracket = box(reach_s, 20, 20, (throat_r + reach_s / 2, 0, pod_top - pod_h / 2)).cut(
        tube(throat_r + fw, 0, pod_bottom, pod_h))
    for i, a in enumerate(DIRECTIONS, 1):
        add(f"fill_sensor_pod_{i}", pod.rotate((0, 0, 0), (0, 0, 1), a), charcoal, "head", lift,
            "Distance-sensor pod above one bin (HC-SR04 first, VL53L1X if bags mislead it)",
            "print", "PETG")
        add(f"fill_sensor_arm_{i}", bracket.rotate((0, 0, 0), (0, 0, 1), a), metal, "head", lift,
            "Sensor arm from the throat lip", "print", "PETG")

    # Rear console as in v3: the display leans back and the camera hides under its chin.
    # The chin reaches in over the funnel mouth so the camera sees the rear plate edge
    # past the throat lip (v3's rim-mounted camera lost about 16 % of the plate there).
    cw, ch = p["console_width_mm"], p["console_height_mm"]
    y_front, chin_h = p["console_chin_front_y_mm"], p["console_chin_height_mm"]
    lean = math.radians(p["display_lean_back_degrees"])
    z_face0, z_top = top + chin_h, top + ch
    y_top = y_front + (z_top - z_face0) * math.tan(lean)
    body = (cq.Workplane("YZ").polyline([(y_front, top), (y_front, z_face0), (y_top, z_top),
                                         (deck_ro + 30, z_top), (deck_ro + 30, top)])
            .close().extrude(cw / 2, both=True).val())
    body = body.intersect(tube(deck_ro, 0, top, ch))
    face_center = (0, y_front + (ch - chin_h) / 2 * math.tan(lean), (z_face0 + z_top) / 2)
    on_face = lambda shape: shape.rotate((0, 0, 0), (1, 0, 0), -math.degrees(lean)).translate(face_center)
    gw, gh, gd = 90, 60, 3
    face = on_face(box(gw, gd, gh, (0, gd / 2, 0)))
    target = (0, 0, plate_z + plate_t)
    lens_at = (0, p["camera_y_mm"], top)
    dx, dy, dz = (t - l for t, l in zip(target, lens_at))
    n = math.sqrt(dx * dx + dy * dy + dz * dz)
    aim = (dx / n, dy / n, dz / n)
    inward = tuple(-a for a in aim)
    along = lambda d: tuple(l + d * a for l, a in zip(lens_at, inward))
    recess = cylinder(11, 14, along(-2), inward)
    led = box(120, 8, 2.5, (0, p["camera_y_mm"] + 24, top + 1.25))
    body = body.cut(face).cut(recess).cut(led)
    add("display_console", body, light, "brain", brain_lift,
        "Rear console, hollow shell: TFT face leaning back, ESP32-S3, servo supply and wiring inside, "
        "camera and LED strip under the chin, clear of any liquid in the funnel", "print",
        "PETG, printed in 2 halves")
    add("tft_screen", face, glass, "brain", brain_lift, "3.5 inch TFT module in the console face", "buy",
        "TFT 3.5 inch SPI")
    add("camera_window", cylinder(10.5, 2, along(10), inward), (.02, .02, .02), "brain", brain_lift,
        "ESP32-S3 camera behind the chin window, 120 degree lens", "buy",
        "ESP32-S3 camera module, OV2640 with 120 degree lens")
    add("led_strip", led, (.98, .96, .80), "brain", brain_lift,
        "White LED strip under the chin lighting the plate evenly for recognition", "buy",
        "5 V white LED strip, 120 mm, with diffuser")
    cam = along(10)

    # Camera sightline: every plate-edge point must pass inside the throat lip and the skirt.
    rings = [(lip_top, throat_r), (lip_bottom, throat_r)]
    rings += [(z, skirt_r) for z in range(int(lip_bottom), int(plate_z + plate_t), -8)]
    hidden = 0
    for k in range(72):
        a = math.radians(k * 5)
        ex, ey, ez = plate_r * math.cos(a), plate_r * math.sin(a), plate_z + plate_t
        for zc, rc in rings:
            f = (cam[2] - zc) / (cam[2] - ez)
            if math.hypot(cam[0] + f * (ex - cam[0]), cam[1] + f * (ey - cam[1])) > rc:
                hidden += 1
                break

    # Field of view the lens must cover: widest angle from the aim axis to the plate edge.
    widest = 0
    for k in range(72):
        a = math.radians(k * 5)
        v = (plate_r * math.cos(a) - cam[0], plate_r * math.sin(a) - cam[1], plate_z + plate_t - cam[2])
        widest = max(widest, math.degrees(math.acos(sum(x * y for x, y in zip(v, aim)) / math.hypot(*v))))

    return {"camera_required_full_fov_degrees": round(2 * widest, 1), "pivot_z": pivot, "plate_z": plate_z, "spider_bottom": spider_bottom,
            "spider_top": spider_top, "lip_top": lip_top, "lip_bottom": lip_bottom,
            "throat_r": throat_r, "exit_gap": exit_gap, "skirt_gap": skirt_gap,
            "low_edge_z": low_edge_z, "belt_center_mm": c, "big_r": big_r, "small_r": small_r,
            "camera": cam, "camera_hidden_edge_samples": hidden, "slope": slope,
            "shell_top": shell_top, "collar_t": collar_t, "mouth_r": mouth_r, "fw": fw}


def body_a(p, add, h):
    d = p["drum"]
    r, wall, floor_t = d["outer_diameter_mm"] / 2, d["wall_mm"], d["bottom_mm"]
    height = d["height_mm"]
    assert abs(height - p["head_deck_height_mm"]) < 1e-6, "head deck rests on the drum rim"
    ri = r - wall
    assert ri > p["locating_ring_outer_radius_mm"] + 2
    drum = tube(r, ri, floor_t, height - floor_t).fuse(tube(r, 0, 0, floor_t))
    add("drum_220l", drum, (.18, .42, .66), "body", (0, 0, 0),
        "Open-top 220 L HDPE drum used as the body; dimensions provisional", "buy",
        "HDPE open-top drum 220 L")
    t, clear = d["divider_thickness_mm"], d["divider_clearance_mm"]
    cap_w, cap_t = d["divider_cap_width_mm"], d["divider_cap_thickness_mm"]
    frame_t, bar, gap = d["bag_frame_thickness_mm"], d["bag_frame_bar_mm"], d["bag_frame_gap_to_spider_mm"]
    # Stack under the joint beam: rubber foot, gap, bag frame, divider cap, divider.
    frame_top = h["spider_bottom"] - gap
    frame_bottom = frame_top - frame_t
    cap_bottom = frame_bottom - cap_t
    top = cap_bottom
    length = 2 * (ri - clear)
    hgt = top - floor_t
    slot = t + .4
    lower = box(length, t, hgt, (0, 0, floor_t + hgt / 2)).cut(
        box(slot, t + 2, hgt / 2, (0, 0, top - hgt / 4)))
    upper = box(t, length, hgt, (0, 0, floor_t + hgt / 2)).cut(
        box(t + 2, slot, hgt / 2, (0, 0, floor_t + hgt / 4)))
    white = (.95, .95, .93)
    add("divider_x", lower, white, "dividers", (0, 0, 380),
        "Divider plate, slot from the top; half-laps with divider_y", "laser", "PVC foam board 5 mm")
    add("divider_y", upper, white, "dividers", (0, 0, 380),
        "Divider plate, slot from the bottom", "laser", "PVC foam board 5 mm")
    cap = box(length, cap_w, cap_t, (0, 0, cap_bottom + cap_t / 2)).fuse(
        box(cap_w, length, cap_t, (0, 0, cap_bottom + cap_t / 2)))
    add("divider_cap", cap, (.55, .58, .57), "dividers", (0, 0, 420),
        "Cross cap on the divider tops: a ledge for the bag frames on both sides", "laser",
        "Aluminium composite 5 mm")

    # One bag frame per quarter: the bag folds over it; the joint beam's feet hold it down.
    r_out = ri - clear
    edge = t / 2 + .5
    for i, a in enumerate(DIRECTIONS, 1):
        sx, sy = math.copysign(1, math.cos(math.radians(a))), math.copysign(1, math.sin(math.radians(a)))
        quarter = lambda r, off: cylinder(r, frame_t, (0, 0, frame_bottom), (0, 0, 1)).intersect(
            box(r, r, frame_t, (sx * (off + r / 2), sy * (off + r / 2), frame_bottom + frame_t / 2)))
        frame = quarter(r_out, edge).cut(quarter(r_out - bar, cap_w / 2))
        add(f"bag_frame_{i}", frame, (.80, .66, .45), "dividers", (sx * 60, sy * 60, 470),
            "Quarter bag frame: lift it out with the full bag", "laser", "Plywood 6 mm, sealed")
        for j, da in enumerate((-30, 0, 30), 1):
            ang = math.radians(a + da)
            tab = box(12, 16, 10, (0, 0, frame_bottom - 5)).rotate((0, 0, 0), (0, 0, 1), a + da).translate(
                ((ri - 6.6) * math.cos(ang), (ri - 6.6) * math.sin(ang), 0))
            add(f"bag_frame_tab_{i}{j}", tab, (.19, .23, .26), "body", (0, 0, 0),
                "Tab bonded to the drum wall under the frame arc", "print", "PETG, bonded with MS polymer")

    # Fixing, orientation and lid sensing on the drum rim.
    pin_r = p["orientation_pin_radius_mm"]
    socket = box(16, ri - .5 - (pin_r - 5), 20, (0, (pin_r - 5 + ri - .5) / 2, height - 20)).cut(
        cylinder(3.3, 20, (0, pin_r, height - 20), (0, 0, 1)))
    add("orientation_socket", socket, (.19, .23, .26), "body", (0, 0, 0),
        "Block bonded inside the rear rim; the deck pin drops into it", "print", "PETG")
    add("lid_switch", box(20, 6, 12, (0, -(ri - 3.5), height - 6.5)), (.85, .2, .2), "body", (0, 0, 0),
        "Microswitch at the front rim: servos stay unpowered unless the head is seated", "buy",
        "Microswitch with lever, KW11")
    for i, x in enumerate((-1, 1), 1):
        add(f"head_latch_{i}", box(15, 24, 35, (x * (r + 7.5), 0, height - 2 - 17.5)), (.61, .66, .69),
            "body", (x * 40, 0, 0), "Toggle latch on the drum side, hooking over the deck rim", "buy",
            "Toggle latch 40 mm, stainless")
    quarter_v = (math.pi * ri ** 2 / 4 - (ri - clear) * t) * (top - floor_t) / 1e6
    return {"body": "A", "outer_mm": [r * 2, r * 2], "bin_rim_z": top, "bin_floor_z": floor_t,
            "capacity_l_each": round(quarter_v, 1), "bin_center_radius": ri * .52,
            "bag_note": "Lift the head off (it stands on its beam feet), lift each bag frame out with its bag"}


def body_b(p, add, h):
    f, b = p["frame"], p["bin"]
    half, prof, panel = f["outer_mm"] / 2, f["profile_mm"], f["panel_mm"]
    deck = p["head_deck_height_mm"]
    top = p["rim_height_mm"]
    pc = half - prof / 2
    inner = half - prof
    seat_t, floor_t = f["seat_plate_mm"], f["floor_plate_mm"]
    seat_z = deck - seat_t
    rail_z = seat_z - prof
    assert inner >= p["locating_ring_outer_radius_mm"] + 2
    alu = (.72, .75, .77)
    n = 0
    for x in (-pc, pc):
        for y in (-pc, pc):
            n += 1
            add(f"post_{n}", box(prof, prof, top, (x, y, top / 2)), alu, "frame", (0, 0, 0),
                "Corner post", "cut", "Aluminium profile 20 x 20")
    rails = [("bottom", prof / 2, "xy"), ("seat", rail_z + prof / 2, "xy"), ("mid", 450, "x")]
    for label, z, sides in rails:
        for s in (-pc, pc):
            add(f"rail_{label}_y{'p' if s > 0 else 'n'}", box(prof, inner * 2, prof, (s, 0, z)), alu,
                "frame", (0, 0, 0), f"{label.title()} rail along Y", "cut", "Aluminium profile 20 x 20")
            if "y" in sides:
                add(f"rail_{label}_x{'p' if s > 0 else 'n'}", box(inner * 2, prof, prof, (0, s, z)), alu,
                    "frame", (0, 0, 0), f"{label.title()} rail along X", "cut", "Aluminium profile 20 x 20")
    notched = lambda t, z: box(half * 2, half * 2, t, (0, 0, z + t / 2)).cut(
        box(prof, prof, t, (pc, pc, z + t / 2)).fuse(box(prof, prof, t, (-pc, pc, z + t / 2)),
                                                     box(prof, prof, t, (pc, -pc, z + t / 2)),
                                                     box(prof, prof, t, (-pc, -pc, z + t / 2))))
    add("floor_plate", notched(floor_t, prof), (.55, .58, .57), "frame", (0, 0, 0),
        "Floor the bins stand on", "laser", "Aluminium composite 4 mm")
    seat_hole = p["locating_ring_outer_radius_mm"] + 2
    pin_hole = cylinder(3.3, seat_t, (0, p["orientation_pin_radius_mm"], seat_z), (0, 0, 1))
    add("head_seat_plate", notched(seat_t, seat_z).cut(tube(seat_hole, 0, seat_z, seat_t)).cut(pin_hole),
        (.55, .58, .57), "frame", (0, 0, 0),
        "Plate the head deck is bolted to; the rear hole takes the deck orientation pin", "laser",
        "Aluminium composite 6 mm (or plywood 6 mm)")
    skin = (.94, .95, .94)
    for s, name in ((-1, "left"), (1, "right")):
        add(f"side_panel_{name}", box(panel, half * 2, top, (s * (half + panel / 2), 0, top / 2)), skin,
            "skin", (s * 250, 0, 0), "Side skin", "laser", "Aluminium composite 3 mm")
    door_top, head_bottom = rail_z, rail_z + 2
    door_h = door_top - 2
    back_y = half + panel / 2
    add("back_panel", box(half * 2, panel, top, (0, back_y, top / 2)), skin, "skin", (0, 250, 0),
        "Fixed back skin: the bin can stand against a wall", "laser", "Aluminium composite 3 mm")
    add("head_panel_front", box(half * 2, panel, top - head_bottom, (0, -back_y, (top + head_bottom) / 2)),
        skin, "skin", (0, -250, 0), "Front panel around the head", "laser", "Aluminium composite 3 mm")
    cover = box(half * 2 + panel * 2, half * 2 + panel * 2, 3, (0, 0, top + 1.5)).cut(
        tube(p["deck_outer_radius_mm"] + 1, 0, top, 3))
    add("top_cover", cover, (.82, .85, .84), "skin", (0, 0, 450),
        "Top cover with the funnel opening, screwed to the frame", "laser", "Aluminium composite 3 mm")

    # Two drawers, left and right, each carrying a front and a rear bin on full-extension slides.
    w, bh, bt, off = b["width_mm"], b["height_mm"], b["wall_mm"], b["center_offset_mm"]
    cw, st, sh, sl = f["center_wall_mm"], f["slide_thickness_mm"], f["slide_height_mm"], f["slide_length_mm"]
    mt, dw, db, dwh = f["slide_mount_mm"], f["drawer_wall_mm"], f["drawer_bottom_mm"], f["drawer_wall_height_mm"]
    base = prof + floor_t
    in_x0, out_x1 = cw / 2 + st, inner - mt - st
    tray_z = base + 2
    z0 = tray_z + db
    assert off - w / 2 >= in_x0 + dw + 2 and off + w / 2 <= out_x1 - dw - 2, "bins fit between the drawer walls"
    tray_y0, tray_y1 = -half, inner - 13
    assert off + w / 2 < tray_y1 - dw, "rear bin fits in the tray"
    steel = (.50, .52, .55)
    add("center_wall", box(cw, inner * 2, 106, (0, 0, base + 53)), (.55, .58, .57), "frame", (0, 0, 0),
        "Centre wall carrying both inner slides", "laser", "Aluminium composite 6 mm")
    for s, name in ((-1, "left"), (1, "right")):
        add(f"slide_mount_{name}", box(mt, inner * 2, 106, (s * (inner - mt / 2), 0, base + 53)),
            (.55, .58, .57), "frame", (0, 0, 0), "Plate on the bottom rail carrying the outer slide",
            "laser", "Aluminium composite 6 mm")
        tray = box(out_x1 - in_x0, tray_y1 - tray_y0, db, (s * (in_x0 + out_x1) / 2, (tray_y0 + tray_y1) / 2, tray_z + db / 2))
        for x in (in_x0 + dw / 2, out_x1 - dw / 2):
            tray = tray.fuse(box(dw, tray_y1 - tray_y0, dwh, (s * x, (tray_y0 + tray_y1) / 2, z0 + dwh / 2)))
        tray = tray.fuse(box(out_x1 - in_x0, dw, dwh, (s * (in_x0 + out_x1) / 2, tray_y1 - dw / 2, z0 + dwh / 2)))
        add(f"drawer_{name}", tray, (.62, .65, .64), "drawers", (0, -420, 0),
            "Drawer tray holding the front and the rear bin", "laser", "Aluminium composite 4 mm, riveted angles")
        add(f"drawer_front_{name}", box(half - 1, panel, door_h, (s * (half + 1) / 2, -back_y, 2 + door_h / 2)),
            skin, "drawers", (0, -420, 0), "Drawer front, full height, with a pull handle", "laser",
            "Aluminium composite 3 mm")
        for x, tag in ((in_x0 - st / 2, "inner"), (out_x1 + st / 2, "outer")):
            add(f"slide_{name}_{tag}", box(st, sl, sh, (s * x, -inner + sl / 2, z0 + 8 + sh / 2)), steel,
                "frame", (0, 0, 0), f"Full-extension ball slide {sl:.0f} mm", "buy",
                f"Ball-bearing drawer slide {sl:.0f} mm, full extension, 35 kg")
        add(f"drawer_switch_{name}", box(20, 8, 12, (s * off, tray_y1 + 5, z0 + 30)), (.85, .2, .2), "frame",
            (0, 0, 0), "Microswitch the closed drawer presses; open drawer locks its two bins", "buy",
            "Microswitch with lever, KW11")
    bin_shell = box(w, w, bh, (0, 0, z0 + bh / 2)).cut(box(w - 2 * bt, w - 2 * bt, bh, (0, 0, z0 + bt + bh / 2)))
    for i, a in enumerate(DIRECTIONS, 1):
        sx, sy = math.copysign(off, math.cos(math.radians(a))), math.copysign(off, math.sin(math.radians(a)))
        add(f"bin_{i}", bin_shell.translate((sx, sy, 0)), None, "bins", (sx * .3, sy * .3 - 420, 0),
            f"Purchased square bin {i} ({p['bin_categories'][i - 1]}); dimensions provisional", "buy",
            "Square bin 25-30 L")
    assert z0 + bh < h["spider_bottom"] - 20
    # The rear bin must leave the head's footprint when the drawer is fully out, so it lifts free.
    assert off + w / 2 - sl < -(p["spider_reach_mm"] + 10), "rear bin clears the head when pulled out"
    return {"body": "B", "outer_mm": [half * 2 + panel * 2, half * 2 + panel * 2],
            "bin_rim_z": z0 + bh, "bin_floor_z": z0 + bt,
            "capacity_l_each": round((w - 2 * bt) ** 2 * (bh - bt) / 1e6, 1),
            "bin_center_radius": off * math.sqrt(2),
            "bag_note": "Pull a drawer out: its front and rear bins lift straight up; the back stays against the wall",
            "flat_pieces": {"drawer_bottom_x2": [out_x1 - in_x0, tray_y1 - tray_y0],
                            "drawer_side_wall_x4": [tray_y1 - tray_y0, dwh],
                            "drawer_back_wall_x2": [out_x1 - in_x0, dwh]}}


BIN_COLORS = [(.29, .56, .72), (.79, .53, .23), (.37, .62, .42), (.60, .42, .69)]


def build(p, body):
    parts, meta = [], {}

    def add(name, shape, color, group, explode=(0, 0, 0), description="", process="", material=""):
        if color is None:
            color = BIN_COLORS[int(name[-1]) - 1]
        parts.append(Part(name, shape.clean(), color, group, explode, description))
        meta[name] = {"process": process, "material": material}

    h = head(p, add)
    info = (body_a if body == "A" else body_b)(p, add, h)

    # Torque each servo must hold at full tilt with the item at the plate edge.
    theta = math.radians(p["maximum_plate_tilt_degrees"])
    g = 9.81
    plate_mass = math.pi * (p["plate_radius_mm"] / 1000) ** 2 * p["plate_thickness_mm"] / 1000 * p["plate_density_kg_m3"]
    cg = (p["plate_bottom_above_pivot_mm"] + p["plate_thickness_mm"] / 2) / 1000
    item_lever = (p["plate_radius_mm"] * math.cos(theta)
                  + (p["plate_bottom_above_pivot_mm"] + p["plate_thickness_mm"] + p["item_diameter_mm"] / 2)
                  * math.sin(theta)) / 1000
    hinge_torque = g * (plate_mass * cg * math.sin(theta) + p["item_mass_kg"] * item_lever)
    ratio = p["pulley_large_teeth"] / p["pulley_small_teeth"]
    servo_need = hinge_torque / (ratio * p["belt_efficiency"])
    stall = p["servo_stall_torque_nm"]
    # Heaviest item the servos lift at half and at full stall torque.
    plate_term = g * plate_mass * cg * math.sin(theta)
    max_item = lambda f: (f * stall * ratio * p["belt_efficiency"] - plate_term) / (g * item_lever)
    edge_force = stall * ratio * p["belt_efficiency"] / (p["plate_radius_mm"] / 1000)

    metrics = {
        "revision": f"ab-{body}-E1", "units": "mm", "body": body, "brain": "E1",
        "outer_mm": info["outer_mm"], "rim_height_mm": p["rim_height_mm"],
        "head_deck_height_mm": p["head_deck_height_mm"],
        "bin_rim_height_mm": info["bin_rim_z"], "bin_floor_height_mm": info["bin_floor_z"],
        "capacity_l_each_provisional": info["capacity_l_each"],
        "plate_level_top_height_mm": h["plate_z"] + p["plate_thickness_mm"],
        "tilt_pivot_mm": [0, 0, h["pivot_z"]],
        "maximum_plate_tilt_degrees": p["maximum_plate_tilt_degrees"],
        "destination_directions_degrees": list(DIRECTIONS),
        "plate_low_edge_height_at_full_tilt_mm": round(h["low_edge_z"], 1),
        "exit_gap_at_full_tilt_mm": round(h["exit_gap"], 1),
        "skirt_gap_at_full_tilt_mm": round(h["skirt_gap"], 1),
        "belt_center_distance_mm": round(h["belt_center_mm"], 2),
        "plate_mass_kg": round(plate_mass, 3),
        "hinge_torque_needed_nm": round(hinge_torque, 3),
        "servo_torque_needed_nm": round(servo_need, 3),
        "servo_stall_torque_nm": stall,
        "servo_load_fraction_of_stall": round(servo_need / stall, 3),
        "design_item_mass_kg": p["item_mass_kg"],
        "max_item_kg_at_half_stall": round(max_item(.5), 2),
        "max_item_kg_at_stall": round(max_item(1), 2),
        "max_plate_edge_force_n": round(edge_force, 1),
        "tilt_stop_degrees": p["tilt_stop_degrees"],
        "bin_categories": p["bin_categories"],
        "camera_position_mm": [round(v, 1) for v in h["camera"]],
        "camera_hidden_plate_edge_samples_of_72": h["camera_hidden_edge_samples"],
        "camera_required_full_fov_degrees": h["camera_required_full_fov_degrees"],
        "bin_landing_radius_mm": round(info["bin_center_radius"], 1),
        "bag_change": info["bag_note"],
        "flat_pieces_mm": info.get("flat_pieces", {}),
        "purchased_dimensions_status": p["purchased_dimensions_status"],
        "status": "Prototype CAD; fasteners, wiring and hinges are not modelled",
    }
    assert h["camera_hidden_edge_samples"] == 0, "camera must see the whole plate edge"
    assert servo_need / stall <= .5, "servo must work at or below half its stall torque"
    return parts, meta, metrics


def export_assembly(items, name, path, exploded=False):
    assembly = cq.Assembly(name=name)
    for part in items:
        shape = part.shape.translate(part.explode) if exploded else part.shape
        assembly.add(shape, name=part.name, color=cq.Color(*part.color))
    assembly.export(str(path))


def mesh_record(part, variant):
    vv, tt = part.shape.tessellate(.8, .15)
    return {"name": part.name, "group": part.group, "color": part.color, "explode": part.explode,
            "description": part.description, "variant": variant,
            "vertices": [[round(v.x, 2), round(v.y, 2), round(v.z, 2)] for v in vv], "triangles": tt}


def flat_dxf(shape, path):
    """Section a flat solid at mid-thickness in its own plane and write the outline as DXF."""
    bb = shape.BoundingBox()
    dims = {"x": bb.xlen, "y": bb.ylen, "z": bb.zlen}
    thin = min(dims, key=dims.get)
    if thin == "x":
        shape = shape.rotate((0, 0, 0), (0, 1, 0), 90)
    elif thin == "y":
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 90)
    bb = shape.BoundingBox()
    shape = shape.translate((-bb.xmin, -bb.ymin, -(bb.zmin + bb.zmax) / 2))
    section = cq.Workplane("XY").add(shape).section()
    cq.exporters.export(section, str(path), exportType="DXF")


def pattern_dxf(workplane_2d, path):
    solid = workplane_2d.extrude(1).val()
    flat_dxf(solid, path)


def funnel_patterns(p, h, out):
    """Flat patterns for the parts rolled from sheet: cone halves, collar, lip, shell, spigot."""
    fw, slope = h["fw"], h["slope"]
    r_bot = h["throat_r"] + fw / 2
    r_top = h["mouth_r"] + fw / 2
    slant = math.hypot(r_top - r_bot, p["funnel_height_mm"])
    s_bot, s_top = r_bot * slant / (r_top - r_bot), r_top * slant / (r_top - r_bot)
    tab = 15
    half = math.pi * r_top / s_top + tab / s_top
    pts = lambda r, a: (r * math.cos(a), r * math.sin(a))
    wp = (cq.Workplane("XY").moveTo(*pts(s_bot, 0)).lineTo(*pts(s_top, 0))
          .threePointArc(pts(s_top, half / 2), pts(s_top, half)).lineTo(*pts(s_bot, half))
          .threePointArc(pts(s_bot, half / 2), pts(s_bot, 0)).close())
    pattern_dxf(wp, out / "funnel_cone_half_x2.dxf")
    pattern_dxf(cq.Workplane("XY").circle(p["deck_outer_radius_mm"]).circle(h["mouth_r"]),
                out / "funnel_collar_ring.dxf")
    strip = lambda length, height: cq.Workplane("XY").rect(length, height)
    pattern_dxf(strip(2 * math.pi * (h["throat_r"] + fw / 2) + tab, p["throat_lip_height_mm"]),
                out / "funnel_lip_band.dxf")
    shell_h = h["shell_top"] - p["head_deck_height_mm"] - p["deck_thickness_mm"]
    pattern_dxf(strip(2 * math.pi * (p["deck_outer_radius_mm"] - p["head_shell_wall_mm"] / 2) + 20, shell_h),
                out / "head_shell_ring_strip.dxf")
    ring_r = p["locating_ring_outer_radius_mm"] - p["locating_ring_wall_mm"] / 2
    pattern_dxf(strip(2 * math.pi * ring_r + 15, p["locating_ring_depth_mm"]),
                out / "head_locating_ring_strip.dxf")
    deck = cq.Workplane("XY").circle(p["deck_outer_radius_mm"]).circle(p["deck_inner_radius_mm"])
    hr = p["hanger_radius_mm"]
    deck = deck.extrude(1).faces(">Z").workplane().pushPoints(
        [(hr, 0), (0, hr), (-hr, 0), (0, -hr)]).hole(6.5)
    flat_dxf(deck.val(), out / "head_deck.dxf")
    return {"funnel_cone_sector_degrees_each_half": round(math.degrees(half), 2),
            "funnel_cone_inner_outer_radius_mm": [round(s_bot, 1), round(s_top, 1)]}


def export_option(p, body, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "parts").mkdir(exist_ok=True)
    (out / "dxf").mkdir(exist_ok=True)
    report = {"variants": {}}
    union, meshes = {}, []
    for brain in ("E1",):
        parts, meta, metrics = build(p, body)
        checks = [{"pose": "neutral", **{k: v for k, v in validate(parts).items() if k == "checks"}}]
        for destination, direction in enumerate(DIRECTIONS, 1):
            # Yaw first with the plate level (half and full turn), then tilt in steps.
            yaw, tilt = angles(p["maximum_plate_tilt_degrees"], direction)
            for yaw_f, fraction in ((.5, 0), (1, 0), (1, .25), (1, .5), (1, .75), (1, 1.0)):
                items = posed(parts, metrics["tilt_pivot_mm"][2], yaw * yaw_f, tilt * fraction)
                validate(items)
                checks.append({"destination": destination, "yaw_fraction": yaw_f, "tilt_fraction": fraction,
                               "yaw_degrees": round(yaw * yaw_f, 3), "tilt_degrees": round(tilt * fraction, 3),
                               "positive_volume_intersections": []})
                if fraction == 1 and brain == "E1":
                    export_assembly(items, f"tilt_to_bin_{destination}", out / f"tilt_to_bin_{destination}.step")
        export_assembly(parts, f"option_{body}_{brain}", out / f"assembly_{brain.lower()}.step")
        if brain == "E1":
            export_assembly(parts, f"option_{body}_{brain}_exploded", out / "exploded_e1.step", True)
        report["variants"][brain] = {"part_count": len(parts), "tilt_pose_checks": checks,
                                     "metrics": metrics}
        for part in parts:
            if part.name in union:
                union[part.name]["variant"] = "both"
            else:
                union[part.name] = {"part": part, "meta": meta[part.name], "variant": brain}
        imported = cq.importers.importStep(str(out / f"assembly_{brain.lower()}.step")).solids().vals()
        assert len(imported) == len(parts)
    for name, entry in union.items():
        part = entry["part"]
        cq.exporters.export(part.shape, str(out / "parts" / f"{name}.step"))
        cq.exporters.export(part.shape, str(out / "parts" / f"{name}.stl"), tolerance=.15, angularTolerance=.08)
        meshes.append(mesh_record(part, entry["variant"]))
        if entry["meta"]["process"] == "laser" and name not in (
                "intake_funnel", "head_shell_ring", "head_locating_ring", "flexible_throat_skirt", "head_deck",
                "drawer_left", "drawer_right"):
            flat_dxf(part.shape, out / "dxf" / f"{name}.dxf")
    for name, (x, y) in metrics["flat_pieces_mm"].items():
        pattern_dxf(cq.Workplane("XY").rect(x, y), out / "dxf" / f"{name}.dxf")
    metrics_e1 = metrics
    h = head(p, lambda *a, **k: None)
    report["flat_patterns"] = funnel_patterns(p, h, out / "dxf")
    (out / "mesh.json").write_text(json.dumps(meshes, separators=(",", ":")))
    with (out / "components.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["component", "quantity", "process", "material", "variant", "description"])
        for name, entry in union.items():
            writer.writerow([name, 1, entry["meta"]["process"], entry["meta"]["material"],
                             entry["variant"], entry["part"].description])
    if body == "B":
        lengths = {}
        for name, entry in union.items():
            if entry["meta"]["material"] == "Aluminium profile 20 x 20":
                bb = entry["part"].shape.BoundingBox()
                key = round(max(bb.xlen, bb.ylen, bb.zlen))
                lengths[key] = lengths.get(key, 0) + 1
        with (out / "cut_list_profile_20x20.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["profile", "length_mm", "quantity"])
            for length, qty in sorted(lengths.items(), reverse=True):
                writer.writerow(["Aluminium 20 x 20", length, qty])
            report["profile_total_length_mm"] = sum(k * v for k, v in lengths.items())
    (out / "dimensions.json").write_text(json.dumps(metrics_e1, indent=2) + "\n")
    report["cadquery_version"] = cq.__version__
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    return metrics_e1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, default=ROOT / "cad/parameters_ab.json")
    parser.add_argument("--output", type=Path, default=ROOT / "ab")
    parser.add_argument("--body", choices=["A", "B", "both"], default="both")
    args = parser.parse_args()
    p = json.loads(args.parameters.read_text())
    for body in (("A", "B") if args.body == "both" else (args.body,)):
        folder = args.output / ("a_drum" if body == "A" else "b_frame")
        print(f"Building option {body} (E1), checking 24 yaw and tilt poses…", flush=True)
        metrics = export_option(p, body, folder)
        print(json.dumps({k: metrics[k] for k in (
            "capacity_l_each_provisional", "servo_load_fraction_of_stall", "max_item_kg_at_half_stall",
            "camera_hidden_plate_edge_samples_of_72", "belt_center_distance_mm")}), flush=True)
    print("All poses passed without positive-volume overlaps.", flush=True)


if __name__ == "__main__":
    main()
