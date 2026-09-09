#!/usr/bin/env python3
"""Routing step 4 -- the power distribution.

Two passes.

**Trunks** (`TRUNKS`) are the deliberate high-current and source-chain paths,
routed in the order the current actually flows and on the component layer, at
widths chosen from the IPC-2221 table in `docs/decisions/actuator-pcb-setup.md`
S3 rather than from the net class alone -- G3 says power is deliberate traces,
G1c says widen locally.  The 24 V bus, the motor bus, both switcher SW nodes
and both switcher output nodes are here, and so is every source-chain
capacitor step 2 deferred: the flow reads source pad -> cap pad -> next pin,
in line, no via inside a switching loop.

**Distribution** then completes each rail with the maze router, joining what
the trunks left to the 49 feed vias step 2 planted.  Rails carry a mild F.Cu
cost bias so the long hauls settle on B.Cu, under the traffic, which is what
the feed vias were put there for.

Per-via current budget is 1.0 A (setup S3).  `VIA_BUDGET` records the design
current for every rail that changes layer, and `tools/route_check.py --power`
proves the counts.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402

# --------------------------------------------------------------------------
# Design currents.  25 W peak at 24 V = 1.04 A for the whole board (REQ-EL-03);
# the motor branch is sized on the 3 A peak the setup file assumed for the
# phases (1.23 A static, prelim calc).  n = ceil(I / 1.0 A), minimum 2 on any
# rail that changes layer.
# --------------------------------------------------------------------------
VIA_BUDGET = {
    "/power_entry_24v/V24_IN": 3.0,
    "Net-(F201-Pad2)": 3.0,
    "Net-(Q201-D)": 3.0,
    "/power_entry_24v/V24_PROT": 3.0,
    "/power_entry_24v/V0_IN": 3.0,
    "/power_entry_24v/+24V_SW": 3.0,
    "Net-(R1101-Pad2)": 3.0,
    "/motor_drive/V24_MOT": 3.0,
    "/motor_drive/MOTOR_U": 3.0,
    "/motor_drive/MOTOR_V": 3.0,
    "/motor_drive/MOTOR_W": 3.0,
    # The low-side source nets carry the leg's full current from the FET
    # source into its shunt, the same 3 A the phase node sees.  They are named
    # after the FET rather than the phase, which is why they were missed.
    "Net-(Q1102-S_3)": 3.0,
    "Net-(Q1104-S_3)": 3.0,
    "Net-(Q1106-S_3)": 3.0,
    "/power_entry_24v/V24_LOGIC": 0.3,
    "Net-(U301-SW)": 0.7,
    "Net-(C306-Pad1)": 0.7,
    "/power_rails/+6V0": 0.6,
    "Net-(U302-SENSE)": 0.3,
    "Net-(U303-SENSE)": 0.3,
    "+5V": 0.3,
    "+5VA": 0.3,
    "Net-(U304-SW)": 1.5,
    "Net-(C320-Pad1)": 1.5,
    "+3V3": 1.5,
    "+3V3A": 0.2,
    "/mcu/+3V3_USB": 0.3,
    "/mcu/+1V8_USB": 0.2,
    "/linear_encoder/+5V_ENC": 0.3,
    "/motor_drive/VENC": 0.3,
    "/motor_drive/VM_DRV": 0.1,
}

# (net, [(ref, pad), ...], width mm)
TRUNKS = [
    # -- 24 V entry: jack -> fuse -> common-mode choke -> reverse-protect FET
    ("/power_entry_24v/V24_IN", [("J201", "1"), ("J201", "2")], 1.0),
    ("/power_entry_24v/V24_IN", [("J201", "2"), ("F201", "1")], 1.0),
    ("/power_entry_24v/V24_IN", [("F201", "1"), ("TP201", "1")], 0.5),
    ("Net-(F201-Pad2)", [("F201", "2"), ("L201", "1")], 1.0, (R.F, R.B)),
    ("Net-(Q201-D)", [("L201", "2"), ("Q201", "5")], 1.0),
    ("/power_entry_24v/V0_IN", [("J201", "3"), ("J201", "4")], 1.0),
    ("/power_entry_24v/V0_IN", [("J201", "4"), ("L201", "4")], 1.0, (R.F, R.B)),
    # the drain-side reservoir pair sits in line on the drain node
    ("Net-(Q201-D)", [("Q201", "5"), ("C201", "1"), ("C202", "1")], 0.8),
    # -- protected 24 V: TVS first (closest to the source), then the bulk
    ("/power_entry_24v/V24_PROT", [("Q201", "1"), ("D201", "2")], 1.0),
    ("/power_entry_24v/V24_PROT", [("Q201", "1"), ("C206", "1"), ("C205", "1")], 0.8),
    ("/power_entry_24v/V24_PROT", [("C205", "1"), ("C204", "1")], 1.0),
    ("/power_entry_24v/V24_PROT", [("C204", "1"), ("R204", "1")], 1.0),
    ("/power_entry_24v/V24_PROT", [("Q201", "1"), ("R203", "1")], 1.0),
    # -- the switched 24 V branch and the motor-bus current break
    ("/power_entry_24v/+24V_SW", [("R203", "2"), ("TP203", "1")], 0.5),
    # 45 mm across the whole regulator block: on B.Cu, under the traffic.
    # On F.Cu this trace slices the power_rails block in half diagonally and
    # walls off every local link in it.
    ("/power_entry_24v/+24V_SW", [("R203", "2"), ("R1101", "1")], 1.0,
     (R.B,)),
    ("Net-(R1101-Pad2)", [("R1101", "2"), ("R1102", "1")], 1.0),
    # -- motor bus: break -> DC-link store -> across the high-side drains
    ("/motor_drive/V24_MOT", [("R1102", "2"), ("TP1101", "1")], 1.0),
    ("/motor_drive/V24_MOT", [("TP1101", "1"), ("TP1102", "1")], 1.0),
    ("/motor_drive/V24_MOT", [("TP1102", "1"), ("C1101", "1")], 1.0),
    ("/motor_drive/V24_MOT", [("C1101", "1"), ("C1102", "1")], 1.0),
    ("/motor_drive/V24_MOT", [("C1102", "1"), ("C1103", "1")], 1.0),
    ("/motor_drive/V24_MOT", [("C1103", "1"), ("C1104", "1")], 1.0),
    # each leg is fed from the store directly above it
    ("/motor_drive/V24_MOT", [("C1101", "1"), ("Q1105", "5_6_7_8")], 1.0),
    ("/motor_drive/V24_MOT", [("C1102", "1"), ("Q1103", "5_6_7_8")], 1.0),
    ("/motor_drive/V24_MOT", [("C1103", "1"), ("Q1101", "5_6_7_8")], 1.0),
    # per-leg bypass, in line off its own drain -- the commutation loop
    ("/motor_drive/V24_MOT", [("Q1105", "5_6_7_8"), ("C1123", "1")], 0.8),
    ("/motor_drive/V24_MOT", [("C1123", "1"), ("C1124", "1")], 0.8),
    ("/motor_drive/V24_MOT", [("Q1103", "5_6_7_8"), ("C1121", "1")], 0.8),
    ("/motor_drive/V24_MOT", [("C1121", "1"), ("C1122", "1")], 0.8),
    ("/motor_drive/V24_MOT", [("Q1101", "5_6_7_8"), ("C1119", "1")], 0.8),
    ("/motor_drive/V24_MOT", [("C1119", "1"), ("C1120", "1")], 0.8),
    # driver supply take-off and its own current break
    # driver supply take-off: leg-A drain is the nearest V24_MOT copper to
    # the break resistor, and it carries only the DRV8323's own ~30 mA
    ("/motor_drive/V24_MOT", [("Q1101", "5_6_7_8"), ("R1114", "1")], 0.6,
     (R.F, R.B)),
    ("/motor_drive/VM_DRV", [("R1114", "2"), ("TP1106", "1")], 0.5),
    # the DRV's own VM pin is a 0.25 mm pad on a 0.5 mm pitch row: the bus
    # narrows for the last 8 mm, which is what it carries (~30 mA)
    ("/motor_drive/V24_MOT", [("R1114", "1"), ("U1101", "5")], 0.25,
     (R.F, R.B)),
    # -- buck 1: VIN caps came in step 2; SW node, boot, output, sense
    ("Net-(U301-SW)", [("U301", "8"), ("L301", "1")], 0.65),
    ("Net-(U301-SW)", [("L301", "1"), ("C305", "2")], 0.40),
    ("Net-(U301-BOOT)", [("C305", "1"), ("U301", "7")], 0.30),
    ("Net-(C306-Pad1)", [("L301", "2"), ("C306", "1")], 0.80),
    ("Net-(C306-Pad1)", [("C306", "1"), ("C308", "1")], 0.80),
    ("Net-(C306-Pad1)", [("C306", "1"), ("C307", "1")], 0.80),
    ("Net-(C306-Pad1)", [("C307", "1"), ("R305", "1")], 0.80),
    ("Net-(C306-Pad1)", [("C308", "1"), ("R303", "1")], 0.25),
    ("/power_rails/+6V0", [("R305", "2"), ("TP302", "1")], 0.50, (R.F, R.B)),
    # both LDOs take VIN on two adjacent pins -- tie them at the package
    ("/power_rails/+6V0", [("U302", "8"), ("U302", "5")], 0.30),
    ("/power_rails/+6V0", [("U303", "8"), ("U303", "5")], 0.30),
    # -- buck 2
    ("Net-(U304-SW)", [("U304", "8"), ("L302", "1")], 0.65),
    ("Net-(U304-SW)", [("L302", "1"), ("C319", "2")], 0.40),
    ("Net-(U304-BOOT)", [("C319", "1"), ("U304", "7")], 0.30),
    ("Net-(C320-Pad1)", [("L302", "2"), ("C320", "1")], 0.80),
    ("Net-(C320-Pad1)", [("C320", "1"), ("C322", "1")], 0.80),
    ("Net-(C320-Pad1)", [("C320", "1"), ("C321", "1")], 0.80),
    ("Net-(C320-Pad1)", [("C321", "1"), ("R312", "1")], 0.80),
    ("Net-(C320-Pad1)", [("C322", "1"), ("R310", "1")], 0.25),
    ("+3V3", [("R312", "2"), ("TP306", "1")], 0.50),
    # -- the two LDOs: output pin -> its own caps -> the current-break link
    ("Net-(U302-SENSE)", [("U302", "1"), ("U302", "2")], 0.30),
    ("Net-(U302-SENSE)", [("U302", "2"), ("C310", "1")], 0.50),
    ("Net-(U302-SENSE)", [("C310", "1"), ("C311", "1")], 0.50),
    ("Net-(U302-SENSE)", [("C311", "1"), ("R306", "1")], 0.50),
    ("+5V", [("R306", "2"), ("TP303", "1")], 0.50),
    ("Net-(U303-SENSE)", [("U303", "1"), ("U303", "2")], 0.30),
    ("Net-(U303-SENSE)", [("U303", "2"), ("C313", "1")], 0.50),
    ("Net-(U303-SENSE)", [("C313", "1"), ("C314", "1")], 0.50),
    ("Net-(U303-SENSE)", [("C314", "1"), ("R307", "1")], 0.50),
    ("+5VA", [("R307", "2"), ("TP304", "1")], 0.50),
    # -- +3V3A: the ferrite's output caps sit in line at the MCU (P1-05)
    ("+3V3A", [("FB301", "2"), ("C323", "1")], 0.50),
    ("+3V3A", [("C323", "1"), ("C324", "1")], 0.50),
    # the PHY's four +3V3_USB pins on the east row, tied along the package
    ("/mcu/+3V3_USB", [("U1002", "11"), ("U1002", "14")], 0.24),
    # -- +5V_ENC current break (the 70 mm haul to R601 is the distribution
    # pass's job, on B.Cu, not a trunk)
    ("Net-(FB601-Pad1)", [("R601", "2"), ("FB601", "1")], 0.50),
]

# Rails completed by the maze router after the trunks, in this order.
# (net, width, F.Cu cost bias -- higher pushes the long hauls onto B.Cu)
RAILS = [
    ("/power_entry_24v/V24_IN", 1.00, 0.0),
    ("Net-(F201-Pad2)", 1.00, 0.0),
    ("/power_entry_24v/V0_IN", 1.00, 0.0),
    ("Net-(Q201-D)", 0.80, 0.0),
    ("/power_entry_24v/V24_PROT", 0.50, 0.0),
    ("/power_entry_24v/+24V_SW", 0.50, 0.0),
    ("/motor_drive/V24_MOT", 1.00, 0.0),
    ("/motor_drive/VM_DRV", 0.50, 0.2),
    ("/power_entry_24v/V24_LOGIC", 0.50, 0.35),
    ("Net-(C306-Pad1)", 0.50, 0.0),
    ("/power_rails/+6V0", 0.50, 0.35),
    ("Net-(U302-SENSE)", 0.50, 0.0),
    ("Net-(U303-SENSE)", 0.50, 0.0),
    ("+5V", 0.50, 0.35),
    ("+5VA", 0.50, 0.35),
    ("Net-(C320-Pad1)", 0.50, 0.0),
    ("+3V3", 0.50, 0.35),
    ("+3V3A", 0.50, 0.20),
    ("Net-(FB601-Pad1)", 0.50, 0.0),
    ("/linear_encoder/+5V_ENC", 0.50, 0.30),
    ("/motor_drive/VENC", 0.50, 0.30),
    ("/mcu/+3V3_USB", 0.50, 0.30),
    ("/mcu/+1V8_USB", 0.40, 0.30),
]

# Local power-block sense / enable / power-good nets: thin, and kept away from
# the SW nodes by routing them after the rails are down.
SENSE = ["Net-(U301-EN)", "Net-(U301-FB)", "Net-(U301-PG)",
         "Net-(U304-EN)", "Net-(U304-FB)", "Net-(U304-PG)",
         "Net-(U302-PG)", "Net-(U303-PG)", "/power_rails/RAIL_PGOOD",
         "Net-(D303-Pad1)", "Net-(Q201-G)", "Net-(D202-Pad1)",
         "Net-(J201-SH)", "Net-(U1002-RBIAS)"]


def grp(board, ref, num):
    out = []
    for f in board.GetFootprints():
        if f.GetReference() != ref:
            continue
        for p in f.Pads():
            if p.GetNumber() == num and R.pad_copper_layers(p):
                out.append((ref, p))
    if not out:
        raise KeyError(f"{ref}.{num}")
    return out


def grp_min_dim(g):
    bs = [R.pad_bbox(p) for _r, p in g]
    bb = (min(b[0] for b in bs), min(b[1] for b in bs),
          max(b[2] for b in bs), max(b[3] for b in bs))
    return min(bb[2] - bb[0], bb[3] - bb[1])


def main():
    board = R.load()
    obst = R.Obstacles(board)
    print(f"   {obst.reserve_pin_escapes(board)} fine-pitch pin escape lanes held")
    maze = R.Maze(obst)

    print("== fan-out: fine-pitch pins first, so nothing can cap a lane")
    R.escape_pass(board, obst)

    print("\n== trunks (component layer unless noted, current-flow order)")
    fails = []
    for entry in TRUNKS:
        net, seq, w = entry[0], entry[1], entry[2]
        lay = entry[3] if len(entry) > 3 else (R.F,)
        for a, b in zip(seq, seq[1:]):
            ln, width, nv, direct = R.link(board, obst, maze, net, a, b, w,
                                           layers=lay, margin=14, via_cost=45)
            if ln is None:
                fails.append((net, a, b, w))
                print(f"   FAIL {net:<28} {a[0]}.{a[1]} -> {b[0]}.{b[1]} "
                      f"@{w}")
                continue
            print(f"   {net:<28} {a[0]+'.'+a[1]:<14} -> "
                  f"{b[0]+'.'+b[1]:<14} {width:5.2f} mm  {ln:6.2f} mm"
                  f"  (direct {direct:5.2f}, vias {nv})")

    print("\n== rail distribution (feed vias are the anchors)")
    for net, w, bias in RAILS:
        f = R.connect_net(board, obst, maze, net, width=w, via_cost=55,
                          margin=18, layer_bias={R.F: bias})
        n = len(R.pad_nodes(board, net))
        print(f"   {net:<30} {n:3d} nodes @ {w:4.2f} mm"
              + ("  UNROUTED " + ",".join(sorted(set(f))) if f else ""))

    print("\n== power-block sense / enable / power-good")
    for net in SENSE:
        w = R.net_width(net)
        f = R.connect_net(board, obst, maze, net, width=max(w, 0.20),
                          via_cost=60, margin=20)
        print(f"   {net:<30}" + ("  UNROUTED " + ",".join(sorted(set(f)))
                                 if f else "  ok"))

    # Reload from disk before repairing.  A board object that has taken many
    # hundreds of Add()s behaves differently from the same board read back --
    # five nets that connect_net refuses in-run route first time from a fresh
    # read - so the repair pass always works on a re-read board.
    R.refill(board)
    R.save(board)
    board = R.load()

    print("\n== repair pass (fresh read, fresh obstacle model)")
    todo = [n for n in ([e[0] for e in TRUNKS] + [r[0] for r in RAILS] + SENSE)
            if not R.net_is_whole(board, n)]
    seen, order = set(), []
    for n in todo:
        if n not in seen:
            seen.add(n)
            order.append(n)
    left = R.repair(board, order,
                    widths={r[0]: r[1] for r in RAILS})
    print(f"   retried {len(order)}: {order}")
    if left:
        print(f"   STILL OPEN: {left}")

    if fails:
        print("\nTRUNK FAILURES:", fails)
    R.refill(board)
    R.save(board)
    print("\nunconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
