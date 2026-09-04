#!/usr/bin/env python3
"""The +5V5 rail becomes +6V0, everywhere.

Round 4 raised the pre-regulator to 6.110 V and left the net called `+5V5`,
with a note saying the name was historical. The captain's ruling: that is not a
question, it is an unfinished change - the label, the test point's silkscreen
name and half the sheet's text still said 5V5. A rail whose name disagrees with
its voltage is a trap for whoever reads the board next.

`+5V5` is a **local label**, not a library power symbol, so the rename is a
string change on `power_rails` alone - no project-local symbol, no root sheet
pin, no other sheet. The netlist net name changes from `/power_rails/+5V5` to
`/power_rails/+6V0`; membership does not.

The decisions log keeps its history: `DEC-P1` still explains why 5.5 V was
chosen against the TPS7A20's input maximum, and `DEC-P10` why it moved. What
changes there is only the rail's *name* where the document states the design as
it is now.

Re-runnable from a pinned base.
"""
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "624bd13"
SHEET = "hardware/kicad/faff2_cbs1/power_rails.kicad_sch"

# (old, new) - each asserted to appear exactly once
EDITS = [
    # the net's own name, and the test point that probes it
    ('(label "+5V5"', '(label "+6V0"'),
    ('(property "Value" "+5V5"', '(property "Value" "+6V0"'),
    # the title block's one-line topology summary
    ('(comment 1 "24 V -> 5V5 pre-reg -> +5V and +5VA; 24 V -> +3V3 -> +3V3A")',
     '(comment 1 "24 V -> 6V0 pre-reg -> +5V and +5VA; 24 V -> +3V3 -> +3V3A")'),
    # block note: the rail set
    ("       +5V    ADPL42005 LDO from +5V5. IKP11 read head (<65 mA plus",
     "       +5V    ADPL42005 LDO from +6V0. IKP11 read head (<65 mA plus"),
    ("       +5VA   ADPL42005 LDO from +5V5. ADS1235 / ADS1120 AVDD and the",
     "       +5VA   ADPL42005 LDO from +6V0. ADS1235 / ADS1120 AVDD and the"),
    # the sheet states the design as it is - the rename's history lives in
    # DEC-P10, not on the drawing
    ("RAILS  +6V0   LMR33630 buck from V24_LOGIC. Pre-regulator only,\\n"
     "              local to this sheet.",
     "RAILS  +6V0   LMR33630 buck from V24_LOGIC, 6.110 V nominal.\\n"
     "              Pre-regulator only, local to this sheet.  DEC-P10."),
    # block note: per-rail breaks, and the sequencing line
    ("       R305 +5V5, R306 +5V, R307 +5VA, R312 +3V3, FB301 +3V3A.",
     "       R305 +6V0, R306 +5V, R307 +5VA, R312 +3V3, FB301 +3V3A."),
    ("       +5V5 and +3V3A follows +3V3.",
     "       +6V0 and +3V3A follows +3V3."),
    # the sheet states the design as it is; DEC-P10 carries the history
    ("6.009 / 6.110 / 6.212 V.  Was 5.5 V while the\\n"
     "TPS7A20's 6.0 V input maximum capped it.",
     "6.009 / 6.110 / 6.212 V.  DEC-P10 has the stack."),
]


def main():
    text = E.normalise(subprocess.run(["git", "show", BASE + ":" + SHEET],
                                      check=True, capture_output=True,
                                      text=True).stdout)
    for old, new in EDITS:
        assert text.count(old) == 1, old[:70]
        text = text.replace(old, new)
    assert "5V5" not in text, "a 5V5 survived"
    open(SHEET, "w", encoding="utf-8", newline="\n").write(text)
    print("power_rails: +5V5 -> +6V0, label, test point, title block and notes")


if __name__ == "__main__":
    main()
