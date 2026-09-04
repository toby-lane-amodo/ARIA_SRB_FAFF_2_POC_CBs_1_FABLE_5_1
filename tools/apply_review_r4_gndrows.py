#!/usr/bin/env python3
"""Round 4, the design-wide rule: parallel parts share ONE ground-flag height.

The captain's example of the defect is `C1101`..`C1104` on `motor_drive` - four
capacitors in parallel across the same rail, their ground flags on four
different heights, which draws as a staircase. `C1113`/`C1114` are the good
case. `tools/gnd_rows.py` finds every instance; this applies the fix.

Where a row's members already agree, the odd one out moves to join them. Where
they do not, the target is the height that makes the bottom stub match the top
one, which is what `schematic-style`'s "equal wire stubs both ends" asks for
anyway - so `C1101`..`C1104`'s flags all come up to 71.12, one grid step below
the capacitor pins, instead of trailing 3.81 to 8.89 mm below them.

Two of these were already on somebody's list: `#PWR323` sat 0.25 mm off R308's
body, which is the overcrowding the captain flagged, and `#PWR1105` was 2.54 mm
out of line because round 3 moved it there to make room for a label. The rule
supersedes that local fix.

Re-runnable from a pinned base.
"""
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "95ddd35"          # round 3's last commit
D = "hardware/kicad/faff2_cbs1/"

# (gnd ref, new y, stub top y) - the stub keeps its top end and follows the flag
ROWS = {
    "power_rails": [
        # +3V3A row: C323/C324 agree at 191.77, TP307's flag was 1.27 high
        ("#PWR357", 287.02, 190.50, 191.77, 187.96),
        # V24_LOGIC input row: C302/C303 agree at 43.18, C301's trailed 3.81
        ("#PWR302", 30.48, 46.99, 43.18, 40.64),
        # the same row on the +3V3 buck - and this one also puts 3.81 mm
        # between the flag and R308, which it was grazing by 0.25
        ("#PWR323", 30.48, 154.94, 151.13, 148.59),
    ],
    "motor_drive": [
        # the captain's example: four flags, four heights, now all one grid
        # step below the capacitor pins
        ("#PWR1102", 57.15, 73.66, 71.12, 69.85),
        ("#PWR1103", 68.58, 78.74, 71.12, 69.85),
        ("#PWR1104", 80.01, 77.47, 71.12, 69.85),
    ],
}


# Levelling the two V24_LOGIC rows moves each flag's name up beside the EN
# divider's top resistor, 0.26 mm inside it - the same overcrowding the captain
# flagged at R308, arriving from the other direction. The divider column has
# open paper to its left, so it moves 2.54 mm there and both clear by 2.28. The
# V24_LOGIC label stays where it is, on the horizontal that now runs under it.
# The whole divider goes, ground flag included: moving the bottom resistor
# without its flag detaches it, which the netlist catches and ERC does not
# always - R302 and R309 came off GND on the first attempt.
DIVIDERS = [
    # (sheet, dy applied to every coordinate below, top R, bottom R, its flag)
    ("power_rails", 0.0, "R301", "R302", "#PWR305"),
    ("power_rails", 107.95, "R308", "R309", "#PWR326"),
]
DIV_WIRES = [((27.94, 33.02), (27.94, 45.72), (25.40, 33.02), (25.40, 45.72)),
             ((27.94, 33.02), (30.48, 33.02), (25.40, 33.02), (30.48, 33.02)),
             ((27.94, 50.80), (27.94, 63.50), (25.40, 50.80), (25.40, 63.50)),
             ((27.94, 63.50), (27.94, 67.31), (25.40, 63.50), (25.40, 67.31)),
             ((27.94, 63.50), (53.34, 63.50), (25.40, 63.50), (53.34, 63.50)),
             ((27.94, 72.39), (27.94, 76.20), (25.40, 72.39), (25.40, 76.20))]
DIV_JUNCTION = (27.94, 63.50), (25.40, 63.50)


def shift_divider(text, dy, r_top, r_bot, gnd):
    for p, q, np_, nq in DIV_WIRES:
        text = E.move_wire(text, (p[0], p[1] + dy), (q[0], q[1] + dy),
                           (np_[0], np_[1] + dy), (nq[0], nq[1] + dy))
    a, b = DIV_JUNCTION
    text = E.move_point(text, "junction", (a[0], a[1] + dy), (b[0], b[1] + dy))
    for r in (r_top, r_bot, gnd):
        text = E.move_symbol(text, r, -2.54, 0)
    return text


def main():
    for sheet, moves in ROWS.items():
        path = D + sheet + ".kicad_sch"
        text = subprocess.run(["git", "show", BASE + ":" + path], check=True,
                              capture_output=True, text=True).stdout
        text = E.normalise(text)
        for ref, x, old_y, new_y, top in moves:
            text = E.move_symbol(text, ref, 0, new_y - old_y)
            text = E.move_wire(text, (x, top), (x, old_y), (x, top), (x, new_y))
        for sh, dy, rt, rb, gnd in DIVIDERS:
            if sh == sheet:
                text = shift_divider(text, dy, rt, rb, gnd)
        open(path, "w", encoding="utf-8", newline="\n").write(text)
        print("levelled %d ground flags on %s" % (len(moves), sheet))


if __name__ == "__main__":
    main()
