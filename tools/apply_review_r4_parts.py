#!/usr/bin/env python3
"""Round 4, the part-level items.

7,8 `linear_encoder`: `R608` and `R609` go. Review round R6 asked for parallel
    DNP positions across `R601`, `FB601` and `D601`; the captain has reversed
    two of the three. `R608` sat across `R601`, and both are the same 0603 - so
    to fit a shunt you replace `R601` rather than populate a second footprint
    beside it. `R609` bypassed `FB601`, which can be lifted and bridged. `D602`
    stays: it is a second clamp *position*, for a different part number or a
    bidirectional device, which is not the same argument.

13. `motor_drive`: `R1128`..`R1133` were the only 100R in the design on a
    project-local symbol - `faff2_passives:RES_TF_100R_0603_H`, a pre-rotated
    variant round 2 added so they could lie horizontally without instance
    rotation. Nine other 100R across mcu, ui_io and motor_drive use the house
    `Amodo_Resistors:RES_TF_100R_0603`. They unify onto it, rotated 90 with
    their field angles compensated to 270, which AGENTS.md permits on that
    exact condition. The local variant then has no users and is deleted.

A3. `motor_drive`: `R1120` and its `+3V3` flag drag 7.62 mm down into the clear
    space below, which is the captain's answer to the arrow the gate-drive bus
    was crossing - no bus reroute needed.

Re-runnable from a pinned base.
"""
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "ce34470"
D = "hardware/kicad/faff2_cbs1/"
STD_100R = "Amodo_Resistors:RES_TF_100R_0603"
UNIFY = ["R1128", "R1129", "R1130", "R1131", "R1132", "R1133"]

ENC_DEL_SYMS = ["R608", "R609"]
ENC_DEL_WIRES = [((25.40, 149.86), (38.10, 149.86)),
                 ((25.40, 154.94), (38.10, 154.94)),
                 ((25.40, 157.48), (44.45, 157.48)),
                 ((44.45, 157.48), (44.45, 158.75)),
                 ((25.40, 165.10), (44.45, 165.10)),
                 ((44.45, 165.10), (44.45, 163.83))]
# each of these was a genuine tee only because of the part that has just gone
ENC_DEL_JUNCTIONS = [(25.40, 149.86), (25.40, 154.94),
                     (25.40, 157.48), (25.40, 165.10)]
ENC_TEXT = [(
    "R608 / R609 / D602 are DNP parallel positions\\n"
    "on R601 / FB601 / D601.  Fit a shunt at R608 and\\n"
    "lift R601 to meter head current in circuit; fit\\n"
    "R609 to bypass the bead; D602 is a second SC-79\\n"
    "clamp position.  None fitted by default.",
    "D602 is a DNP second SC-79 clamp position on\\n"
    "D601 - a different clamp voltage, or a\\n"
    "bidirectional part, without reworking D601's\\n"
    "pads.  Not fitted by default.\\n"
    "To meter head current, replace R601 with a\\n"
    "shunt.  To bypass the bead, lift FB601.")]

MOTOR_MOVE = [("R1120", 0, 7.62), ("#PWR1131", 0, 7.62)]
# dropping R1120 put its reference 0.02 mm off R1117's body; the gap between
# the two bodies is 6.85 mm for 5.95 mm of text, so it centres in it
MOTOR_FIELDS = [("R1120", "Reference", 164.90, 187.32)]

MOTOR_WIRES = [((166.37, 175.26), (166.37, 179.07),
                (166.37, 182.88), (166.37, 186.69)),
               ((166.37, 184.15), (166.37, 196.85),
                (166.37, 191.77), (166.37, 196.85))]


def main():
    path = D + "linear_encoder.kicad_sch"
    text = E.normalise(subprocess.run(["git", "show", BASE + ":" + path],
                                      check=True, capture_output=True,
                                      text=True).stdout)
    for old, new in ENC_TEXT:
        text = E.edit_note(text, old, new)
    for ref in ENC_DEL_SYMS:
        text = E.del_symbol(text, ref)
    for p, q in ENC_DEL_WIRES:
        text = E.del_wire(text, p, q)
    for p in ENC_DEL_JUNCTIONS:
        text = E.del_point(text, "junction", p)
    open(path, "w", encoding="utf-8", newline="\n").write(text)
    print("linear_encoder: dropped %s" % ", ".join(ENC_DEL_SYMS))

    path = D + "motor_drive.kicad_sch"
    text = E.normalise(subprocess.run(["git", "show", BASE + ":" + path],
                                      check=True, capture_output=True,
                                      text=True).stdout)
    for ref in UNIFY:
        text = E.set_lib_id(text, ref, STD_100R)
        text = E.set_rotation(text, ref, 90, 270)
    for ref, dx, dy in MOTOR_MOVE:
        text = E.move_symbol(text, ref, dx, dy)
    for p, q, np_, nq in MOTOR_WIRES:
        text = E.move_wire(text, p, q, np_, nq)
    for ref, prop, x, y in MOTOR_FIELDS:
        text = E.set_field(text, ref, prop, x, y)
    # the pre-rotated local variant now has no users on this sheet
    text = E.del_lib_symbol(text, "faff2_passives:RES_TF_100R_0603_H")
    open(path, "w", encoding="utf-8", newline="\n").write(text)
    print("motor_drive: %d resistors onto the house 100R; R1120 dropped 7.62"
          % len(UNIFY))


if __name__ == "__main__":
    main()
