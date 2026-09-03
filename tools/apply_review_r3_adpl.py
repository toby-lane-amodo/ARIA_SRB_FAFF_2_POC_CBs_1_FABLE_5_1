#!/usr/bin/env python3
"""Round 3 item 3 - both 5 V LDOs become ADPL42005ACPZ-5.0-R7.

The captain overruled DEC-P3's TPS7A20 for both `+5V` and `+5VA`. The part is
already in the house library (`Amodo_Power_ICs`, `SymLifecycle: tested`) with
the `Amodo:LFCSP-8 - 3x3mm body - 0.5mm pitch - 2.5x1.8mm EP` footprint, so
nothing goes project-local.

Every value below comes from the datasheet, now in `datasheets/ADPL42005.pdf`
(analog.com times out from this environment; `datasheetall.com` mirrors the
same Rev. 0 PDF):

  Table 5, pin descriptions
    1 VOUT    "Bypass VOUT to GND with a 1uF or greater capacitor."
    2 SENSE   "Measures the actual output voltage at the load ... Connect SENSE
              as close as possible to the load."
    3, 6 GND
    4 NC      "Do Not Connect to This Pin."
    5 EN      "For automatic startup, connect EN to VIN."
    7 PG      open drain, needs a pull-up to VIN or VOUT; "If the power-good
              function is not used, the pin may be left open or connected to
              ground."
    8 VIN     "Bypass VIN to GND with a 1uF or greater capacitor."
    EPAD      internally GND; "highly recommended that the EPAD be connected to
              the ground plane."
  Applications Information, Capacitor Selection, p.17
    COUT      "A minimum of 1uF capacitance with an ESR of 1 ohm or less is
              recommended to ensure the stability of the ADPL42005."
    CIN       1uF, and "if greater than 1uF of output capacitance is required,
              the input capacitor should be increased to match it."

So: COUT stays 10uF + 100nF (>= the 1uF minimum, and the datasheet says a
larger COUT improves transient response), and CIN rises 1uF -> 10uF to match
it, which is the one passive value that had to change. C309/C312 move to
`CAP_MLCC_10uF_0805_20%_25V` rather than the 0603 10 V part the outputs use:
these sit on the 5.5 V pre-regulator rail, and a 10 V X5R at 5.5 V DC bias
loses most of its capacitance, which is the wrong way to satisfy a
"match COUT" requirement. loadcell_afe already uses this exact part for a
10uF on a 5 V-class rail.

SENSE ties to VOUT **at the regulator**, not past the 0R rail link. R306/R307
are TEST_PLAN 3.2 current-measurement breaks that get lifted deliberately;
sensing downstream would open the feedback loop when they are. The datasheet's
own specifications are given for "SENSE connected to VOUT" (p.3).

PG gets a no-connect. Wiring it into DEC-P9's RAIL_PGOOD wired-AND would be
the natural next step and is worth a decision - see the decisions file - but
the captain asked for a part swap with re-derived passives, not new rail
supervision, and nothing regresses: the TPS7A20 had no PG pin at all.

The two clusters are identical, 101.6 mm apart, so one builder runs twice.
Re-runnable: rebuilds the sheet from `git show HEAD:<path>`.
"""
import re
import subprocess
import uuid

SHEET = "hardware/kicad/faff2_cbs1/power_rails.kicad_sch"
LIBSRC = "/mnt/c/Amodo/AmodoKiCadLib/Amodo_Power_ICs.kicad_sym"
CAPSRC = "/mnt/c/Amodo/AmodoKiCadLib/Amodo_Capacitors.kicad_sym"
NS = uuid.UUID("cfac6e86-3b1f-5c4c-b992-5519585fa944")
PATH = "/5edb00fd-45c9-5fe7-8d71-adbf38f38546/cfac6e86-3b1f-5c4c-b992-5519585fa944"
LIB = "Amodo_Power_ICs:ADPL42005ACPZ-5.0-R7"
CIN = "Amodo_Capacitors:CAP_MLCC_10uF_0805_20%_25V"

# (refdes, GND refdes, left-pin x, input cap refdes) - the two clusters differ
# only by 101.6 mm, and X0 lands VIN and EN on the wires that already feed them
LDOS = [("U302", "#PWR314", 228.60, "C309"),
        ("U303", "#PWR319", 330.20, "C312")]
Y = 72.39                     # so VIN sits at 73.66, where IN sat before
VIN_Y, EN_Y, NC_Y = 73.66, 78.74, 83.82
GND_Y = [86.36, 88.90, 91.44]           # GND, GND, EPAD - a 2.54 mm pin row
PG_Y = 91.44
OUT_DX, RAIL_DX = 19.05, -5.08          # VOUT/SENSE/PG column; the GND rail
SENSE_Y = 78.74
CAP_X = 25.40                           # first output cap, unchanged

PROPS = [
    ("Reference", None, 2.54, 67.74, False),
    ("Value", "ADPL42005", 2.54, 69.79, False),
    ("Footprint", "Amodo:LFCSP-8 - 3x3mm body - 0.5mm pitch - 2.5x1.8mm EP",
     0.0, 0.0, True),
    ("Datasheet", "https://www.analog.com/media/en/technical-documentation/"
     "data-sheets/adpl42005.pdf", 0.0, 0.0, True),
    ("Description", "LDO Voltage Regulator, 5.0V, 0.5 A, 20 V in, 8-LFCSP",
     0.0, 0.0, True),
    ("SymLifecycle", "tested", 0.0, 0.0, True),
    ("mpn", "ADPL42005ACPZ-5.0-R7", 0.0, 0.0, True),
]

# The 0805 input caps are wider than the 0603 they replace, so the library's
# own Value offset put "10uF" 0.44 mm into the EN feed vertical at x=222.25.
# Aligning the Value anchor with the Reference above it clears the wire by
# 0.83 mm and reads better than two differently-indented lines.
FIELD_FIXES = [("C309", "Value", 216.66, 71.98),
               ("C312", "Value", 318.26, 71.98)]

TEXT_EDITS = [
    ("B.  POST-REGULATED 5 V RAILS  (TPS7A20: +5V digital, +5VA analog)",
     "B.  POST-REGULATED 5 V RAILS  (ADPL42005: +5V digital, +5VA analog)"),
    ("5.5 V, not 5.0 V: it gives both TPS7A20 LDOs\\ntheir dropout headroom "
     "while staying inside the\\nTPS7A20 6.0 V recommended input maximum.",
     "5.5 V, not 5.0 V: it gives both ADPL42005 LDOs\\ntheir dropout headroom. "
     "500 mV covers the 325 mV\\nworst-case dropout at 300 mA (Table 1); the "
     "part\\ntakes up to 20 V in, so 6.0 V no longer caps it."),
    ("EN is tied to each LDO input, so the 5 V rails\\nfollow the "
     "pre-regulator with no sequencing logic.",
     "EN is tied to each LDO input - the datasheet's own\\nautomatic-startup "
     "connection - so the 5 V rails\\nfollow the pre-regulator with no "
     "sequencing logic.\\nSENSE ties to VOUT at the regulator, not past the\\n"
     "0R link, so lifting the link cannot open the loop.\\nPG is unused: "
     "no-connect, not tied to RAIL_PGOOD."),
    ("       +5V    TPS7A20 LDO from +5V5.", "       +5V    ADPL42005 LDO from +5V5."),
    ("       +5VA   TPS7A20 LDO from +5V5.", "       +5VA   ADPL42005 LDO from +5V5."),
]


def uid(key):
    return str(uuid.uuid5(NS, key))


def _fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def block(text, start):
    d, j = 0, start
    while True:
        c = text[j]
        if c == '"':
            j += 1
            while not (text[j] == '"' and text[j - 1] != "\\"):
                j += 1
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return text[start:j + 1]
        j += 1


def sym_span(text, ref):
    i = text.index('(property "Reference" "%s"' % ref)
    start = text.rindex("\n\t(symbol\n", 0, i) + 2
    return start, start + len(block(text, start))


def drop_symbol(text, ref):
    s, e = sym_span(text, ref)
    return text[:s - 1] + text[e + 1:]


def move_symbol(text, ref, dx, dy):
    s, e = sym_span(text, ref)
    def shift(m):
        return "(at %s %s%s)" % (_fmt(float(m.group(1)) + dx),
                                 _fmt(float(m.group(2)) + dy), m.group(3) or "")
    return text[:s] + re.sub(r"\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)", shift,
                             text[s:e]) + text[e:]


def retype_symbol(text, ref, lib_id, value):
    """Swap a part for a same-shape one: new lib_id and Value, same position."""
    s, e = sym_span(text, ref)
    blk = re.sub(r'\(lib_id "[^"]*"\)', '(lib_id "%s")' % lib_id, text[s:e], count=1)
    blk = re.sub(r'\(property "Value" "[^"]*"',
                 '(property "Value" "%s"' % value, blk, count=1)
    return text[:s] + blk + text[e:]


def set_field(text, ref, prop, x, y):
    s, e = sym_span(text, ref)
    blk = text[s:e]
    k = blk.index('(property "%s"' % prop)
    ke = k + len(block(blk, k))
    fld = re.sub(r"\(at [-\d.]+ [-\d.]+ ([-\d.]+)\)",
                 lambda m: "(at %s %s %s)" % (_fmt(x), _fmt(y), m.group(1)),
                 blk[k:ke], count=1)
    return text[:s] + blk[:k] + fld + blk[ke:] + text[e:]


def drop_geom(text, tag, pred):
    out, pos = text, 0
    while True:
        i = out.find("\n\t(%s\n" % tag, pos)
        if i < 0:
            return out
        blk = block(out, i + 2)
        nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", blk)]
        if pred(nums):
            out = out[:i + 1] + out[i + 2 + len(blk) + 1:]
            pos = i
        else:
            pos = i + 1


def drop_wire(text, p, q):
    before = text
    text = drop_geom(text, "wire", lambda n, p=p, q=q: (
        abs(n[0] - p[0]) < 0.01 and abs(n[1] - p[1]) < 0.01 and
        abs(n[2] - q[0]) < 0.01 and abs(n[3] - q[1]) < 0.01))
    assert text != before, (p, q)
    return text


def wire(p, q, key):
    return (f"\t(wire\n\t\t(pts\n\t\t\t(xy {_fmt(p[0])} {_fmt(p[1])}) "
            f"(xy {_fmt(q[0])} {_fmt(q[1])})\n\t\t)\n\t\t(stroke\n"
            f"\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            f'\t\t(uuid "{uid(key)}")\n\t)\n')


def junction(x, y, key):
    return (f"\t(junction\n\t\t(at {_fmt(x)} {_fmt(y)})\n\t\t(diameter 0)\n"
            f'\t\t(color 0 0 0 0)\n\t\t(uuid "{uid(key)}")\n\t)\n')


def no_connect(x, y, key):
    return (f"\t(no_connect\n\t\t(at {_fmt(x)} {_fmt(y)})\n"
            f'\t\t(uuid "{uid(key)}")\n\t)\n')


def instance(ref, x0):
    eff_hidden = ("\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                  "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t\t(hide yes)\n"
                  "\t\t\t)\n")
    eff_shown = ("\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
                 "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t)\n")
    s = [f'\t(symbol\n\t\t(lib_id "{LIB}")\n'
         f"\t\t(at {_fmt(x0)} {_fmt(Y)} 0)\n\t\t(unit 1)\n"
         "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"
         "\t\t(dnp no)\n\t\t(fields_autoplaced no)\n"
         f'\t\t(uuid "{uid("sym-" + ref)}")\n']
    for name, val, dx, dy, hide in PROPS:
        v = ref if val is None else val
        px, py = (x0 + dx, dy) if not hide else (x0, Y)
        s.append(f'\t\t(property "{name}" "{v}"\n'
                 f"\t\t\t(at {_fmt(px)} {_fmt(py)} 0)\n"
                 + (eff_hidden if hide else eff_shown) + "\t\t)\n")
    for n in range(1, 10):
        s.append(f'\t\t(pin "{n}"\n'
                 f'\t\t\t(uuid "{uid("%s-pin%d" % (ref, n))}")\n\t\t)\n')
    s.append('\t\t(instances\n\t\t\t(project "faff2_cbs1"\n'
             f'\t\t\t\t(path "{PATH}"\n\t\t\t\t\t(reference "{ref}")\n'
             "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
    return "".join(s)


def cluster(ref, gnd_ref, x0):
    """Everything the new footprint needs that the old one did not."""
    out_x, rail_x = x0 + OUT_DX, x0 + RAIL_DX
    add = [instance(ref, x0)]
    # VOUT to the first output cap - 1.27 mm shorter than the SOT23's OUT stub
    add.append(wire((out_x, VIN_Y), (x0 + CAP_X, VIN_Y), ref + "-out"))
    # SENSE back to VOUT, at the regulator
    add.append(wire((out_x, VIN_Y), (out_x, SENSE_Y), ref + "-sense"))
    add.append(junction(out_x, VIN_Y, ref + "-j-vout"))
    # GND, GND and EPAD: three pins on a 2.54 row, stubbed to one rail that
    # ends in a single downward GND - the schematic-style dense-row rule
    for n, gy in enumerate(GND_Y):
        add.append(wire((rail_x, gy), (x0, gy), "%s-gstub%d" % (ref, n)))
    for n in range(len(GND_Y)):
        lo = GND_Y[n]
        hi = GND_Y[n + 1] if n + 1 < len(GND_Y) else GND_Y[-1] + 2.54
        add.append(wire((rail_x, lo), (rail_x, hi), "%s-grail%d" % (ref, n)))
        if n:
            add.append(junction(rail_x, lo, "%s-gj%d" % (ref, n)))
    add.append(no_connect(out_x, PG_Y, ref + "-nc-pg"))
    return "".join(add)


def main():
    text = subprocess.run(["git", "show", "HEAD:" + SHEET], check=True,
                          capture_output=True, text=True).stdout

    add = []
    for ref, gnd_ref, x0, cap in LDOS:
        text = drop_symbol(text, ref)
        text = drop_wire(text, (x0 + 20.32, VIN_Y), (x0 + CAP_X, VIN_Y))
        text = drop_wire(text, (x0 + 10.16, NC_Y), (x0 + 10.16, GND_Y[0]))
        # the GND that hung under the SOT23 becomes the new rail's terminus
        text = move_symbol(text, gnd_ref,
                           x0 + RAIL_DX - (x0 + 10.16), GND_Y[-1] + 2.54 - GND_Y[0])
        text = retype_symbol(text, cap, CIN, "10uF")
        add.append(cluster(ref, gnd_ref, x0))
    text = text.replace("\t(junction\n", "".join(add) + "\t(junction\n", 1)

    for ref, prop, x, y in FIELD_FIXES:
        text = set_field(text, ref, prop, x, y)

    for old, new in TEXT_EDITS:
        assert text.count(old) == 1, old
        text = text.replace(old, new)

    # embedded library: the new regulator, and the 0805 25 V input cap
    for src, name, anchor in (
            (LIBSRC, LIB, '\t\t(symbol "Amodo_Power_ICs:TPS7A2050PDBV"\n'),
            (CAPSRC, CIN, '\t\t(symbol "Amodo_Capacitors:CAP_MLCC_10uF_0603_20%_10V"\n')):
        s = open(src, encoding="utf-8").read()
        sym = block(s, s.index('\t(symbol "%s"\n' % name.split(":", 1)[1]) + 1)
        sym = re.sub(r'^\(symbol "', '(symbol "%s:' % name.split(":", 1)[0],
                     sym, count=1)
        sym = "\n".join("\t" + l if l else l for l in sym.split("\n"))
        assert text.count(anchor) == 1, anchor
        text = text.replace(anchor, "\t\t" + sym.lstrip("\t") + "\n" + anchor, 1)

    # the old TPS7A20 symbol is no longer instantiated
    s, e = (text.index('\t\t(symbol "Amodo_Power_ICs:TPS7A2050PDBV"\n'), 0)
    e = s + len(block(text, s + 2)) + 2
    text = text[:s] + text[e + 1:]

    open(SHEET, "w", encoding="utf-8", newline="\n").write(text)
    print("U302/U303 -> ADPL42005ACPZ-5.0-R7; C309/C312 -> 10uF 0805 25V")


if __name__ == "__main__":
    main()
