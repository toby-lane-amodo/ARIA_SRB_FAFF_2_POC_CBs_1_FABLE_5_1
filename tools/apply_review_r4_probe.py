#!/usr/bin/env python3
"""Round 4 item 4 - the rail probe header moves to the sheet it observes.

`J1004` sat on `mcu` in a block of its own. Its own note said why, and named
the alternative: "It sits on the mcu page because +3V3 and +3V3A are the MCU's
own supply ... power_rails is the alternative home." The captain has chosen the
alternative, and it is the better one: the rails, their isolation links and
their current breaks are all on `power_rails`, and the header only observes
them. It becomes `J301`, in block D, which already carries `RAIL_PGOOD`,
`D303` and `TP308` - the other rail-observation parts.

Everything moves as one: the connector, its four rail flags, its ground rail and
its note. mcu loses a whole block rectangle; the header joins block D rather
than nesting a new box inside it, and D's title says so.

The refdes changes, so this is a netlist change - the topology does not.

Re-runnable from a pinned base.
"""
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "8face45"
D = "hardware/kicad/faff2_cbs1/"
DX, DY = -173.99, -45.72          # J1004 (424.18,193.04) -> J301 (250.19,147.32)

MOVE_SYMS = [("J1004", "J301"), ("#PWR1055", "#PWR358"),
             ("#PWR1056", "#PWR359"), ("#PWR1057", "#PWR360"),
             ("#PWR1058", "#PWR361")]
WIRES = [((427.99, 186.69), (439.42, 186.69)),
         ((427.99, 189.23), (447.04, 189.23)),
         ((427.99, 191.77), (454.66, 191.77)),
         ((427.99, 194.31), (434.34, 194.31)),
         ((427.99, 196.85), (434.34, 196.85)),
         ((427.99, 199.39), (434.34, 199.39)),
         ((434.34, 194.31), (434.34, 196.85)),
         ((434.34, 196.85), (434.34, 199.39)),
         ((434.34, 199.39), (434.34, 203.20))]
JUNCTIONS = [(434.34, 196.85), (434.34, 199.39)]
MCU_RECT = (411.48, 173.99, 581.66, 251.46)
MCU_TITLE = "J  RAIL PROBE HEADER  (TEST_PLAN 4)"
# The instance is useless without its library definition: KiCad loads a symbol
# with no pins, every wire on it collapses into one net, and the netlist shows
# all six pads shorted. The lib_symbol travels with the part.
PART = "Amodo_Connectors:Header_Male_6-way_1-row_Straight_2.54mm_THT"

NOTE = ("RAIL PROBE HEADER (TEST_PLAN 4)\\n"
        "One header to check every logic rail with a DMM during bring-up\\n"
        "steps 2 and 3 of TEST_PLAN 5.  It only observes: the rails, their\\n"
        "isolation links and their current breaks are the rest of this sheet.\\n"
        "  1 +5V    2 +3V3    3 +3V3A    4 GND    5 GND    6 GND\\n"
        "\\n"
        "+24V IS DELIBERATELY NOT ON THIS HEADER.  24 V next to 3.3 V on a\\n"
        "2.54 mm strip is one slip away from destroying the board;\\n"
        "power_entry_24v carries the +24V_SW test point and the current break\\n"
        "that TEST_PLAN 4 asks for.\\n"
        "\\n"
        "Moved here from mcu in review round 4.  Its old note named this sheet\\n"
        "as the alternative home; the captain chose it.")
NOTE_AT = (290.83, 140.97)   # clear of the three rail stubs, which reach 280.67


def main():
    # --- take the block out of mcu, keeping the blocks to re-plant
    path = D + "mcu.kicad_sch"
    mcu = E.normalise(subprocess.run(["git", "show", BASE + ":" + path],
                                     check=True, capture_output=True,
                                     text=True).stdout)
    carried = []
    for old, new in MOVE_SYMS:
        s, e = E.sym_span(mcu, old)
        carried.append(mcu[s - 1:e + 1].replace('"%s"' % old, '"%s"' % new))
        mcu = E.del_symbol(mcu, old)
    for p, q in WIRES:
        mcu = E.del_wire(mcu, p, q)
    for p in JUNCTIONS:
        mcu = E.del_point(mcu, "junction", p)
    mcu = E.del_note(mcu, MCU_TITLE)
    mcu = E.del_note(mcu, "One header to check every logic rail")
    mcu = E.del_rect(mcu, MCU_RECT)
    mcu = E.del_lib_symbol(mcu, PART)      # no other mcu part uses it
    open(path, "w", encoding="utf-8", newline="\n").write(mcu)
    print("mcu: block J removed")

    # --- plant it on power_rails, shifted, renumbered, re-pathed
    path = D + "power_rails.kicad_sch"
    pr = E.normalise(subprocess.run(["git", "show", BASE + ":" + path],
                                    check=True, capture_output=True,
                                    text=True).stdout)
    pr_path = E.instance_path(pr, "R315")
    pr = E.embed_lib_symbol(
        pr, open("/mnt/c/Amodo/AmodoKiCadLib/Amodo_Connectors.kicad_sym",
                 encoding="utf-8").read(), PART)
    chunks = ""
    for blk, (old, new) in zip(carried, MOVE_SYMS):
        blk = E.shift_block(blk, DX, DY)
        blk = E.repath(blk, pr_path)
        blk = E.reuid(blk, new)
        chunks += blk.lstrip("\n")
    for p, q in WIRES:
        chunks += E.wire_block((p[0] + DX, p[1] + DY), (q[0] + DX, q[1] + DY),
                               E.uid5("pr", "probe", p, q))
    for p in JUNCTIONS:
        chunks += E.junction_block(p[0] + DX, p[1] + DY,
                                   E.uid5("pr", "probej", p))
    pr = E.add(pr, chunks)
    pr = E.add(pr, E.note_block(NOTE, NOTE_AT[0], NOTE_AT[1],
                                E.uid5("pr", "probenote")))
    pr = E.edit_note(
        pr, "D.  ANALOG 3V3 FOR THE ADC DIGITAL SUPPLIES, AND RAIL POWER-GOOD",
        "D.  ANALOG 3V3, RAIL POWER-GOOD, AND THE RAIL PROBE HEADER")
    open(path, "w", encoding="utf-8", newline="\n").write(pr)
    print("power_rails: J301 planted in block D")


if __name__ == "__main__":
    main()
