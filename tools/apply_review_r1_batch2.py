#!/usr/bin/env python3
"""Round-1 captain review, batch 2 - power_rails.kicad_sch.

Re-runnable: rebuilds the sheet from the committed HEAD copy each time.

Captain's six points:
  1  no 4-way junctions (the U301 feedback node), and no test coverage on a
     PSU feedback node - TP301 and TP305 removed, which is also what turns
     both feedback nodes back into plain 3-way tees
  2  a dual test point at every regulator output, for a scope probe + ground
  3  series output 0R links horizontal, not vertical
  4  regulators moved onto the parts ARIA_EITSYS_CBs_1 uses, where they meet
     our requirements - U301 becomes an LMR51610XFDBVR
  5  rail ferrite beads horizontal, same reason as the 0R links
  6  power LEDs vertical

Point 4 is an authorised design change; everything else is placement.
Reasoning and the re-derived values are in docs/decisions/actuator-sch-review-r1.md.
"""
import os, re, subprocess, sys, uuid

LIB_DIR = "/mnt/c/Amodo/AmodoKiCadLib"
SHEET = "hardware/kicad/faff2_cbs1/power_rails.kicad_sch"
SHEET_UUID = "f48a7003-4839-5242-bafe-13cbac888ed8"
INST_PATH = "/5edb00fd-45c9-5fe7-8d71-adbf38f38546/cfac6e86-3b1f-5c4c-b992-5519585fa944"
PROJECT = "faff2_cbs1"
NS = uuid.UUID(SHEET_UUID)


def uid(key):
    return str(uuid.uuid5(NS, "review-r1-batch2/" + key))


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


def grab(src, marker):
    i = src.index(marker)
    return src[i:block_end(src, i)]


_libcache = {}


def libsym(lib, name):
    if lib not in _libcache:
        _libcache[lib] = open(os.path.join(LIB_DIR, lib + ".kicad_sym"),
                              encoding="utf-8").read()
    return grab(_libcache[lib], '(symbol "%s"\n' % name)


# ------------------------------------------------------------------ new parts
# ref -> (lib, symbol, x, y, rot, value or None, {property: (x, y, rot)})
REPLACE = {
    # 4. the pre-regulator moves to the buck ARIA_EITSYS_CBs_1 uses.  Same
    #    400 kHz, same 24 V input, 1 A against this rail's ~0.25 A.
    "U301":  ("Amodo_Power_ICs", "LMR51610XFDBVR", 66.04, 40.64, 0, "LMR51610",
              {"Reference": (63.50, 34.29, 0), "Value": (63.50, 36.69, 0)}),
    # VFB is 0.8 V on the LMR516xx, not 1.0 V: 100k / 16.9k gives 5.534 V
    "R304":  ("Amodo_Resistors", "RES_TNF_16.9k_0603_0.1%", 132.08, 68.58, 0, "16k9",
              {"Reference": (134.11, 69.58, 0), "Value": (134.11, 71.98, 0)}),
    # L re-derived for the 1 A part at 400 kHz: 33 uH, KIND = 0.32
    "L301":  ("Amodo_Inductors", "IND_SMD_33uH", 121.92, 53.34, 90, "33uH",
              {"Reference": (114.30, 47.94, 270), "Value": (114.30, 50.34, 270)}),
    # 2. dual test points at every regulator output
    "TP302": ("Amodo_Connectors", "TestPointDual", 190.50, 68.58, 270, "+5V5",
              {"Reference": (196.85, 69.85, 90), "Value": (196.85, 72.25, 90)}),
    "TP303": ("Amodo_Connectors", "TestPointDual", 281.94, 88.90, 270, "+5V",
              {"Reference": (288.29, 90.17, 90), "Value": (288.29, 92.57, 90)}),
    "TP304": ("Amodo_Connectors", "TestPointDual", 383.54, 88.90, 270, "+5VA",
              {"Reference": (389.89, 90.17, 90), "Value": (389.89, 92.57, 90)}),
    "TP306": ("Amodo_Connectors", "TestPointDual", 190.50, 176.53, 270, "+3V3",
              {"Reference": (196.85, 177.80, 90), "Value": (196.85, 180.20, 90)}),
    "TP307": ("Amodo_Connectors", "TestPointDual", 287.02, 186.69, 270, "+3V3A",
              {"Reference": (293.37, 187.96, 90), "Value": (293.37, 190.36, 90)}),
}

# ref -> (x, y, rot, {property: (x, y, rot)}) - placement only, same part
MOVE = {
    # 3. series 0R output links laid horizontal, so each rail runs one way
    "R305": (177.80, 53.34, 90, {"Reference": (176.53, 48.26, 270),
                                 "Value":     (176.53, 50.66, 270)}),
    "R306": (274.32, 73.66, 90, {"Reference": (273.05, 68.58, 270),
                                 "Value":     (273.05, 70.98, 270)}),
    "R307": (375.92, 73.66, 90, {"Reference": (374.65, 68.58, 270),
                                 "Value":     (374.65, 70.98, 270)}),
    "R312": (177.80, 161.29, 90, {"Reference": (176.53, 156.21, 270),
                                  "Value":     (176.53, 158.61, 270)}),
    # 5. the rail ferrite the same way up as the 0R links
    "FB301": (243.84, 171.45, 90, {"Reference": (240.03, 166.37, 270),
                                   "Value":     (240.03, 168.77, 270)}),
    # 6. power LED vertical, anode up out of R314
    "D303": (274.32, 200.66, 270, {"Reference": (276.35, 201.93, 90),
                                   "Value":     (276.35, 204.33, 90)}),
    # R314's fields sat left of its body, where "330R" ran into C324's GND
    # label; the LED standing up frees the right-hand side for them
    "R314": (274.32, 193.04, 0, {"Reference": (276.35, 194.04, 0),
                                 "Value":     (276.35, 196.44, 0)}),
}

# R314's fields were right-justified, so moving the anchor alone still grew the
# text back across the body - they read rightward from the anchor now.
JUSTIFY = {"R314": {"Reference": "left", "Value": "left"}}

# new GND symbols, one per dual test point's ground pad
NEW_GND = {
    "#PWR353": (190.50, 72.39),
    "#PWR354": (281.94, 92.71),
    "#PWR355": (383.54, 92.71),
    "#PWR356": (190.50, 180.34),
    "#PWR357": (287.02, 190.50),
}

# 1. the feedback-node test points; and the parts the LMR51610 does not have
DELETE = ["TP301", "TP305",     # test coverage off both PSU feedback nodes
          "C304", "#PWR307",    # LMR51610 has no VCC pin
          "#PWR308",            # nor a thermal-pad pin
          "R315"]               # nor a PG pin, so no series resistor into PGOOD

LIB_ADD = [("Amodo_Power_ICs", "LMR51610XFDBVR"),
           ("Amodo_Inductors", "IND_SMD_33uH"),
           ("Amodo_Resistors", "RES_TNF_16.9k_0603_0.1%"),
           ("Amodo_Connectors", "TestPointDual")]
LIB_DROP = ["Amodo_Inductors:IND_SMD_15uH_5.3A",
            "Amodo_Resistors:RES_TNF_22.1k_0603_0.1%"]

DEL_LABELS = [("RAIL_PGOOD", 104.14, 93.98)]      # U301 no longer drives it
MOVE_LABELS = {("+5V5", 180.34, 63.50):  (196.85, 63.50),
               ("+3V3", 180.34, 171.45): (193.04, 171.45),
               ("+3V3A", 242.57, 181.61): (256.54, 181.61)}

DEL_WIRES = [
    # --- section A: LMR33630 -> LMR51610 -------------------------------------
    (60.96, 33.02, 60.96, 43.18),                       # VIN drop
    (83.82, 43.18, 99.06, 43.18), (99.06, 43.18, 99.06, 45.72),   # BOOT
    (83.82, 48.26, 88.90, 48.26), (88.90, 48.26, 88.90, 53.34),   # SW
    (83.82, 59.69, 127.00, 59.69),                                # FB
    (57.15, 57.15, 57.15, 59.69), (57.15, 57.15, 60.96, 57.15),
    (57.15, 64.77, 57.15, 67.31),                                 # VCC + C304
    (72.39, 67.31, 72.39, 71.12),                                 # thermal pad
    (83.82, 54.61, 86.36, 54.61), (86.36, 54.61, 86.36, 78.74),
    (86.36, 78.74, 86.36, 81.28), (86.36, 86.36, 86.36, 88.90),
    (86.36, 88.90, 86.36, 93.98), (86.36, 93.98, 104.14, 93.98),  # PG + R315
    (132.08, 66.04, 134.62, 66.04),                     # TP301 off the FB node
    # --- 0R links horizontal, and the dual test points ----------------------
    (177.80, 53.34, 177.80, 55.88), (177.80, 60.96, 177.80, 63.50),
    (177.80, 63.50, 180.34, 63.50), (180.34, 63.50, 190.50, 63.50),
    (190.50, 58.42, 190.50, 63.50),
    (274.32, 73.66, 274.32, 76.20), (274.32, 81.28, 274.32, 83.82),
    (274.32, 83.82, 281.94, 83.82), (281.94, 78.74, 281.94, 83.82),
    (375.92, 73.66, 375.92, 76.20), (375.92, 81.28, 375.92, 83.82),
    (375.92, 83.82, 383.54, 83.82), (383.54, 78.74, 383.54, 83.82),
    (177.80, 161.29, 177.80, 163.83), (177.80, 168.91, 177.80, 171.45),
    (177.80, 171.45, 180.34, 171.45), (180.34, 171.45, 190.50, 171.45),
    (190.50, 166.37, 190.50, 171.45),
    (287.02, 176.53, 287.02, 181.61),
    (132.08, 173.99, 134.62, 173.99),                   # TP305 off the FB node
    # --- ferrite horizontal --------------------------------------------------
    (240.03, 171.45, 240.03, 172.72), (240.03, 180.34, 240.03, 181.61),
    (240.03, 181.61, 242.57, 181.61), (242.57, 181.61, 254.00, 181.61),
    # --- power LED vertical --------------------------------------------------
    (281.94, 200.66, 281.94, 210.82),
    (231.14, 210.82, 281.94, 210.82), (281.94, 210.82, 292.10, 210.82),
]

ADD_WIRES = [
    # --- LMR51610: VIN/EN/GND keep their rows, CB and SW move up ------------
    (60.96, 33.02, 60.96, 40.64),
    (76.20, 40.64, 99.06, 40.64), (99.06, 40.64, 99.06, 45.72),   # CB -> C305
    (76.20, 45.72, 88.90, 45.72), (88.90, 45.72, 88.90, 53.34),   # SW -> L301
    (76.20, 50.80, 80.01, 50.80), (80.01, 50.80, 80.01, 59.69),
    (80.01, 59.69, 127.00, 59.69),                                # FB divider
    # --- +5V5 out: R305 in line on the rail, then one step down -------------
    (182.88, 53.34, 190.50, 53.34), (190.50, 53.34, 190.50, 63.50),
    (190.50, 63.50, 190.50, 67.31), (190.50, 69.85, 190.50, 72.39),
    # --- +5V out -------------------------------------------------------------
    (279.40, 73.66, 281.94, 73.66), (281.94, 73.66, 281.94, 83.82),
    (281.94, 83.82, 281.94, 87.63), (281.94, 90.17, 281.94, 92.71),
    # --- +5VA out ------------------------------------------------------------
    (381.00, 73.66, 383.54, 73.66), (383.54, 73.66, 383.54, 83.82),
    (383.54, 83.82, 383.54, 87.63), (383.54, 90.17, 383.54, 92.71),
    # --- +3V3 out ------------------------------------------------------------
    (182.88, 161.29, 190.50, 161.29), (190.50, 161.29, 190.50, 171.45),
    (190.50, 171.45, 190.50, 175.26), (190.50, 177.80, 190.50, 180.34),
    # --- +3V3A: ferrite in line, then one step down -------------------------
    (247.65, 171.45, 254.00, 171.45), (254.00, 171.45, 254.00, 181.61),
    (287.02, 181.61, 287.02, 185.42), (287.02, 187.96, 287.02, 190.50),
    # --- RAIL_PGOOD row, LED now dropping into it at its own column ---------
    (274.32, 208.28, 274.32, 210.82),
    (231.14, 210.82, 274.32, 210.82), (274.32, 210.82, 292.10, 210.82),
]

DEL_JUNCTIONS = [(281.94, 210.82)]
ADD_JUNCTIONS = [(274.32, 210.82)]

TEXT_EDITS = [
    ("A.  PRE-REGULATOR  V24_LOGIC -> 5.5 V  (LMR33630, 400 kHz)",
     "A.  PRE-REGULATOR  V24_LOGIC -> 5.5 V  (LMR51610, 400 kHz)"),
    ("+5V5   LMR33630 buck from V24_LOGIC. Pre-regulator only,",
     "+5V5   LMR51610 buck from V24_LOGIC. Pre-regulator only,"),
    ("downstream of it, and a test point on each feedback node:",
     "downstream of it, on a dual pad so a scope ground clips beside\\n"
     "       the probe. No test point sits on a feedback node:"),
    ("RAIL_PGOOD is open drain, the wired-AND of both converters\\n"
     "       through R315 / R316.",
     "RAIL_PGOOD is open drain from the +3V3 buck alone, through\\n"
     "       R316 - the LMR51610 pre-regulator has no PG pin.")
]


# ------------------------------------------------------------------- builders
def props_of(sym_text):
    """[(name, value, hidden)] in library order."""
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


def pins_of(sym_text):
    return re.findall(r'\(pin [^\n]*\n(?:[^\n]*\n)*?\t*\t\(number "([^"]+)"', sym_text)


def build_symbol(lib, name, ref, value, x, y, rot, fields, mirror=None):
    sym = libsym(lib, name)
    lib_id = "%s:%s" % (lib, name)
    L = ["\t(symbol", '\t\t(lib_id "%s")' % lib_id,
         "\t\t(at %s %s %d)" % (g(x), g(y), rot)]
    if mirror:
        L.append("\t\t(mirror %s)" % mirror)
    L += ["\t\t(unit 1)", "\t\t(exclude_from_sim no)", "\t\t(in_bom yes)",
          "\t\t(on_board yes)", "\t\t(dnp no)", "\t\t(fields_autoplaced no)",
          '\t\t(uuid "%s")' % uid("sym " + ref)]
    for pname, pval, hidden in props_of(sym):
        if pname == "Reference":
            pval = '"%s"' % ref
        elif pname == "Value" and value is not None:
            pval = '"%s"' % value
        px, py, prot = fields.get(pname, (x, y, rot))
        L.append('\t\t(property "%s" %s' % (pname, pval))
        L.append("\t\t\t(at %s %s %d)" % (g(px), g(py), prot))
        L += ["\t\t\t(effects", "\t\t\t\t(font", "\t\t\t\t\t(size 1.27 1.27)",
              "\t\t\t\t)", "\t\t\t\t(justify left)"]
        if hidden or pname not in fields:
            L.append("\t\t\t\t(hide yes)")
        L += ["\t\t\t)", "\t\t)"]
    for pn in pins_of(sym):
        L += ['\t\t(pin "%s"' % pn,
              '\t\t\t(uuid "%s")' % uid("pin %s %s" % (ref, pn)), "\t\t)"]
    L += ["\t\t(instances", '\t\t\t(project "%s"' % PROJECT,
          '\t\t\t\t(path "%s"' % INST_PATH,
          '\t\t\t\t\t(reference "%s")' % ref, "\t\t\t\t\t(unit 1)",
          "\t\t\t\t)", "\t\t\t)", "\t\t)", "\t)"]
    return "\n".join(L) + "\n"


def embed(lib, name):
    """Library symbol text re-indented and renamed for the sheet's lib_symbols."""
    sym = libsym(lib, name)
    lines = sym.split("\n")
    lines[0] = '(symbol "%s:%s"' % (lib, name)
    return "\t\t" + "\n".join([lines[0]] + ["\t" + l for l in lines[1:]]) + "\n"


# --------------------------------------------------------------------- edits
def norm(v):
    return round(float(v), 3)


def drop_blocks(t, kind, keyfn, targets, marker=None):
    out, pos, hits = [], 0, set()
    marker = marker or "\t(%s\n" % kind
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


def main():
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)
    t = subprocess.check_output(["git", "show", "HEAD:" + SHEET], text=True)

    # ---- lib_symbols: add the new parts, drop the ones nothing uses any more
    ls_start = t.index("\t(lib_symbols\n")
    ls_end = block_end(t, ls_start + 1)
    ls = t[ls_start:ls_end]
    for lib_id in LIB_DROP:
        i = ls.index('(symbol "%s"\n' % lib_id)
        s = ls.rindex("\t\t", 0, i)
        ls = ls[:s] + ls[block_end(ls, i):].lstrip("\n")
    add = "".join(embed(lib, nm) for lib, nm in LIB_ADD)
    ls = ls[:ls.rindex("\t)")] + add + ls[ls.rindex("\t)"):]
    t = t[:ls_start] + ls + t[ls_end:]

    # ---- symbols: delete, replace, move
    def sym_ref(blk):
        m = re.search(r'\(property "Reference" "([^"]+)"', blk)
        return m.group(1) if m else None

    out, pos = [], 0
    gnd_template = None
    seen = set()
    while True:
        i = t.find("\t(symbol\n", pos)
        if i < 0:
            break
        e = block_end(t, i + 1)
        blk = t[i:e]
        ref = sym_ref(blk)
        if gnd_template is None and ref == "#PWR309":
            gnd_template = blk
        out.append(t[pos:i])
        if ref in DELETE:
            pass
        elif ref in REPLACE:
            lib, nm, x, y, rot, val, fl = REPLACE[ref]
            out.append(build_symbol(lib, nm, ref, val, x, y, rot, fl))
            seen.add(ref)
        elif ref in MOVE:
            x, y, rot, fl = MOVE[ref]
            blk = re.sub(r"\n\t\t\(at [^\n]*\)",
                         "\n\t\t(at %s %s %d)" % (g(x), g(y), rot), blk, count=1)

            def fix(pm, x=x, y=y, rot=rot, fl=fl):
                nm2 = pm.group(1)
                px, py, prot = fl.get(nm2, (x, y, rot))
                return '(property "%s" %s\n\t\t\t(at %s %s %d)' % (
                    nm2, pm.group(2), g(px), g(py), prot)
            blk = re.sub(r'\(property "([^"]+)" ("[^"\\]*(?:\\.[^"\\]*)*")'
                         r'\n\t\t\t\(at [^\n]*\)', fix, blk)
            for pname, how in JUSTIFY.get(ref, {}).items():
                ps = blk.index('(property "%s" ' % pname)
                pe = block_end(blk, ps)
                blk = (blk[:ps]
                       + re.sub(r"\(justify \w+\)", "(justify %s)" % how,
                                blk[ps:pe])
                       + blk[pe:])
            out.append(blk)
            seen.add(ref)
        else:
            out.append(blk)
        pos = e
    out.append(t[pos:])
    t = "".join(out)

    missing = (set(REPLACE) | set(MOVE)) - seen
    if missing:
        sys.exit("symbols not found: %s" % sorted(missing))

    # ---- new GND symbols for the dual test points' ground pads
    newsyms = ""
    for ref, (x, y) in NEW_GND.items():
        b = gnd_template
        b = re.sub(r"\n\t\t\(at [^\n]*\)", "\n\t\t(at %s %s 0)" % (g(x), g(y)), b, 1)
        b = re.sub(r'\(property "Reference" "[^"]+"', '(property "Reference" "%s"' % ref, b)
        b = re.sub(r'\(property "Value" "GND"\n\t\t\t\(at [^\n]*\)',
                   '(property "Value" "GND"\n\t\t\t(at %s %s 0)' % (g(x), g(y + 3.81)), b)
        b = re.sub(r'\(property "(Footprint|Datasheet|Description|ki_keywords|'
                   r'ki_fp_filters|SymLifecycle|mpn)" ("[^"\\]*(?:\\.[^"\\]*)*")'
                   r'\n\t\t\t\(at [^\n]*\)',
                   lambda m: '(property "%s" %s\n\t\t\t(at %s %s 0)'
                             % (m.group(1), m.group(2), g(x), g(y)), b)
        b = re.sub(r'\(uuid "[^"]+"\)\n\t\t\(property "Reference"',
                   '(uuid "%s")\n\t\t(property "Reference"' % uid("sym " + ref), b, 1)
        b = re.sub(r'\(pin "1"\n\t\t\t\(uuid "[^"]+"\)',
                   '(pin "1"\n\t\t\t(uuid "%s")' % uid("pin %s 1" % ref), b)
        b = re.sub(r'\(reference "[^"]+"\)', '(reference "%s")' % ref, b)
        newsyms += b
    anchor = t.index("\t(symbol\n")
    t = t[:anchor] + newsyms + t[anchor:]

    # ---- labels
    def lab_key(blk):
        m = re.match(r'\t\(label "([^"]+)"\n\t\t\(at ([-\d.]+) ([-\d.]+)', blk)
        return (m.group(1), norm(m.group(2)), norm(m.group(3)))
    want = {(n, norm(x), norm(y)) for n, x, y in DEL_LABELS}
    t, hits = drop_blocks(t, "label", lab_key, want, marker='\t(label "')
    if want - hits:
        sys.exit("labels not found: %s" % sorted(want - hits))
    for (name, ox, oy), (nx, ny) in MOVE_LABELS.items():
        old = '(label "%s"\n\t\t(at %s %s 0)' % (name, g(ox), g(oy))
        if old not in t:
            sys.exit("label not found: %s at %g,%g" % (name, ox, oy))
        t = t.replace(old, '(label "%s"\n\t\t(at %s %s 0)' % (name, g(nx), g(ny)), 1)

    # ---- wires and junctions
    t, hw = drop_blocks(t, "wire", wire_key,
                        {wire_key("(xy %g %g) (xy %g %g)" % w) for w in DEL_WIRES})
    t, hj = drop_blocks(t, "junction", at_key,
                        {tuple(norm(c) for c in j) for j in DEL_JUNCTIONS})
    mw = {wire_key("(xy %g %g) (xy %g %g)" % w) for w in DEL_WIRES} - hw
    mj = {tuple(norm(c) for c in j) for j in DEL_JUNCTIONS} - hj
    if mw or mj:
        sys.exit("wires not found: %s\njunctions not found: %s" % (sorted(mw), sorted(mj)))

    anchor = t.index("\t(symbol\n")
    t = (t[:anchor]
         + "".join(wire_block(*w) for w in ADD_WIRES)
         + "".join(junction_block(*j) for j in ADD_JUNCTIONS)
         + t[anchor:])

    # ---- sheet notes
    for old, new in TEXT_EDITS:
        if old not in t:
            sys.exit("text not found: %r" % old[:60])
        t = t.replace(old, new, 1)

    with open(SHEET, "w", encoding="utf-8", newline="") as f:
        f.write(t)
    print("batch 2 applied: %d parts swapped, %d moved, %d deleted, %d GND added, "
          "%d wires removed, %d added"
          % (len(REPLACE), len(MOVE), len(DELETE), len(NEW_GND),
             len(DEL_WIRES), len(ADD_WIRES)))


if __name__ == "__main__":
    main()
