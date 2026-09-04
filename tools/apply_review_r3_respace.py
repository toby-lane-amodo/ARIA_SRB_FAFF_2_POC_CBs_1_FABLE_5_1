#!/usr/bin/env python3
"""Round 3 item 4 - respace every grazing placement, and rehome the notes.

Round 2 left thirteen power-symbol net names grazing a wire, body or note, and
pinned the labels: the rule is that a label never moves sideways to dodge - the
symbol moves along its own stub, the neighbour moves, or the block box grows.
Item 1's improved checker then turned thirteen into fifty by treating labels and
symbol bodies as subjects rather than only obstacles.

The dominant defect, nine times over, is a power symbol's arrow with a vertex
exactly on a wire that runs past it and does not connect - the same thing the
captain screenshotted. A GND arrow moves UP off the wire beneath it; a rail
arrow moves DOWN, because its name sits above it and moving up would only put
the text where the arrow was.

Re-runnable: every sheet is rebuilt from `git show HEAD:<path>`.
"""
import subprocess
import sys
import uuid

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

# Rebuilt from a PINNED base, not HEAD: once this script's own commit lands,
# HEAD already contains its edits and a re-run would double-apply them or
# assert. Item 5, the last commit before this one.
BASE = "c978b96"

D = "hardware/kicad/faff2_cbs1/"
NS = uuid.UUID("5edb00fd-45c9-5fe7-8d71-adbf38f38546")


def uid(key):
    return str(uuid.uuid5(NS, "r3-respace-" + key))


# --------------------------------------------------------------- motor_drive
MD_SYMS = [
    # GND arrows whose tips sat on the bus running beneath them
    ("#PWR1143", 0, -2.54), ("#PWR1144", 0, -2.54),
    ("#PWR1145", 0, -2.54), ("#PWR1146", 0, -2.54),
    ("#PWR1147", 0, -2.54), ("#PWR1148", 0, -2.54),
    # +3V3 arrows whose tips crossed the encoder and hall signal rows
    ("#PWR1116", 0, 2.54), ("#PWR1117", 0, 2.54), ("#PWR1120", 0, 2.54),
    ("#PWR1105", 0, -1.27),
]
# TP1109's own reference and value ended up against the labels that moved in
# from the border, so they move the same 1.27-1.91 mm out of the way.
MD_FIELDS = [("TP1109", "Reference", 147.32, 190.50),
             ("TP1109", "Value", 145.41, 195.30)]
# VBUS_MON read leftward off the end of its wire, through C1102's ground stub
# and into #PWR1104's arrow. Turning it round puts the text over its own wire,
# and the anchor clears the arrow.
MD_JUSTIFY = [("VBUS_MON", 0, "left bottom")]
MD_WIRES = [
    ((275.59, 81.28), (275.59, 85.09), (275.59, 81.28), (275.59, 82.55)),
    ((285.75, 81.28), (285.75, 85.09), (285.75, 81.28), (285.75, 82.55)),
    ((311.15, 110.49), (311.15, 114.30), (311.15, 110.49), (311.15, 111.76)),
    ((321.31, 110.49), (321.31, 114.30), (321.31, 110.49), (321.31, 111.76)),
    ((292.10, 161.29), (292.10, 165.10), (292.10, 161.29), (292.10, 162.56)),
    ((302.26, 161.29), (302.26, 165.10), (302.26, 161.29), (302.26, 162.56)),
    ((69.85, 193.04), (69.85, 196.85), (69.85, 195.58), (69.85, 196.85)),
    ((77.47, 207.01), (77.47, 210.82), (77.47, 209.55), (77.47, 210.82)),
    ((69.85, 238.76), (69.85, 242.57), (69.85, 241.30), (69.85, 242.57)),
    # #PWR1113: its arrow's top-left vertex met this wire's elbow, and the
    # vertical then ran down through the "GND" beneath it. The elbow moves
    # 2.54 mm left, where nothing else runs.
    ((29.21, 185.42), (43.18, 185.42), (29.21, 185.42), (40.64, 185.42)),
    ((43.18, 185.42), (43.18, 204.47), (40.64, 185.42), (40.64, 204.47)),
    ((43.18, 204.47), (69.85, 204.47), (40.64, 204.47), (69.85, 204.47)),
]
# The TIM1 note sat on top of #PWR1129 and #PWR1130 - both bodies and both
# pinned names. Round 2 recorded that nothing 47.6 x 8.7 fitted anywhere in
# this block; with item 1's geometry that was simply wrong - 495 positions fit
# at 0.35 mm, and the nearest to where it was is beside U1101's logic inputs,
# which is what the note is about.
MD_NOTES = [
    ("TIM1 CH1/CH1N", 124.46, 83.82),
    # 0.13 mm above #PWR1111/#PWR1112's names; the block title has room above
    ("MOTOR ROTARY ENCODER AND HALL", 17.78, 151.01),
    # 1.17 mm past its block's right border
    ("RT1101 sits on the power stage", 73.66, 113.98),
]
MD_RECTS = [((15.24, 147.32, 114.30, 271.78), (15.24, 147.32, 114.30, 279.40))]
MD_TEXT = [(
    "J102 A/B/Z -> TIM3 CH1/CH2/CH3 (PC6/PC7/PC8).  J103 halls -> PE14/PD14/PD15 (GPIO).\\n"
    "Motor not fixed (DEC-0004): this pinout suits every candidate BLDC in the design log.\\n"
    "R1128..R1133 100R bound the current into the six MCU pins, the same treatment the\\n"
    "limit and button harnesses get. The cable is internal, so no TVS array - see the\\n"
    "ESD audit in docs/decisions/actuator-sch-review-r1.md.",
    "J102 A/B/Z -> TIM3 CH1/CH2/CH3 (PC6/PC7/PC8).  J103 halls -> PE14/PD14/PD15\\n"
    "(GPIO).  Motor not fixed (DEC-0004): this pinout suits every candidate BLDC\\n"
    "in the design log.  R1128..R1133 100R bound the current into the six MCU\\n"
    "pins, the same treatment the limit and button harnesses get. The cable is\\n"
    "internal, so no TVS array - see the ESD audit in\\n"
    "docs/decisions/actuator-sch-review-r1.md.")]

# --------------------------------------------------------------- power_rails
# #PWR304 and #PWR325: the EN feed's elbow ran down the GND arrow's right edge
# and through its name. The elbow moves 1.27 mm right, which clears both the
# name (0.76 mm) and #PWR306/#PWR327 beyond it.
PR_WIRES = [
    ((52.07, 45.72), (52.07, 63.50), (53.34, 45.72), (53.34, 63.50)),
    ((52.07, 45.72), (60.96, 45.72), (53.34, 45.72), (60.96, 45.72)),
    ((27.94, 63.50), (52.07, 63.50), (27.94, 63.50), (53.34, 63.50)),
    ((52.07, 153.67), (52.07, 171.45), (53.34, 153.67), (53.34, 171.45)),
    ((52.07, 153.67), (60.96, 153.67), (53.34, 153.67), (60.96, 153.67)),
    ((27.94, 171.45), (52.07, 171.45), (27.94, 171.45), (53.34, 171.45)),
]
PR_SYMS = []

# Both 5 V PWR_FLAGs: round 2 centred the 9.5 mm "PWR_FLAG" string 3.81 mm
# above each flag, straight across the rail wire dropping past it, 2.22 mm in.
# Moving along the stub cannot help - the wire is vertical and spans the whole
# range - so each flag moves onto the test-point stub below, where the name has
# clear air either side. The flag is still on the same node.
PR_FLAGS = [("#FLG345", 284.48, 275.59, 281.94), ("#FLG347", 386.08, 377.19, 383.54)]

# The new home leaves 9.10 mm between the output cap's "100nF" and the rail
# wire dropping to the test point, for 9.52 mm of "PWR_FLAG". Left is blocked
# by the cap's own ground stub, so the cap's value drops 2.36 mm instead and
# the two clear each other in y.
PR_FIELDS = [("C311", "Value", 266.19, 84.50), ("C314", "Value", 367.79, 84.50)]

# --------------------------------------------------------------- other sheets
TS_WIRES = [
    ((179.07, 85.09), (182.88, 85.09), (179.07, 85.09), (181.61, 85.09)),
    ((179.07, 87.63), (182.88, 87.63), (179.07, 87.63), (181.61, 87.63)),
    ((182.88, 85.09), (182.88, 87.63), (181.61, 85.09), (181.61, 87.63)),
    ((182.88, 87.63), (182.88, 90.17), (181.61, 87.63), (181.61, 90.17)),
    # #PWR714's name was 0.13 mm off C711's body. Down runs the arrow into
    # #PWR713 and there is no x where both the arrow clears C711's "100nF" and
    # the name clears C711's body - so the drop moves 2.54 mm right and C711's
    # value moves out from under it.
    ((215.90, 48.26), (215.90, 52.07), (218.44, 48.26), (218.44, 52.07)),
    ((215.90, 52.07), (213.36, 52.07), (218.44, 52.07), (213.36, 52.07)),
]

# Hierarchical labels whose text ran out through the block border they sit
# against: each anchor moves 2.54 mm inwards and its wire shortens to match.
MD_LABELS = [("CONFIG_SPI_SCK", 0, 2.54, 0), ("CONFIG_SPI_MOSI", 0, 2.54, 0),
             ("CONFIG_SPI_MISO", 0, 2.54, 0), ("DRV8323_nFAULT", 0, 2.54, 0)]
MD_LABEL_WIRES = [
    ((137.16, 189.23), (143.51, 189.23), (139.70, 189.23), (143.51, 189.23)),
    ((137.16, 193.04), (157.48, 193.04), (139.70, 193.04), (157.48, 193.04)),
    ((137.16, 168.91), (140.97, 168.91), (139.70, 168.91), (140.97, 168.91)),
    ((137.16, 196.85), (146.05, 196.85), (139.70, 196.85), (146.05, 196.85)),
    # V24_MOT's decoupling feed sat 1.27 mm under the third gate-drive bus, so
    # the label's caps touched it. The feed drops 1.27 mm; the stubs into
    # C1119/C1120 shorten to match and stay equal.
    ((275.59, 73.66), (285.75, 73.66), (275.59, 74.93), (285.75, 74.93)),
    ((285.75, 73.66), (290.83, 73.66), (285.75, 74.93), (290.83, 74.93)),
    ((275.59, 73.66), (275.59, 76.20), (275.59, 74.93), (275.59, 76.20)),
    ((285.75, 73.66), (285.75, 76.20), (285.75, 74.93), (285.75, 76.20)),
    # C1104's ground name was under VBUS_MON's new run; the ground goes up
    # its own stub.
    ((90.17, 69.85), (90.17, 72.39), (90.17, 69.85), (90.17, 71.12)),
    # VBUS_MON's wire kept a 3.81 mm tail west of the label purely to hold it,
    # and that tail crossed C1103's ground stub end-on - a crossing that reads
    # as a connection and is only not one because there is no junction. With
    # the label moved past #PWR1104 the tail goes, and so does the crossing.
    ((78.74, 77.47), (88.90, 77.47), (82.55, 77.47), (88.90, 77.47)),
]
MCU_LABELS = [("LINEAR_ENCODER_A", 0, 2.54, 0), ("LINEAR_ENCODER_B", 0, 2.54, 0),
              ("LINEAR_ENCODER_Z", 0, 2.54, 0)]
MCU_LABEL_WIRES = [
    ((43.18, 161.29), (63.50, 161.29), (45.72, 161.29), (63.50, 161.29)),
    ((43.18, 163.83), (63.50, 163.83), (45.72, 163.83), (63.50, 163.83)),
    ((43.18, 166.37), (63.50, 166.37), (45.72, 166.37), (63.50, 166.37)),
]

EDITS = {
    "motor_drive": dict(syms=MD_SYMS, wires=MD_WIRES + MD_LABEL_WIRES,
                        notes=MD_NOTES, rects=MD_RECTS, text=MD_TEXT,
                        labels=MD_LABELS + [("VBUS_MON", 0, 3.81, 0),
                                            ("V24_MOT", 0, 0, 1.27)],
                        fields=MD_FIELDS, justify=MD_JUSTIFY),
    # Both V24_LOGIC labels read back over their wire and 0.21 mm out through
    # the block's left border. Sliding the label along its wire only puts it on
    # the vertical dropping from the same corner, so the border moves instead -
    # 1.27 mm, which round 2's rule lists as the third option.
    "power_rails": dict(syms=PR_SYMS, wires=PR_WIRES, flags=PR_FLAGS,
                        fields=PR_FIELDS,
                        rects=[((15.24, 26.67, 205.74, 128.27),
                                (13.97, 26.67, 205.74, 128.27)),
                               ((15.24, 134.62, 205.74, 236.22),
                                (13.97, 134.62, 205.74, 236.22))]),
    # #PWR717's name was 0.51 mm inside the CONFIG_SPI_MISO bundle wire. Its
    # column moves 1.27 mm left, and the block box's left border goes with it -
    # growing the box is what round 2's rule says to do when the label cannot.
    "temp_sense": dict(syms=[("#PWR717", -1.27, 0), ("#PWR714", 2.54, 0)],
                       fields=[("C711", "Value", 220.34, 46.35)],
                       wires=TS_WIRES,
                       points=[("junction", (182.88, 87.63), (181.61, 87.63)),
                               ],
                       rects=[((180.34, 31.75, 238.76, 181.61),
                               (177.80, 31.75, 238.76, 181.61))]),
    # #FLG203's name was 0.13 mm off C201's body; the flag slides 3.81 mm left
    # along its own feed, which is a wire end, so the wire just shortens.
    "power_entry_24v": dict(syms=[("#FLG203", -3.81, 0)],
                            wires=[((71.12, 45.72), (81.28, 45.72),
                                    (71.12, 45.72), (77.47, 45.72))]),
    # The 5 V excitation block's title ran through the +5VA stub, and the +5VA
    # arrow crossed the box's top border - there is only 2.5 mm above it. The
    # border drops to 16.51 so the arrow and its name sit outside, where a
    # power symbol belongs, and the title moves to the top right, the only
    # clear run in a 21 mm tall box.
    # Three bold block titles, all wider than the 1.27 model claimed. Two ran
    # across the long vertical at x=99.06 and move right of it. The third, the
    # excitation title, is the awkward one: at 35 mm it cannot fit either side
    # of the +5VA stub inside a 48 mm box, so the box grows right and the title
    # goes after the stub. Meanwhile the +5VA arrow crossed the box's top
    # border, with only 2.5 mm of paper above it - so that border drops to
    # 16.51 and the arrow sits outside, which is where a power symbol belongs.
    "loadcell_afe": dict(notes=[("5 V BRIDGE EXCITATION", 216.51, 17.15),
                                ("SIGNAL INPUT FILTER", 100.33, 41.66),
                                ("REFERENCE (SENSE) FILTER", 100.33, 84.84),
                                ("OPERATING POINT (prelim", 251.46, 76.20)],
                         rects=[((196.85, 13.97, 245.11, 35.56),
                                 (196.85, 16.51, 254.00, 35.56))]),
    # 7.73 mm past its block's right border and 1.38 mm into the next block's
    # note. #PWR1041's GND blocks the obvious move left, so it re-wraps.
    "mcu": dict(notes=[("USB 2.0 data only", 316.23, 66.04)],
                labels=MCU_LABELS, wires=MCU_LABEL_WIRES, text=[(
        # 63 characters of bold title in a 94 mm block is 105 mm of text; the
        # DEC number is in docs/DECISIONS.md, the block note, and DECISIONS.md's
        # index, so it is the part that goes.
        "D  OCTOSPI1 FORCE-PROFILE RAM (QPI PSRAM)  REQ-AR-12 / DEC-0006",
        "D  OCTOSPI1 FORCE-PROFILE RAM (QPI PSRAM)  REQ-AR-12"), (
        "USB 2.0 data only: no VBUS load, no sink, no PD (REQ-EL-10, DEC-0002).\\n"
        "5.1k Rd on both CC lines is what makes this a valid USB-C device attachment.\\n"
        "VBUS is SENSED ONLY, through RVBUS in block F, so the PHY SessVld comparator\\n"
        "tells firmware a host is present - which is why VBUS_MON (PC5) stays free for\\n"
        "the motor DC link (supports OQ-01 / DEC-0011). CC carries nothing but the two\\n"
        "Rd resistors, so it needs no ESD part; the high-speed pair has the USBLC6-2P6.",
        "USB 2.0 data only: no VBUS load, no sink, no PD (REQ-EL-10, DEC-0002).\\n"
        "5.1k Rd on both CC lines is what makes this a valid USB-C device\\n"
        "attachment. VBUS is SENSED ONLY, through RVBUS in block F, so the PHY\\n"
        "SessVld comparator tells firmware a host is present - which is why\\n"
        "VBUS_MON (PC5) stays free for the motor DC link (supports OQ-01 /\\n"
        "DEC-0011). CC carries nothing but the two Rd resistors, so it needs no\\n"
        "ESD part; the high-speed pair has the USBLC6-2P6.")]),
    # 0.60 mm past its block's right border
    "nvm_calibration": dict(notes=[("R801/R802 are the removable", 16.51, 66.04)]),
    # J902's reference printed straight through its "SMA Jack" value, and the
    # value sat above the reference besides. The bundled checker had this one
    # right and this one wrong - see the decisions file. Reference on top,
    # value under it, 0.64 mm apart.
    "ui_io": dict(fields=[("J902", "Reference", 218.48, 19.19),
                          ("J902", "Value", 218.48, 19.83)]),
}


def relocate_flag(text, ref, old_x, new_x, tp_x):
    """Move a PWR_FLAG from its own stub onto the test-point stub below it."""
    text = E.del_wire(text, (old_x, 81.28), (old_x, 83.82))
    text = E.del_point(text, "junction", (old_x, 83.82))
    text = E.del_wire(text, (tp_x, 83.82), (old_x, 83.82))
    text = E.del_wire(text, (old_x, 83.82), (old_x + 7.62, 83.82))
    text = E.move_symbol(text, ref, new_x - old_x, 5.08)
    # split the test-point stub so the flag lands on a real tee
    text = E.move_wire(text, (tp_x, 83.82), (tp_x, 87.63),
                       (tp_x, 83.82), (tp_x, 86.36))
    return E.add(text, "".join((
        E.wire_block((tp_x, 83.82), (old_x + 7.62, 83.82), uid("f%s-h" % ref)),
        E.wire_block((tp_x, 86.36), (tp_x, 87.63), uid("f%s-v" % ref)),
        E.wire_block((new_x, 86.36), (tp_x, 86.36), uid("f%s-s" % ref)),
        E.junction_block(tp_x, 86.36, uid("f%s-j" % ref)))))


def main():
    for sheet, ed in EDITS.items():
        path = D + sheet + ".kicad_sch"
        text = subprocess.run(["git", "show", BASE + ":" + path], check=True,
                              capture_output=True, text=True).stdout
        text = E.normalise(text)
        for old, new in ed.get("text", []):
            text = E.edit_note(text, old, new)
        for ref, prop, x, y in ed.get("fields", []):
            text = E.set_field(text, ref, prop, x, y)
        for name, occ, just in ed.get("justify", []):
            text = E.set_label_justify(text, name, occ, just)
        for name, occ, dx, dy in ed.get("labels", []):
            text = E.move_label(text, name, occ, dx, dy)
        for ref, dx, dy in ed.get("syms", []):
            text = E.move_symbol(text, ref, dx, dy)
        for p, q, np_, nq in ed.get("wires", []):
            text = E.move_wire(text, p, q, np_, nq)
        for tag, p, np_ in ed.get("points", []):
            text = E.move_point(text, tag, p, np_)
        for key, x, y in ed.get("notes", []):
            text = E.move_note(text, key, x, y)
        for old, new in ed.get("rects", []):
            text = E.set_rect(text, old, new)
        for ref, old_x, new_x, tp_x in ed.get("flags", []):
            text = relocate_flag(text, ref, old_x, new_x, tp_x)
        open(path, "w", encoding="utf-8", newline="\n").write(text)
        print("respaced %s" % sheet)


if __name__ == "__main__":
    main()
