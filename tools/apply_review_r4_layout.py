#!/usr/bin/env python3
"""Round 4, the per-sheet layout items.

2. `power_rails`: U304's PGND ground sat on top of C318. The answer was already
   on the sheet - U301 is the same regulator wired the same way, and its PGND
   ground hangs 1.27 mm below the pin with its name clear above the VCC stub.
   U304's hung 6.35 mm down, which put it in C318's lane. Making it match U301
   also closes both of round 3's residual findings.

3. `loadcell_afe`: the +5VA symbol and its name sat in the frame's ruler band.
   Measured off a render, the drawing area starts at y=11.94 and the name's box
   ran 10.79..12.06 - straddling it. The whole excitation cluster drops 6.35 mm
   so the name lands at 17.15..18.42, and the block box follows.

9. `temp_sense`: the PROBE 1 and CHANNEL 1 FILTER blocks crossed the same top
   boundary - their rectangles start at y=11.43, half a millimetre above the
   drawing area. So do four of `mcu`'s, laid out to the same wrong value, so
   both sheets are fixed: every top edge to 12.70 and the block titles under it
   to 13.34.

Re-runnable from a pinned base.
"""
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "b53794b"
D = "hardware/kicad/faff2_cbs1/"
DY = 6.35                       # the excitation cluster's drop

EXC_SYMS = ["#PWR510", "R508", "C507", "#PWR511", "C508", "#PWR512"]
EXC_WIRES = [((215.90, 15.24), (215.90, 19.05)),
             ((215.90, 24.13), (223.52, 24.13)),
             ((223.52, 24.13), (233.68, 24.13))]
EXC_JUNCTIONS = [(215.90, 24.13), (223.52, 24.13)]

# Item 5: FL501/FL502 are U.FL coaxial connectors - `Amodo_Connectors:
# CONUFL001-SMD`, connector footprints, and the library symbol's own default
# reference prefix is **J**. The FL prefix was an instance-level override
# contradicting the part, and FL is the prefix for a filter. They become J503
# and J504, the next free in loadcell_afe's 5xx range.
RENAMES = [("FL501", "J503"), ("FL502", "J504")]

# Item 6: the full pin-out lives in the right-hand notes column, 90 mm from the
# connector. This is the concise version, directly under J501 where somebody
# landing a cable will look. Width is capped by the signal wires dropping at
# x=48.26.
J501_NOTE = (
    "J501 -> HBK S2M cable\\n"
    "1 SIG+ wht   2 SIG- red\\n"
    "3 EXC+ blu   4 SEN+ grn\\n"
    "5 SEN- gry   6 EXC- blk\\n"
    "7,8 SHLD screen, R510")

# Every block rectangle that started at y=11.43 - 0.51 mm above the drawing
# area, which starts at 11.94 (measured off a render, not guessed). The titles
# just inside them move down to stay clear of their own border.
TOP_RECTS = {
    "mcu": [(22.86, 11.43, 198.12, 78.74), (202.31, 11.43, 295.91, 139.70),
            (297.18, 11.43, 407.67, 80.01), (411.48, 11.43, 581.66, 88.90)],
    "temp_sense": [(17.78, 11.43, 84.46, 49.53), (86.36, 11.43, 146.05, 46.99)],
}
TOP_NOTES = {
    "mcu": [("A  MCU CORE - SUPPLIES", 24.13), ("F  USB3320C Hi-SPEED ULPI", 203.58),
            ("G  USB-C RECEPTACLE", 298.45), ("C  USB3320 24 MHz CRYSTAL", 412.75)],
    "temp_sense": [("PROBE 1 - LOAD CELL (J701)", 19.05),
                   ("CHANNEL 1 FILTER", 87.63)],
}

EDITS = {
    "power_rails": dict(
        syms=[("#PWR327", 0, -5.08)],
        wires=[((55.88, 158.75), (55.88, 165.10),
                (55.88, 158.75), (55.88, 160.02))]),
    "loadcell_afe": dict(
        syms=[(r, 0, DY) for r in EXC_SYMS],
        wires=[(p, q, (p[0], p[1] + DY), (q[0], q[1] + DY))
               for p, q in EXC_WIRES]
              # the feed keeps its long run and doglegs down to the new row
              + [((208.28, 24.13), (215.90, 24.13),
                  (208.28, 30.48), (215.90, 30.48))],
        points=[("junction", p, (p[0], p[1] + DY)) for p in EXC_JUNCTIONS],
        add=[("wire", (208.28, 24.13), (208.28, 30.48))],
        notes=[("5 V BRIDGE EXCITATION", 216.51, 23.50),
               # the excitation box's new bottom border ran through the
               # pin-out note's first line
               ("J501 PIN-OUT - HBK S2M", 250.19, 43.18)],
        renames=RENAMES,
        text=[("  FL501/FL502 U.FL on the ADC-side SIG+/SIG- nodes",
               "  J503/J504 U.FL on the ADC-side SIG+/SIG- nodes")],
        newnotes=[(J501_NOTE, 19.05, 76.20)],
        rects=[((196.85, 16.51, 254.00, 35.56),
                (196.85, 22.86, 254.00, 41.91))]),
    "mcu": dict(),
    "temp_sense": dict(),
}
for _sh, _rr in TOP_RECTS.items():
    EDITS[_sh].setdefault("rects", []).extend(
        [(r, (r[0], 12.70, r[2], r[3])) for r in _rr])
for _sh, _nn in TOP_NOTES.items():
    EDITS[_sh].setdefault("notes", []).extend([(k, x, 13.34) for k, x in _nn])
EDITS["temp_sense"]["notes"].append(("OQ-04 RESOLVED: RTD, NOT NTC", 266.70, 12.70))


def main():
    for sheet, ed in EDITS.items():
        path = D + sheet + ".kicad_sch"
        text = subprocess.run(["git", "show", BASE + ":" + path], check=True,
                              capture_output=True, text=True).stdout
        text = E.normalise(text)
        for old, new in ed.get("text", []):
            text = E.edit_note(text, old, new)
        for old, new in ed.get("renames", []):
            text = E.rename_symbol(text, old, new)
        for ref, dx, dy in ed.get("syms", []):
            text = E.move_symbol(text, ref, dx, dy)
        for p, q, np_, nq in ed.get("wires", []):
            text = E.move_wire(text, p, q, np_, nq)
        for tag, p, np_ in ed.get("points", []):
            text = E.move_point(text, tag, p, np_)
        chunks = ""
        for kind, p, q in ed.get("add", []):
            chunks += E.wire_block(p, q, E.uid5(sheet, "r4", p, q))
        if chunks:
            text = E.add(text, chunks)
        for key, x, y in ed.get("notes", []):
            text = E.move_note(text, key, x, y)
        for old, new in ed.get("rects", []):
            text = E.set_rect(text, old, new)
        for body, x, y in ed.get("newnotes", []):
            text = E.add(text, E.note_block(body, x, y,
                                            E.uid5(sheet, "note", x, y)))
        open(path, "w", encoding="utf-8", newline="\n").write(text)
        print("laid out %s" % sheet)


if __name__ == "__main__":
    main()
