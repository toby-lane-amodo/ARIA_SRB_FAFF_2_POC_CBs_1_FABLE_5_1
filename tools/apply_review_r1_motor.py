#!/usr/bin/env python3
"""Round-1 captain review, motor_drive batch - motor_drive.kicad_sch.

Re-runnable: rebuilds the sheet from the committed HEAD copy each time.

Captain's four points:
  1  the 24 V feed note names R101/R102 and reads as fit-one-or-the-other;
     the parts are R1101/R1102, in series, both fitted
  2  text overlap around C1101
  3  sheet entry/exit labels whose text lies over their own wire
  4  bulk decoupling, and whether it goes per FET

Point 4 is the authorised design change; everything else is text and placement.
Reasoning is in docs/decisions/actuator-sch-review-r1.md.
"""
import os, re, subprocess, sys, uuid

LIB_DIR = "/mnt/c/Amodo/AmodoKiCadLib"
SHEET = "hardware/kicad/faff2_cbs1/motor_drive.kicad_sch"
SHEET_UUID = "3a19ad2f-9f2c-5b39-a51a-1f7ba4c04d29"     # replaced at run time
INST_PATH = "/5edb00fd-45c9-5fe7-8d71-adbf38f38546/25605169-cb1e-52bd-8388-77d0027da969"
PROJECT = "faff2_cbs1"


def uid(key):
    return str(uuid.uuid5(uuid.UUID(SHEET_UUID), "review-r1-motor/" + key))


def g(v):
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def block_end(t, i):
    d, j = 0, i
    while True:
        c = t[j]
        if c == '"':
            j += 1
            while t[j] != '"' or t[j - 1] == "\\":
                j += 1
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return j + 1
        j += 1


_libcache = {}


def libsym(lib, name):
    if lib not in _libcache:
        _libcache[lib] = open(os.path.join(LIB_DIR, lib + ".kicad_sym"),
                              encoding="utf-8").read()
    src = _libcache[lib]
    i = src.index('(symbol "%s"\n' % name)
    return src[i:block_end(src, i)]


# 2. the bulk column at 8.89 pitch left C1101's fields on C1102's body
MOVE = {
    "C1102":   (68.58, 67.31, 0, {"Reference": (70.485, 65.405, 0),
                                  "Value":     (70.485, 69.215, 0)}),
    "#PWR1103": (68.58, 73.66, 0, {}),
    "C1103":   (80.01, 67.31, 0, {"Reference": (81.915, 65.405, 0),
                                  "Value":     (81.915, 69.215, 0)}),
    "#PWR1104": (80.01, 73.66, 0, {}),
    "C1104":   (90.17, 67.31, 0, {"Reference": (92.075, 65.405, 0),
                                  "Value":     (92.075, 69.215, 0)}),
    "#PWR1105": (90.17, 73.66, 0, {}),
    # TP1103's pad sat in the row the capacitor values occupy; the respaced
    # column pushes C1104 into it, so the test point moves right with it
    "TP1103": (101.60, 72.39, 0, {"Reference": (103.505, 71.12, 0)}),
}

# 4. one decoupling pair per half-bridge, at the leg it belongs to
NEW_CAPS = [
    # ref, lib symbol, x, y
    ("C1119", "CAP_MLCC_2.2uF_1206_10%_100V", 275.59, 78.74),
    ("C1120", "CAP_MLCC_100nF_0805_10%_100V", 285.75, 78.74),
    ("C1121", "CAP_MLCC_2.2uF_1206_10%_100V", 311.15, 107.95),
    ("C1122", "CAP_MLCC_100nF_0805_10%_100V", 321.31, 107.95),
    ("C1123", "CAP_MLCC_2.2uF_1206_10%_100V", 292.10, 158.75),
    ("C1124", "CAP_MLCC_100nF_0805_10%_100V", 302.26, 158.75),
]
NEW_GND = {
    "#PWR1143": (275.59, 83.82), "#PWR1144": (285.75, 83.82),
    "#PWR1145": (311.15, 113.03), "#PWR1146": (321.31, 113.03),
    "#PWR1147": (292.10, 163.83), "#PWR1148": (302.26, 163.83),
}
NEW_LABELS = [("V24_MOT", 290.83, 73.66), ("V24_MOT", 326.39, 102.87),
              ("V24_MOT", 307.34, 153.67)]

# 3. a hierarchical label whose wire arrives from the left needs its text on
#    the right, or the wire runs straight through it
HLABELS = {
    # name -> (old x, old y) : (new x, new y, rot, justify)
    ("+24V_SW", 25.40, 30.48):         (25.40, 30.48, 0, "left"),
    ("MOTOR_FETTEMP", 71.12, 128.27):  (71.12, 128.27, 0, "left"),
    ("MOTOR_ENCODER_A", 99.06, 190.50): (91.44, 190.50, 0, "left"),
    ("MOTOR_ENCODER_B", 99.06, 204.47): (91.44, 204.47, 0, "left"),
    ("MOTOR_ENCODER_I", 99.06, 218.44): (91.44, 218.44, 0, "left"),
    ("HALL1", 99.06, 236.22):          (91.44, 236.22, 0, "left"),
    ("HALL2", 99.06, 250.19):          (91.44, 250.19, 0, "left"),
    ("HALL3", 99.06, 264.16):          (91.44, 264.16, 0, "left"),
}

DEL_WIRES = [
    # bulk column re-spaced
    (57.15, 60.96, 66.04, 60.96), (66.04, 60.96, 66.04, 64.77),
    (66.04, 60.96, 74.93, 60.96), (66.04, 69.85, 66.04, 73.66),
    (74.93, 60.96, 74.93, 64.77), (74.93, 60.96, 83.82, 60.96),
    (74.93, 69.85, 74.93, 73.66), (83.82, 60.96, 83.82, 64.77),
    (83.82, 60.96, 110.49, 60.96), (83.82, 69.85, 83.82, 73.66),
    # encoder / hall label column pulled left to make room for its own text
    (88.90, 77.47, 96.52, 77.47), (96.52, 77.47, 110.49, 77.47),
    (96.52, 72.39, 96.52, 77.47),
    (62.23, 190.50, 99.06, 190.50), (69.85, 204.47, 99.06, 204.47),
    (77.47, 218.44, 99.06, 218.44), (62.23, 236.22, 99.06, 236.22),
    (69.85, 250.19, 99.06, 250.19), (77.47, 264.16, 99.06, 264.16),
]
ADD_WIRES = [
    (57.15, 60.96, 68.58, 60.96), (68.58, 60.96, 68.58, 64.77),
    (68.58, 60.96, 80.01, 60.96), (68.58, 69.85, 68.58, 73.66),
    (80.01, 60.96, 80.01, 64.77), (80.01, 60.96, 90.17, 60.96),
    (80.01, 69.85, 80.01, 73.66), (90.17, 60.96, 90.17, 64.77),
    (90.17, 60.96, 110.49, 60.96), (90.17, 69.85, 90.17, 73.66),
    (88.90, 77.47, 101.60, 77.47), (101.60, 77.47, 110.49, 77.47),
    (101.60, 72.39, 101.60, 77.47),
    (62.23, 190.50, 91.44, 190.50), (69.85, 204.47, 91.44, 204.47),
    (77.47, 218.44, 91.44, 218.44), (62.23, 236.22, 91.44, 236.22),
    (69.85, 250.19, 91.44, 250.19), (77.47, 264.16, 91.44, 264.16),
    # leg A decoupling, in the clear band between the phase-A and phase-B fan-outs
    (275.59, 73.66, 285.75, 73.66), (285.75, 73.66, 290.83, 73.66),
    (275.59, 73.66, 275.59, 76.20), (275.59, 81.28, 275.59, 83.82),
    (285.75, 73.66, 285.75, 76.20), (285.75, 81.28, 285.75, 83.82),
    # leg B decoupling, right of the fan-out and above phase B's own gates
    (311.15, 102.87, 321.31, 102.87), (321.31, 102.87, 326.39, 102.87),
    (311.15, 102.87, 311.15, 105.41), (311.15, 110.49, 311.15, 113.03),
    (321.31, 102.87, 321.31, 105.41), (321.31, 110.49, 321.31, 113.03),
    # leg C decoupling, above phase C's own gates
    (292.10, 153.67, 302.26, 153.67), (302.26, 153.67, 307.34, 153.67),
    (292.10, 153.67, 292.10, 156.21), (292.10, 161.29, 292.10, 163.83),
    (302.26, 153.67, 302.26, 156.21), (302.26, 161.29, 302.26, 163.83),
]
DEL_JUNCTIONS = [(66.04, 60.96), (74.93, 60.96), (83.82, 60.96), (96.52, 77.47)]
ADD_JUNCTIONS = [(68.58, 60.96), (80.01, 60.96), (90.17, 60.96), (101.60, 77.47),
                 (285.75, 73.66), (321.31, 102.87), (302.26, 153.67)]

OLD_NOTE = ("R101 isolation link, R102 current-measurement break.\\n"
            "Both fitted. Opening R101 leaves the whole logic side\\n"
            "powered with the actuator dead - TEST_PLAN.md 3.3, step 8.")
NEW_NOTE = ("R1101 and R1102 are in SERIES and both fitted - two\\n"
            "0R links, not alternatives to each other.\\n"
            "R1101 is the isolation link: open it and the logic\\n"
            "side stays powered, actuator dead (TEST_PLAN 3.3).\\n"
            "R1102 is the current-measurement break: lift it and\\n"
            "fit a shunt to read the motor bus current.")

# the 24 V note grows down into TP1102 at six lines, so it starts higher; the
# temperature note moves up to clear MOTOR_FETTEMP's text, now on its right
TEXT_MOVES = {(46.99, 41.91): (46.99, 34.29), (76.20, 118.11): (76.20, 113.98)}

NEW_TEXT = [(251.46, 30.48,
             "BRIDGE DECOUPLING   one 2.2 uF + 100 nF pair per half-bridge:\\n"
             "C1119/C1120 phase U, C1121/C1122 phase V, C1123/C1124 phase W.\\n"
             "The 210 uF bulk at the bus entry is too far round the loop to\\n"
             "serve commutation; each pair goes hard against its own leg,\\n"
             "across the high-side drain and the shunt return.  Not per FET -\\n"
             "a capacitor across one FET is a snubber, not decoupling, and is\\n"
             "a bring-up decision (SLVSDJ3D 10, 11.1).")]


def props_of(sym_text):
    out, pos = [], 0
    while True:
        i = sym_text.find('(property "', pos)
        if i < 0:
            break
        e = block_end(sym_text, i)
        blk = sym_text[i:e]
        m = re.match(r'\(property "([^"]+)" ("[^"\\]*(?:\\.[^"\\]*)*")', blk)
        out.append((m.group(1), m.group(2), "(hide yes)" in blk))
        pos = e
    return out


def build_cap(lib, name, ref, x, y):
    sym = libsym(lib, name)
    fields = {"Reference": (x + 1.905, y - 1.905, 0),
              "Value":     (x + 1.905, y + 1.905, 0)}
    L = ["\t(symbol", '\t\t(lib_id "%s:%s")' % (lib, name),
         "\t\t(at %s %s 0)" % (g(x), g(y)), "\t\t(unit 1)",
         "\t\t(exclude_from_sim no)", "\t\t(in_bom yes)", "\t\t(on_board yes)",
         "\t\t(dnp no)", "\t\t(fields_autoplaced no)",
         '\t\t(uuid "%s")' % uid("sym " + ref)]
    for pname, pval, hidden in props_of(sym):
        if pname == "Reference":
            pval = '"%s"' % ref
        px, py, prot = fields.get(pname, (x, y, 0))
        L.append('\t\t(property "%s" %s' % (pname, pval))
        L.append("\t\t\t(at %s %s %d)" % (g(px), g(py), prot))
        L += ["\t\t\t(effects", "\t\t\t\t(font", "\t\t\t\t\t(size 1.27 1.27)",
              "\t\t\t\t)", "\t\t\t\t(justify left)"]
        if hidden or pname not in fields:
            L.append("\t\t\t\t(hide yes)")
        L += ["\t\t\t)", "\t\t)"]
    for pn in ("1", "2"):
        L += ['\t\t(pin "%s"' % pn,
              '\t\t\t(uuid "%s")' % uid("pin %s %s" % (ref, pn)), "\t\t)"]
    L += ["\t\t(instances", '\t\t\t(project "%s"' % PROJECT,
          '\t\t\t\t(path "%s"' % INST_PATH,
          '\t\t\t\t\t(reference "%s")' % ref, "\t\t\t\t\t(unit 1)",
          "\t\t\t\t)", "\t\t\t)", "\t\t)", "\t)"]
    return "\n".join(L) + "\n"


def embed(lib, name):
    sym = libsym(lib, name)
    lines = sym.split("\n")
    lines[0] = '(symbol "%s:%s"' % (lib, name)
    return "\t\t" + "\n".join([lines[0]] + ["\t" + l for l in lines[1:]]) + "\n"


def norm(v):
    return round(float(v), 3)


def drop_blocks(t, keyfn, targets, marker):
    out, pos, hits = [], 0, set()
    while True:
        i = t.find(marker, pos)
        if i < 0:
            break
        e = block_end(t, i + 1)
        blk = t[i:e]
        key = keyfn(blk)
        out.append(t[pos:i])
        if key in targets:
            hits.add(key)
        else:
            out.append(blk)
        pos = e
    out.append(t[pos:])
    return "".join(out), hits


def wire_key(blk):
    m = re.search(r"\(xy ([-\d.]+) ([-\d.]+)\) \(xy ([-\d.]+) ([-\d.]+)\)", blk)
    k = tuple(norm(v) for v in m.groups())
    return min(k, k[2:] + k[:2])


def at_key(blk):
    m = re.search(r"\(at ([-\d.]+) ([-\d.]+)\)", blk)
    return tuple(norm(v) for v in m.groups())


def wire_block(x1, y1, x2, y2):
    return ("\t(wire\n\t\t(pts\n\t\t\t(xy %s %s) (xy %s %s)\n\t\t)\n"
            "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type default)\n\t\t)\n"
            "\t\t(uuid \"%s\")\n\t)\n"
            % (g(x1), g(y1), g(x2), g(y2),
               uid("wire %g %g %g %g" % (x1, y1, x2, y2))))


def junction_block(x, y):
    return ("\t(junction\n\t\t(at %s %s)\n\t\t(diameter 0)\n\t\t(color 0 0 0 0)\n"
            "\t\t(uuid \"%s\")\n\t)\n" % (g(x), g(y), uid("junction %g %g" % (x, y))))


def label_block(name, x, y):
    return ('\t(label "%s"\n\t\t(at %s %s 0)\n\t\t(effects\n\t\t\t(font\n'
            '\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n\t\t\t(justify left bottom)\n'
            '\t\t)\n\t\t(uuid "%s")\n\t)\n'
            % (name, g(x), g(y), uid("label %s %g %g" % (name, x, y))))


def text_block(x, y, s):
    return ('\t(text "%s"\n\t\t(exclude_from_sim no)\n\t\t(at %s %s 0)\n'
            '\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n'
            '\t\t\t(justify left top)\n\t\t)\n\t\t(uuid "%s")\n\t)\n'
            % (s, g(x), g(y), uid("text %g %g" % (x, y))))


def main():
    global SHEET_UUID
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)
    t = subprocess.check_output(["git", "show", "HEAD:" + SHEET], text=True)
    SHEET_UUID = re.search(r'\n\t\(uuid "([0-9a-f-]+)"\)', t).group(1)

    # ---- lib_symbols: the 2.2 uF is new to this sheet
    if 'Amodo_Capacitors:CAP_MLCC_2.2uF_1206_10%_100V' not in t:
        ls = t.index("\t(lib_symbols\n")
        le = block_end(t, ls + 1)
        blk = t[ls:le]
        cut = blk.rindex("\t)")
        blk = blk[:cut] + embed("Amodo_Capacitors",
                                "CAP_MLCC_2.2uF_1206_10%_100V") + blk[cut:]
        t = t[:ls] + blk + t[le:]

    # ---- move existing symbols
    out, pos, seen, gnd_template = [], 0, set(), None
    while True:
        i = t.find("\t(symbol\n", pos)
        if i < 0:
            break
        e = block_end(t, i + 1)
        blk = t[i:e]
        m = re.search(r'\(property "Reference" "([^"]+)"', blk)
        ref = m.group(1) if m else None
        if gnd_template is None and ref == "#PWR1137":
            gnd_template = blk
        out.append(t[pos:i])
        if ref in MOVE:
            x, y, rot, fl = MOVE[ref]
            blk = re.sub(r"\n\t\t\(at [^\n]*\)",
                         "\n\t\t(at %s %s %d)" % (g(x), g(y), rot), blk, count=1)

            def fix(pm, x=x, y=y, rot=rot, fl=fl):
                nm = pm.group(1)
                px, py, prot = fl.get(nm, (x, y, rot))
                return '(property "%s" %s\n\t\t\t(at %s %s %d)' % (
                    nm, pm.group(2), g(px), g(py), prot)
            blk = re.sub(r'\(property "([^"]+)" ("[^"\\]*(?:\\.[^"\\]*)*")'
                         r'\n\t\t\t\(at [^\n]*\)', fix, blk)
            seen.add(ref)
        out.append(blk)
        pos = e
    out.append(t[pos:])
    t = "".join(out)
    if set(MOVE) - seen:
        sys.exit("symbols not found: %s" % sorted(set(MOVE) - seen))

    # ---- new decoupling caps and their grounds
    newsyms = "".join(build_cap("Amodo_Capacitors", nm, ref, x, y)
                      for ref, nm, x, y in NEW_CAPS)
    for ref, (x, y) in NEW_GND.items():
        b = gnd_template
        b = re.sub(r"\n\t\t\(at [^\n]*\)", "\n\t\t(at %s %s 0)" % (g(x), g(y)),
                   b, count=1)
        b = re.sub(r'\(property "Reference" "[^"]+"\n\t\t\t\(at [^\n]*\)',
                   '(property "Reference" "%s"\n\t\t\t(at %s %s 0)'
                   % (ref, g(x), g(y - 6.35)), b)
        b = re.sub(r'\(property "(Value|Footprint|Datasheet|Description)" '
                   r'("[^"\\]*(?:\\.[^"\\]*)*")\n\t\t\t\(at [^\n]*\)',
                   lambda m: '(property "%s" %s\n\t\t\t(at %s %s 0)'
                             % (m.group(1), m.group(2), g(x),
                                g(y + 6.35 if m.group(1) == "Value" else y)), b)
        b = re.sub(r'\(uuid "[^"]+"\)\n\t\t\(property "Reference"',
                   '(uuid "%s")\n\t\t(property "Reference"' % uid("sym " + ref),
                   b, count=1)
        b = re.sub(r'\(pin "1"\n\t\t\t\(uuid "[^"]+"\)',
                   '(pin "1"\n\t\t\t(uuid "%s")' % uid("pin %s 1" % ref), b)
        b = re.sub(r'\(reference "[^"]+"\)', '(reference "%s")' % ref, b)
        newsyms += b
    anchor = t.index("\t(symbol\n")
    t = t[:anchor] + newsyms + t[anchor:]

    # ---- hierarchical labels: rotation, position and justification.
    # The (shape ...) line sits between the name and the (at ...), so walk the
    # blocks rather than pattern-matching across them.
    seen_hl, out, pos = set(), [], 0
    while True:
        i = t.find('\t(hierarchical_label "', pos)
        if i < 0:
            break
        e = block_end(t, i + 1)
        blk = t[i:e]
        m = re.match(r'\t\(hierarchical_label "([^"]+)"', blk)
        ma = re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", blk)
        key = (m.group(1), norm(ma.group(1)), norm(ma.group(2)))
        out.append(t[pos:i])
        if key in HLABELS:
            nx, ny, rot, how = HLABELS[key]
            seen_hl.add(key)
            blk = blk.replace(ma.group(0), "(at %s %s %d)" % (g(nx), g(ny), rot), 1)
            blk = re.sub(r"\(justify \w+\)", "(justify %s)" % how, blk)
        out.append(blk)
        pos = e
    out.append(t[pos:])
    t = "".join(out)
    if set(HLABELS) - seen_hl:
        sys.exit("hier labels not found: %s" % sorted(set(HLABELS) - seen_hl))

    # ---- notes
    if OLD_NOTE not in t:
        sys.exit("24 V note not found")
    t = t.replace(OLD_NOTE, NEW_NOTE, 1)
    for (ox, oy), (nx, ny) in TEXT_MOVES.items():
        old = "\t\t(at %s %s 0)" % (g(ox), g(oy))
        if old not in t:
            sys.exit("text anchor not found: %g,%g" % (ox, oy))
        t = t.replace(old, "\t\t(at %s %s 0)" % (g(nx), g(ny)), 1)

    # ---- wires and junctions
    t, hw = drop_blocks(t, wire_key,
                        {wire_key("(xy %g %g) (xy %g %g)" % w) for w in DEL_WIRES},
                        "\t(wire\n")
    t, hj = drop_blocks(t, at_key,
                        {tuple(norm(c) for c in j) for j in DEL_JUNCTIONS},
                        "\t(junction\n")
    mw = {wire_key("(xy %g %g) (xy %g %g)" % w) for w in DEL_WIRES} - hw
    mj = {tuple(norm(c) for c in j) for j in DEL_JUNCTIONS} - hj
    if mw or mj:
        sys.exit("wires not found: %s\njunctions: %s" % (sorted(mw), sorted(mj)))

    anchor = t.index("\t(symbol\n")
    t = (t[:anchor]
         + "".join(wire_block(*w) for w in ADD_WIRES)
         + "".join(junction_block(*j) for j in ADD_JUNCTIONS)
         + "".join(label_block(*l) for l in NEW_LABELS)
         + "".join(text_block(*x) for x in NEW_TEXT)
         + t[anchor:])

    with open(SHEET, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    print("motor_drive batch applied: %d caps added, %d moved, %d hier labels "
          "re-justified, %d wires removed, %d added"
          % (len(NEW_CAPS), len(MOVE), len(HLABELS), len(DEL_WIRES), len(ADD_WIRES)))


if __name__ == "__main__":
    main()
