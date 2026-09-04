#!/usr/bin/env python3
"""Round 4, the captain's two answers on power_rails.

A1. Both ADPL42005 power-good pins join DEC-P9's wired-AND. R317 and R318, 1 k
    each like R315/R316, from each PG down to a local `RAIL_PGOOD` label - the
    same idiom the sheet already uses to reach that node three times. A dead
    5 V rail is now visible at D303 and TP308, where it was not.

A2. `+5V5` becomes 6.0 V nominal - the ADPL42005's characterised
    V_IN = V_OUT + 1 V point. The divider has to go slightly above it, and the
    arithmetic is in the decisions file:

      V_OUT = V_FB x (1 + R303/R304),  V_FB = 0.985 / 1.000 / 1.015 V
                                       (LMR33630 SNVSAN3F, Electrical
                                       Characteristics - +/-1.5%)

      100k / 20k    -> 5.900 / 6.000 / 6.100 V   nominal is exactly 6.0, but
                                                 the floor is 5.90
      64.9k / 12.7k -> 6.009 / 6.110 / 6.212 V   the floor clears 6.0

    So R303 and R304 both change. 64.9k keeps the divider impedance close to
    what it was (77.6k against 122.1k), so the 50 nA max FB bias current costs
    3.2 mV, 0.05%.

Re-runnable from a pinned base.
"""
import re
import subprocess
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sch_edit as E

BASE = "c4fa19e"
SHEET = "hardware/kicad/faff2_cbs1/power_rails.kicad_sch"
LIBSRC = "/mnt/c/Amodo/AmodoKiCadLib/Amodo_Resistors.kicad_sym"

DIVIDER = [("R303", "Amodo_Resistors:RES_TNF_64.9k_0603_0.1%", "64k9"),
           ("R304", "Amodo_Resistors:RES_TNF_12.7k_0603_0.1%", "12k7")]

# (ref, PG pin x) - the two clusters are 101.6 mm apart like everything else here
PG = [("R317", 247.65), ("R318", 349.25)]
PG_Y, R_TOP, R_BOT, LABEL_Y = 91.44, 93.98, 99.06, 101.60
LABEL_DX = 12.70

TEXT = [
    ("A.  PRE-REGULATOR  V24_LOGIC -> 5.5 V  (LMR33630, 400 kHz)",
     "A.  PRE-REGULATOR  V24_LOGIC -> 6.0 V  (LMR33630, 400 kHz)"),
    ("5.5 V, not 5.0 V: it gives both ADPL42005 LDOs\\ntheir dropout headroom. "
     "500 mV covers the 325 mV\\nworst-case dropout at 300 mA (Table 1); the "
     "part\\ntakes up to 20 V in, so 6.0 V no longer caps it.",
     "6.0 V, not 5.0 V: it is the ADPL42005's own\\ncharacterised VIN = VOUT + 1 V "
     "point, so the LDOs\\nmeet their noise and PSRR numbers on +5VA, which\\n"
     "carries REQ-FF-04.  R303/R304 are sized so the\\nworst-case floor clears "
     "6.0 V, not just the nominal:\\n6.009 / 6.110 / 6.212 V.  Was 5.5 V while the\\n"
     "TPS7A20's 6.0 V input maximum capped it."),
    # the net keeps its name - the captain's own instruction calls it +5V5 -
    # so the note has to say the voltage, or the drawing reads as a lie
    ("RAILS  +5V5   LMR33630 buck from V24_LOGIC. Pre-regulator only,",
     "RAILS  +5V5   LMR33630 buck from V24_LOGIC, 6.110 V since review\n"
     "              round 4 - the name is historical. Pre-regulator only,"),
    ("       buck at 5.5 V feeding two LDOs costs one converter and post-",
     "       buck at 6.0 V feeding two LDOs costs one converter and post-"),
    ("       RAIL_PGOOD is open drain, the wired-AND of both converters\\n"
     "       through R315 / R316. It stays SHEET-LOCAL: LED D303 and TP308",
     "       RAIL_PGOOD is open drain, the wired-AND of all four regulators\\n"
     "       through R315 / R316 / R317 / R318. SHEET-LOCAL: LED D303, TP308"),
]


def clone_resistor(text, model, ref, x, y, uid):
    """A new resistor cloned from an existing one - same part, same property
    set, new designator and position.

    Hand-building the block is how this went wrong first time: the effects
    string was assembled with `str.replace("\\t\\t\\t)")`, which also matched the
    font block's closing paren and put `(hide yes)` inside it. KiCad answered
    with "Failed to load schematic" and a sheet truncated to 349 components -
    exactly the silent-truncation trap AGENTS.md warns about, and the netlist
    component count is what caught it.
    """
    s, e = sym_span_local(text, model)
    blk = text[s:e]
    mx, my = at_of(blk)
    dx, dy = x - mx, y - my

    def shift(m):
        return "(at %s %s%s)" % (E.fmt(float(m.group(1)) + dx),
                                 E.fmt(float(m.group(2)) + dy),
                                 m.group(3) or "")
    out = re.sub(r"\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)", shift, blk)
    out = out.replace('"%s"' % model, '"%s"' % ref)
    out = re.sub(r'\(uuid "[0-9a-f-]{36}"\)', lambda m: '(uuid "%s")' % uid,
                 out, count=1)
    # the pin uuids must be unique too
    n = [0]

    def pinuid(m):
        n[0] += 1
        return '(uuid "%s")' % E.uid5(ref, "pin", n[0])
    head, tail = out.split('(pin "1"', 1)
    tail = re.sub(r'\(uuid "[0-9a-f-]{36}"\)', pinuid, tail)
    return "\t" + head + '(pin "1"' + tail + "\n"


def sym_span_local(text, ref):
    return E.sym_span(text, ref)


def at_of(blk):
    m = re.search(r"\(at ([-\d.]+) ([-\d.]+) [-\d.]+\)", blk)
    return float(m.group(1)), float(m.group(2))


def main():
    text = E.normalise(subprocess.run(["git", "show", BASE + ":" + SHEET],
                                      check=True, capture_output=True,
                                      text=True).stdout)
    for old, new in TEXT:
        text = E.edit_note(text, old, new)

    # A2: the feedback divider
    src = open(LIBSRC, encoding="utf-8").read()
    for ref, lib_id, value in DIVIDER:
        text = E.set_lib_id(text, ref, lib_id)
        # ...and the cached property values with it: mpn, datasheet and
        # description all belonged to the old part, and a swap that leaves them
        # ships the wrong part number to the BOM.
        text = E.sync_properties(text, ref, src, lib_id.split(":", 1)[1],
                                 value=value)
        text = E.embed_lib_symbol(text, src, lib_id)
    text = E.del_lib_symbol(text, "Amodo_Resistors:RES_TNF_22.1k_0603_0.1%")

    # A1: the two power-good branches
    add = ""
    for ref, x in PG:
        text = E.del_point(text, "no_connect", (x, PG_Y))
        add += clone_resistor(text, "R315", ref, x, R_TOP, E.uid5(ref, "sym"))
        add += E.wire_block((x, PG_Y), (x, R_TOP), E.uid5(ref, "w1"))
        add += E.wire_block((x, R_BOT), (x, LABEL_Y), E.uid5(ref, "w2"))
        add += E.wire_block((x, LABEL_Y), (x + LABEL_DX, LABEL_Y),
                            E.uid5(ref, "w3"))
        add += E.label_block("RAIL_PGOOD", x + LABEL_DX, LABEL_Y, 180,
                             "right bottom", E.uid5(ref, "lab"))
    text = E.add(text, add)

    open(SHEET, "w", encoding="utf-8", newline="\n").write(text)
    print("+5V5 -> 6.0 V (64k9/12k7); R317/R318 tie both PG pins to RAIL_PGOOD")


if __name__ == "__main__":
    main()
