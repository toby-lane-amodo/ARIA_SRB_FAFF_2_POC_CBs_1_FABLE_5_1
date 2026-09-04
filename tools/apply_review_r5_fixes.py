#!/usr/bin/env python3
"""The five verification findings from the captain's hand-edited state.

Minimal deltas, riding on top of his placement: nothing he moved is moved back
unless the finding is the move itself.

1. `J603` and `J1003` lost their reference designators and both read `J?`,
   which merged them into a single netlist component - 17 nodes, pin numbers
   3/4/5/10 twice, and only the 8510-4500PL's value and footprint, so the
   SAMTEC SWD header had dropped out of the BOM. The two references are set
   back by hand rather than by a blind re-annotate, which would renumber other
   parts. Both the Reference property AND the `(instances ... (reference ...))`
   entry carry the name; a sheet with the two disagreeing loads without
   complaint and exports the old one.

2. The `+6V0` rename, completed again. `c9d85d6` branched from `624bd13`, one
   commit before the rename, so the merge kept `+6V0` on the net label, TP302's
   silkscreen and the netlist net, and restored `+5V5` in the title-block
   comment and four note lines - leaving one note reading "+6V0 LMR33630 buck"
   two lines above "LDO from +5V5".

3. `temp_sense`: the ADS1120 block border sat at x=163.83, through U701's body
   (152.40..176.53). The box is titled ADS1120 SUPPLIES AND SPI2 and U701 *is*
   the ADS1120, so the border goes to 151.13 - just left of the part, which is
   what dragging it leftwards was reaching for - rather than back to 177.80.

4. `power_rails`: the two `V24_LOGIC` labels moved 1.27 mm left in the hand
   edit and now cross the block border. The border moves instead, 13.97 ->
   12.70, so his label placement stands; 12.70 is the same inset the top
   borders use, and the drawing area starts at 11.94.

5. `loadcell_afe`: `R522`'s reference cleared `#PWR509`'s body by 0.20 mm after
   the flag moved down. Its two fields drop 1.27 mm instead of moving left -
   left put R523's value onto the filter block's top border, and down keeps
   both resistors' text on the same x and the same 1.91 mm pitch.

Re-runnable from a pinned base.
"""
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "d109e19"
D = "hardware/kicad/faff2_cbs1/"

RENAMES = {"linear_encoder": ("J?", "J603"), "mcu": ("J?", "J1003")}

PR_TEXT = [
    ('(comment 1 "24 V -> 5V5 pre-reg -> +5V and +5VA; 24 V -> +3V3 -> +3V3A")',
     '(comment 1 "24 V -> 6V0 pre-reg -> +5V and +5VA; 24 V -> +3V3 -> +3V3A")'),
    ("       +5V    ADPL42005 LDO from +5V5. IKP11 read head (<65 mA plus",
     "       +5V    ADPL42005 LDO from +6V0. IKP11 read head (<65 mA plus"),
    ("       +5VA   ADPL42005 LDO from +5V5. ADS1235 / ADS1120 AVDD and the",
     "       +5VA   ADPL42005 LDO from +6V0. ADS1235 / ADS1120 AVDD and the"),
    ("       R305 +5V5, R306 +5V, R307 +5VA, R312 +3V3, FB301 +3V3A.",
     "       R305 +6V0, R306 +5V, R307 +5VA, R312 +3V3, FB301 +3V3A."),
    ("       +5V5 and +3V3A follows +3V3.",
     "       +6V0 and +3V3A follows +3V3."),
]
PR_RECTS = [((13.97, 26.67, 205.74, 128.27), (12.70, 26.67, 205.74, 128.27)),
            ((13.97, 134.62, 205.74, 236.22), (12.70, 134.62, 205.74, 236.22))]
TS_RECTS = [((163.83, 31.75, 238.76, 181.61), (151.13, 31.75, 238.76, 181.61))]
AFE_FIELDS = [("R522", "Reference", 167.00, 34.16),
              ("R522", "Value", 167.00, 36.07)]


def load(sheet):
    return E.normalise(subprocess.run(
        ["git", "show", BASE + ":" + D + sheet + ".kicad_sch"], check=True,
        capture_output=True, text=True).stdout)


def save(sheet, text):
    open(D + sheet + ".kicad_sch", "w", encoding="utf-8",
         newline="\n").write(text)


def main():
    for sheet, (old, new) in RENAMES.items():
        t = E.rename_symbol(load(sheet), old, new)
        assert '"J?"' not in t, sheet
        save(sheet, t)
        print("%s: %s -> %s" % (sheet, old, new))

    t = load("power_rails")
    for old, new in PR_TEXT:
        t = E.edit_note(t, old, new)
    for old, new in PR_RECTS:
        t = E.set_rect(t, old, new)
    assert "5V5" not in t, "a 5V5 survived on power_rails"
    save("power_rails", t)
    print("power_rails: +6V0 completed, block borders 13.97 -> 12.70")

    t = load("temp_sense")
    for old, new in TS_RECTS:
        t = E.set_rect(t, old, new)
    save("temp_sense", t)
    print("temp_sense: ADS1120 border 163.83 -> 151.13, clear of U701")

    t = load("loadcell_afe")
    for ref, prop, x, y in AFE_FIELDS:
        t = E.set_field(t, ref, prop, x, y)
    save("loadcell_afe", t)
    print("loadcell_afe: R522's fields 1.27 mm down")


if __name__ == "__main__":
    main()
