#!/usr/bin/env python3
"""Write the FAFF 2 CBs_1 net classes and DRC constraints into faff2_cbs1.kicad_pro.

Net classes and DRC floors live in the project file, not the board (see the
pcb-layout-style skill).  This edits only `net_settings` and
`board.design_settings`; everything else in the .kicad_pro is left untouched.

The numbers come from three places, all recorded in
docs/decisions/actuator-pcb-setup.md:
  * captain's rulings for this board (via 0.6/0.20, 6/6 mil default),
  * house guidelines G2/G3/G12,
  * JLCPCB's published capability sheet for 4-layer 1 oz.

KiCad 9 only.  AGENTS.md: an open KiCad session rewrites .kicad_pro wholesale on
save -- close KiCad before running this.

Usage:  python3 tools/gen_pcb_rules.py
"""

import glob
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRO = os.path.join(REPO, "hardware", "kicad", "faff2_cbs1", "faff2_cbs1.kicad_pro")

MIL6 = 0.1524          # captain's 6 mil default trace/space
VIA_D, VIA_DRILL = 0.6, 0.20    # captain's single via definition (G2 for this board)

# Net classes.  Lower `priority` wins where several patterns match a net.
#
# Every class keeps the 6 mil clearance.  A class clearance has to be satisfiable by
# the finest-pitch pads that carry the class's nets, and it is not: 0.5 mm pitch pads
# on the LQFP100, the DRV8323 QFN and the ADS1235 QFN sit 0.20-0.25 mm apart, so a
# 0.25-0.30 mm class clearance fails DRC on the pads themselves before a single track
# is drawn.  Generous spacing between these nets is routing discipline, recorded in the
# decisions file -- not a class constraint the pads cannot meet.
CLASSES = [
    dict(name="Motor", priority=10, track_width=1.0, clearance=MIL6,
         description="Motor phases and the 24 V motor branch: up to ~3 A peak"),
    dict(name="RF50", priority=20, track_width=0.37, clearance=MIL6,
         description="50 ohm microstrip on F.Cu over the L2 GND plane (SMA + U.FL)"),
    dict(name="USB_HS", priority=30, track_width=0.30, clearance=MIL6,
         diff_pair_width=0.30, diff_pair_gap=0.20,
         description="USB 2.0 HS D+/D-: 90 ohm differential microstrip"),
    dict(name="Power", priority=40, track_width=0.5, clearance=MIL6,
         description="G3 power rails: deliberate 0.5 mm traces on the outer layers"),
    dict(name="Analog", priority=50, track_width=0.25, clearance=MIL6,
         description="Bridge, RTD and reference nets: extra clearance from digital"),
    dict(name="Signal", priority=60, track_width=MIL6, clearance=MIL6,
         description="General signals, 6/6 mil"),
]

# Net-name patterns -> class.  Evaluated by the class priorities above.
PATTERNS = [
    # --- motor
    ("/motor_drive/MOTOR_U", "Motor"),
    ("/motor_drive/MOTOR_V", "Motor"),
    ("/motor_drive/MOTOR_W", "Motor"),
    ("/motor_drive/V24_MOT", "Motor"),
    ("/motor_drive/VM_DRV", "Motor"),
    # --- 50 ohm
    ("/mcu/SYNC_TRIG", "RF50"),
    ("Net-(J503-In)", "RF50"),
    ("Net-(J504-In)", "RF50"),
    # --- USB high speed
    ("/mcu/USB_DM", "USB_HS"),
    ("/mcu/USB_DP", "USB_HS"),
    # --- power rails
    ("+3V3", "Power"),
    ("+3V3A", "Power"),
    ("+5V", "Power"),
    ("+5VA", "Power"),
    ("/power_entry_24v/*", "Power"),
    ("/power_rails/+6V0", "Power"),
    ("/mcu/+3V3_USB", "Power"),
    ("/mcu/+1V8_USB", "Power"),
    ("/linear_encoder/+5V_ENC", "Power"),
    ("/motor_drive/VENC", "Power"),
    # --- analog sense chains
    ("Net-(U501B-*)", "Analog"),      # ADS1235 bridge inputs and references
    ("Net-(U701-AIN*)", "Analog"),    # ADS1120 RTD inputs
    ("Net-(U701-REF*)", "Analog"),
    ("Net-(J501-*)", "Analog"),       # load cell terminal block
    ("Net-(J701-*)", "Analog"),       # temp sensor terminal blocks
    ("Net-(J702-*)", "Analog"),
    ("/linear_encoder/ENC_VREF", "Analog"),
]

# DRC constraints.  G12 floors where the house is stricter than JLC; JLC's own
# capability numbers where it is the binding constraint.
RULES = {
    "min_clearance": 0.15,                 # G12 floor (JLC allows 0.09 at 1 oz)
    "min_track_width": 0.15,               # G12 floor
    "min_connection": 0.0,
    "min_via_diameter": VIA_D,             # single via definition, G2
    "min_through_hole_diameter": VIA_DRILL,
    "min_via_annular_width": 0.20,         # JLC "recommended 0.20 or above"
    "min_hole_clearance": 0.25,
    "min_hole_to_hole": 0.45,              # JLC PTH hole-to-hole
    "min_copper_edge_clearance": 0.30,     # JLC needs >= 0.20; margin for the router
    "min_microvia_diameter": 0.2,
    "min_microvia_drill": 0.1,
    "min_resolved_spokes": 2,
    "min_silk_clearance": 0.0,             # silk tidy-up belongs to the placement gate
    "min_text_height": 0.8,                # legible references (house silk rule)
    "min_text_thickness": 0.08,
    "solder_mask_to_copper_clearance": 0.0,
    "min_groove_width": 0.0,
    "max_error": 0.005,
    "allow_blind_buried_vias": False,      # JLC standard 4-layer: through vias only
    "allow_microvias": False,
    "use_height_for_length_calcs": True,
}


def main():
    locks = glob.glob(os.path.join(os.path.dirname(PRO), "*.lck"))
    if locks:
        sys.exit(f"KiCad lock files present, refusing to edit project settings: {locks}")

    with open(PRO) as f:
        pro = json.load(f)

    default = dict(
        name="Default", priority=2147483647,
        clearance=MIL6, track_width=MIL6,
        via_diameter=VIA_D, via_drill=VIA_DRILL,
        microvia_diameter=0.3, microvia_drill=0.1,
        diff_pair_width=0.30, diff_pair_gap=0.20, diff_pair_via_gap=0.25,
        bus_width=12, line_style=0, wire_width=6,
        pcb_color="rgba(0, 0, 0, 0.000)", schematic_color="rgba(0, 0, 0, 0.000)",
    )
    classes = [default]
    for c in CLASSES:
        nc = dict(default)
        nc.pop("description", None)
        nc.update(c)
        # every class shares the one via definition (G2)
        nc["via_diameter"], nc["via_drill"] = VIA_D, VIA_DRILL
        classes.append(nc)

    known = {c["name"] for c in classes}
    for pat, cls in PATTERNS:
        if cls not in known:
            sys.exit(f"pattern {pat!r} refers to unknown net class {cls!r}")

    pro["net_settings"]["classes"] = classes
    pro["net_settings"]["netclass_patterns"] = [
        {"pattern": p, "netclass": c} for p, c in PATTERNS
    ]
    pro["net_settings"].setdefault("meta", {"version": 4})

    ds = pro["board"].setdefault("design_settings", {})
    # Without this version stamp KiCad's settings loader silently discards the whole
    # design_settings block and DRC quietly runs on built-in defaults instead.
    ds["meta"] = {"version": 2}
    ds["rules"] = RULES
    ds["track_widths"] = [0.0, MIL6, 0.25, 0.30, 0.37, 0.5, 1.0]
    ds["via_dimensions"] = [{"diameter": VIA_D, "drill": VIA_DRILL}]
    ds["diff_pair_dimensions"] = [{"width": 0.30, "gap": 0.20, "via_gap": 0.25}]
    ds["zones_allow_external_fillets"] = False

    with open(PRO, "w") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")

    print(f"wrote {PRO}")
    print(f"  {len(classes)} net classes, {len(PATTERNS)} patterns")
    print(f"  via {VIA_D}/{VIA_DRILL} mm -> annulus {(VIA_D - VIA_DRILL) / 2:.3f} mm")


if __name__ == "__main__":
    main()
