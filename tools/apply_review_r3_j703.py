#!/usr/bin/env python3
"""Round 3 item 2 - temp_sense: TP707..TP711 become one keyed LA header, J703.

Five separate hooks on the SPI2 nets meant five probe leads and five chances to
slip a clip off a 47R terminator. `loadcell_afe` (J502) and `linear_encoder`
(J603) already solved this with the Amodo keyed 0.1" socket - one plug carries
the whole digital interface - so this is the third instance of a settled
pattern, not a new idea. Channel order copies J603 exactly: CH0..CH4 on pins
1..5, CH5..CH7 no-connect, GND on 9 and 10 for the analyser's ground leads.

Two things drove the placement:

  * The header reaches its nets by **local labels**, the way J502 does, not by
    doglegging five wires at 7.62 mm pitch into a 2.54 mm pin stack.
  * A label must sit entirely over its wire, so each side needs ~19 mm of run.
    That is 66 mm of cluster, and the right-hand third of the "ADS1120 SUPPLIES
    AND SPI2" box is only 58 mm wide with the U701 bundle descending through the
    left 20 mm of it. The clean space is the empty band under the box, so the
    box border moves down from y=154.94 to y=181.61 to take the header in.

Re-runnable: rebuilds the sheet from `git show HEAD:<path>`.
"""
import re
import subprocess
import uuid

# Rebuilt from a PINNED base, not HEAD: once this script's own commit lands,
# HEAD already contains its edits and a re-run would double-apply them or
# assert. Item 1, the checker sweep.
BASE = "310469b"

SHEET = "hardware/kicad/faff2_cbs1/temp_sense.kicad_sch"
SRC = "hardware/kicad/faff2_cbs1/linear_encoder.kicad_sch"
NS = uuid.UUID("4e1514d5-7414-55f0-9f35-1d20cac21a6b")     # temp_sense's own uuid
PATH = "/5edb00fd-45c9-5fe7-8d71-adbf38f38546/4e1514d5-7414-55f0-9f35-1d20cac21a6b"
LIB = ("Amodo_Connectors:Header_Female_10-way_2-row_"
       "Straight_2.54mm_THT__KEYED_LOGIC_TEST")

DROP_SYMS = ["TP707", "TP708", "TP709", "TP710", "TP711"]

# the TP taps: each bus row was split at x=220.98 to land a hook on it
DROP_JUNCTIONS = [(220.98, 114.30), (220.98, 121.92),
                  (220.98, 129.54), (220.98, 137.16)]
MERGE_WIRES = [                       # (drop, drop) -> (add)
    (((208.28, 114.30), (220.98, 114.30)), ((220.98, 114.30), (241.30, 114.30)),
     ((208.28, 114.30), (241.30, 114.30))),
    (((208.28, 121.92), (220.98, 121.92)), ((220.98, 121.92), (241.30, 121.92)),
     ((208.28, 121.92), (241.30, 121.92))),
    (((208.28, 129.54), (220.98, 129.54)), ((220.98, 129.54), (241.30, 129.54)),
     ((208.28, 129.54), (241.30, 129.54))),
    (((208.28, 137.16), (220.98, 137.16)), ((220.98, 137.16), (241.30, 137.16)),
     ((208.28, 137.16), (241.30, 137.16))),
]

# J703 at (209.55, 165.10): left pins x=201.93, right x=217.17,
# rows y = 162.56 / 165.10 / 167.64 / 170.18 / 172.72
JX, JY = 209.55, 165.10
LX, RX = JX - 7.62, JX + 7.62
ROW = [JY - 2.54 + 2.54 * k for k in range(5)]
LABEL_L, LABEL_R = 182.88, 236.22          # 19.05 mm of wire each side

CHANNELS = [                               # (pin, x, y, net) - J603's order
    ("1", LX, ROW[0], "ADS1120_nDRDY"),
    ("2", RX, ROW[0], "ADS1120_nCS"),
    ("3", LX, ROW[1], "CONFIG_SPI_SCK"),
    ("4", RX, ROW[1], "CONFIG_SPI_MOSI"),
    ("5", LX, ROW[2], "CONFIG_SPI_MISO"),
]
NO_CONNECTS = [(RX, ROW[2]), (LX, ROW[3]), (RX, ROW[3])]   # CH5, CH6, CH7
GND_PINS = [("#PWR720", LX), ("#PWR721", RX)]              # pins 9 and 10

# U701's ~{DRDY} stub lost its hook, so it needs the net name the header joins
# it by - the one actuator-sch-afe.md already uses. It goes at the wire's end,
# right-justified, reading back over the wire.
DRDY_LABEL = (220.98, 106.68, "ADS1120_nDRDY")

# TP712's GND cluster goes up 5.08 mm to make room for that label - and it
# needed to move anyway. Its arrow's tip sat exactly on the DRDY wire at
# y=106.68: no connection, but it draws as one, and it is why the label had
# nowhere to go. The band above is empty, and the 3.81 mm net-name offset
# travels with the symbol, so round 2's rule is preserved.
MOVE = {"TP712": (0, -5.08), "#PWR718": (0, -5.08)}
MOVE_WIRES = [(((212.09, 99.06), (212.09, 104.14)),
               ((212.09, 93.98), (212.09, 99.06)))]

BOX_OLD, BOX_NEW = "(end 238.76 154.94)", "(end 238.76 181.61)"

TEXT_EDITS = [
    ("TP707 only; firmware polls", "J703 CH0 only; firmware polls"),
    ("  TP707..TP711 hooks on the SPI2 nets, TP712/TP713 GND hooks.",
     "  TP712/TP713 GND hooks.\\n"
     "  J703 is the logic-analyser socket (Amodo keyed 0.1in, 8510-4500PL):\\n"
     "  one plug for the whole SPI2 interface, in place of the TP707..TP711\\n"
     "  hooks, as on J502 and J603.  CH0 ADS1120_nDRDY, CH1 ADS1120_nCS,\\n"
     "  CH2 CONFIG_SPI_SCK, CH3 CONFIG_SPI_MOSI, CH4 CONFIG_SPI_MISO,\\n"
     "  CH5..CH7 spare, 9 and 10 GND for the leads.  Tapped MCU-side of\\n"
     "  R712..R715, so the bus is still visible with an isolation link out."),
]


def uid(key):
    return str(uuid.uuid5(NS, key))


def block(text, start):
    """The balanced s-expression beginning at `start`, quotes respected."""
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


def move_symbol(text, ref, dx, dy):
    """Shift a symbol and every field it owns - the fields are absolute."""
    i = text.index('(property "Reference" "%s"' % ref)
    start = text.rindex("\n\t(symbol\n", 0, i) + 2
    blk = block(text, start)
    def shift(m):
        return "(at %s %s%s)" % (_fmt(float(m.group(1)) + dx),
                                 _fmt(float(m.group(2)) + dy), m.group(3))
    new = re.sub(r"\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)", shift, blk)
    return text[:start] + new + text[start + len(blk):]


def _fmt(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def drop_symbol(text, ref):
    i = text.index('(property "Reference" "%s"' % ref)
    # +2 so start lands on the "(", not on the leading tab - block() tolerates
    # the tab but then the caller's own "\t" prefix makes the match fail, and
    # str.replace says nothing when it matches nothing.
    start = text.rindex("\n\t(symbol\n", 0, i) + 2
    blk = "\t" + block(text, start) + "\n"
    assert blk in text, ref
    return text.replace(blk, "", 1)


def drop_geom(text, tag, pred):
    """Remove every top-level `tag` block whose parsed coords satisfy pred."""
    out, pos = text, 0
    while True:
        i = out.find("\n\t(%s\n" % tag, pos)
        if i < 0:
            return out
        blk = block(out, i + 1)
        nums = [float(v) for v in re.findall(r"[-\d]+\.?\d*", blk)
                if re.match(r"^-?\d+\.?\d*$", v)]
        if pred(blk, nums):
            out = out[:i + 1] + out[i + 1 + len(blk) + 1:]
            pos = i
        else:
            pos = i + 1


def wire(p, q, key):
    return (f"\t(wire\n\t\t(pts\n\t\t\t(xy {p[0]:g} {p[1]:g}) "
            f"(xy {q[0]:g} {q[1]:g})\n\t\t)\n\t\t(stroke\n\t\t\t(width 0)\n"
            f"\t\t\t(type default)\n\t\t)\n\t\t(uuid \"{uid(key)}\")\n\t)\n")


def label(x, y, name, side, key=None):
    """A local label reading back over its wire - the skill's wire-end form."""
    rot, just = (0, "left bottom") if side == "l" else (180, "right bottom")
    return (f'\t(label "{name}"\n\t\t(at {x:g} {y:g} {rot})\n\t\t(effects\n'
            f"\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
            f"\t\t\t(justify {just})\n\t\t)\n"
            f'\t\t(uuid "{uid(key or "label-" + name)}")\n\t)\n')


def no_connect(x, y):
    return (f"\t(no_connect\n\t\t(at {x:g} {y:g})\n"
            f'\t\t(uuid "{uid("nc-%g-%g" % (x, y))}")\n\t)\n')


def gnd(ref, x, y):
    """A GND power symbol with round 2's pinned label: centred, 3.81 below."""
    hid = ("\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
           "\t\t\t\t)\n\t\t\t\t(justify left)\n\t\t\t\t(hide yes)\n\t\t\t)\n")
    props = [("Reference", ref, x + 2.54, y - 1.27, hid),
             ("Value", "GND", x, y + 3.81,
              "\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n"
              "\t\t\t\t)\n\t\t\t)\n"),
             ("Footprint", "", x, y, hid),
             ("Datasheet", "", x, y, hid),
             ("Description",
              'Power symbol creates a global label with name \\"GND\\" , ground',
              x, y, hid),
             ("SymLifecycle", "tested", x, y, hid)]
    s = ['\t(symbol\n\t\t(lib_id "Amodo_Symbols:GND")\n'
         f"\t\t(at {x:g} {y:g} 0)\n\t\t(unit 1)\n"
         "\t\t(exclude_from_sim no)\n\t\t(in_bom no)\n\t\t(on_board no)\n"
         f'\t\t(dnp no)\n\t\t(uuid "{uid("sym-" + ref)}")\n']
    for name, val, px, py, eff in props:
        s.append(f'\t\t(property "{name}" "{val}"\n\t\t\t(at {px:g} {py:g} 0)\n'
                 f"\t\t\t(do_not_autoplace yes)\n{eff}\t\t)\n")
    s.append(f'\t\t(pin "1"\n\t\t\t(uuid "{uid("pin-" + ref)}")\n\t\t)\n')
    s.append('\t\t(instances\n\t\t\t(project "faff2_cbs1"\n'
             f'\t\t\t\t(path "{PATH}"\n\t\t\t\t\t(reference "{ref}")\n'
             "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
    return "".join(s)


def header(src_text):
    """J703, its property placement copied from J603's instance."""
    fields = [
        ("Reference", "J703", JY - 8.382, False),
        ("Value", "8510-4500PL", JY + 15.24, True),
        ("Footprint", "Amodo:8510-4500PL_LOGIC_TEST", JY + 15.24, True),
        ("Datasheet", "https://www.mouser.co.uk/datasheet/3/167/1/ts0413.pdf",
         JY + 15.24, True),
        ("Description", '10-way 0.1\\" keyed PCB THT socket, for connecting '
         "8-channel Hobby Electronics Logic Analyser", JY + 15.24, True),
        ("SymLifecycle", "reviewed", JY + 15.24, True),
        ("mpn", "8510-4500PL ", JY + 15.24, True),
        ("Use With", "logic analyser", JY + 15.24, True),
    ]
    s = [f'\t(symbol\n\t\t(lib_id "{LIB}")\n\t\t(at {JX:g} {JY:g} 0)\n'
         "\t\t(unit 1)\n\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n"
         "\t\t(on_board yes)\n\t\t(dnp no)\n"
         f'\t\t(uuid "{uid("sym-J703")}")\n']
    for name, val, py, hide in fields:
        show = "\t\t\t(show_name)\n" if name == "Use With" else ""
        s.append(f'\t\t(property "{name}" "{val}"\n'
                 f"\t\t\t(at {JX:g} {py:g} 0)\n{show}\t\t\t(effects\n"
                 "\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n"
                 + ("\t\t\t\t(hide yes)\n" if hide else "")
                 + "\t\t\t)\n\t\t)\n")
    for n in range(1, 11):
        s.append(f'\t\t(pin "{n}"\n\t\t\t(uuid "{uid("J703-pin%d" % n)}")\n'
                 "\t\t)\n")
    s.append('\t\t(instances\n\t\t\t(project "faff2_cbs1"\n'
             f'\t\t\t\t(path "{PATH}"\n\t\t\t\t\t(reference "J703")\n'
             "\t\t\t\t\t(unit 1)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n\t)\n")
    return "".join(s)


def main():
    text = subprocess.run(["git", "show", BASE + ":" + SHEET], check=True,
                          capture_output=True, text=True).stdout

    for ref in DROP_SYMS:
        text = drop_symbol(text, ref)

    text = drop_geom(text, "junction", lambda b, n: any(
        abs(n[0] - x) < 0.01 and abs(n[1] - y) < 0.01 for x, y in DROP_JUNCTIONS))

    for a_, b_, merged in MERGE_WIRES:
        for seg in (a_, b_):
            text = drop_geom(text, "wire", lambda b, n, s=seg: (
                abs(n[0] - s[0][0]) < 0.01 and abs(n[1] - s[0][1]) < 0.01 and
                abs(n[2] - s[1][0]) < 0.01 and abs(n[3] - s[1][1]) < 0.01))
        text = text.replace("\t(junction\n",
                            wire(*merged, "merge-%g" % merged[0][1])
                            + "\t(junction\n", 1)

    for ref, (dx, dy) in MOVE.items():
        text = move_symbol(text, ref, dx, dy)
    for old, new in MOVE_WIRES:
        before = text
        text = drop_geom(text, "wire", lambda b, n, s=old: (
            abs(n[0] - s[0][0]) < 0.01 and abs(n[1] - s[0][1]) < 0.01 and
            abs(n[2] - s[1][0]) < 0.01 and abs(n[3] - s[1][1]) < 0.01))
        assert text != before, old
        text = text.replace("\t(junction\n",
                            wire(*new, "moved-%g-%g" % new[0]) + "\t(junction\n", 1)

    # the header, its stubs, its labels and its two grounds
    add = [header(open(SRC, encoding="utf-8").read())]
    for pin, x, y, net in CHANNELS:
        side = "l" if x == LX else "r"
        far = LABEL_L if side == "l" else LABEL_R
        add.append(wire((far, y), (x, y), "stub-" + net))
        add.append(label(far, y, net, side))
    for x, y in NO_CONNECTS:
        add.append(no_connect(x, y))
    for ref, x in GND_PINS:
        add.append(wire((x, ROW[4]), (x, ROW[4] + 2.54), "gnd-" + ref))
        add.append(gnd(ref, x, ROW[4] + 2.54))
    add.append(label(*DRDY_LABEL, "r", key="drdy-stub-label"))
    text = text.replace("\t(junction\n", "".join(add) + "\t(junction\n", 1)

    for old, new in TEXT_EDITS:
        assert text.count(old) == 1, old
        text = text.replace(old, new)

    # the block box grows to take the header in
    assert text.count(BOX_OLD) == 1
    text = text.replace(BOX_OLD, BOX_NEW)

    # the embedded library needs the header's graphics
    src = open(SRC, encoding="utf-8").read()
    sym = block(src, src.index('\t\t(symbol "%s"\n' % LIB) + 2)
    anchor = '\t\t(symbol "Amodo_Connectors:TestPoint"\n'
    assert text.count(anchor) == 1
    text = text.replace(anchor, "\t\t" + sym + "\n" + anchor, 1)

    open(SHEET, "w", encoding="utf-8", newline="\n").write(text)
    print(f"J703 at ({JX}, {JY}); dropped {', '.join(DROP_SYMS)}")


if __name__ == "__main__":
    main()
