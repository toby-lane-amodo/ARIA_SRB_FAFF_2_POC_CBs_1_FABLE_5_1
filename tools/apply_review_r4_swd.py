#!/usr/bin/env python3
"""Round 4 items 10 and 11 - the SWD header becomes the STM32 14-way part.

11. `J1003` was a 2x5 2.54 mm header on the ARM Cortex Debug 10-pin order. It
    becomes `Amodo_Connectors:SAMTEC_SHF-107-01-L-D-SM`, the 14-way 1.27 mm IDC
    socket `ARIA_EITSYS_CBs_1` uses for the same job - a house-library part, so
    nothing goes project-local. The pinout is copied from that repo's
    `Microcontroller.kicad_sch`, J11, traced pin by pin from a read-only sparse
    clone rather than assumed:

        1  NC        2  NC
        3  VDD via 100R (their R625)
        4  SWDIO     5  GND
        6  SWCLK     7  GND
        8  NC        9  NC
        10 NC        11 GND
        12 nRESET    13 UART RX
        14 UART TX

    **One deviation, and it is an addition:** `SWO` goes on pin 10, which is
    NC there. This design has SWO (REQ-AR-15) and the reference board does not;
    dropping it to match exactly would remove a capability, and pin 10 is a
    spare in the signal column. A cable wired for the reference board simply
    leaves it open. Flagged for the captain.

10. The 100R between the header and +3V3 is `R1015` - the same series
    resistance their R625 puts on the same pin, and the reason the two items
    arrived together. `R1013` (DBG_RX) and `R1014` (DBG_TX) already existed and
    keep their jobs.

The three separate GND flags become one rail with a single flag, which is
`schematic-style`'s rule for a 2.54 mm pin row - here the pins are on 2.54 and
three of them are ground.

Re-runnable from a pinned base.
"""
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "7dd11ba"
SHEET = "hardware/kicad/faff2_cbs1/mcu.kicad_sch"
LIB = "Amodo_Connectors:SAMTEC_SHF-107-01-L-D-SM"
LIBSRC = "/mnt/c/Amodo/AmodoKiCadLib/Amodo_Connectors.kicad_sym"
PATH = ("/5edb00fd-45c9-5fe7-8d71-adbf38f38546/"
        "b1a1f0ad-3ac0-5e07-a3d8-a6f1c0d5c50f")

JX, JY = 447.04, 105.41
ODD, EVEN = JX - 10.16, JX + 7.62
ROW = {n: JY + 2.54 * k for k, n in
       enumerate([1, 3, 5, 7, 9, 11, 13], start=1)}
ROW.update({n: JY + 2.54 * k for k, n in
            enumerate([2, 4, 6, 8, 10, 12, 14], start=1)})
GND_RAIL = 434.34
GND_AT = 125.73
RX_ROW = 130.81

OLD_WIRES = [
    ((416.56, 107.95), (447.04, 107.95)), ((421.64, 110.49), (447.04, 110.49)),
    ((421.64, 110.49), (421.64, 113.03)), ((426.72, 113.03), (447.04, 113.03)),
    ((426.72, 113.03), (426.72, 115.57)), ((441.96, 118.11), (447.04, 118.11)),
    ((441.96, 118.11), (441.96, 120.65)), ((431.80, 115.57), (447.04, 115.57)),
    ((431.80, 115.57), (431.80, 118.11)), ((431.80, 123.19), (431.80, 125.73)),
    ((419.10, 125.73), (431.80, 125.73)), ((459.74, 107.95), (474.98, 107.95)),
    ((459.74, 110.49), (474.98, 110.49)), ((459.74, 113.03), (474.98, 113.03)),
    ((459.74, 118.11), (482.60, 118.11)), ((459.74, 115.57), (487.68, 115.57)),
    ((487.68, 115.57), (487.68, 118.11)), ((487.68, 123.19), (487.68, 125.73)),
    ((472.44, 125.73), (487.68, 125.73)),
]
OLD_SYMS = ["J1003", "#PWR1053", "#PWR1054"]

# (label, its new anchor x, row) - all read back over their wire, as before
# (name, its CURRENT anchor, new anchor x, pin) - keyed by where the label is,
# not by an occurrence index: every one of these nets is labelled at both ends
SIGNALS = [("SWDIO", (474.98, 107.95), 474.98, 4),
           ("SWCLK", (474.98, 110.49), 474.98, 6),
           ("SWO", (474.98, 113.03), 474.98, 10),
           ("MCU_nRESET", (482.60, 118.11), 482.60, 12)]
NO_CONNECT = [(ODD, 1), (ODD, 9), (EVEN, 2), (EVEN, 8)]

NOTE_OLD = ("PINOUT - standard ARM Cortex Debug 10-pin order on 2.54 mm pitch,\\n"
            "so a 2x5 SWD probe cable plugs straight on:\\n"
            "  1 VTref (+3V3)  2 SWDIO     3 GND     4 SWCLK   5 GND\\n"
            "  6 SWO           7 DBG_RX    8 DBG_TX  9 GND    10 nRESET\\n"
            "\\n"
            "Pins 7 and 8 are KEY / NC on the ARM pinout and are reused here\\n"
            "for the USART3 console (REQ-AR-15 and the block diagram both put\\n"
            "SWD and UART on ONE header). They are SWD-safe: an SWD probe\\n"
            "drives only 2, 4 and 10 and reads 6, and the .ioc sets\\n"
            "Trace_Asynchronous_SW, so PB4 / PB3 are not JTAG. The 100R series\\n"
            "resistors make a mis-plugged JTAG probe or a shorted console pin\\n"
            "a nuisance rather than damage.")
NOTE_NEW = ("PINOUT - the STM32 14-way 1.27 mm IDC order, copied pin for pin\\n"
            "from ARIA_EITSYS_CBs_1 (Microcontroller.kicad_sch, J11) so one\\n"
            "debug cable serves both boards:\\n"
            "  1  NC       2  NC       3  VDD (+3V3 via R1015 100R)\\n"
            "  4  SWDIO    5  GND      6  SWCLK    7  GND\\n"
            "  8  NC       9  NC      10  SWO     11  GND\\n"
            " 12  nRESET  13  DBG_RX  14  DBG_TX\\n"
            "\\n"
            "SWO on pin 10 is this board's ONE addition: pin 10 is NC on the\\n"
            "reference board, this design has SWO (REQ-AR-15), and a cable\\n"
            "wired for that board just leaves it open.\\n"
            "USART3 shares the header, as REQ-AR-15 and the block diagram both\\n"
            "ask. It is SWD-safe: a probe drives 4, 6 and 12 and reads 10, and\\n"
            "the .ioc sets Trace_Asynchronous_SW so PB4 / PB3 are not JTAG.\\n"
            "R1013 / R1014 / R1015, 100R each, make a mis-plugged probe or a\\n"
            "shorted console pin a nuisance rather than damage.")


def main():
    text = E.normalise(subprocess.run(["git", "show", BASE + ":" + SHEET],
                                      check=True, capture_output=True,
                                      text=True).stdout)
    text = E.edit_note(text, NOTE_OLD, NOTE_NEW)
    text = E.edit_note(text, "H  SWD + USART3 DEBUG HEADER  (REQ-AR-15)",
                       "H  SWD + USART3 DEBUG HEADER  (REQ-AR-15)")
    for p, q in OLD_WIRES:
        text = E.del_wire(text, p, q)
    for ref in OLD_SYMS:
        text = E.del_symbol(text, ref)

    src = open(LIBSRC, encoding="utf-8").read()
    text = E.embed_lib_symbol(text, src, LIB)
    text = E.add(text, E.symbol_block(
        LIB, "J1003", "SAMTEC_SHF-107-01-L-D-SM", JX, JY, PATH, src,
        E.uid5("mcu", "J1003"),
        # both names above the body: below it is the ground rail's lane
        fields={"Reference": (JX - 5.08, JY - 4.06),
                "Value": (JX - 5.08, JY - 2.03)},
        npins=14))

    # the +3V3 feed, now through R1015
    text = E.move_symbol(text, "#PWR1051", 0, 2.54)
    text = E.move_symbol(text, "R1013", -7.62, 12.70)
    text = E.set_rotation(text, "R1013", 90, 270)
    text = E.move_symbol(text, "R1014", -12.70, 5.08)
    text = E.set_rotation(text, "R1014", 90, 270)
    text = E.move_symbol(text, "#PWR1052", 12.70, 12.70)

    add = E.clone_symbol(text, "R1013", "R1015", 421.64, 110.49,
                         E.uid5("mcu", "R1015"))
    chunks = [add]
    W = lambda p, q, k: E.wire_block(p, q, E.uid5("mcu", "swd", k))
    chunks += [
        W((416.56, 110.49), (421.64, 110.49), "vdd1"),
        W((426.72, 110.49), (ODD, 110.49), "vdd2"),
        W((GND_RAIL, ROW[5]), (ODD, ROW[5]), "g5"),
        W((GND_RAIL, ROW[7]), (ODD, ROW[7]), "g7"),
        W((GND_RAIL, ROW[11]), (ODD, ROW[11]), "g11"),
        W((GND_RAIL, ROW[5]), (GND_RAIL, ROW[7]), "gr1"),
        W((GND_RAIL, ROW[7]), (GND_RAIL, ROW[11]), "gr2"),
        W((GND_RAIL, ROW[11]), (GND_RAIL, GND_AT), "gr3"),
        E.junction_block(GND_RAIL, ROW[7], E.uid5("mcu", "swd", "j7")),
        E.junction_block(GND_RAIL, ROW[11], E.uid5("mcu", "swd", "j11")),
        W((ODD, ROW[13]), (ODD, RX_ROW), "rx1"),
        W((429.26, RX_ROW), (ODD, RX_ROW), "rx2"),
        W((416.56, RX_ROW), (424.18, RX_ROW), "rx3"),
        W((EVEN, ROW[14]), (474.98, ROW[14]), "tx1"),
        W((480.06, ROW[14]), (487.68, ROW[14]), "tx2"),
    ]
    for name, _old, x, pin in SIGNALS:
        chunks.append(W((EVEN, ROW[pin]), (x, ROW[pin]), "sig" + name))
    for x, pin in NO_CONNECT:
        chunks.append(E.nc_block(x, ROW[pin], E.uid5("mcu", "swd", "nc", pin)))
    text = E.add(text, "".join(chunks))

    for name, old, x, pin in SIGNALS:
        text = E.move_label_at(text, name, old, x, ROW[pin])
    text = E.move_label_at(text, "DBG_RX", (419.10, 125.73), 416.56, RX_ROW)
    text = E.move_label_at(text, "DBG_TX", (472.44, 125.73), 487.68, ROW[14],
                           rot=180, justify="right bottom")

    # The three series resistors are horizontal now, so their names go above
    # and below the body. They are left-justified, so the anchor is the body's
    # left edge, not its centre. R1014's go BOTH below: above it is the nRESET
    # row, 2.54 mm away.
    # R1013's names sit 1.27 mm right of its body's left edge: square on it
    # they run into the DBG_RX label that arrives from the left.
    for ref, rx, ry, dy1, dy2 in (("R1013", 426.47, 130.81, -2.03, 2.29),
                                  ("R1014", 474.98, 123.19, 2.29, 4.32),
                                  ("R1015", 421.64, 110.49, -2.03, 2.29)):
        text = E.set_field(text, ref, "Reference", rx - 1.02, ry + dy1)
        text = E.set_field(text, ref, "Value", rx - 1.02, ry + dy2)

    open(SHEET, "w", encoding="utf-8", newline="\n").write(text)
    print("J1003 -> SAMTEC SHF-107-01-L-D-SM, 14-way; R1015 100R on VDD")


if __name__ == "__main__":
    main()
