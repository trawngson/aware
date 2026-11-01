"""Buildable prototype B: aluminium frame, stainless shell and four square bins. Units mm.

The body carries one head: funnel, soft skirt, 320 mm aluminium tipping plate on a
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
# How each board in the console is held: number of points and the hardware at each point.
M3_INSERT = [("hex bolt", "M3 x 6", 1), ("heat-set insert", "M3", 1)]
BOARD_MOUNTS = {
    "esp32_s3_board": (2, [("self-tapping screw", "M2 x 6", 1)]),
    "servo_buck_xl4015": (4, M3_INSERT),
    "logic_buck_5v": (2, M3_INSERT),
    "relay_module": (4, M3_INSERT),
    "led_switch_xy_mos": (2, M3_INSERT),
    "terminal_4p": (2, [("self-tapping screw", "M3 x 10", 1)]),
    "divider_board": (2, M3_INSERT),
    "supply_capacitor": (1, [("cable tie", "100 x 2.5 mm", 1)]),
}
SKIN_SCREW = [("button bolt", "M4 x 20 stainless", 1), ("spacer sleeve", "M4, 6 mm", 1), ("large washer", "M4", 1),
              ("nut", "M4", 1)]
# Joints whose bolts are recorded one by one (start point, axis, length) by head() and body_b():
# how each is made and the hardware at every point. "*" takes the bolt size from the record.
FASTENER_JOINTS = {
    "yaw_servo_to_shelf": ("bolt", ["yaw_servo", "yaw_bracket"], [("hex bolt", "*", 1), ("nut", "M2", 1)]),
    "yaw_bracket_to_beam": ("bolt", ["yaw_bracket", "joint_beam", "beam_splice_plate"],
                            [("countersunk bolt", "*", 1), ("nut", "M5", 1), ("washer", "M5", 1)]),
    "yaw_bearing_lower_to_bracket": ("bolt", ["yaw_bearing_lower", "yaw_bracket"], [("hex bolt", "*", 1), ("nut", "M4", 1)]),
    "yaw_bearing_upper_to_bracket": ("bolt", ["yaw_bearing_upper", "yaw_bracket", "yaw_cable_channel"],
                                     [("hex bolt", "*", 1), ("nut", "M4", 1)]),
    "yaw_horn_to_hub": ("screw", ["yaw_servo_horn", "yaw_hub"], [("self-tapping screw", "*", 1)]),
    "yaw_flange_set_screw": ("set_screw", ["yaw_flange", "yaw_shaft"], [("set screw", "comes with the part", 1, False)]),
    "yaw_flange_to_platform": ("tapped", ["yaw_flange", "yaw_platform"], [("hex bolt", "*", 1)]),
    "tilt_servo_bracket_to_platform": ("tapped", ["tilt_servo_bracket", "yaw_platform"], [("countersunk bolt", "*", 1)]),
    "tilt_stop_pad_to_platform": ("tapped", ["tilt_stop_pad_*", "yaw_platform"], [("hex bolt", "*", 1)]),
    "hinge_post_to_platform": ("tapped", ["hinge_post_*", "yaw_platform"], [("hex bolt", "*", 1)]),
    "hinge_block_to_post": ("tapped", ["hinge_block_*", "hinge_post_*"], [("hex bolt", "*", 1)]),
    "tilt_servo_to_bracket": ("bolt", ["tilt_servo", "tilt_servo_bracket"], [("hex bolt", "*", 1), ("nut", "M3", 1)]),
    "tilt_horn_to_adapter": ("tapped", ["tilt_servo_horn", "tilt_pulley_adapter"], [("hex bolt", "*", 1)]),
    "plate_lug_set_screw": ("set_screw", ["plate_lug_*", "hinge_shaft"], [("set screw", "*", 1)]),
    "plate_to_lug": ("tapped", ["tipping_plate", "plate_lug_*"], [("countersunk bolt", "*", 1), ("heat-set insert", "M4", 1)]),
    "rail_to_post": ("bolt", ["rail_*", "post_*"], [("carriage bolt", "*", 1), ("nut", "M8", 1)]),
    "floor_board_to_rail": ("bolt", ["floor_plate", "rail_bottom_*"], [("hex bolt", "*", 1), ("large washer", "M8", 1), ("nut", "M8", 1)]),
    "seat_board_to_rail": ("bolt", ["head_seat_plate", "rail_seat_*"], [("hex bolt", "*", 1), ("large washer", "M8", 1), ("nut", "M8", 1)]),
    "slide_mount_to_post": ("bolt", ["slide_mount_*", "post_*"],
                            [("hex bolt", "*", 1), ("spacer sleeve", "M5, 18 mm", 1), ("nut", "M5", 1), ("washer", "M5", 2)]),
}


def cylinder(radius, length, origin, direction):
    return cq.Solid.makeCylinder(radius, length, cq.Vector(*origin), cq.Vector(*direction))


def cable(points, radius):
    """Round cable along a polyline: one cylinder per leg, a ball at each bend."""
    shape = None
    for i, (a, b) in enumerate(zip(points, points[1:])):
        d = [q - r for q, r in zip(b, a)]
        n = math.sqrt(sum(x * x for x in d))
        leg = cylinder(radius, n, a, d)
        if i:
            leg = leg.fuse(cq.Solid.makeSphere(radius, cq.Vector(*a), angleDegrees1=-90, angleDegrees2=90))
        shape = leg if shape is None else shape.fuse(leg)
    return shape.clean()


def path_length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def sector(r_out, r_in, a0, a1, z0, h):
    """Annular sector from angle a0 to a1 (degrees, counter-clockwise about Z), from z0 up h."""
    at = lambda r, a: (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
    mid = (a0 + a1) / 2
    return (cq.Workplane("XY").workplane(offset=z0).moveTo(*at(r_out, a0))
            .threePointArc(at(r_out, mid), at(r_out, a1)).lineTo(*at(r_in, a1))
            .threePointArc(at(r_in, mid), at(r_in, a0)).close().extrude(h).val())


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


def polar(r, degrees, z=0.0):
    a = math.radians(degrees)
    return (r * math.cos(a), r * math.sin(a), z)


def joinery_holes(p):
    """Hole centres (x, y) shared by the head parts and their flat patterns: the deck bolts into the
    seat board, the rivets of the ring clips, and the console bolts through the funnel collar."""
    j = p["joinery"]
    leg = j["clip_angle_mm"][0]
    shell_in = p["deck_outer_radius_mm"] - p["head_shell_wall_mm"]
    ring_in = p["locating_ring_outer_radius_mm"] - p["locating_ring_wall_mm"]
    xy = lambda r, angles: [polar(r, a)[:2] for a in angles]
    return {"deck_bolts": xy(j["deck_bolt_radius_mm"], j["deck_bolt_angles"]),
            "shell_clip_rivets": xy(shell_in - leg / 2 - 1, j["shell_clip_angles"]),
            "locating_clip_rivets": xy(ring_in - leg / 2 - 1, j["locating_clip_angles"]),
            "console_bolts": xy(j["console_bolt_radius_mm"], j["console_bolt_angles"])}


def angle_clip(theta, r_face, z_face, up, leg, t, width):
    """Small aluminium angle inside a ring: one leg against the ring's inner face, the other flat
    on the deck (up=1) or under the deck or collar (up=-1)."""
    r_face = math.sqrt(r_face ** 2 - (width / 2) ** 2) - .05    # the flat leg touches the curved face at its ends
    v = box(t, width, leg, (r_face - t / 2, 0, z_face + up * leg / 2))
    h = box(leg, width, t, (r_face - leg / 2, 0, z_face + up * t / 2))
    return v.fuse(h).rotate((0, 0, 0), (0, 0, 1), theta)


def seg_dist(pt, a, b):
    """Plan distance from a point to a cable segment."""
    (px, py), (ax, ay), (bx, by) = pt[:2], a[:2], b[:2]
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / ((dx * dx + dy * dy) or 1)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def head(p, add, joint=None):
    """Shared head module. Returns geometry facts used by the bodies and checks."""
    J = joint or (lambda *a, **k: None)
    j = p["joinery"]
    jh = joinery_holes(p)
    leg, clip_t, clip_w = j["clip_angle_mm"]
    rivet = [("blind rivet", "Ø4 x 8 aluminium", 1)]
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

    # Motor cables run from the rear console down the rear hanger: they pass the deck at
    # cab_hang_y and the funnel collar at cab_shell_y, in the gap between the cone and the shell.
    mc = p["motor_cable"]
    cab_r, cab_dx = mc["radius_mm"], mc["offset_x_mm"]
    cab_hang_y = p["hanger_radius_mm"] - p["hanger_size_mm"] / 2 - mc["hanger_gap_mm"]
    cab_shell_y = mc["shell_y_mm"]
    cone_r_at = lambda z: throat_r + fw + (z - lip_top) / slope
    assert cone_r_at(shell_top) + cab_r < cab_shell_y < deck_ro - p["head_shell_wall_mm"] - cab_r
    cab_holes = lambda y, z0, h: cylinder(cab_r + .75, h, (-cab_dx, y, z0), (0, 0, 1)).fuse(
        cylinder(cab_r + .75, h, (cab_dx, y, z0), (0, 0, 1)))

    # Deck ring: the one interface every body must carry at deck_z. Holes: hanger bolts, four bolts
    # into the seat board, the rivets of the ring clips and the tapped hole of the orientation pin.
    hs, hr, reach = p["hanger_size_mm"], p["hanger_radius_mm"], p["spider_reach_mm"]
    pin_r = p["orientation_pin_radius_mm"]
    deck = tube(deck_ro, deck_ri, deck_z, deck_t).cut(cab_holes(cab_hang_y, deck_z, deck_t))
    for (x, y), r in ([(xy, 3.25) for xy in jh["deck_bolts"]] + [(polar(hr, a)[:2], 3.25) for a in (0, 90, 180, 270)]
                      + [(xy, 2.05) for xy in jh["shell_clip_rivets"] + jh["locating_clip_rivets"]]
                      + [((0, pin_r), 2.5)]):
        deck = deck.cut(cylinder(r, deck_t, (x, y, deck_z), (0, 0, 1)))
    add("head_deck", deck, metal, "head", lift,
        "Head deck ring carrying all head loads; rests on the seat board, 4 bolts into inserts in that board",
        "laser", "Aluminium sheet 3 mm")
    J("deck_to_seat_board", "tapped", ["head_deck", "head_seat_plate"],
      [("button bolt", "M6 x 16", 1), ("washer", "M6", 1), ("insert nut", "M6, for 15 mm board", 1)],
      positions=[(*xy, deck_z + deck_t) for xy in jh["deck_bolts"]], proposed=True,
      note="Undo these four bolts to lift the head out")
    add("orientation_pin", cylinder(3, 25, (0, pin_r, deck_z - 25), (0, 0, 1)), metal, "head", lift,
        "Orientation pin: an M6 bolt screwed down into the tapped deck, its shank below the deck goes into "
        "the seat board's rear hole, so the head seats one way only", "buy", "Hex bolt M6 x 30, fully threaded")
    J("orientation_pin_in_deck", "tapped", ["orientation_pin", "head_deck"], [],
      positions=[(0, pin_r, deck_z + deck_t)], proposed=True, note="Deck hole tapped M6; the bolt itself is the pin")
    ring_ro, ring_w = p["locating_ring_outer_radius_mm"], p["locating_ring_wall_mm"]
    ring_in = ring_ro - ring_w
    add("head_locating_ring", tube(ring_ro, ring_in, deck_z - p["locating_ring_depth_mm"],
                                   p["locating_ring_depth_mm"]),
        charcoal, "head", lift, "Spigot under the deck that centres the head in the body",
        "laser", "PP sheet 3 mm, rolled and riveted")
    for i, a in enumerate(j["locating_clip_angles"], 1):
        add(f"locating_ring_clip_{i}", angle_clip(a, ring_in, deck_z, -1, leg, clip_t, clip_w), metal, "head", lift,
            "Angle clip holding the locating ring under the deck: one rivet into the ring, one into the deck",
            "cut", f"Aluminium angle {leg:.0f} x {leg:.0f} x {clip_t:.0f}, {clip_w:.0f} mm long")
    J("locating_ring_to_deck", "rivet", ["head_locating_ring", "locating_ring_clip_*", "head_deck"], rivet,
      positions=[polar(ring_in, a, deck_z - .6 * leg) for a in j["locating_clip_angles"]]
      + [(*xy, deck_z + deck_t) for xy in jh["locating_clip_rivets"]], status="positions", proposed=True,
      note="Deck holes are cut; drill the ring through the clip on assembly")
    J("locating_ring_seam", "rivet", ["head_locating_ring"], rivet, count=2, status="count",
      note="Overlap of the rolled strip")
    shell_w = p["head_shell_wall_mm"]
    shell_in = deck_ro - shell_w
    add("head_shell_ring", tube(deck_ro, shell_in, deck_z + deck_t, shell_top - deck_z - deck_t),
        light, "head", lift, "Raised wall between deck and funnel collar, held by 4 angle clips at each edge",
        "laser", "Aluminium composite 3 mm, rolled")
    for i, a in enumerate(j["shell_clip_angles"], 1):
        for tag, z_face, up in (("low", deck_z + deck_t, 1), ("high", shell_top, -1)):
            add(f"shell_ring_clip_{tag}_{i}", angle_clip(a, shell_in, z_face, up, leg, clip_t, clip_w), metal, "head",
                lift, f"Angle clip joining the shell ring to the {'deck' if tag == 'low' else 'funnel collar'}",
                "cut", f"Aluminium angle {leg:.0f} x {leg:.0f} x {clip_t:.0f}, {clip_w:.0f} mm long")
    J("shell_ring_to_deck", "rivet", ["head_shell_ring", "shell_ring_clip_low_*", "head_deck"], rivet,
      positions=[polar(shell_in, a, deck_z + deck_t + .6 * leg) for a in j["shell_clip_angles"]]
      + [(*xy, deck_z + deck_t) for xy in jh["shell_clip_rivets"]], status="positions", proposed=True,
      note="Deck holes are cut; drill the ring through the clip on assembly")
    J("shell_ring_to_collar", "rivet", ["head_shell_ring", "shell_ring_clip_high_*", "intake_funnel"], rivet,
      positions=[polar(shell_in, a, shell_top - .6 * leg) for a in j["shell_clip_angles"]]
      + [(*xy, top) for xy in jh["shell_clip_rivets"]], status="positions", proposed=True,
      note="Collar holes are cut; drill the ring through the clip on assembly")
    J("shell_ring_seam", "rivet", ["head_shell_ring"], rivet, count=3, status="count",
      note="20 mm overlap of the rolled strip")
    funnel = revolve([(mouth_r, top), (deck_ro, top), (deck_ro, shell_top),
                      (mouth_r + fw - collar_t / slope, shell_top),
                      (throat_r + fw, lip_top), (throat_r + fw, lip_bottom),
                      (throat_r, lip_bottom), (throat_r, lip_top)])
    funnel = funnel.cut(cab_holes(cab_shell_y, shell_top - 2, collar_t + 4))
    for (x, y), r in [(xy, 2.25) for xy in jh["console_bolts"]] + [(xy, 2.05) for xy in jh["shell_clip_rivets"]]:
        funnel = funnel.cut(cylinder(r, collar_t, (x, y, shell_top), (0, 0, 1)))
    add("intake_funnel", funnel, (.78, .81, .80), "head", lift,
        "Collar, cone and throat lip; cone, collar and lip band are cut flat and riveted",
        "laser", "PP sheet 2 mm")
    # Rivet counts of the rolled funnel at the set pitch: two cone seams, cone to lip band and
    # cone to collar round the circle, and the lip band seam.
    pitch = j["rivet_pitch_mm"]
    slant = math.hypot(mouth_r - throat_r, p["funnel_height_mm"])
    J("funnel_cone_seams", "rivet", ["intake_funnel"], rivet, count=2 * (math.ceil(slant / pitch) + 1), status="count",
      note=f"Two seams of the cone halves, 15 mm overlap, about {pitch:.0f} mm apart")
    J("funnel_cone_to_lip", "rivet", ["intake_funnel"], rivet, count=math.ceil(2 * math.pi * throat_r / pitch),
      status="count", note=f"Round the throat, about {pitch:.0f} mm apart")
    J("funnel_cone_to_collar", "rivet", ["intake_funnel"], rivet, count=math.ceil(2 * math.pi * mouth_r / pitch),
      status="count", note=f"Round the mouth, about {pitch:.0f} mm apart")
    J("funnel_lip_seam", "rivet", ["intake_funnel"], rivet, count=2, status="count")
    fringe = (cq.Workplane("XY").polarArray(skirt_r + 1, 0, 360, strips)
              .rect(2, p["skirt_strip_width_mm"]).extrude(lip_bottom - plate_z)
              .translate((0, 0, plate_z))).vals()
    add("flexible_throat_skirt", tube(skirt_r + 2, skirt_r, lip_bottom - 8, 8).fuse(*fringe),
        (.14, .15, .16), "head", lift, "Flexible strip fringe under the throat lip",
        "laser", "Soft PVC strip curtain 2 mm")
    J("skirt_to_lip", "rivet", ["flexible_throat_skirt", "intake_funnel"], rivet,
      count=math.ceil(2 * math.pi * skirt_r / pitch), status="count",
      note=f"Strip curtain riveted round the lip band, about {pitch:.0f} mm apart")

    # Hangers on the four axes run above the dividers, never over a bin opening. Each square tube
    # takes a threaded insert in both ends; one M6 bolt down through the deck and one up through
    # the beam hold it, so nothing is welded.
    assert math.hypot(hr + hs / 2, hs / 2) < ring_ro - ring_w
    ti = j["tube_insert_mm"]
    fl_i, dep = ti["flange"], ti["depth"]
    hang_len = deck_z - spider_top - 2 * fl_i
    hanger_tops, hanger_bottoms, insert_pts = [], [], []
    for i, a in enumerate((0, 90, 180, 270), 1):
        cx, cy, _ = polar(hr, a)
        zc = (deck_z + spider_top) / 2
        add(f"hanger_{i}", box(hs, hs, hang_len, (cx, cy, zc)).cut(box(hs - 4, hs - 4, hang_len, (cx, cy, zc))),
            metal, "head", lift, f"Square aluminium tube hanging the joint beam from the deck; cut {hang_len:.0f} mm, "
            "a threaded insert in each end", "cut", "Aluminium square tube 30 x 30 x 2")
        for end, z_fl, z_body in (("top", deck_z - fl_i, deck_z - fl_i - dep), ("bottom", spider_top, spider_top + fl_i)):
            plug = box(hs, hs, fl_i, (cx, cy, z_fl + fl_i / 2)).fuse(
                box(hs - 4.2, hs - 4.2, dep, (cx, cy, z_body + dep / 2))).cut(
                cylinder(2.5, fl_i + dep, (cx, cy, min(z_fl, z_body)), (0, 0, 1)))
            add(f"hanger_insert_{end}_{i}", plug, charcoal, "head", lift,
                "Threaded insert pressed into the tube end; its flange sits between the tube and the "
                + ("deck" if end == "top" else "beam"), "buy", f"Square tube insert 30 x 30 (2 mm wall), {ti['thread']} thread")
            insert_pts.append((cx, cy, z_fl + fl_i / 2))
        hanger_tops.append((cx, cy, deck_z + deck_t))
        hanger_bottoms.append((cx, cy, spider_bottom))
    J("hanger_inserts", "press", ["hanger_insert_*", "hanger_*"], [], positions=insert_pts, proposed=True,
      note="Tap the inserts into the tube ends with a mallet")
    J("hanger_to_deck", "tapped", ["head_deck", "hanger_insert_top_*", "hanger_*"], [("button bolt", "M6 x 16", 1)],
      positions=hanger_tops, proposed=True, note="Button heads: the rear one sits between the two motor cables")
    J("hanger_to_beam", "tapped", ["joint_beam", "hanger_insert_bottom_*", "hanger_*"], [("button bolt", "M6 x 45", 1)],
      positions=hanger_bottoms, proposed=True, note="Up through both walls of the beam into the insert")
    for x, y, _ in hanger_tops:
        assert all(seg_dist((x, y), (s * cab_dx, cab_shell_y), (s * cab_dx, cab_hang_y)) - 5.25 - cab_r >= .5
                   for s in (-1, 1)), "hanger bolt heads clear the motor cables on the deck"
    # Cross beam: one tube along X through the middle and two half tubes along Y butted against it,
    # all bolted to a splice plate underneath. Countersunk heads keep the plate the lowest steel.
    sw = p["spider_width_mm"]
    spider = box(reach * 2, sw, spider_top - spider_bottom, (0, 0, (spider_top + spider_bottom) / 2)).fuse(
        box(sw, reach * 2, spider_top - spider_bottom, (0, 0, (spider_top + spider_bottom) / 2)))
    # Fasteners are not modelled as solids; each joint records its bolt here for the BOM and the
    # assembly page (head end, direction into the parts, length).
    fasteners = []

    def fastener(joint, size, start, axis, length, head="hex"):
        fasteners.append({"joint": joint, "size": size, "head": head, "start_mm": [round(v, 2) for v in start],
                          "axis": list(axis), "length_mm": round(length, 1)})
    # The yaw bracket foot bolts through the beam and the splice plate with two M5 bolts.
    foot_holes = [(-30.0, -9.0), (-30.0, 9.0)]
    splice_xy = [tuple(xy) for xy in j["splice_bolts_xy_mm"]]
    for x, y in foot_holes + splice_xy:
        spider = spider.cut(cylinder(2.75, spider_top - spider_bottom, (x, y, spider_bottom), (0, 0, 1)))
    for x, y, _ in hanger_bottoms:
        spider = spider.cut(cylinder(3.25, spider_top - spider_bottom, (x, y, spider_bottom), (0, 0, 1)))
    add("joint_beam", spider, metal, "head", lift,
        f"Cross beam: one tube along X ({2 * reach:.0f} mm) and two half tubes along Y ({reach - sw / 2:.0f} mm) butted "
        "against it, bolted to the splice plate underneath; its arms lie above the bin dividers",
        "cut", "Aluminium rectangular tube 40 x 30 x 2")
    spw, spl, spt = j["splice_plate_mm"]
    splice = box(spw, spl, spt, (0, 0, spider_bottom - spt / 2))
    for x, y in foot_holes + splice_xy:
        splice = splice.cut(cylinder(2.75, spt, (x, y, spider_bottom - spt), (0, 0, 1)))
    add("beam_splice_plate", splice, metal, "head", lift,
        "Splice plate under the beam crossing: the Y half tubes and the X tube bolt to it", "laser",
        f"Aluminium sheet {spt:.0f} mm")
    J("beam_splice", "bolt", ["joint_beam", "beam_splice_plate"],
      [("countersunk bolt", "M5 x 40", 1), ("nut", "M5", 1), ("washer", "M5", 1)],
      positions=[(x, y, spider_bottom - spt) for x, y in splice_xy], proposed=True,
      note="Countersunk from below, nuts on the beam top")
    pad_w, pad_t = j["spider_pad_mm"]
    pad_r = j["spider_pad_radius_mm"]
    assert pad_r + pad_w / 2 + 5.25 <= hr and pad_t > 3.3 and pad_t >= spt, "pads stand lower than the bolt heads and the plate"
    for i, a in enumerate((0, 90, 180, 270), 1):
        add(f"spider_foot_{i}", box(pad_w, pad_w, pad_t, (*polar(pad_r, a)[:2], spider_bottom - pad_t / 2)),
            rubber, "head", lift, "Rubber foot under a beam arm: the head stands on the four feet when lifted out",
            "buy", f"Rubber pad {pad_w:.0f} x {pad_w:.0f} x {pad_t:.0f}, self-adhesive")
    J("beam_feet", "adhesive", ["spider_foot_*", "joint_beam"], [], count=4, note="Self-adhesive rubber")

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
    belt_c, block_x = p["tilt_belt_center_x_mm"], p["hinge_block_x_mm"]
    belt_x = belt_c - bw / 2                             # near face of the belt
    ring_x = lambda ro, ri, x0, length, z: cylinder(ro, length, (x0, 0, z), (1, 0, 0)).cut(
        cylinder(ri, length, (x0, 0, z), (1, 0, 0)))
    ring_z = lambda ro, ri, z0, h: tube(ro, ri, z0, h)
    servo_blue = (.12, .32, .58)
    sd, pb = p["servo_dims_mm"], p["pillow_blocks_mm"]

    # Fixed yaw support on the beam hub: back plate, two bearing arms and the yaw servo shelf.
    st = p["yaw_stack_mm"]
    shelf_z, arm_lo, arm_hi = st["servo_shelf_z_offset"], st["lower_arm_z_offset"], st["upper_arm_z_offset"]
    z_of = lambda off: spider_top + off
    kfl = pb["kfl08"]
    kfl_j, kfl_hole = kfl["bolt_spacing"] / 2, kfl["bolt_hole_d"] / 2
    bracket = box(5, 32, z_of(arm_hi) + 5 - spider_top, (-42.5, 0, (spider_top + z_of(arm_hi) + 5) / 2))
    for z0 in (z_of(arm_lo), z_of(arm_hi)):
        bracket = bracket.fuse(box(72, 32, 5, (-4, 0, z0 + 2.5)).cut(cylinder(5, 5, (0, 0, z0), (0, 0, 1))))
        for x in (-kfl_j, kfl_j):
            # Slotted 1 mm each way: KFL08 bolt spacing is 36-37 mm depending on the maker.
            bracket = bracket.cut(box(2 * kfl_hole + 2, 2 * kfl_hole, 5, (x, 0, z0 + 2.5)))
    # MG90S hangs through a cut-out in the shelf with its ears resting on top (TowerPro: ear underside
    # 18.5 mm above the base, spline 4.1 mm proud of the bed).
    mg90 = sd["mg90s"]
    y_len, y_wid, y_hgt = p["yaw_servo_body_mm"]
    shelf_top = z_of(shelf_z) + 4
    y_top = shelf_top + mg90["ear_below_bed"] + mg90["ear_thickness"]   # spline bed
    y_cx = y_len / 2 - 6                                  # output shaft 6 mm from the body end
    bracket = bracket.fuse(box(62, 32, 4, (-9, 0, z_of(shelf_z) + 2)).cut(
        box(y_len + .6, y_wid + .6, 4, (y_cx, 0, z_of(shelf_z) + 2))))
    yaw_ear_x = [y_cx - mg90["ear_hole_pitch"] / 2, y_cx + mg90["ear_hole_pitch"] / 2]
    for x in yaw_ear_x:
        bracket = bracket.cut(cylinder(1.1, 4, (x, 0, z_of(shelf_z)), (0, 0, 1)))
        fastener("yaw_servo_to_shelf", "M2 x 10", (x, 0, shelf_top + mg90["ear_thickness"]), (0, 0, -1),
                 mg90["ear_thickness"] + 4 + 2)
    # Foot on the beam hub, stopping short of the yaw servo cable that runs along the beam top.
    foot_l, foot_t = p["yaw_bracket_foot_mm"]
    bracket = bracket.fuse(box(foot_l, 32, foot_t, (-45 + foot_l / 2, 0, spider_top + foot_t / 2)))
    for x, y in foot_holes:
        bracket = bracket.cut(cylinder(2.75, foot_t, (x, y, spider_top), (0, 0, 1)))
        # Countersunk from under the splice plate (nothing may hang below the rubber feet), nut on the foot.
        fastener("yaw_bracket_to_beam", "M5 x 45", (x, y, spider_bottom - spt), (0, 0, 1),
                 spt + spider_top - spider_bottom + foot_t + 5, "countersunk")
    add("yaw_bracket", bracket, charcoal, "tilt_fixed", lift,
        "Fixed C-bracket on the beam hub: two arms for the yaw bearings, a shelf the MG90S hangs through and a "
        "foot bolted through the hub", "print", "PETG, 60 % infill (or bent aluminium 3 mm)")
    # KFL08 (catalogue: 48 x 27 rhombic flange, holes 37 apart for M4, round body about 27 mm,
    # 12.5 mm overall with the inner ring proud on top).
    kfl_t, kfl_body, kfl_h = kfl["flange_t"], kfl["body_height"], kfl["total_height"]
    for name, z0 in (("lower", z_of(arm_lo) + 5), ("upper", z_of(arm_hi) + 5)):
        lobe_r = (kfl["flange_length"] / 2 - kfl_j)
        brg = cylinder(kfl["body_d"] / 2, kfl_body, (0, 0, z0), (0, 0, 1)).fuse(
            box(2 * kfl_j, 2 * lobe_r + 2, kfl_t, (0, 0, z0 + kfl_t / 2)),
            cylinder(lobe_r, kfl_t, (-kfl_j, 0, z0), (0, 0, 1)), cylinder(lobe_r, kfl_t, (kfl_j, 0, z0), (0, 0, 1)),
            cylinder(7, kfl_h - kfl_body, (0, 0, z0 + kfl_body), (0, 0, 1))).cut(
            cylinder(bore, kfl_h, (0, 0, z0), (0, 0, 1)))
        for x in (-kfl_j, kfl_j):
            brg = brg.cut(cylinder(kfl_hole, kfl_t, (x, 0, z0), (0, 0, 1)))
            # Bolted from under the arm; the upper pair's nuts sink into the cable channel floor.
            fastener(f"yaw_bearing_{name}_to_bracket", "M4 x 16" if name == "lower" else "M4 x 16, nut sunk in channel",
                     (x, 0, z0 - 5), (0, 0, 1), 5 + kfl_t + (3.5 if name == "lower" else 5))
        add(f"yaw_bearing_{name}", brg, (.55, .58, .60), "tilt_fixed", lift,
            "Flanged bearing for the vertical yaw shaft, 2 M4 bolts through the bracket arm", "buy",
            "Flanged pillow block KFL08, bore 8 mm")
    yaw_servo = box(y_len, y_wid, y_hgt, (y_cx, 0, y_top - y_hgt / 2)).fuse(
        box(mg90["ear_length"], y_wid, mg90["ear_thickness"], (y_cx, 0, shelf_top + mg90["ear_thickness"] / 2)),
        cylinder(mg90["spline_d"] / 2, mg90["spline_above_bed"], (0, 0, y_top), (0, 0, 1)))
    for x in yaw_ear_x:
        yaw_servo = yaw_servo.cut(cylinder(1.1, mg90["ear_thickness"], (x, 0, shelf_top), (0, 0, 1)))
    add("yaw_servo", yaw_servo, servo_blue, "tilt_fixed", lift,
        "MG90S turning the tilt stage plus or minus 45 degrees toward the bin", "buy", "MG90S, metal gears")

    # Yaw stage: horn hub, vertical shaft, collar, platform, hinge posts and blocks, tilt servo.
    plat_bot = pivot - p["yaw_platform_below_pivot_mm"]
    plat_top = plat_bot + 5
    upper_top = z_of(arm_hi) + 5 + kfl_h                   # top of the upper KFL08 inner ring
    assert upper_top + 8 <= plat_bot, "collar fits between the upper bearing and the platform"
    # The MG90S ships with arm horns only, no round disc: the cross horn sits in the printed hub's
    # underside and two of its arm holes take screws into the hub. Horn sizes are provisional.
    hb = p["yaw_hub_mm"]
    horn_z = y_top                                       # horn boss rests on the spline bed
    boss_h, arm_t = 4.5, 1.8
    hub_z, hub_r, depth = horn_z + boss_h, hb["diameter"] / 2, hb["shaft_depth"]
    hub_top = hub_z + hb["height"]
    assert hub_top + 1 <= z_of(arm_lo), "hub clears the lower bearing arm"
    cross = cylinder(3.6, boss_h, (0, 0, horn_z), (0, 0, 1)).fuse(
        box(20, 5, arm_t, (0, 0, hub_z - arm_t / 2)), box(5, 20, arm_t, (0, 0, hub_z - arm_t / 2))).cut(
        cylinder(mg90["spline_d"] / 2 + .05, mg90["spline_above_bed"], (0, 0, horn_z), (0, 0, 1)))
    for y in (-hb["horn_screw_radius"], hb["horn_screw_radius"]):
        cross = cross.cut(cylinder(1, arm_t, (0, y, hub_z - arm_t), (0, 0, 1)))
    add("yaw_servo_horn", cross, pp, "yaw", lift,
        "Cross horn that ships with the MG90S, screwed into the hub (sizes provisional, measure the horn)",
        "buy", "Comes with the servo")
    screw_z = hub_top - depth / 2
    hub = cylinder(hub_r, hb["height"], (0, 0, hub_z), (0, 0, 1)).cut(
        cylinder(bore, depth, (0, 0, hub_top - depth), (0, 0, 1))).cut(
        cylinder(2.5, 2, (0, 0, hub_z), (0, 0, 1))).cut(                     # relief for the horn's centre screw head
        cylinder(1.6, hub_r, (0, 0, screw_z), (1, 0, 0))).cut(               # M3 set screw onto the shaft flat
        box(2.6, 5.8, hub_top - screw_z + 3, (7, 0, (hub_top + screw_z - 3) / 2)))  # M3 nut drops in from the top
    for y in (-hb["horn_screw_radius"], hb["horn_screw_radius"]):
        hub = hub.cut(cylinder(.9, 4, (0, y, hub_z), (0, 0, 1)))           # pilot holes for the horn screws
        fastener("yaw_horn_to_hub", "M2 x 6 self-tapping", (0, y, hub_z - arm_t), (0, 0, 1), arm_t + 4)
    add("yaw_hub", hub, light, "yaw", lift,
        "Hub from the yaw servo horn to the 8 mm shaft: horn screws below, M3 set screw and nut on the shaft "
        "flat", "print", "PETG, 100 % infill")
    # The shaft runs up through the platform into a flange coupling bolted on top of it, so the
    # platform is held by the shaft and turns with it. Common 8 mm rigid flange: 32 x 3 flange,
    # 16 mm hub, 13 mm overall, 4 M4 holes on a 24 mm circle, 2 M4 set screws.
    yf = p["yaw_flange_mm"]
    (fl_d, fl_t), (fh_d, fh_h) = yf["flange"], yf["hub"]
    shaft_top = plat_top + fl_t + fh_h - 1
    add("yaw_shaft", cylinder(4, shaft_top - (hub_top - depth), (0, 0, hub_top - depth), (0, 0, 1)), metal, "yaw",
        lift, f"Vertical yaw shaft in the two flanged bearings, through the platform into the flange coupling; "
        f"cut {shaft_top - (hub_top - depth):.0f} mm, flats for the hub and coupling set screws",
        "cut", "Stainless 304 rod 8 mm")
    add("yaw_collar", ring_z(8, bore, upper_top, 8), metal, "yaw", lift,
        "Shaft collar resting on the upper bearing inner ring: carries the stage weight", "buy", "Shaft collar 8 mm")
    flange = cylinder(fl_d / 2, fl_t, (0, 0, plat_top), (0, 0, 1)).fuse(
        cylinder(fh_d / 2, fh_h, (0, 0, plat_top + fl_t), (0, 0, 1))).cut(
        cylinder(bore, fl_t + fh_h, (0, 0, plat_top), (0, 0, 1)))
    for a in (0, 180):
        flange = flange.cut(cylinder(2, fh_d / 2, (0, 0, plat_top + fl_t + fh_h / 2),
                                     (math.cos(math.radians(a)), math.sin(math.radians(a)), 0)))
        fastener("yaw_flange_set_screw", "M4 set screw",
                 (fh_d / 2 * math.cos(math.radians(a)), 0, plat_top + fl_t + fh_h / 2),
                 (-math.cos(math.radians(a)), 0, 0), fh_d / 2 - 4, "set screw")
    flange_screws = [(yf["screw_radius"] * math.cos(math.radians(a)), yf["screw_radius"] * math.sin(math.radians(a)))
                     for a in (45, 135, 225, 315)]
    for x, y in flange_screws:
        flange = flange.cut(cylinder(2, fl_t, (x, y, plat_top), (0, 0, 1)))
        # Tapped M4 into the platform: a nut under it would hit the shaft collar.
        fastener("yaw_flange_to_platform", "M4 x 8", (x, y, plat_top + fl_t), (0, 0, -1), fl_t + 5)
    add("yaw_flange", flange, metal, "yaw", lift,
        "Flange coupling on top of the platform: 2 set screws on the shaft flat, 4 M4 screws into the platform",
        "buy", "Rigid flange coupling 8 mm (32 x 13)")
    half_y = p["yaw_platform_half_y_mm"]
    # The ribbon leaves the rolling-loop channel next to the drum and climbs through the platform.
    drum_ri, drum_ro = mc["drum_radius_mm"]
    rib_t = mc["ribbon_thickness_mm"]
    exit_r = drum_ro + .25 + rib_t / 2
    exit_a = math.radians(mc["exit_angle_degrees"])
    exit_xy = (exit_r * math.cos(exit_a), exit_r * math.sin(exit_a))
    # Real pulleys (seller CAD): 20T is 16 long (flange, teeth, Ø16 hub); 40T is 17 long with two
    # flanges and a Ø16 hub on one side. The 20T hub faces the servo so its set screws grip the
    # adapter boss; the 40T hub faces inward so the outer flange stays clear of the KP08.
    pm = p["pulley_mm"]
    ps, pl = pm["small"], pm["large"]
    ps_face = belt_c + ps["belt_from_flange_face"]      # outer flange face of the 20T
    ps_hub_end = ps_face - ps["length"]
    pl_face = belt_c + pl["belt_from_flange_face"]
    assert pl_face + 1.5 <= block_x - 6.5, "40T outer flange clears the KP08"
    # MG996R (TowerPro: 37 mm to the spline bed, spline 5.7 proud, ear underside 10.2 below the bed).
    m996 = sd["mg996r"]
    ad = p["tilt_pulley_adapter_mm"]
    (hh_d, hh_t), (horn_d, horn_t) = ad["horn_hub"], ad["horn_disc"]
    face = ps_hub_end - .5 - ad["disc_length"] - (.2 + hh_t + horn_t)   # spline bed
    body_y0 = -from_top
    body_cy = body_y0 + s_len / 2
    ear_lo = face - m996["ear_below_bed"] - m996["ear_thickness"]        # ear face toward the base
    bracket_x = ear_lo - 2.5                                             # 5 mm bracket plate under the ears
    bracket_y = [body_cy + s for s in (-25, 25)]
    post_t, post_w = p["hinge_post_mm"]
    kp = pb["kp08"]
    kp_j, kp_hole = kp["bolt_spacing"] / 2, kp["bolt_hole_d"] / 2
    post_y = post_w / 2 - 12
    pad_y = p["tilt_stop_pad_y_mm"]
    # Holes in the platform: shaft, coupling screws, posts, servo bracket and stop pads. Everything
    # bolted from below at r < 62 uses countersunk screws, so nothing hits the yaw stop lugs.
    platform = box(2 * (block_x + 15), 2 * half_y, 5, (0, 0, plat_bot + 2.5)).cut(
        cylinder(cab_r + .75, 5, (*exit_xy, plat_bot), (0, 0, 1))).cut(cylinder(bore, 5, (0, 0, plat_bot), (0, 0, 1)))
    for x, y, r in ([(x, y, 1.65) for x, y in flange_screws] + [(x, y, 2.25) for x in (-block_x, block_x)
                    for y in (-post_y, post_y)] + [(bracket_x, y, 2.2) for y in bracket_y]
                    + [(0, y, 1.7) for y in (-pad_y, pad_y)]
                    + [(-p["yaw_hard_stop"]["pin_radius_mm"], 0, 1.65)]):     # tapped M4 for the stop pin
        platform = platform.cut(cylinder(r, 5, (x, y, plat_bot), (0, 0, 1)))
    add("yaw_platform", platform, charcoal, "yaw", lift,
        "Turning platform carrying the hinge posts, the tilt servo and the stop pads; holes for the shaft, "
        "coupling (M4 tapped), posts, servo bracket and stop pads", "laser", "Aluminium sheet 4 mm")
    for y in bracket_y:
        fastener("tilt_servo_bracket_to_platform", "M4 x 12", (bracket_x, y, plat_bot), (0, 0, 1), 12, "countersunk")
    for y in (-pad_y, pad_y):
        fastener("tilt_stop_pad_to_platform", "M3 x 12", (0, y, plat_bot), (0, 0, 1), 12)
    block_base = pivot - 15
    proud = kp["inner_ring_proud"]
    for i, x in enumerate((-block_x, block_x), 1):
        # KP08 (catalogue: 55 x 13 base, holes 42 apart, round holes for M4, centre 15 above the base).
        # The 60 x 10 post is tapped M4 at both ends: two bolts from the platform, two from the block.
        post = box(post_t, post_w, block_base - plat_top, (x, 0, (block_base + plat_top) / 2))
        for y in (-post_y, post_y):
            post = post.cut(cylinder(1.65, 12, (x, y, plat_top), (0, 0, 1)))
            fastener("hinge_post_to_platform", "M4 x 16", (x, y, plat_bot), (0, 0, 1), 5 + 11)
        for y in (-kp_j, kp_j):
            post = post.cut(cylinder(1.65, 12, (x, y, block_base - 12), (0, 0, 1)))
        add(f"hinge_post_{i}", post, metal, "yaw", lift,
            f"Post from the platform to a hinge pillow block, tapped M4 at both ends; cut "
            f"{block_base - plat_top:.0f} mm", "cut", f"Aluminium flat bar {post_w:.0f} x {post_t:.0f}")
        out = 1 if x > 0 else -1                          # the inner ring stands proud on the outer side
        blk = box(13, 55, 5, (x, 0, block_base + 2.5)).fuse(ring_x(14, bore, x - 6.5, 13, pivot)).fuse(
            ring_x(7, bore, x + out * 6.5 - (proud if out < 0 else 0), proud, pivot)).cut(
            cylinder(bore, 13, (x - 6.5, 0, pivot), (1, 0, 0)))
        for y in (-kp_j, kp_j):
            blk = blk.cut(cylinder(kp_hole, 5, (x, y, block_base), (0, 0, 1)))
            fastener("hinge_block_to_post", "M4 x 16", (x, y, block_base + 5), (0, 0, -1), 5 + 11)
        add(f"hinge_block_{i}", blk, (.55, .58, .60), "yaw", lift,
            "Horizontal pillow block carrying the hinge shaft; takes the plate load off the servo", "buy",
            "Pillow block KP08, bore 8 mm")
    tilt_servo = box(s_hgt, s_len, s_wid, (face - s_hgt / 2, body_cy, shaft_z)).fuse(
        box(m996["ear_thickness"], m996["ear_length"], s_wid, (ear_lo + m996["ear_thickness"] / 2, body_cy, shaft_z)),
        cylinder(m996["spline_d"] / 2, m996["spline_above_bed"], (face, 0, shaft_z), (1, 0, 0)))
    ehy, ehz = m996["ear_holes"][0] / 2, m996["ear_holes"][1] / 2
    ear_holes = [(y, z) for y in (body_cy - ehy, body_cy + ehy) for z in (shaft_z - ehz, shaft_z + ehz)]
    for y, z in ear_holes:
        tilt_servo = tilt_servo.cut(cylinder(2.1, m996["ear_thickness"], (ear_lo, y, z), (1, 0, 0)))
    add("tilt_servo", tilt_servo, servo_blue, "yaw", lift,
        "MG996R driving the hinge through the 2:1 belt; cable leaves the end near the output shaft", "buy",
        "MG996R, metal gears")
    srv_bracket = box(5, 68, shaft_z + s_wid / 2 + 6 - plat_top,
                      (bracket_x, body_cy, (shaft_z + s_wid / 2 + 6 + plat_top) / 2)).cut(
        box(5, s_len + .6, s_wid + .6, (bracket_x, body_cy, shaft_z)))
    for y in bracket_y:
        srv_bracket = srv_bracket.cut(cylinder(1.7, 10, (bracket_x, y, plat_top), (0, 0, 1)))
    for y, z in ear_holes:
        # Slotted 2 mm vertically: the pulley centre distance is vertical, so this sets belt tension.
        srv_bracket = srv_bracket.cut(box(5, 3.4, 3.4 + 2, (bracket_x, y, z)))
        fastener("tilt_servo_to_bracket", "M3 x 12", (ear_lo + m996["ear_thickness"], y, z), (-1, 0, 0),
                 m996["ear_thickness"] + 5 + 3)
    add("tilt_servo_bracket", srv_bracket, charcoal, "yaw", lift,
        "Bracket the MG996R ears bolt to; vertical slots set the belt tension; 2 M4 countersunk screws from "
        "under the platform", "print", "PETG, 60 % infill")
    # Aluminium 25T disc horn (Ø20, 4 tapped M3 holes at r7, hub on the servo side), then a printed
    # adapter whose boss carries the 20T pulley through its full 16 mm bore.
    hx = face + .2
    horn = cylinder(hh_d / 2, hh_t, (hx, 0, shaft_z), (1, 0, 0)).fuse(
        cylinder(horn_d / 2, horn_t, (hx + hh_t, 0, shaft_z), (1, 0, 0))).cut(
        cylinder(m996["spline_d"] / 2 + .05, hh_t + horn_t, (hx, 0, shaft_z), (1, 0, 0)))
    horn_holes = [(0, ad["horn_hole_radius"]), (0, -ad["horn_hole_radius"]),
                  (ad["horn_hole_radius"], 0), (-ad["horn_hole_radius"], 0)]
    for y, dz in horn_holes:
        horn = horn.cut(cylinder(1.25, horn_t, (hx + hh_t, y, shaft_z + dz), (1, 0, 0)))
    add("tilt_servo_horn", horn, metal, "yaw", lift,
        "Aluminium 25T disc horn on the MG996R, 4 tapped M3 holes", "buy", "Aluminium disc horn 25T, Ø20")
    a0 = hx + hh_t + horn_t
    a1 = a0 + ad["disc_length"]
    adapter = cylinder(horn_d / 2, ad["disc_length"], (a0, 0, shaft_z), (1, 0, 0)).cut(
        cylinder(3.5, 2.5, (a0, 0, shaft_z), (1, 0, 0))).fuse(                # relief for the horn screw head
        cylinder(ad["boss_d"] / 2, ps_face - a1, (a1, 0, shaft_z), (1, 0, 0)))
    for y, dz in horn_holes:
        adapter = adapter.cut(cylinder(1.7, ad["disc_length"], (a0, y, shaft_z + dz), (1, 0, 0))).cut(
            cylinder(3, 3, (a1 - 3, y, shaft_z + dz), (1, 0, 0)))             # counterbore: heads clear the pulley hub
        fastener("tilt_horn_to_adapter", "M3 x 6", (a1 - 3, y, shaft_z + dz), (-1, 0, 0), ad["disc_length"] - 3 + horn_t)
    add("tilt_pulley_adapter", adapter, light, "yaw", lift,
        "Adapter from the MG996R horn to the 20T pulley: 4 M3 screws into the horn, the pulley's set screws on a "
        "boss flat 4 mm from its hub end", "print", "PETG, 100 % infill")
    small = cylinder(ps["hub_d"] / 2, ps["length"] - ps["flange_t"] - ps["tooth_w"], (ps_hub_end, 0, shaft_z), (1, 0, 0)).fuse(
        cylinder(ps["tooth_od"] / 2, ps["tooth_w"], (ps_face - ps["flange_t"] - ps["tooth_w"], 0, shaft_z), (1, 0, 0)),
        cylinder(ps["flange_d"] / 2, ps["flange_t"], (ps_face - ps["flange_t"], 0, shaft_z), (1, 0, 0))).cut(
        cylinder(ps["bore"] / 2 + .05, ps["length"], (ps_hub_end, 0, shaft_z), (1, 0, 0)))
    add("tilt_pulley_small", small, metal, "yaw", lift,
        "GT2 20-tooth pulley, 16 mm long, hub toward the servo, on the printed adapter boss", "buy",
        "GT2 20T, 6 mm belt, 6 mm bore")
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
        pad = box(24, 2 * pad_hw, pad_top - plat_top, (0, y, (pad_top + plat_top) / 2)).cut(
            cylinder(1.25, 10, (0, y, plat_top), (0, 0, 1)))
        add(f"tilt_stop_pad_{i}", pad,
            rubber, "yaw", lift, f"Stop pad: the plate lands on it at {p['tilt_stop_degrees']:.0f} degrees",
            "print", "PETG block with a rubber bumper on top")
    J("tilt_stop_bumpers", "adhesive", ["tilt_stop_pad_*"], [("rubber bumper", "Ø10 x 3, self-adhesive", 1)], count=2)

    # Tilt stage: hinge shaft, collars, lugs under the plate, large pulley, plate and IMU.
    shaft_len = 2 * (block_x + 6.5 + proud + 8 + 1)
    add("hinge_shaft", cylinder(4, shaft_len, (-shaft_len / 2, 0, pivot), (1, 0, 0)), metal, "tilt_plate", lift,
        "Hinge shaft 22 mm under the plate surface, turning in the two pillow blocks", "cut",
        "Stainless 304 rod 8 mm")
    for i, x in enumerate((-block_x - 6.5 - proud - 8, block_x + 6.5 + proud), 1):
        add(f"hinge_collar_{i}", ring_x(8, bore, x, 8, pivot), metal, "tilt_plate", lift,
            "Shaft collar holding the hinge shaft in place", "buy", "Shaft collar 8 mm")
    lug_x = p["plate_lug_x_mm"]
    holes = [(x, y) for x in (-lug_x, lug_x) for y in (-12, 12)]
    for i, x in enumerate((-lug_x, lug_x), 1):
        lug = box(6, 24, plate_z - 4 - (pivot - 10), (x, 0, (plate_z - 4 + pivot - 10) / 2)).fuse(
            box(20, 40, 4, (x, 0, plate_z - 2))).cut(cylinder(bore, 6, (x - 3, 0, pivot), (1, 0, 0)))
        for hx, hy in holes:
            lug = lug.cut(cylinder(2.2, 4, (hx, hy, plate_z - 4), (0, 0, 1)))
        # The lug drives the plate, so it grips the shaft: M3 set screw from below onto a flat.
        lug = lug.cut(cylinder(1.25, 6, (x, 0, pivot - 10), (0, 0, 1)))
        fastener("plate_lug_set_screw", "M3 x 6 set screw", (x, 0, pivot - 10), (0, 0, 1), 6, "set screw")
        add(f"plate_lug_{i}", lug, charcoal, "tilt_plate", lift,
            "Lug under the plate, clamped to the hinge shaft by an M3 set screw on a flat", "print",
            "PETG, 60 % infill; M4 heat-set inserts for the plate screws")
    for hx, hy in holes:
        fastener("plate_to_lug", "M4 x 6", (hx, hy, plate_z + plate_t), (0, 0, -1), plate_t + 4, "countersunk")
    lt0 = pl_face - pl["flange_t"] - pl["tooth_w"]
    large = cylinder(pl["flange_d"] / 2, pl["flange_t"], (pl_face - pl["flange_t"], 0, pivot), (1, 0, 0)).fuse(
        cylinder(pl["tooth_od"] / 2, pl["tooth_w"], (lt0, 0, pivot), (1, 0, 0)),
        cylinder(pl["flange_d"] / 2, pl["flange_t"], (lt0 - pl["flange_t"], 0, pivot), (1, 0, 0)),
        cylinder(pl["hub_d"] / 2, (lt0 - pl["flange_t"]) - (pl_face - pl["length"]),
                 (pl_face - pl["length"], 0, pivot), (1, 0, 0))).cut(
        cylinder(bore, pl["length"], (pl_face - pl["length"], 0, pivot), (1, 0, 0)))
    add("tilt_pulley_large", large, metal, "tilt_plate", lift,
        "GT2 40-tooth pulley, 17 mm long with two flanges, hub toward the plate centre, clamped to the hinge shaft",
        "buy", "GT2 40T, 6 mm belt, 8 mm bore (check: some are 5 mm)")
    plate = (cq.Workplane("XY").circle(plate_r).extrude(plate_t).edges().fillet(min(1, plate_t / 3))
             .translate((0, 0, plate_z))).val()
    for x, y in holes:
        plate = plate.cut(cylinder(2.2, plate_t, (x, y, plate_z), (0, 0, 1)))
    add("tipping_plate", plate, pp, "tilt_plate", lift,
        "320 mm tipping plate bolted to the two lugs; does not melt under a hot ember", "laser",
        "Aluminium sheet 1.5 mm, matt grey powder coat")
    J("imu_under_plate", "adhesive", ["tilt_imu", "tipping_plate"], [("VHB tape", "20 x 15 mm piece", 1)], count=1,
      proposed=True, note="No holes in the plate surface")
    add("tilt_imu", box(21, 16, 3, (0, 30, plate_z - 1.5)), (.10, .35, .20), "tilt_plate", lift,
        "IMU under the plate: true tilt angle for jam detection and homing after a power cut",
        "buy", "MPU-6050 (GY-521)")

    # Motor cables. Both share the route console -> rear hanger -> beam top. The MG90S cable ends
    # there; the MG996R cable rises beside the bracket, makes a quarter loop round the yaw axis
    # close to it (little length change over the 90 degree yaw travel) and climbs onto the platform.
    on_beam, top_z = spider_top + cab_r + .25, deck_z + deck_t + cab_r + 2
    common = lambda x: [(x, cab_shell_y, top), (x, cab_shell_y, top_z), (x, cab_hang_y, top_z),
                        (x, cab_hang_y, on_beam)]
    yaw_cable = common(-cab_dx) + [(-cab_dx, 0, on_beam), (-cab_dx, 0, y_top - y_hgt + 4.5)]
    add("motor_cable_yaw_servo", cable(yaw_cable, cab_r), (.93, .55, .15), "tilt_fixed", lift,
        "MG90S cable: console, rear hanger, beam top to the yaw servo; no moving joint", "buy",
        "Servo extension 3 x 22 AWG, about 1 m")
    # Rolling loop under the platform. The ribbon enters through the fixed outer wall, runs along
    # it, folds back in a U and runs along the drum that turns with the platform. Turning the
    # platform only rolls the U along the channel, so the ribbon always bends at the same radius.
    wall_ri, wall_ro = mc["channel_wall_radius_mm"]
    rib_w = mc["ribbon_width_mm"]
    floor_z = z_of(arm_hi) + 5 + kfl_t                   # on the upper KFL08 flange lobes
    floor_t = 6                                          # thick enough to sink the KFL08 nuts
    rib_z = floor_z + floor_t + .5
    assert rib_z + rib_w < plat_bot - .5, "ribbon fits under the platform"
    assert drum_ri > 11 + 1, "drum clears the upper bearing hub"
    ent_a, fold_a = mc["entry_angle_degrees"], mc["fold_angle_degrees"]
    hs_ = p["yaw_hard_stop"]
    lug_a = (hs_["lug_width_mm"] / 2 + hs_["pin_r_mm"]) / hs_["pin_radius_mm"]
    lug_angles = [180 + s * (hs_["travel_degrees"] + math.degrees(lug_a)) for s in (-1, 1)]
    assert kfl["body_d"] / 2 + .5 <= 14 and floor_z + floor_t >= z_of(arm_hi) + 5 + kfl_body, \
        "the channel floor clears the KFL08 body"
    channel = tube(wall_ro, 14, floor_z, floor_t).fuse(tube(wall_ro, wall_ri, floor_z, plat_bot - .5 - floor_z))
    for x in (-kfl_j, kfl_j):
        # The upper KFL08 bolts clamp the channel too; their nuts sink 4 mm into the floor.
        channel = channel.cut(cylinder(kfl_hole, floor_t, (x, 0, floor_z), (0, 0, 1))).cut(
            cylinder(4.3, 4, (x, 0, floor_z + floor_t - 4), (0, 0, 1)))
    for a in lug_angles:
        lug_len = hs_["lug_outer_radius_mm"] - wall_ri
        channel = channel.fuse(box(lug_len, hs_["lug_width_mm"], 12, (wall_ri + lug_len / 2, 0, floor_z + floor_t + 6))
                               .rotate((0, 0, 0), (0, 0, 1), a))
    slot = box(10, 7, rib_w + .6, (wall_ri + 1.5, 0, rib_z + rib_w / 2)).rotate((0, 0, 0), (0, 0, 1), ent_a)
    channel = channel.cut(slot)
    add("yaw_cable_channel", channel, charcoal, "tilt_fixed", lift,
        f"Fixed rolling-loop channel on the upper bearing, with the two yaw stop lugs at +/-{hs_['travel_degrees']:.0f} degrees",
        "print", "PETG, 100 % infill at the stop lugs; rubber pads on the lug faces")
    add("yaw_cable_drum", tube(drum_ro, drum_ri, rib_z, plat_bot - rib_z), charcoal, "yaw", lift,
        "Drum under the platform, turning with it: the inner face of the rolling loop", "print", "PETG")
    pr, pin_r = hs_["pin_radius_mm"], hs_["pin_r_mm"]
    add("yaw_stop_pin", cylinder(pin_r, plat_bot - (floor_z + floor_t + 2), (-pr, 0, floor_z + floor_t + 2), (0, 0, 1)),
        metal, "yaw", lift,
        "Stop pin under the platform: hits a lug at the yaw limit even if the hub slips", "buy",
        "M4 steel bolt with an 8 mm sleeve")
    J("yaw_stop_pin_in_platform", "tapped", ["yaw_stop_pin", "yaw_platform"], [], positions=[(-pr, 0, plat_bot)],
      note="The bolt is the pin; the platform hole is tapped M4")
    J("cable_channel_on_bearing", "bolt", ["yaw_cable_channel", "yaw_bearing_upper"], [], count=2,
      note="Clamped by the two upper KFL08 bolts, counted under yaw_bearing_upper_to_bracket")
    J("drum_to_platform", "screw", ["yaw_cable_drum", "yaw_platform"], [("self-tapping screw", "M2 x 10", 1)], count=3,
      status="count", proposed=True, note="Down through the platform into the drum wall; holes not cut yet")

    # Ribbon in the channel, drawn at mid travel: outer run, U fold, drum run.
    r_o, r_i = wall_ri - .25 - rib_t / 2, exit_r
    fold_c, fold_rad = (r_o + r_i) / 2, (r_o - r_i) / 2
    outer_run = sector(r_o + rib_t / 2, r_o - rib_t / 2, fold_a, ent_a, rib_z, rib_w)
    inner_run = sector(r_i + rib_t / 2, r_i - rib_t / 2, fold_a, mc["exit_angle_degrees"], rib_z, rib_w)
    fa = math.radians(fold_a)
    centre = (fold_c * math.cos(fa), fold_c * math.sin(fa))
    tangent = math.degrees(math.atan2(-math.cos(fa), math.sin(fa)))     # pointing past the fold
    fold = tube(fold_rad + rib_t / 2, fold_rad - rib_t / 2, rib_z, rib_w).translate((*centre, 0)).intersect(
        box(40, 60, rib_w + 2, (20, 0, rib_z + rib_w / 2)).rotate((0, 0, 0), (0, 0, 1), tangent).translate((*centre, 0)))
    loop = outer_run.fuse(inner_run).fuse(fold).clean()
    add("yaw_ribbon_loop", loop, (.85, .18, .18), "yaw", lift,
        f"{mc['ribbon_cores']}-core ribbon in the rolling loop (drawn at mid travel): 6 V x2, GND x2, PWM, GND, SDA, GND, SCL, 3.3 V",
        "buy", f"Flat ribbon cable {mc['ribbon_cores']} cores, 1.27 mm pitch, high-flex")
    loop_len = (r_o * math.radians(ent_a - fold_a) + math.pi * fold_rad
                + r_i * math.radians(mc["exit_angle_degrees"] - fold_a))

    # Fixed run of the MG996R cable: beam top, a riser outside the channel, in through the wall slot.
    rr, ea = mc["riser_radius_mm"], math.radians(ent_a)
    riser_xy = (rr * math.cos(ea), rr * math.sin(ea))
    entry_z = rib_z + rib_w / 2
    tilt_fixed_path = common(cab_dx) + [(cab_dx, 60, on_beam), (*riser_xy, on_beam), (*riser_xy, entry_z),
                                        ((wall_ro + 1) * math.cos(ea), (wall_ro + 1) * math.sin(ea), entry_z)]
    add("motor_cable_tilt_servo", cable(tilt_fixed_path, cab_r), (.85, .18, .18), "tilt_fixed", lift,
        "MG996R and IMU cable, fixed part: console to the rolling-loop channel; becomes the ribbon at the wall",
        "buy", "Ribbon cable, same as the loop")
    # From the drum up through the platform, then up the servo's rear end face to its lead.
    # The MG996R lead leaves the end face nearest the output shaft, close to the base: rise above the
    # flange coupling, cross to that end face and climb to the lead.
    lead_x, lead_y = face - s_hgt + m996["cable_from_base"], body_y0 - cab_r - .5
    run_z = plat_top + fl_t + fh_h + cab_r + .5
    assert run_z + cab_r < shaft_z - s_wid / 2, "cable run passes under the MG996R"
    stage_path = [(*exit_xy, max(rib_z + rib_w + 1, plat_bot + .5)), (*exit_xy, run_z), (lead_x, lead_y, run_z), (lead_x, lead_y, shaft_z)]
    add("motor_cable_tilt_servo_stage", cable(stage_path, cab_r), (.85, .18, .18), "yaw", lift,
        "Cable on the turning platform: up through the platform, on the -x side of the servo, clear of the belt",
        "buy", "Same ribbon, split to the servo plug and the IMU lead")
    add("cable_clip_stage", box(6, 8, 4, (exit_xy[0] + cab_r + 3.35, 18, plat_top + 2)), charcoal, "yaw", lift,
        "Clip on the platform: strain relief where the ribbon leaves the loop", "print", "PETG clip with a cable tie")
    J("cable_clip_to_platform", "tapped", ["cable_clip_stage", "yaw_platform"],
      [("hex bolt", "M3 x 8", 1), ("cable tie", "100 x 2.5 mm", 1)], count=1, status="count", proposed=True)
    J("motor_cable_ties", "cable_tie", ["motor_cable_yaw_servo", "motor_cable_tilt_servo", "hanger_2", "joint_beam"],
      [("cable tie", "100 x 2.5 mm", 1)], count=8, status="count", proposed=True,
      note="Rear hanger 3, beam top 4, under the console 1")
    J("supplied_set_screws", "set_screw", ["yaw_collar", "hinge_collar_*", "tilt_pulley_small", "tilt_pulley_large",
                                           "hinge_block_*"], [("set screw", "comes with the part", 1, False)], count=7)
    # Nuts of the splice plate stand on the beam top, where the motor cables run.
    beam_runs = [((-cab_dx, cab_hang_y), (-cab_dx, 0)), ((cab_dx, cab_hang_y), (cab_dx, 60)), ((cab_dx, 60), riser_xy)]
    for x, y in splice_xy:
        assert min(seg_dist((x, y), a, b) for a, b in beam_runs) - 5 - cab_r >= .5, "splice nuts clear the beam cables"
    travel = math.radians(2 * hs_["travel_degrees"])
    cable_lengths = {"yaw_servo": round(path_length(yaw_cable)),
                     "tilt_servo": round(path_length(tilt_fixed_path) + loop_len + path_length(stage_path)),
                     "rolling_loop_length": round(loop_len),
                     "rolling_loop_bend_radius": round(fold_rad, 1),
                     "fold_travel_over_full_yaw": round(math.degrees(travel * r_i / (r_o + r_i)))}

    # Fill sensors hang off the throat lip, under the funnel and out of the item path. Each pod
    # holds an HC-SR04 face down, its two transducers on a tangential line at sensor_r, and flares
    # each transducer into a printed horn: the wider mouth narrows the beam. The tray is open on
    # top; the header points outward and the wires leave over the top.
    fs, sensor_r = p["fill_sensor"], p["fill_sensor_radial_position_mm"]
    board_l, board_w, board_t = fs["board_mm"]
    can_r, can_h, pitch = fs["transducer_diameter_mm"] / 2, fs["transducer_height_mm"], fs["transducer_pitch_mm"]
    horn_l, horn_r, horn_wall, wall = (fs["horn_length_mm"], fs["horn_mouth_diameter_mm"] / 2,
                                       fs["horn_wall_mm"], fs["wall_mm"])
    assert pitch - 2 * horn_r >= horn_wall, "the two horn mouths need a wall between them"
    pod_top = lip_top
    board_z = pod_top - fs["space_above_board_mm"] - board_t
    window_z = board_z - can_h - horn_l
    half_x = max(board_w / 2 + wall, horn_r + horn_wall)
    half_y = max(board_l / 2 + wall, pitch / 2 + horn_r + horn_wall)
    x_in, x_out = sensor_r - half_x, sensor_r + board_w / 2 + fs["connector_space_mm"] + wall
    # Printed horn mouths down, so a 45 degree web carries the connector shelf without supports.
    shelf_z, web = board_z - wall, x_out - sensor_r - half_x
    pod = box(x_out - x_in, 2 * half_y, pod_top - board_z + wall,
              ((x_in + x_out) / 2, 0, (pod_top + board_z - wall) / 2)).fuse(
        box(2 * half_x, 2 * half_y, shelf_z - window_z, (sensor_r, 0, (shelf_z + window_z) / 2)),
        cq.Workplane("XZ").polyline([(x_out - web, shelf_z), (x_out, shelf_z), (x_out - web, shelf_z - web)])
        .close().extrude(half_y, both=True).val())
    c0, c1 = sensor_r - board_w / 2 - .5, x_out - wall
    pod = pod.cut(box(c1 - c0, board_l + 1, pod_top - board_z, ((c0 + c1) / 2, 0, (pod_top + board_z) / 2)))
    pod = pod.cut(box(12, 8, 4, (sensor_r, 0, board_z - 2)))  # crystal between the transducers
    for y in (-pitch / 2, pitch / 2):
        pod = pod.cut(cylinder(can_r + .3, can_h + .01, (sensor_r, y, board_z - can_h), (0, 0, 1))).cut(
            cq.Solid.makeCone(can_r + .3, horn_r, horn_l + .01, cq.Vector(sensor_r, y, board_z - can_h),
                              cq.Vector(0, 0, -1)))
    reach_s = x_in - throat_r
    bracket = box(reach_s, 20, 20, (throat_r + reach_s / 2, 0, pod_top - 15)).cut(
        tube(throat_r + fw, 0, window_z, pod_top - window_z))
    for i, a in enumerate(DIRECTIONS, 1):
        add(f"fill_sensor_pod_{i}", pod.rotate((0, 0, 0), (0, 0, 1), a), charcoal, "head", lift,
            "HC-SR04 pod above one bin, face down, with a printed horn on each transducer",
            "print", "PETG")
        add(f"fill_sensor_arm_{i}", bracket.rotate((0, 0, 0), (0, 0, 1), a), metal, "head", lift,
            "Sensor arm from the throat lip", "print", "PETG")
    J("sensor_pod_and_arm", "one_piece", ["fill_sensor_pod_*", "fill_sensor_arm_*"], [], count=4, proposed=True,
      note="Print each pod and its arm as one piece")
    J("sensor_arm_to_lip", "bolt", ["fill_sensor_arm_*", "intake_funnel"],
      [("hex bolt", "M3 x 12", 1), ("nut", "M3", 1), ("washer", "M3", 1)], count=8, status="count", proposed=True,
      note="2 per arm through the lip band, drilled on assembly")
    J("hcsr04_in_pod", "screw", ["fill_sensor_pod_*"], [("self-tapping screw", "M2 x 6", 1)], count=8, status="count",
      proposed=True, note="2 per board; check the board's hole size on arrival")

    # Rear console: a small display slab leaning back on a low base. The slab is a thin frame
    # around the display board (a 4.3 inch board with its own ESP32-S3); the base carries the camera
    # board and the supplies and falls away to a half-round back, and the camera hides under its chin.
    # The chin reaches in over the funnel mouth so the camera sees the rear plate edge
    # past the throat lip (v3's rim-mounted camera lost about 16 % of the plate there).
    cw, ch = p["console_width_mm"], p["console_height_mm"]
    y_front, chin_h = p["console_chin_front_y_mm"], p["console_chin_height_mm"]
    y_back, back_h = p["console_back_y_mm"], p["console_back_height_mm"]
    edge_r, wall = p["console_edge_radius_mm"], p["console_wall_mm"]
    lean = math.radians(p["display_lean_back_degrees"])
    (sw, st, sh), (gw, gd, gh) = p["display_slab_mm"], p["display_glass_mm"]
    mw, md, mh = p["display_module_mm"]
    z_face0, z_top = top + chin_h, top + ch
    y_top = y_front + (z_top - z_face0) * math.tan(lean)
    assert y_back <= deck_ro, "console stays on the head"
    upper = cq.selectors.BoxSelector((-cw, 0, top + 1), (cw, y_back + 1, z_top + 1))
    body = (cq.Workplane("YZ").polyline([(y_front, top), (y_front, z_face0), (y_top, z_top),
                                         (y_back, top + back_h), (y_back, top)])
            .close().extrude(cw / 2, both=True).edges("|X").edges(upper).fillet(edge_r).val())
    # Plan outline of the base: a straight front and a half-round back.
    round_y = y_back - cw / 2
    # The motor cables leave through the console floor, so their collar holes must open inside
    # the half-round back, clear of its wall.
    assert math.hypot(cab_dx, cab_shell_y - round_y) + cab_r + .75 <= cw / 2 - wall, \
        "motor cable holes open inside the console"
    plan =(cq.Workplane("XY").center(0, (y_front + round_y) / 2).rect(cw, round_y - y_front).extrude(ch)
            .edges("|Z").edges("<Y").fillet(edge_r).val().translate((0, 0, top))
            .fuse(cylinder(cw / 2, ch, (0, round_y, top), (0, 0, 1))))
    body = body.intersect(plan)
    # Saddle: a low arc on the rim collar either side of the base, where the console is screwed down.
    saddle = tube(deck_ro, mouth_r, top, p["console_saddle_height_mm"]).intersect(
        box(2 * deck_ro, deck_ro, 40, (0, p["console_saddle_from_y_mm"] + deck_ro / 2, top)))
    body = body.fuse(saddle)
    saddle_h = p["console_saddle_height_mm"]
    for x, y in jh["console_bolts"]:
        body = body.cut(cylinder(2.25, saddle_h, (x, y, top), (0, 0, 1)))
    J("console_to_collar", "bolt", ["display_console", "intake_funnel"],
      [("hex bolt", "M4 x 16", 1), ("nut", "M4", 1), ("washer", "M4", 2)],
      positions=[(x, y, top + saddle_h) for x, y in jh["console_bolts"]], proposed=True,
      note="Through the saddle and the collar, nuts under the collar")
    # Display slab: stands on the chin and leans back with the base face, corners rounded like a tablet.
    face_center = (0, y_front + sh / 2 * math.sin(lean), z_face0 + sh / 2 * math.cos(lean))
    on_face = lambda shape: shape.rotate((0, 0, 0), (1, 0, 0), -math.degrees(lean)).translate(face_center)
    slab = on_face(cq.Workplane("XY").box(sw, st, sh, centered=(True, False, True))
                   .edges("|Y").fillet(p["display_corner_radius_mm"]).val())
    body = body.fuse(slab)
    shell = body
    # The glass is the module's visible area; the frame only has to cover the board around it.
    assert gw < mw and gh < mh and sw - mw <= 12 and sh - mh <= 12, "the slab is a thin frame around the display board"
    face = on_face(box(gw, gd, gh, (0, gd / 2, 1.7)))      # active area sits 1.7 mm above the board centre
    target = (0, 0, plate_z + plate_t)
    lens_at = (0, p["camera_y_mm"], top)
    dx, dy, dz = (t - l for t, l in zip(target, lens_at))
    n = math.sqrt(dx * dx + dy * dy + dz * dz)
    aim = (dx / n, dy / n, dz / n)
    inward = tuple(-a for a in aim)
    along = lambda d: tuple(l + d * a for l, a in zip(lens_at, inward))
    recess = cylinder(11, 14, along(-2), inward)
    led_len = p["led_strip_length_mm"]
    assert led_len <= cw - 12 and y_front <= p["camera_y_mm"] - 16
    led = box(led_len, 9, 2.5, (0, p["camera_y_mm"] + 24, top + 1.25))
    body = body.cut(face).cut(recess).cut(led)

    # Space check: the boards that live in the console must fit inside it with a printed wall
    # around each, clear of the screen module, the camera recess, the LED pocket and each other.
    inside = lambda part, solid: part.intersect(solid).Volume() > part.Volume() * .999
    tft_module = on_face(box(mw, md, mh, (0, md / 2, 0)))
    assert inside(tft_module, shell), "display module and its controller fit inside the slab"
    slots = [tft_module]
    for name, slot in p["console_electronics_mm"].items():
        (sx, sy, sz), (x, y, z) = slot["size"], slot["at"]
        room = box(sx + 2 * wall, sy + 2 * wall, sz + 2 * wall, (x, y, top + z))
        assert inside(room, body), f"{name} fits inside the console"
        assert all(room.intersect(other).Volume() < 1 for other in slots), f"{name} is clear of the other boards"
        slots.append(room)
    # Guition JC4827W543 (maker drawing): 4 M3 holes 112.6 x 62.1 behind the board, and USB-C and the
    # 4-pin JST power/UART socket on its left edge, reached through a slot in the slab side.
    display_pts = []
    for hx in (-56.3, 56.3):
        for hz in (-31.05, 31.05):
            body = body.cut(on_face(cylinder(1.25, 8, (hx, md, hz), (0, 1, 0))))
            v = on_face(cq.Vertex.makeVertex(hx, md + 4, hz))
            display_pts.append((v.X, v.Y, v.Z))
    body = body.cut(on_face(box(8, md, 22, (-mw / 2 - 2.5, md / 2, .5))))
    # Both USB-C ports of the ESP32-S3 CAM board face the left wall of the base, through a slot.
    eb_ = p["console_electronics_mm"]["esp32_s3_board"]
    usb_x1 = eb_["at"][0] - eb_["size"][0] / 2 + 1
    body = body.cut(box(usb_x1 + cw / 2 + 3, 24, 9, ((usb_x1 - cw / 2 - 3) / 2, eb_["at"][1], top + eb_["at"][2])))
    add("display_console", body, light, "brain", brain_lift,
        "Rear console, hollow shell: a 4.3 inch display slab leaning back on a low base; ESP32-S3 "
        "camera board, supplies, voltage dividers and wiring in the base, camera and LED strip under the "
        "chin, clear of any liquid in the funnel; leave the USB-C ports of both boards reachable", "print",
        "PETG, printed in 2 halves")
    J("display_to_console", "tapped", ["tft_screen", "display_console"],
      [("hex bolt", "M3 x 6", 1), ("heat-set insert", "M3", 1)], positions=display_pts,
      note="The 4 holes of the Guition board, into inserts in the slab")
    J("console_halves", "tapped", ["display_console"], [("hex bolt", "M3 x 12", 1), ("heat-set insert", "M3", 1)],
      count=6, status="count", proposed=True)
    for name, (n, hw) in BOARD_MOUNTS.items():
        kind = "cable_tie" if hw[0][0] == "cable tie" else "screw" if hw[0][0] == "self-tapping screw" else "tapped"
        J(f"{name}_in_console", kind, ["display_console"], hw, count=n, status="count", proposed=True,
          note="Hole positions from the board on arrival")
    J("camera_in_window", "adhesive", ["camera_window", "display_console"], [("hot glue", "stick", 1)], count=1,
      status="count", proposed=True, note="Lens pressed into the window and glued from inside; no clamp drawn yet")
    J("led_strip_in_groove", "adhesive", ["led_strip", "display_console"], [], count=1, note="Self-adhesive back")
    add("tft_screen", face, glass, "brain", brain_lift,
        "4.3 inch display: sorting status and fill levels; its own ESP32-S3 also reads the 4 fill sensors",
        "buy", f"Guition JC4827W543, ESP32-S3 N4R8, IPS 480x272, UART on a 4-pin JST 1.25, "
        f"board {mw:g} x {mh:g} x {md:g} mm (shop figures, measure)")
    # Lens 3 mm inside the Ø22 window: the window wall stays outside the 120 degree cone (free cone about 127 degrees).
    add("camera_window", cylinder(5, 2, along(3), inward), (.02, .02, .02), "brain", brain_lift,
        "OV2640 camera behind the chin window, 120 degree lens, on a 75 mm ribbon to the board in the base",
        "buy", "OV2640, 120 degree lens, 75 mm 24-pin ribbon")
    add("led_strip", led, (.98, .96, .80), "brain", brain_lift,
        "White LED strip under the chin lighting the plate evenly for recognition", "buy",
        f"5 V white 2835 LED strip, {led_len:.0f} mm (cuts every 50 mm), 8 mm wide, in a 9 mm groove")
    cam = along(3)
    # The camera ribbon has to reach the camera connector on the board in the base.
    eb = p["console_electronics_mm"]["esp32_s3_board"]
    connector = (eb["at"][0], eb["at"][1], top + eb["at"][2] + eb["size"][2] / 2)   # FPC socket mid-board (Freenove)
    cable_reach = math.dist(cam, connector)
    assert cable_reach <= p["camera_cable_mm"] - 15, "the camera ribbon reaches the board with slack"

    # Camera sightline: every plate-edge point must pass inside the throat lip and the skirt.
    rings = [(lip_top, throat_r), (lip_bottom, throat_r)]
    rings += [(z, skirt_r) for z in range(int(lip_bottom), int(plate_z + plate_t), -8)]
    hidden, sight_margin = 0, math.inf
    for k in range(72):
        a = math.radians(k * 5)
        ex, ey, ez = plate_r * math.cos(a), plate_r * math.sin(a), plate_z + plate_t
        gaps = []
        for zc, rc in rings:
            f = (cam[2] - zc) / (cam[2] - ez)
            gaps.append(rc - math.hypot(cam[0] + f * (ex - cam[0]), cam[1] + f * (ey - cam[1])))
        hidden += min(gaps) < 0
        sight_margin = min(sight_margin, min(gaps))

    # Field of view the lens must cover: widest angle from the aim axis to the plate edge.
    widest = 0
    for k in range(72):
        a = math.radians(k * 5)
        v = (plate_r * math.cos(a) - cam[0], plate_r * math.sin(a) - cam[1], plate_z + plate_t - cam[2])
        widest = max(widest, math.degrees(math.acos(sum(x * y for x, y in zip(v, aim)) / math.hypot(*v))))

    return {"fasteners": fasteners, "head_lowest": spider_bottom - max(pad_t, spt), "camera_cable_reach": cable_reach, "motor_cable_mm": cable_lengths, "camera_required_full_fov_degrees": round(2 * widest, 1), "pivot_z": pivot, "plate_z": plate_z, "spider_bottom": spider_bottom,
            "spider_top": spider_top, "lip_top": lip_top, "lip_bottom": lip_bottom,
            "throat_r": throat_r, "exit_gap": exit_gap, "skirt_gap": skirt_gap,
            "low_edge_z": low_edge_z, "belt_center_mm": c, "big_r": big_r, "small_r": small_r,
            "camera": cam, "camera_hidden_edge_samples": hidden, "slope": slope,
            "camera_sight_margin": sight_margin, "camera_aim_from_vertical": math.degrees(math.atan2(-dy, -dz)),
            "sensor_r": sensor_r, "sensor_window_z": window_z,
            "shell_top": shell_top, "collar_t": collar_t, "mouth_r": mouth_r, "fw": fw}


def fold_allowance(leg, t, k, hem=False):
    """Flat-pattern numbers for one folded edge of sheet t: a leg of outer length `leg` bent 90
    degrees on an inside radius t, or closed back on itself as a hem (inside radius about 0).
    All three are measured from the blank edge: how far the blank reaches past the finished
    outline, where the bend centre line lies, and the square corner relief that keeps two
    folded edges from meeting."""
    r = 0 if hem else t
    ba = (math.pi if hem else math.pi / 2) * (r + k * t)
    straight = leg - (r + t)
    return {"blank_past_outline": round(straight + ba - (r + t), 2),
            "bend_line_from_edge": round(straight + ba / 2, 2), "corner_relief": round(straight + ba, 2)}


def hemmed_panel(w, h, t, hem):
    """Sheet panel w x h with a closed hem folded back along all four edges. Local frame: outer
    face on y = 0, the hem behind it (y = t to 2t), centred on x and z."""
    face = box(w, t, h, (0, t / 2, 0))
    return face.fuse(box(w, t, h, (0, 1.5 * t, 0)).cut(box(w - 2 * hem, t, h - 2 * hem, (0, 1.5 * t, 0))))


def body_b(p, add, h, joint=None):
    J = joint or (lambda *a, **k: None)
    j = p["joinery"]
    jh = joinery_holes(p)
    f, b = p["frame"], p["bin"]
    half, prof, sheet = f["outer_mm"] / 2, f["profile_mm"], f["panel_mm"]
    deck = p["head_deck_height_mm"]
    top = p["rim_height_mm"]
    pc = half - prof / 2
    inner = half - prof
    seat_t, floor_t = f["seat_plate_mm"], f["floor_plate_mm"]
    seat_z = deck - seat_t
    rail_z = seat_z - prof
    assert inner >= p["locating_ring_outer_radius_mm"] + 2
    style = f.get("style", "alu")
    body_fasteners = []
    # Stainless skins: always on the aluminium frame; on the slotted-angle frame when chosen.
    stainless = style != "vlo" or f["vlo"].get("skin_kind") == "stainless"
    if style != "vlo":
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
        # The back has no drawer in the way, so a mid rail holds its 1 mm sheet flat like the sides.
        add("rail_mid_xp", box(inner * 2, prof, prof, (0, pc, 450)), alu, "frame", (0, 0, 0),
            "Mid rail along X behind the back panel", "cut", "Aluminium profile 20 x 20")
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
        # Shell: 1 mm stainless sheet with a closed hem on every edge, hem side against the frame, so
        # no cut edge is left exposed. The side panels run past the back and front panels to cover
        # their edges, and the top cover's skirt folds down over the top edges of all four sides.
        skin = (.94, .95, .94)
        hem, k, mat = f["panel_hem_mm"], f["bend_k_factor"], f["panel_material"]
        folds = {"hem": fold_allowance(hem, sheet, k, hem=True), "skirt": fold_allowance(f["top_skirt_mm"], sheet, k)}
        skin_out = half + 2 * sheet
        shell = {"material": mat, "sheet_mm": sheet, "hem_mm": hem, "top_skirt_mm": f["top_skirt_mm"],
                 "k_factor": k, "folds": folds, "blanks": {}, "volume": 0.0}

        def add_skin(name, shape, color, group, explode, description, w, hgt, fold="hem", **extra):
            add(name, shape, color, group, explode, description, "bend", mat)
            past = folds[fold]["blank_past_outline"]
            shell["blanks"][name] = {"finished_mm": [round(w, 1), round(hgt, 1)], "fold": fold,
                                     "blank_mm": [round(w + 2 * past, 1), round(hgt + 2 * past, 1)], **extra}
            shell["volume"] += shape.Volume()

        for s, name in ((-1, "left"), (1, "right")):
            side = hemmed_panel(2 * skin_out, top, sheet, hem).rotate((0, 0, 0), (0, 0, 1), 90 * s)
            add_skin(f"side_panel_{name}", side.translate((s * skin_out, 0, top / 2)), skin, "skin", (s * 250, 0, 0),
                     "Side skin; covers the edges of the back and front panels", 2 * skin_out, top)
        door_top, head_bottom = rail_z, rail_z + 2
        door_z0 = 2
        door_h = door_top - door_z0
        back = hemmed_panel(half * 2, top, sheet, hem).rotate((0, 0, 0), (0, 0, 1), 180)
        add_skin("back_panel", back.translate((0, skin_out, top / 2)), skin, "skin", (0, 250, 0),
                 "Fixed back skin: the bin can stand against a wall", half * 2, top)
        add_skin("head_panel_front", hemmed_panel(half * 2, top - head_bottom, sheet, hem).translate(
            (0, -skin_out, (top + head_bottom) / 2)), skin, "skin", (0, -250, 0), "Front panel around the head",
            half * 2, top - head_bottom)
        co, skirt = skin_out + sheet, f["top_skirt_mm"]
        hole_r = p["deck_outer_radius_mm"] + 1
        cover = box(2 * co, 2 * co, sheet, (0, 0, top + sheet / 2)).cut(tube(hole_r, 0, top, sheet)).fuse(
            box(2 * co, 2 * co, skirt, (0, 0, top + sheet - skirt / 2)).cut(
                box(2 * co - 2 * sheet, 2 * co - 2 * sheet, skirt, (0, 0, top + sheet - skirt / 2))))
        add_skin("top_cover", cover, (.82, .85, .84), "skin", (0, 0, 450),
                 "Top cover with the funnel opening; its skirt folds down over the panels, screwed to the frame",
                 2 * co, 2 * co, fold="skirt", hole_d=2 * hole_r)

    else:
        # Mix 2: a bolted frame of slotted steel angle (like a warehouse shelf), Formex boards
        # inside, Formex 8 mm skins outside and only the top cover in stainless, where hands,
        # spills and eyes land most. The angles sit on the outer envelope, so the drawer bays
        # keep the same inner widths as the aluminium frame.
        v = f["vlo"]
        a, t, sk, bd = v["angle_leg_mm"], v["angle_thick_mm"], v["skin_mm"], v["board_mm"]
        steel_v, vmat, fmx = (.36, .42, .48), v["angle_material"], (.95, .95, .93)
        ft = v["foot"]
        zf, pt = ft["height_mm"], ft["plate_mm"]            # the posts stand on four levelling feet

        def bolt(joint, size, start, axis, length, head="carriage"):
            body_fasteners.append({"joint": joint, "size": size, "head": head, "start_mm": [round(c, 2) for c in start],
                                   "axis": list(axis), "length_mm": round(length, 1)})
        n = 0
        weld_pts = []
        for sx in (-1, 1):
            for sy in (-1, 1):
                n += 1
                cx, cy = sx * (half - a / 2), sy * (half - a / 2)
                weld_pts.append((cx, cy, zf - pt))
                post = box(a, t, top - zf, (cx, sy * (half - t / 2), (top + zf) / 2)).fuse(
                    box(t, a, top - zf, (sx * (half - t / 2), cy, (top + zf) / 2)))
                add(f"post_{n}", post, steel_v, "frame", (0, 0, 0), "Corner post, slotted angle, standing on a foot plate",
                    "cut", vmat)
                # Foot plate under the post: a bent steel plate whose tab is clamped between the post leg and
                # the bottom side rail by that rail's bolts, and an M8 nut welded under it for the foot.
                plate = box(a, a, pt, (cx, cy, zf - pt / 2)).fuse(
                    box(pt, a - t, a + t, (sx * (half - t - pt / 2), sy * (half - t - (a - t) / 2), zf + (a + t) / 2))).cut(
                    cylinder(4.25, pt, (cx, cy, zf - pt), (0, 0, 1)))
                add(f"foot_plate_{n}", plate, (.30, .32, .34), "frame", (0, 0, 0),
                    "Foot plate under a post: its tab is clamped by the bottom rail bolts, M8 nut welded underneath",
                    "bend", f"Steel plate {pt:.0f} mm, {a:.0f} x {a:.0f} with a {a + t:.0f} mm tab, M8 nut welded")
                foot = cylinder(ft["pad_d_mm"] / 2, ft["pad_h_mm"], (cx, cy, 0), (0, 0, 1)).fuse(
                    cylinder(4, zf - pt - ft["pad_h_mm"], (cx, cy, ft["pad_h_mm"]), (0, 0, 1)))
                add(f"foot_{n}", foot, (.12, .12, .12), "frame", (0, 0, 0), "Levelling foot M8 under a post", "buy",
                    f"Levelling foot M8, pad {ft['pad_d_mm']:.0f} mm")
        J("foot_plate_nut_weld", "weld", ["foot_plate_*"], [("nut", "M8", 1)], positions=weld_pts,
          note="The only weld: an M8 nut under each foot plate, done by the shop that cuts and bends the plates")
        J("foot_into_plate", "thread", ["foot_*", "foot_plate_*"], [], positions=weld_pts,
          note="The foot screws into the welded nut; turn it to level the bin")
        span = 2 * (half - 2 * t) - 1

        def rail(name, side, z_leg, z_flat, desc, inset=0, length=span):
            """Angle bolted inside two posts, like a warehouse shelf: its upright leg lies against the inner
            faces of the post legs, the flat leg turns inwards. Rails along Y sit one sheet lower or higher,
            so where two rails meet in a corner one flat leg rests on the other."""
            if side in ("xn", "xp"):
                sx = -1 if side == "xn" else 1
                shape = box(t, length, a, (sx * (half - 1.5 * t - inset), 0, z_leg)).fuse(
                    box(a, length, t, (sx * (half - t - a / 2 - inset), 0, z_flat)))
                for sy in (-1, 1):
                    bolt("rail_to_post", "M8 x 12" if not inset else "M8 x 15", (sx * half, sy * (half - a / 2), z_leg),
                         (-sx, 0, 0), 2 * t + inset + 7)
            else:
                sy = -1 if side == "yn" else 1
                shape = box(length, t, a, (0, sy * (half - 1.5 * t - inset), z_leg)).fuse(
                    box(length, a, t, (0, sy * (half - t - a / 2 - inset), z_flat)))
                for sx in (-1, 1):
                    bolt("rail_to_post", "M8 x 12", (sx * (half - a / 2), sy * half, z_leg), (0, -sy, 0), 2 * t + 7)
            add(name, shape, steel_v, "frame", (0, 0, 0), desc, "cut", vmat)
        # Bottom rails carry the floor on their flat legs; there is none across the front, where the
        # drawers run out. Seat rails hang below the head seat board; mid rails stop the skins drumming.
        mid = v["mid_rail_z_mm"]
        for side in ("xn", "xp", "yp"):
            dz = t if side in ("xn", "xp") else 0
            # The side bottom rails clamp the foot plate tabs, so they sit one plate further in.
            rail(f"rail_bottom_{side}", side, zf + a / 2 + dz, zf + t / 2 + dz,
                 "Bottom rail, slotted angle bolted inside the posts; the floor board rests on it",
                 inset=pt if side != "yp" else 0, length=span if side != "yp" else 2 * (half - 2 * t - pt) - 1)
            rail(f"rail_mid_{side}", side, mid + dz, mid - a / 2 + t / 2 + dz, "Mid rail, slotted angle bolted inside the posts")
        seat_t = bd
        seat_z = deck - seat_t
        for side in ("xn", "xp", "yn", "yp"):
            dz = -t if side in ("xn", "xp") else 0
            rail(f"rail_seat_{side}", side, seat_z - a / 2 + dz, seat_z - t / 2 + dz,
                 "Seat rail, slotted angle bolted inside the posts; the head seat board rests on it")
        # Boards fit inside the rail uprights, with the corners notched round the foot tabs and the
        # rail bolt nuts, and bolt to the flat legs with M8 x 30.
        bh_ = half - 2 * t

        def board(z, th, wx=bh_):
            b_ = box(2 * wx, 2 * bh_, th, (0, 0, z + th / 2))
            for sx in (-1, 1):
                for sy in (-1, 1):
                    b_ = b_.cut(box(a + 2, a + 2, th, (sx * (half - (a + 2) / 2), sy * (half - (a + 2) / 2), z + th / 2)))
            return b_
        floor_z = zf + 2 * t
        floor_pts = [(-(half - t - a / 2 - pt), 0), (half - t - a / 2 - pt, 0), (0, half - t - a / 2)]
        floor = board(floor_z, bd, bh_ - pt)
        for x, y in floor_pts:
            floor = floor.cut(cylinder(4.5, bd, (x, y, floor_z), (0, 0, 1)))
            bolt("floor_board_to_rail", "M8 x 30", (x, y, floor_z + bd), (0, 0, -1), bd + t + 9, "hex")
        add("floor_plate", floor, fmx, "frame", (0, 0, 0), "Floor board on the bottom rails; waterproof",
            "laser", v["board_material"])
        seat_hole = p["locating_ring_outer_radius_mm"] + 2
        pin_hole = cylinder(3.3, seat_t, (0, p["orientation_pin_radius_mm"], seat_z), (0, 0, 1))
        seat = board(seat_z, seat_t).cut(tube(seat_hole, 0, seat_z, seat_t)).cut(pin_hole)
        for x, y in jh["deck_bolts"]:
            seat = seat.cut(cylinder(4, seat_t, (x, y, seat_z), (0, 0, 1)))    # M6 insert nuts for the deck bolts
        seat_pts = [(-(half - t - a / 2), 0), (half - t - a / 2, 0), (0, half - t - a / 2), (0, -(half - t - a / 2))]
        for x, y in seat_pts:
            seat = seat.cut(cylinder(4.5, seat_t, (x, y, seat_z), (0, 0, 1)))
            bolt("seat_board_to_rail", "M8 x 30", (x, y, seat_z + seat_t), (0, 0, -1), seat_t + t + 9, "hex")
        add("head_seat_plate", seat, fmx, "frame",
            (0, 0, 0), "Head seat board on the four seat rails; the rear hole takes the deck orientation pin, "
            "4 M6 insert nuts take the deck bolts",
            "laser", v["board_material"])
        assert half - t - seat_hole >= a, "the seat board ring reaches over the seat rails"
        floor_t, base = bd, floor_z + bd
        rail_z = seat_z - a
        skin = (.93, .93, .91)
        hem, k, mat = f["panel_hem_mm"], f["bend_k_factor"], f["panel_material"]
        folds = {"hem": fold_allowance(hem, sheet, k, hem=True), "skirt": fold_allowance(f["top_skirt_mm"], sheet, k)}
        shell = {"material": mat, "sheet_mm": sheet, "hem_mm": hem, "top_skirt_mm": f["top_skirt_mm"],
                 "k_factor": k, "folds": folds, "blanks": {}, "volume": 0.0}

        def add_skin(name, shape, color, group, explode, description, w, hgt, fold="hem", **extra):
            add(name, shape, color, group, explode, description, "bend", mat)
            past = folds[fold]["blank_past_outline"]
            shell["blanks"][name] = {"finished_mm": [round(w, 1), round(hgt, 1)], "fold": fold,
                                     "blank_mm": [round(w + 2 * past, 1), round(hgt + 2 * past, 1)], **extra}
            shell["volume"] += shape.Volume()
        door_top = rail_z - 2
        door_z0 = zf + 2                                 # drawer fronts start just above the post feet
        door_h = door_top - door_z0
        head_bottom = rail_z
        if stainless:
            # 1 mm stainless with a closed hem on every edge, hem side against the angles, bolted
            # through the angle holes; the side skins run past the back and front to cover their edges.
            skin = (.94, .95, .94)
            # The skins stand off the posts by the bolt heads and corner brackets on the outside.
            skin_out = half + v["skin_gap_mm"] + 2 * sheet
            sk_h = top - zf
            for s, name in ((-1, "left"), (1, "right")):
                side = hemmed_panel(2 * skin_out, sk_h, sheet, hem).rotate((0, 0, 0), (0, 0, 1), 90 * s)
                add_skin(f"side_panel_{name}", side.translate((s * skin_out, 0, zf + sk_h / 2)), skin, "skin",
                         (s * 250, 0, 0), "Side skin, stainless with closed hems; covers the edges of the back and front "
                         "panels; M4 screws with spacers into the angle holes", 2 * skin_out, sk_h)
            back = hemmed_panel(2 * (skin_out - 2 * sheet), sk_h, sheet, hem).rotate((0, 0, 0), (0, 0, 1), 180)
            add_skin("back_panel", back.translate((0, skin_out, zf + sk_h / 2)), skin, "skin", (0, 250, 0),
                     "Fixed back skin, stainless with closed hems: the bin can stand against a wall",
                     2 * (skin_out - 2 * sheet), sk_h)
            add_skin("head_panel_front", hemmed_panel(2 * (skin_out - 2 * sheet), top - head_bottom, sheet, hem).translate(
                (0, -skin_out, (top + head_bottom) / 2)), skin, "skin", (0, -250, 0),
                "Front panel around the head, stainless with closed hems", 2 * (skin_out - 2 * sheet), top - head_bottom)
        else:
            skin_out = half + sk
            for s, name in ((-1, "left"), (1, "right")):
                add(f"side_panel_{name}", box(sk, 2 * skin_out, top, (s * (half + sk / 2), 0, top / 2)), skin, "skin",
                    (s * 250, 0, 0), "Side skin, covers the edges of the back and front panels", "laser", v["skin_material"])
            add("back_panel", box(2 * half, sk, top, (0, half + sk / 2, top / 2)), skin, "skin", (0, 250, 0),
                "Fixed back skin: the bin can stand against a wall", "laser", v["skin_material"])
            add("head_panel_front", box(2 * half, sk, top - head_bottom, (0, -(half + sk / 2), (top + head_bottom) / 2)), skin,
                "skin", (0, -250, 0), "Front panel around the head", "laser", v["skin_material"])
        co, skirt = skin_out + sheet, f["top_skirt_mm"]
        hole_r = p["deck_outer_radius_mm"] + 1
        cover = box(2 * co, 2 * co, sheet, (0, 0, top + sheet / 2)).cut(tube(hole_r, 0, top, sheet)).fuse(
            box(2 * co, 2 * co, skirt, (0, 0, top + sheet - skirt / 2)).cut(
                box(2 * co - 2 * sheet, 2 * co - 2 * sheet, skirt, (0, 0, top + sheet - skirt / 2))))
        add("top_cover", cover, (.82, .85, .84), "skin", (0, 0, 450),
            "Stainless top cover with the funnel opening; its skirt folds down over the skins", "bend", mat)
        if stainless:
            # Skin screws: along each post and across the rails behind each skin, about one per pitch.
            # The angle holes are not measured yet, so the skins are drilled to the real holes on assembly.
            po, along = half - a / 2, (-200, 0, 200)
            nz = max(2, math.ceil((top - zf - 120) / j["skin_screw_pitch_mm"]) + 1)
            post_z = [zf + 60 + k_ * (top - zf - 120) / (nz - 1) for k_ in range(nz)]
            rail_zx = [zf + a / 2 + t, mid + t, seat_z - a / 2 - t]      # side rails sit one leg off the back ones
            rail_zy = [zf + a / 2, mid, seat_z - a / 2]
            pts = []
            for s in (-1, 1):
                pts += [(s * skin_out, y, z) for y in (-po, po) for z in post_z]
                pts += [(s * skin_out, y, z) for y in along for z in rail_zx]
            pts += [(x, skin_out, z) for x in (-po, po) for z in post_z] + [(x, skin_out, z) for x in along for z in rail_zy]
            pts += [(x, -skin_out, z) for x in (-po, po) for z in (head_bottom + 40, top - 40)]
            pts += [(x, -skin_out, seat_z - a / 2) for x in along]
            J("skins_to_frame", "bolt", ["side_panel_*", "back_panel", "head_panel_front", "post_*", "rail_*"],
              SKIN_SCREW, positions=pts, status="positions",
              note="Spacer keeps the skin 6 mm off the angles; drill the skin at the real angle holes on assembly")
            J("top_cover_to_frame", "bolt", ["top_cover", "post_*"], SKIN_SCREW,
              positions=[(s * co, y, top - skirt / 2) for s in (-1, 1) for y in (-po, po)]
              + [(x, s * co, top - skirt / 2) for s in (-1, 1) for x in (-po, po)], status="positions",
              note="Through the skirt and the skin into the post tops")
        shell["blanks"]["top_cover"] = {"finished_mm": [round(2 * co, 1)] * 2, "fold": "skirt", "hole_d": 2 * hole_r,
                                        "blank_mm": [round(2 * co + 2 * folds["skirt"]["blank_past_outline"], 1)] * 2}
        shell["volume"] += cover.Volume()

    # Two drawers, left and right, each carrying a front and a rear bin on full-extension slides.
    w, bh, bt, off = b["width_mm"], b["height_mm"], b["wall_mm"], b["center_offset_mm"]
    cw, st, sh, sl = f["center_wall_mm"], f["slide_thickness_mm"], f["slide_height_mm"], f["slide_length_mm"]
    mt, dw, db, dwh = f["slide_mount_mm"], f["drawer_wall_mm"], f["drawer_bottom_mm"], f["drawer_wall_height_mm"]
    if style == "vlo":
        db = f["vlo"]["tray_bottom_mm"]
    else:
        base = prof + floor_t
    in_x0, out_x1 = cw / 2 + st, inner - mt - st
    tray_z = base + 2
    z0 = tray_z + db
    assert off - w / 2 >= in_x0 + dw + 2 and off + w / 2 <= out_x1 - dw - 2, "bins fit between the drawer walls"
    tray_y0, tray_y1 = -half, inner - 13
    assert off + w / 2 < tray_y1 - dw, "rear bin fits in the tray"
    steel = (.50, .52, .55)
    sc, sd, sf = (f["drawer_stiffener_mm"][key] for key in ("crown", "depth", "flange"))

    def hat(xc, z_lo, z_hi):
        """Top-hat stiffener on the back of a drawer front: flanges on the sheet, crown inside."""
        y0, length, zc = -skin_out + sheet, z_hi - z_lo, (z_lo + z_hi) / 2
        channel = box(sc, sd, length, (xc, y0 + sd / 2, zc)).cut(
            box(sc - 2 * sheet, sd - sheet, length, (xc, y0 + (sd - sheet) / 2, zc)))
        return channel.fuse(*[box(sf, sheet, length, (xc + d * (sc + sf) / 2, y0 + sheet / 2, zc)) for d in (-1, 1)])

    stiffener_z = (z0 + 1, door_top - hem - 4)
    mount_mat = f["vlo"]["mount_material"] if style == "vlo" else "Aluminium composite 6 mm"
    add("center_wall", box(cw, inner * 2, 106, (0, 0, base + 53)), (.55, .58, .57), "frame", (0, 0, 0),
        "Centre wall carrying both inner slides", "laser", mount_mat)
    for s, name in ((-1, "left"), (1, "right")):
        mount_y = half - 5 if style == "vlo" else inner
        add(f"slide_mount_{name}", box(mt, 2 * mount_y, 106, (s * (inner - mt / 2), 0, base + 53)),
            (.55, .58, .57), "frame", (0, 0, 0),
            "Plate carrying the outer slide" + (f"; bolted to the front and rear posts through {f['vlo']['mount_spacer_mm']:.0f} mm spacers"
                                                 if style == "vlo" else ", on the bottom rail"), "laser", mount_mat)
        mx, my, ly = s * (in_x0 + out_x1) / 2, (tray_y0 + tray_y1) / 2, tray_y1 - tray_y0
        if style == "vlo":
            # The PP walls wrap the edges of the Formex floor and screw into them; the back wall sits
            # between the side walls, with an aluminium angle riveted inside each rear corner.
            wall_h = dwh + db
            tray = box(out_x1 - in_x0 - 2 * dw, ly - dw, db, (mx, my - dw / 2, tray_z + db / 2))
            for x in (in_x0 + dw / 2, out_x1 - dw / 2):
                tray = tray.fuse(box(dw, ly, wall_h, (s * x, my, tray_z + wall_h / 2)))
            tray = tray.fuse(box(out_x1 - in_x0 - 2 * dw, dw, wall_h, (mx, tray_y1 - dw / 2, tray_z + wall_h / 2)))
        else:
            tray = box(out_x1 - in_x0, ly, db, (mx, my, tray_z + db / 2))
            for x in (in_x0 + dw / 2, out_x1 - dw / 2):
                tray = tray.fuse(box(dw, ly, dwh, (s * x, my, z0 + dwh / 2)))
            tray = tray.fuse(box(out_x1 - in_x0, dw, dwh, (mx, tray_y1 - dw / 2, z0 + dwh / 2)))
        add(f"drawer_{name}", tray, (.62, .65, .64), "drawers", (0, -420, 0),
            "Drawer tray holding the front and the rear bin", "laser",
            f"Formex {db:.0f} mm floor, PP 3 mm walls screwed into its edges" if style == "vlo"
            else "Aluminium composite 4 mm, riveted angles")
        if style == "vlo":
            pitch = j["tray_screw_pitch_mm"]
            span_y = tray_y1 - dw - tray_y0 - 50
            ys = [tray_y0 + 25 + k_ * span_y / math.ceil(span_y / pitch) for k_ in range(math.ceil(span_y / pitch) + 1)]
            span_x = out_x1 - in_x0 - 2 * dw - 50
            xs = [in_x0 + dw + 25 + k_ * span_x / math.ceil(span_x / pitch) for k_ in range(math.ceil(span_x / pitch) + 1)]
            zs = tray_z + db / 2
            J(f"tray_walls_to_floor_{name}", "screw", [f"drawer_{name}"], [("wood screw", "3.5 x 16 stainless", 1)],
              positions=[(s * x, y, zs) for x in (in_x0, out_x1) for y in ys] + [(s * x, tray_y1, zs) for x in xs],
              status="positions", proposed=True,
              note="Into the middle of the 8 mm Formex edge, pre-drill 2.5 mm")
            ca, ct3, ch_ = j["tray_corner_angle_mm"]
            yb, rv = tray_y1 - dw, []
            for k_, xw in enumerate((in_x0 + dw, out_x1 - dw), 1):
                d = 1 if k_ == 1 else -1                      # into the tray
                corner = box(ca, ct3, ch_, (s * (xw + d * ca / 2), yb - ct3 / 2, z0 + ch_ / 2)).fuse(
                    box(ct3, ca, ch_, (s * (xw + d * ct3 / 2), yb - ca / 2, z0 + ch_ / 2)))
                add(f"tray_corner_{name}_{k_}", corner, (.70, .72, .74), "drawers", (0, -420, 0),
                    "Angle inside a rear tray corner, riveted to the back and the side wall", "cut",
                    f"Aluminium angle {ca:.0f} x {ca:.0f} x {ct3:g}, {ch_:.0f} mm long")
                for z in (z0 + 15, z0 + ch_ - 15):
                    rv += [(s * (xw + d * ca * .6), tray_y1, z), (s * (xw - d * dw), yb - ca * .6, z)]
            J(f"tray_corners_{name}", "rivet", [f"drawer_{name}", f"tray_corner_{name}_*"],
              [("blind rivet", "Ø4 x 10 aluminium", 1), ("washer", "M4", 1)], positions=rv, status="positions",
              proposed=True, note="Heads outside the tray, washers on the PP side")
        if style == "vlo" and stainless:
            vs = f["vlo"]
            hw_, hh_ = vs["handle_slot_mm"]
            front = hemmed_panel(half - 1, door_h, sheet, hem).translate((s * (half + 1) / 2, -skin_out, door_z0 + door_h / 2))
            slot_z = door_z0 + door_h - vs["handle_below_top_mm"] - hh_ / 2
            front = front.cut(box(hw_, 2 * sheet + 2, hh_, (s * (half + 1) / 2, -skin_out + sheet, slot_z)))
            assert half - (off + w / 2) >= 35, "finger room behind the pull slot"
            add_skin(f"drawer_front_{name}", front, skin, "drawers", (0, -420, 0),
                     f"Drawer front, stainless with closed hems, recessed pull slot {hw_:.0f} x {hh_:.0f} mm; two "
                     "stiffeners keep the sheet flat", half - 1, door_h,
                     slot={"size_mm": [hw_, hh_], "from_top_mm": vs["handle_below_top_mm"]})
        elif style == "vlo":
            vs = f["vlo"]
            hw_, hh_ = vs["handle_slot_mm"]
            front = box(half - 1, vs["skin_mm"], door_h, (s * (half + 1) / 2, -(half + vs["skin_mm"] / 2), door_z0 + door_h / 2))
            # Recessed pull: a slot cut through the board near its top edge; the gap in front of the
            # front bin leaves room for the fingers behind it.
            slot_z = door_z0 + door_h - vs["handle_below_top_mm"] - hh_ / 2
            front = front.cut(box(hw_, vs["skin_mm"] + 2, hh_, (s * (half + 1) / 2, -(half + vs["skin_mm"] / 2), slot_z)))
            assert half - (off + w / 2) >= 35, "finger room behind the pull slot"
            add(f"drawer_front_{name}", front, skin, "drawers", (0, -420, 0),
                f"Drawer front, full height, with a recessed pull slot {hw_:.0f} x {hh_:.0f} mm", "laser", vs["skin_material"])
        else:
          add_skin(f"drawer_front_{name}", hemmed_panel(half - 1, door_h, sheet, hem).translate(
            (s * (half + 1) / 2, -skin_out, door_z0 + door_h / 2)), skin, "drawers", (0, -420, 0),
            "Drawer front, full height, with a pull handle; two stiffeners keep the sheet flat", half - 1, door_h)
        # One stiffener just inside each tray wall, clear of the hems, the tray floor and the frame.
        for i, xc in enumerate((in_x0 + dw + 1 + sc / 2 + sf, out_x1 - dw - 1 - sc / 2 - sf) if stainless else (), 1):
            stiff = hat(s * xc, *stiffener_z)
            add(f"drawer_stiffener_{name}_{i}", stiff, (.70, .72, .74), "drawers", (0, -420, 0),
                "Top-hat stiffener bonded to the back of the drawer front with VHB tape; its foot bolts to the tray wall",
                "bend", f"{mat}, top-hat {sc:.0f} x {sd:.0f} with {sf:.0f} mm flanges")
            shell["volume"] += stiff.Volume()
            xw = in_x0 if i == 1 else out_x1                   # outer face of the tray wall next to it
            J(f"stiffener_{name}_{i}_to_tray", "bolt", [f"drawer_stiffener_{name}_{i}", f"drawer_{name}"],
              [("hex bolt", "M4 x 20", 1), ("spacer sleeve", f"M4, {sf + 1:.0f} mm", 1), ("nut", "M4", 1), ("washer", "M4", 1)],
              positions=[(s * xw, tray_y0 + 6, z) for z in (z0 + 15, z0 + dwh - 10)], status="positions", proposed=True,
              note="Through the tray wall and a spacer into the stiffener web: the drawer front hangs on these")
            J(f"stiffener_{name}_{i}_to_front", "adhesive", [f"drawer_stiffener_{name}_{i}", f"drawer_front_{name}"],
              [("VHB tape", f"{sf:.0f} mm wide, metres", round(2 * (stiffener_z[1] - stiffener_z[0]) / 1000, 2))], count=1,
              note="Both flanges taped to the back of the front")
        for x, tag in ((in_x0 - st / 2, "inner"), (out_x1 + st / 2, "outer")):
            add(f"slide_{name}_{tag}", box(st, sl, sh, (s * x, -inner + sl / 2, z0 + 8 + sh / 2)), steel,
                "frame", (0, 0, 0), f"Full-extension ball slide {sl:.0f} mm", "buy",
                f"Ball-bearing drawer slide {sl:.0f} mm, 3-section full extension, {sh:.0f} x {st:.1f}, 45 kg per pair (First Slide)")
        # TIAIHUA 1 A subminiature switch (13 x 6.8 x 6, lever about as long as the body, 2 M2 holes 6.5 apart).
        sw_ = box(13, 6.8, 6, (s * off, tray_y1 + 6, z0 + 30)).fuse(box(13, 0.6, 4, (s * off - s * 1, tray_y1 + 2.3, z0 + 30)))
        add(f"drawer_switch_{name}", sw_, (.85, .2, .2), "frame",
            (0, 0, 0), "Microswitch the closed drawer presses; open drawer locks its two bins", "buy",
            "Subminiature lever switch TIAIHUA 1 A 125 VAC, 13 x 6.8 x 6")
        if style == "vlo":
            # Printed L bracket on the floor board behind the tray holds the switch.
            sb_w, sb_h = j["switch_bracket_mm"]
            y_face, y_back = tray_y1 + 6 + 3.4, half - 2 * f["vlo"]["angle_thick_mm"]
            sb = box(sb_w, 5, sb_h, (s * off, y_face + 2.5, base + sb_h / 2)).fuse(
                box(sb_w, y_back - y_face, 5, (s * off, (y_face + y_back) / 2, base + 2.5)))
            add(f"drawer_switch_bracket_{name}", sb, (.25, .27, .30), "frame", (0, 0, 0),
                "Printed L bracket on the floor board holding the drawer switch", "print", "PETG")
            J(f"switch_to_bracket_{name}", "bolt", [f"drawer_switch_{name}", f"drawer_switch_bracket_{name}"],
              [("hex bolt", "M2 x 12", 1), ("nut", "M2", 1)],
              positions=[(s * off + d * 3.25, y_face, z0 + 30) for d in (-1, 1)], status="positions")
            J(f"switch_bracket_to_floor_{name}", "screw", [f"drawer_switch_bracket_{name}", "floor_plate"],
              [("wood screw", "3.5 x 16 stainless", 1)],
              positions=[(s * off + d * 5, y_face + 12, base + 5) for d in (-1, 1)], status="positions", proposed=True)
            # Slides: the outer ones bolt to the slide plates; the inner pair share through-bolts in the
            # centre wall. The inner members bolt to the tray only where the nut has room: in front of
            # the front bin and in the gap between the bins.
            zc = z0 + 8 + sh / 2
            ys6 = [-inner + sl * (k_ + .5) / 6 for k_ in range(6)]
            J(f"outer_slide_to_plate_{name}", "bolt", [f"slide_{name}_outer", f"slide_mount_{name}"],
              [("hex bolt", "M4 x 12", 1), ("nut", "M4", 1), ("washer", "M4", 1)],
              positions=[(s * (inner - mt), y, zc) for y in ys6], status="positions")
            J(f"slides_to_tray_{name}", "bolt", [f"slide_{name}_inner", f"slide_{name}_outer", f"drawer_{name}"],
              [("hex bolt", "M4 x 10", 1), ("nut", "M4", 1)],
              positions=[(s * x, y, zc) for x in (in_x0, out_x1) for y in (-315, -300, -10, 10)], status="positions",
              proposed=True, note="Nuts only in front of the front bin and between the bins (2 mm gap beside the bins)")
    if style == "vlo":
        zc = z0 + 8 + sh / 2
        J("inner_slides_through_wall", "bolt", ["slide_left_inner", "slide_right_inner", "center_wall"],
          [("hex bolt", "M4 x 16", 1), ("nut", "M4", 1), ("washer", "M4", 1)],
          positions=[(0, -inner + sl * (k_ + .5) / 6, zc) for k_ in range(6)], status="positions",
          note="One bolt through both inner slides and the centre wall")
        # The centre wall stands on the floor board, held by small angles at its two ends, in the
        # slot under the inner slides.
        cl, ct2, clen = j["center_wall_clip_mm"]
        assert cw / 2 + cl < in_x0 and base + cl < z0 + 8, "wall clips fit under the inner slides"
        clip_y = (-(inner - 40), inner - 40)
        n_ = 0
        for y in clip_y:
            for sx in (-1, 1):
                n_ += 1
                add(f"center_wall_clip_{n_}", box(ct2, clen, cl, (sx * (cw / 2 + ct2 / 2), y, base + cl / 2)).fuse(
                    box(cl, clen, ct2, (sx * (cw / 2 + cl / 2), y, base + ct2 / 2))), (.70, .72, .74), "frame", (0, 0, 0),
                    "Angle at the foot of the centre wall", "cut", f"Aluminium angle {cl:.0f} x {cl:.0f} x {ct2:g}, {clen:.0f} mm long")
        J("center_wall_clips_through", "bolt", ["center_wall", "center_wall_clip_*"],
          [("hex bolt", "M4 x 16", 1), ("nut", "M4", 1)], positions=[(-cw / 2 - ct2, y, base + .6 * cl) for y in clip_y],
          status="positions", proposed=True, note="One bolt through both clips and the wall at each end")
        J("center_wall_clips_to_floor", "screw", ["center_wall_clip_*", "floor_plate"], [("wood screw", "3.5 x 12 stainless", 1)],
          positions=[(sx * (cw / 2 + .6 * cl), y, base + ct2) for y in clip_y for sx in (-1, 1)], status="positions",
          proposed=True)
        for s in (-1, 1):
            for y in (-(half - f["vlo"]["angle_leg_mm"] / 2), half - f["vlo"]["angle_leg_mm"] / 2):
                for zz in (base + 23, base + 83):
                    body_fasteners.append({"joint": "slide_mount_to_post", "size": "M5 x 40, 18 mm sleeve", "head": "hex",
                                           "start_mm": [round(s * (inner - mt), 2), round(y, 2), round(zz, 2)],
                                           "axis": [s, 0, 0], "length_mm": round(half - inner + mt + 4, 1)})
    # Each bin is folded from PP sheet: a wall strip wrapped into a square tube with a rim flange
    # turned outwards (it stiffens the 590 mm walls and the bag folds over it), and a floor whose
    # flaps turn up inside the walls. No purchased bin of this size exists.
    fl, (hw, hh) = b["rim_flange_mm"], b["handle_slot_mm"]
    bin_shell = box(w, w, bh, (0, 0, z0 + bh / 2)).cut(box(w - 2 * bt, w - 2 * bt, bh, (0, 0, z0 + bt + bh / 2)))
    bin_shell = bin_shell.fuse(box(w + 2 * fl, w + 2 * fl, bt, (0, 0, z0 + bh - bt / 2))
                               .cut(box(w, w, bt, (0, 0, z0 + bh - bt / 2))))
    # Hand slots in the two side walls, for lifting the whole bin when a bag has torn.
    handle_z = z0 + bh - b["handle_below_rim_mm"]
    bin_shell = bin_shell.cut(box(w + 2, hw, hh, (0, 0, handle_z)))
    # Vent holes in the floor let air in under a full bag, so it pulls out without suction.
    vr, vo = b["vent_hole_diameter_mm"] / 2, b["vent_hole_offset_mm"]
    assert vo + vr < w / 2 - bt
    for vx in (-vo, vo):
        for vy in (-vo, vo):
            bin_shell = bin_shell.cut(cylinder(vr, bt + 2, (vx, vy, z0 - 1), (0, 0, 1)))
    # The bag is changed with the bin left in its drawer: the bag folds over the rim and an
    # elastic band round the outside holds it, so a full bag is lifted out, not a full bin.
    bw, bnt = b["bag_band_width_mm"], b["bag_band_thickness_mm"]
    band_z1 = z0 + bh - b["bag_band_below_rim_mm"]
    band = box(w + 2 * bnt, w + 2 * bnt, bw, (0, 0, band_z1 - bw / 2)).cut(box(w, w, bw, (0, 0, band_z1 - bw / 2)))
    assert 2 * off - w >= 2 * bnt + 20, "bands of the front and rear bin leave a finger gap"
    assert 2 * off - w - 2 * fl >= 15, "rim flanges of the front and rear bin leave a finger gap"
    assert off + w / 2 + fl < inner, "rim flange stays inside the frame posts"
    assert handle_z + hh / 2 < band_z1 - bw - 10, "hand slots sit below the bag band"
    for i, a in enumerate(DIRECTIONS, 1):
        sx, sy = math.copysign(off, math.cos(math.radians(a))), math.copysign(off, math.sin(math.radians(a)))
        add(f"bin_{i}", bin_shell.translate((sx, sy, 0)), None, "bins", (sx * .3, sy * .3 - 420, 0),
            f"Bin {i} ({p['bin_categories'][i - 1]}), folded from sheet: wall strip and floor riveted, "
            f"rim flange {fl:.0f} mm, 2 hand slots, 4 vent holes of {2 * vr:.0f} mm", "laser",
            b["sheet_material"])
        add(f"bin_bag_band_{i}", band.translate((sx, sy, 0)), (.16, .18, .20), "bins", (sx * .3, sy * .3 - 420, 0),
            "Elastic band holding the bag folded over the bin rim", "buy",
            f"Flat elastic {bw:.0f} mm, loop of about {4 * w * .85 / 10:.0f} cm")
    assert z0 + bh < h["spider_bottom"] - 20
    assert z0 + bh < h["head_lowest"] - 10, "bin rims clear the head's feet and splice plate"
    J("bin_rivets", "rivet", [f"bin_{i}" for i in range(1, 5)], [("blind rivet", "Ø4 x 10 aluminium", 1), ("washer", "M4", 1)],
      count=4 * (b["seam_rivets"] + 8), note=f"{b['seam_rivets'] + 8} per bin: {b['seam_rivets']} on the wall seam, "
      "2 per floor flap; the holes are in the DXFs")
    # The rear bin must leave the head's footprint when the drawer is fully out, so it lifts free.
    assert off + w / 2 - sl < -(p["spider_reach_mm"] + 10), "rear bin clears the head when pulled out"
    # The stiffener's flat strip: flange, web, crown, web, flange with four 90 degree bends.
    if stainless:
        bend = fold_allowance(sd, sheet, k)
        ba = bend["corner_relief"] - (sd - 2 * sheet)
        legs = [sf - 2 * sheet, sd - 4 * sheet, sc - 4 * sheet, sd - 4 * sheet, sf - 2 * sheet]
        edges = [sum(legs[:i + 1]) + ba * i for i in range(4)]
        shell["stiffener"] = {"quantity": 4, "section_mm": f"{sf:.0f}-{sd:.0f}-{sc:.0f}-{sd:.0f}-{sf:.0f}",
                              "blank_mm": [round(sum(legs) + 4 * ba, 2), round(stiffener_z[1] - stiffener_z[0], 1)],
                              "bends_from_edge_mm": [round(e + ba / 2, 2) for e in edges]}
    if style == "vlo":
        shell["stainless_mass_kg"] = round(shell.pop("volume") * f["panel_density_kg_m3"] / 1e9, 1)
        return {"body": "B", "style": "vlo", "outer_mm": [2 * co, 2 * co], "shell": shell, "fasteners": body_fasteners,
                "bin_rim_z": z0 + bh, "bin_floor_z": z0 + bt,
                "capacity_l_each": round((w - 2 * bt) ** 2 * (bh - bt) / 1e6, 1),
                "bin_center_radius": off * math.sqrt(2),
                "bag_note": "Pull a drawer out, slip off the elastic band and lift the full bag out; the bins stay in the drawer",
                "flat_pieces": {"drawer_bottom_formex_x2": [out_x1 - in_x0 - 2 * dw, tray_y1 - tray_y0 - dw],
                                "drawer_side_wall_pp_x4": [tray_y1 - tray_y0, dwh + db],
                                "drawer_back_wall_pp_x2": [out_x1 - in_x0 - 2 * dw, dwh + db]}}
    shell["stainless_mass_kg"] = round(shell.pop("volume") * f["panel_density_kg_m3"] / 1e9, 1)
    return {"body": "B", "outer_mm": [2 * co, 2 * co], "shell": shell,
            "bin_rim_z": z0 + bh, "bin_floor_z": z0 + bt,
            "capacity_l_each": round((w - 2 * bt) ** 2 * (bh - bt) / 1e6, 1),
            "bin_center_radius": off * math.sqrt(2),
            "bag_note": "Pull a drawer out, slip off the elastic band and lift the full bag out; the bins stay in the drawer",
            "flat_pieces": {"drawer_bottom_x2": [out_x1 - in_x0, tray_y1 - tray_y0],
                            "drawer_side_wall_x4": [tray_y1 - tray_y0, dwh],
                            "drawer_back_wall_x2": [out_x1 - in_x0, dwh]}}


BIN_COLORS = [(.29, .56, .72), (.79, .53, .23), (.37, .62, .42), (.60, .42, .69)]


def fill_sightlines(parts, h, info, full_fraction):
    """What a fill sensor can hear before the waste at the full level. For each part, the smallest
    angle off the sensor axis among its edge points nearer than that level (edges and corners
    scatter sound back; flat faces seen at an angle mostly reflect it away), or 0 when the part
    crosses the axis itself. Worst of the four sensors, with the plate level, out to 40 degrees
    (about where a bare 16 mm transducer stops hearing). Shadowing by other parts is ignored."""
    floor, window = info["bin_floor_z"], h["sensor_window_z"]
    full_z = floor + full_fraction * (info["bin_rim_z"] - floor)
    reach = window - full_z
    worst = {}
    for a in DIRECTIONS:
        sx, sy = h["sensor_r"] * math.cos(math.radians(a)), h["sensor_r"] * math.sin(math.radians(a))
        axis = cq.Edge.makeLine(cq.Vector(sx, sy, window - .01), cq.Vector(sx, sy, full_z))
        for part in parts:
            bb = part.shape.BoundingBox()
            near = math.dist((sx, sy, window), (min(max(sx, bb.xmin), bb.xmax), min(max(sy, bb.ymin), bb.ymax),
                                                min(max(window, bb.zmin), bb.zmax)))
            if part.name.startswith("fill_sensor_") or bb.zmin >= window or near >= reach:
                continue
            best = None
            if part.shape.distance(axis) < .01:
                best = (0.0, part.shape.distance(cq.Vertex.makeVertex(sx, sy, window)))
            else:
                for e in part.shape.Edges():
                    n = max(2, math.ceil(e.Length() / 4))
                    for k in range(n):
                        v = e.positionAt(k / (n - 1))
                        lat, dz = math.hypot(v.x - sx, v.y - sy), window - v.z
                        if dz > 0 and math.hypot(lat, dz) < reach:
                            ang = math.degrees(math.atan2(lat, dz))
                            if best is None or ang < best[0]:
                                best = (ang, math.hypot(lat, dz))
            name = part.name.rstrip("0123456789").rstrip("_")
            if best and (name not in worst or best[0] < worst[name][0]):
                worst[name] = best
    return {"window_height_mm": round(window, 1), "radial_position_mm": h["sensor_r"],
            "empty_distance_mm": round(window - floor), "full_fraction": full_fraction,
            "full_distance_mm": round(reach),
            "nearer_than_full": [{"part": k, "off_axis_degrees": round(v[0], 1), "distance_mm": round(v[1])}
                                 for k, v in sorted(worst.items(), key=lambda kv: kv[1][0]) if v[0] < 40]}


def build(p):
    parts, meta, joints = [], {}, []

    def add(name, shape, color, group, explode=(0, 0, 0), description="", process="", material=""):
        if color is None:
            color = BIN_COLORS[int(name[-1]) - 1]
        parts.append(Part(name, shape.clean(), color, group, explode, description))
        meta[name] = {"process": process, "material": material}

    def joint(jid, kind, members, hardware, positions=None, count=None, status="drawn", proposed=False, note=""):
        """One way two or more parts are held together. status: drawn (holes in the CAD and DXFs),
        positions (points known, drilled on assembly) or count (number only)."""
        joints.append({"id": jid, "kind": kind, "parts": members, "status": status, "proposed": proposed, "note": note,
                       "points": len(positions) if positions else (count or 1),
                       "positions_mm": [[round(c, 1) for c in pt] for pt in positions or []],
                       "hardware": [{"item": hw[0], "size": hw[1], "per_point": hw[2],
                                     "bought": hw[3] if len(hw) > 3 else True} for hw in hardware]})

    h = head(p, add, joint)
    info = body_b(p, add, h, joint)
    # Bolts recorded one by one become joints too, grouped by joint and size.
    for records in (h["fasteners"], info.get("fasteners", [])):
        groups = {}
        for r in records:
            groups.setdefault((r["joint"], r["size"]), []).append(r)
        for (name, size), recs in groups.items():
            kind, members, hardware = FASTENER_JOINTS[name]
            clean = size.split(",")[0].replace(" self-tapping", "").replace(" set screw", "")
            many = sum(1 for key in groups if key[0] == name) > 1
            jid = f"{name}_{clean.replace(' ', '')}" if many else name
            if name == "rail_to_post" and clean == "M8 x 15":
                members = members + ["foot_plate_*"]
            joint(jid, kind, members, [(i, clean if s == "*" else s, *rest) for i, s, *rest in hardware],
                  positions=[r["start_mm"] for r in recs])
    names = {part.name for part in parts}
    for jn in joints:
        for pat in jn["parts"]:
            assert any(n == pat or (pat.endswith("*") and n.startswith(pat[:-1])) for n in names), f"{jn['id']}: no part {pat}"
    bom = {}
    for jn in joints:
        for hw in jn["hardware"]:
            if hw["bought"]:
                e = bom.setdefault((hw["item"], hw["size"]), {"item": hw["item"], "size": hw["size"], "quantity": 0, "joints": []})
                e["quantity"] = round(e["quantity"] + hw["per_point"] * jn["points"], 2)
                e["joints"].append(jn["id"])

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
        "revision": "ab-B-E1", "units": "mm", "body": "B", "brain": "E1",
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
        "tilt_drive_fasteners": h["fasteners"],
        "body_fasteners": info.get("fasteners", []),
        "joints": joints,
        "hardware_bom": sorted(bom.values(), key=lambda e: (e["item"], e["size"])),
        "weld_points": sum(jn["points"] for jn in joints if jn["kind"] == "weld"),
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
        "motor_cable_mm": h["motor_cable_mm"],
        "camera_hidden_plate_edge_samples_of_72": h["camera_hidden_edge_samples"],
        "camera_required_full_fov_degrees": h["camera_required_full_fov_degrees"],
        "camera_sight_margin_at_throat_mm": round(h["camera_sight_margin"], 1),
        "camera_ribbon_reach_mm": round(h["camera_cable_reach"], 1),
        "camera_aim_from_vertical_degrees": round(h["camera_aim_from_vertical"], 1),
        "console_mm": [p["console_width_mm"], p["console_back_y_mm"] - p["console_chin_front_y_mm"],
                       p["console_height_mm"]],
        "display_slab_mm": p["display_slab_mm"], "display_glass_mm": p["display_glass_mm"],
        "display_top_height_mm": round(p["rim_height_mm"] + p["console_chin_height_mm"]
                                       + p["display_slab_mm"][2] * math.cos(math.radians(p["display_lean_back_degrees"])), 1),
        "console_electronics_envelopes_mm": {k: v["size"] for k, v in p["console_electronics_mm"].items()},
        "bin_landing_radius_mm": round(info["bin_center_radius"], 1),
        "fill_sensor": fill_sightlines(parts, h, info, p["fill_sensor"]["full_fraction"]),
        "bag_change": info["bag_note"],
        "flat_pieces_mm": info.get("flat_pieces", {}),
        **({"shell": info["shell"]} if "shell" in info else {}),
        "purchased_dimensions_status": p["purchased_dimensions_status"],
        "status": "Prototype CAD; every joint is listed in joints (fasteners as points, not solids); wiring is not modelled",
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


def sheet_dxf(path, outline, bends, note, hole=None, cuts=()):
    """Flat blank of a folded sheet part for a laser-and-bend shop: outline (and hole) on layer
    CUT, dashed bend centre lines on layer BEND, the fold note under the blank on layer NOTE."""
    import ezdxf
    doc = ezdxf.new("R2010", setup=True, units=4)
    for layer, color in (("CUT", 7), ("BEND", 1), ("NOTE", 3)):
        doc.layers.add(layer, color=color)
    msp = doc.modelspace()
    msp.add_lwpolyline(outline, close=True, dxfattribs={"layer": "CUT"})
    if hole:
        msp.add_circle(hole[0], hole[1], dxfattribs={"layer": "CUT"})
    for c in cuts:
        msp.add_lwpolyline(c, close=True, dxfattribs={"layer": "CUT"})
    for a, b in bends:
        msp.add_line(a, b, dxfattribs={"layer": "BEND", "linetype": "DASHED"})
    for i, line in enumerate(note):
        msp.add_text(line, height=6, dxfattribs={"layer": "NOTE"}).set_placement((0, -14 - 10 * i))
    doc.saveas(path)


def shell_dxfs(shell, out):
    """Blanks for the stainless shell: each panel folded on all four edges, and the stiffener strip."""
    t, k = shell["sheet_mm"], shell["k_factor"]
    for name, blank in shell["blanks"].items():
        fold = shell["folds"][blank["fold"]]
        b, c = fold["bend_line_from_edge"], fold["corner_relief"]
        W, H = blank["blank_mm"]
        outline = [(c, 0), (W - c, 0), (W - c, c), (W, c), (W, H - c), (W - c, H - c), (W - c, H), (c, H),
                   (c, H - c), (0, H - c), (0, c), (c, c)]
        bends = [((c, b), (W - c, b)), ((c, H - b), (W - c, H - b)), ((b, c), (b, H - c)), ((W - b, c), (W - b, H - c))]
        how = (f"closed hem {shell['hem_mm']:.0f} mm folded back on all 4 edges" if blank["fold"] == "hem" else
               f"skirt {shell['top_skirt_mm']:.0f} mm bent 90 deg down on all 4 edges, inside radius {t:.0f} mm")
        hole = ((W / 2, H / 2), blank["hole_d"] / 2) if "hole_d" in blank else None
        cuts = []
        if "slot" in blank:
            (sw, sh), past = blank["slot"]["size_mm"], (H - blank["finished_mm"][1]) / 2
            y1 = H - past - blank["slot"]["from_top_mm"]
            cuts.append([(W / 2 - sw / 2, y1 - sh), (W / 2 + sw / 2, y1 - sh), (W / 2 + sw / 2, y1), (W / 2 - sw / 2, y1)])
        sheet_dxf(out / f"{name}.dxf", outline, bends, [
            f"{name}: stainless 304, {t:.1f} mm. Finished {blank['finished_mm'][0]} x {blank['finished_mm'][1]} mm, {how}.",
            f"Blank {W} x {H} mm. Dashed = bend centre lines, K {k}. Confirm the allowance with the shop before cutting."], hole, cuts)
    if "stiffener" not in shell:
        return
    st = shell["stiffener"]
    W, L = st["blank_mm"]
    sheet_dxf(out / "drawer_stiffener_x4.dxf", [(0, 0), (W, 0), (W, L), (0, L)],
              [((x, 0), (x, L)) for x in st["bends_from_edge_mm"]], [
                  f"drawer_stiffener x{st['quantity']}: stainless 304, {t:.1f} mm, top-hat {st['section_mm']} mm outside "
                  "(flange, web, crown, web, flange). Bends 1 and 4 go one way, 2 and 3 the other.",
                  f"Blank {W} x {L} mm. Dashed = bend centre lines, K {k}, inside radius {t:.0f} mm. Confirm with the shop."])


def pattern_dxf(workplane_2d, path):
    solid = workplane_2d.extrude(1).val()
    flat_dxf(solid, path)


def add_fold_lines(path, lines, note):
    """Put a cut pattern on the shop layers used by sheet_dxf: outline on CUT, the score lines the
    shop V-grooves (not cuts) dashed on BEND, and the fold note under the blank on NOTE."""
    import ezdxf  # cadquery's exporter writes the outline only, on layer 0
    doc = ezdxf.readfile(str(path))
    for layer, color in (("CUT", 7), ("BEND", 1), ("NOTE", 3)):
        if layer not in doc.layers:
            doc.layers.add(layer, color=color)
    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[10.0, 6.0, -4.0])
    msp = doc.modelspace()
    for entity in msp:
        entity.dxf.layer = "CUT"
    for start, end in lines:
        msp.add_line(start, end, dxfattribs={"layer": "BEND", "linetype": "DASHED"})
    for i, line in enumerate(note):
        msp.add_text(line, height=6, dxfattribs={"layer": "NOTE"}).set_placement((0, -14 - 10 * i))
    doc.saveas(str(path))


def bin_patterns(p, out):
    """Flat patterns of the folded PP bin: one wall strip and one floor per bin, with fold lines."""
    b = p["bin"]
    w, bh, t = b["width_mm"], b["height_mm"], b["wall_mm"]
    fl, tab, flap = b["rim_flange_mm"], b["glue_tab_mm"], b["bottom_flap_mm"]
    (hw, hh), rh = b["handle_slot_mm"], b["rivet_hole_mm"] / 2
    sheet_w, sheet_l = b["stock_sheet_mm"]
    hole = lambda x, y, r: cylinder(r, t + 2, (x, y, -1), (0, 0, 1))
    # Wall strip: 4 faces, a glue tab at the end, the rim flange above the rim line. The flange is
    # slit at each corner fold so the 4 flange pieces turn out separately; the tab has no flange.
    length, height = 4 * w + tab, bh + fl
    strip = box(length, height, t, (length / 2, height / 2, t / 2))
    for i in range(1, 4):
        strip = strip.cut(box(2, fl, t + 2, (i * w, bh + fl / 2, t / 2)))
    strip = strip.cut(box(tab + 1, fl, t + 2, (4 * w + tab / 2 + .5, bh + fl / 2, t / 2)))
    for face in (1, 3):
        strip = strip.cut(box(hw, hh, t + 2, ((face + .5) * w, bh - b["handle_below_rim_mm"], t / 2)))
    n = b["seam_rivets"]
    for k in range(n):
        y = 40 + k * (bh - 80) / (n - 1)
        strip = strip.cut(hole(4 * w + tab / 2, y, rh)).cut(hole(tab / 2, y, rh))
    for face in range(4):
        for dx in (-70, 70):
            strip = strip.cut(hole((face + .5) * w + dx, flap / 2, rh))
    wall_path = out / "bin_wall_strip_x4.dxf"
    flat_dxf(strip, wall_path)
    add_fold_lines(wall_path, [((i * w, 0), (i * w, bh)) for i in range(1, 5)] + [((0, bh), (4 * w, bh))],
                   [f"PP {t:g} mm, cut 4. V-groove the BEND lines 2/3 deep, do not cut through.",
                    "Fold the 4 faces into a tube, glue tab inside face 1, rivet 4 mm with washers.",
                    f"Turn the {fl:g} mm rim flange outwards."])
    # Floor: the inside square plus 4 flaps that turn up inside the walls, corners cut away.
    s = w - 2 * t
    span = s + 2 * flap
    floor = box(s, span, t, (0, 0, t / 2)).fuse(box(span, s, t, (0, 0, t / 2)))
    vo, vr = b["vent_hole_offset_mm"], b["vent_hole_diameter_mm"] / 2
    for vx in (-vo, vo):
        for vy in (-vo, vo):
            floor = floor.cut(hole(vx, vy, vr))
    for ang in range(0, 360, 90):
        c, sn = round(math.cos(math.radians(ang))), round(math.sin(math.radians(ang)))
        for d in (-70, 70):
            r = s / 2 + flap / 2
            floor = floor.cut(hole(c * r - sn * d, sn * r + c * d, rh))
    floor_path = out / "bin_floor_x4.dxf"
    flat_dxf(floor, floor_path)
    o = span / 2  # flat_dxf moves the pattern so its corner sits at the origin
    add_fold_lines(floor_path, [((o - s / 2, o - s / 2), (o + s / 2, o - s / 2)), ((o + s / 2, o - s / 2), (o + s / 2, o + s / 2)),
                                ((o + s / 2, o + s / 2), (o - s / 2, o + s / 2)), ((o - s / 2, o + s / 2), (o - s / 2, o - s / 2))],
                   [f"PP {t:g} mm, cut 4. V-groove the BEND lines 2/3 deep, do not cut through.",
                    f"Turn the {flap:g} mm flaps up inside the walls, rivet 2 per flap."])
    # Nesting on a stock sheet: 2 rows of 2 wall strips across the sheet, the floors go on a second piece.
    strips_per_sheet = int(sheet_w // (height + 3)) * int(sheet_l // (length + 3))
    assert strips_per_sheet >= 4, "the 4 wall strips nest on one stock sheet"
    area = lambda shape: shape.Volume() / t / 1e6
    return {"bin_wall_strip_mm": [length, height], "bin_floor_mm": [span, span],
            "bin_wall_strips_per_stock_sheet": strips_per_sheet,
            "bin_sheet_area_m2_each": round(area(strip) + area(floor), 3),
            "bin_seam_rivets_each": n + 8}


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
    dx, cr = p["motor_cable"]["offset_x_mm"], p["motor_cable"]["radius_mm"] + .75
    collar = cq.Workplane("XY").circle(p["deck_outer_radius_mm"]).circle(h["mouth_r"]).extrude(1)
    collar = collar.faces(">Z").workplane().pushPoints([(-dx, p["motor_cable"]["shell_y_mm"]),
                                                        (dx, p["motor_cable"]["shell_y_mm"])]).hole(2 * cr)
    jh = joinery_holes(p)
    collar = collar.faces(">Z").workplane().pushPoints(jh["console_bolts"]).hole(4.5)
    collar = collar.faces(">Z").workplane().pushPoints(jh["shell_clip_rivets"]).hole(4.1)
    flat_dxf(collar.val(), out / "funnel_collar_ring.dxf")
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
    hang_y = hr - p["hanger_size_mm"] / 2 - p["motor_cable"]["hanger_gap_mm"]
    deck = deck.faces(">Z").workplane().pushPoints([(-dx, hang_y), (dx, hang_y)]).hole(2 * cr)
    deck = deck.faces(">Z").workplane().pushPoints(jh["deck_bolts"]).hole(6.5)
    deck = deck.faces(">Z").workplane().pushPoints(jh["shell_clip_rivets"] + jh["locating_clip_rivets"]).hole(4.1)
    deck = deck.faces(">Z").workplane().pushPoints([(0, p["orientation_pin_radius_mm"])]).hole(5.0)   # tap M6
    flat_dxf(deck.val(), out / "head_deck.dxf")
    return {"funnel_cone_sector_degrees_each_half": round(math.degrees(half), 2),
            "funnel_cone_inner_outer_radius_mm": [round(s_bot, 1), round(s_top, 1)]}


def export_option(p, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / "parts").mkdir(exist_ok=True)
    (out / "dxf").mkdir(exist_ok=True)
    report = {"variants": {}}
    union, meshes = {}, []
    for brain in ("E1",):
        parts, meta, metrics = build(p)
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
        export_assembly(parts, f"option_B_{brain}", out / f"assembly_{brain.lower()}.step")
        if brain == "E1":
            export_assembly(parts, f"option_B_{brain}_exploded", out / "exploded_e1.step", True)
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
                "drawer_left", "drawer_right") and not name.startswith("bin_"):
            flat_dxf(part.shape, out / "dxf" / f"{name}.dxf")
    for name, (x, y) in metrics["flat_pieces_mm"].items():
        pattern_dxf(cq.Workplane("XY").rect(x, y), out / "dxf" / f"{name}.dxf")
    if "shell" in metrics:
        shell_dxfs(metrics["shell"], out / "dxf")
    metrics_e1 = metrics
    h = head(p, lambda *a, **k: None)
    report["flat_patterns"] = funnel_patterns(p, h, out / "dxf")
    metrics_e1["bin_flat_patterns"] = bin_patterns(p, out / "dxf")
    (out / "mesh.json").write_text(json.dumps(meshes, separators=(",", ":")))
    with (out / "components.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["component", "quantity", "process", "material", "variant", "description"])
        for name, entry in union.items():
            writer.writerow([name, 1, entry["meta"]["process"], entry["meta"]["material"],
                             entry["variant"], entry["part"].description])
    lengths = {}
    vlo = p["frame"].get("style") == "vlo"
    stock = p["frame"]["vlo"]["angle_material"] if vlo else "Aluminium profile 20 x 20"
    for name, entry in union.items():
        if entry["meta"]["material"] == stock:
            bb = entry["part"].shape.BoundingBox()
            key = round(max(bb.xlen, bb.ylen, bb.zlen))
            lengths[key] = lengths.get(key, 0) + 1
    cut_list = "cut_list_slotted_angle.csv" if vlo else "cut_list_profile_20x20.csv"
    with (out / cut_list).open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["profile", "length_mm", "quantity"])
        for length, qty in sorted(lengths.items(), reverse=True):
            writer.writerow(["Slotted steel angle 3x3 x 2 (26 x 26 real)" if vlo else "Aluminium 20 x 20", length, qty])
        report["profile_total_length_mm"] = sum(k * v for k, v in lengths.items())
    (out / "dimensions.json").write_text(json.dumps(metrics_e1, indent=2) + "\n")
    report["cadquery_version"] = cq.__version__
    (out / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    return metrics_e1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", type=Path, default=ROOT / "cad/parameters_ab.json")
    parser.add_argument("--output", type=Path, default=ROOT / "ab")
    args = parser.parse_args()
    p = json.loads(args.parameters.read_text())
    print("Building option B (E1), checking 24 yaw and tilt poses…", flush=True)
    metrics = export_option(p, args.output / "b_frame")
    print(json.dumps({k: metrics[k] for k in (
        "capacity_l_each_provisional", "servo_load_fraction_of_stall", "max_item_kg_at_half_stall",
        "camera_hidden_plate_edge_samples_of_72", "belt_center_distance_mm")}), flush=True)
    print("All poses passed without positive-volume overlaps.", flush=True)

if __name__ == "__main__":
    main()
