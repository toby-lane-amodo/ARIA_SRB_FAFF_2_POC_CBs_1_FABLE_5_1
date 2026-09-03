#!/usr/bin/env python3
"""Round-1 captain review, final design-wide sweep.

Re-runnable: every sheet is rebuilt from its committed HEAD copy.

Five sweeps the captain asked for after the per-sheet batches:
  A  power labels - every power symbol and PWR_FLAG shows its rail name
  B  test points - a terse silkscreen name on all 83, under 6 characters
  C  text overlapping wires or block borders, including the leftward-growing
     fields the bundled overlap checker structurally cannot see
  D  ground symbols upside down
  E  graphic lines shadowing electrical wires
"""
import os, re, subprocess, sys, uuid

DIR = "hardware/kicad/faff2_cbs1"

# ---------------------------------------------------------------- A. power labels
# House pattern, from the 193 already visible: GND reads below the symbol,
# every rail arrow reads above it, both centred on the symbol's x.
POWER_LABEL_SHEETS = ["loadcell_afe", "motor_drive", "temp_sense"]

# ---------------------------------------------------------------- B. test points
# What each test point measures, in under six characters, from the net it
# actually lands on in the exported netlist.
TP_NAMES = {
    # power_entry_24v - the 24 V chain, in order along it
    "TP201": "24VIN", "TP202": "24VPR", "TP203": "24VSW", "TP204": "24VLG",
    "TP205": "24MON", "TP206": "GND",   "TP207": "GND",
    # power_rails - rail names as they already read
    "TP302": "+5V5", "TP303": "+5V", "TP304": "+5VA", "TP306": "+3V3",
    "TP307": "+3V3A", "TP308": "PGOOD",
    "TP309": "GND", "TP310": "GND", "TP311": "GND", "TP312": "GND",
    # loadcell_afe - bridge excitation, sense pair, ADC reference pair
    "TP501": "EXC+", "TP502": "SNS+", "TP503": "SNS-",
    "TP504": "REFP", "TP505": "REFN", "TP513": "PWRDN",
    "TP515": "GND", "TP516": "GND",
    # linear_encoder
    "TP601": "5VENC",
    # temp_sense - two probes, then the ADC's reference and its SPI
    "TP701": "PRB1A", "TP702": "PRB1B", "TP703": "PRB2A", "TP704": "PRB2B",
    "TP705": "REFP", "TP706": "REFN", "TP707": "DRDY",
    "TP708": "nCS", "TP709": "SCK", "TP710": "MOSI", "TP711": "MISO",
    "TP712": "GND", "TP713": "GND",
    # nvm_calibration
    "TP801": "SCL", "TP802": "SDA", "TP803": "WP", "TP804": "GND", "TP805": "GND",
    # ui_io - the sync output either side of its source termination
    "TP901": "SYNC", "TP902": "SYNCO",
    "TP903": "LIM_A", "TP904": "LIM_B", "TP905": "nBRK",
    "TP906": "GND", "TP907": "GND",
    # mcu
    "TP1001": "BOOT0", "TP1002": "nRST", "TP1003": "24MHZ",
    "TP1004": "3V3U", "TP1005": "1V8U",
    "TP1006": "GND", "TP1007": "GND", "TP1008": "GND",
    "TP1009": "GND", "TP1010": "GND", "TP1011": "GND",
    # motor_drive - bus, monitors, then the bridge gate and phase nodes
    "TP1101": "24MOT", "TP1102": "24MOT", "TP1103": "VBUSM", "TP1104": "FETT",
    "TP1105": "VENC", "TP1106": "VMDRV", "TP1107": "VCP", "TP1108": "GND",
    "TP1109": "nFLT", "TP1110": "SOA", "TP1111": "SOB", "TP1112": "SOC",
    "TP1113": "GHA", "TP1114": "GLA", "TP1115": "PH_U",
    "TP1116": "GHB", "TP1117": "GLB", "TP1118": "PH_V",
    "TP1119": "GHC", "TP1120": "GLC", "TP1121": "PH_W",
}

# ---------------------------------------------------------------- C. text overlap
# sheet -> ref -> property -> (x, y, rot, justify or None to leave alone)
FIELD_FIXES = {
    # C1016's fields are right-justified, so they grew left onto U1003's VDD
    # wire at x=154.94. Moved to the right of the body, like C1017's.
    "mcu": {"C1016": {"Reference": (164.59, 96.52, 0, "left"),
                      "Value":     (164.59, 99.06, 0, "left")}},
    # J501 is mirrored, so "justify left" renders leftward - its value ran out
    # through the block border. Same fix as J201 in batch 1.
    "loadcell_afe": {"J501": {"Reference": (22.86, 46.99, 0, "right"),
                              "Value":     (22.86, 48.90, 0, "right")}},
}

# ---------------------------------------------------------------- E. graphic/wire
# power_rails block D's bottom border ran along the last PWR_FLAG's wire.
# The whole flag column moves up 2.54 so the border is clear of all five.
PWRFLAG_SHIFT = {
    "power_rails": {
        "refs": ["#FLG344", "#FLG345", "#PWR346", "#FLG347", "#PWR348",
                 "#FLG349", "#PWR350", "#FLG351", "#PWR352"],
        "labels": [("+5V5", 360.68, 200.66)],
        "wires": [(353.06, 200.66, 360.68, 200.66), (353.06, 209.55, 360.68, 209.55),
                  (353.06, 218.44, 360.68, 218.44), (353.06, 227.33, 360.68, 227.33),
                  (353.06, 236.22, 360.68, 236.22)],
        "dy": -2.54,
    }
}



# --------------------------------------------------------------- placement
# Newly visible text has to go somewhere that is actually empty. Rather than a
# fixed offset, each field is tried against every wire, block border, symbol
# body, note, label and already-placed field on its sheet, and takes the first
# candidate offset that collides with nothing.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import sch_geom as G

CAND_BELOW = [(0, 3.81, ''), (2.54, 3.81, 'left'), (-2.54, 3.81, 'right'), (5.08, 3.81, 'left'), (-5.08, 3.81, 'right'), (7.62, 3.81, 'left'), (-7.62, 3.81, 'right'), (0, 5.08, ''), (2.54, 5.08, 'left'), (-2.54, 5.08, 'right'), (5.08, 5.08, 'left'), (-5.08, 5.08, 'right'), (7.62, 5.08, 'left'), (-7.62, 5.08, 'right'), (0, 6.35, ''), (2.54, 6.35, 'left'), (-2.54, 6.35, 'right'), (5.08, 6.35, 'left'), (-5.08, 6.35, 'right'), (7.62, 6.35, 'left'), (-7.62, 6.35, 'right'), (0, 7.62, ''), (2.54, 7.62, 'left'), (-2.54, 7.62, 'right'), (5.08, 7.62, 'left'), (-5.08, 7.62, 'right'), (7.62, 7.62, 'left'), (-7.62, 7.62, 'right'), (0, 8.89, ''), (2.54, 8.89, 'left'), (-2.54, 8.89, 'right'), (5.08, 8.89, 'left'), (-5.08, 8.89, 'right'), (7.62, 8.89, 'left'), (-7.62, 8.89, 'right')]
CAND_ABOVE = [(0, -3.81, ''), (2.54, -3.81, 'left'), (-2.54, -3.81, 'right'), (5.08, -3.81, 'left'), (-5.08, -3.81, 'right'), (7.62, -3.81, 'left'), (-7.62, -3.81, 'right'), (0, -5.08, ''), (2.54, -5.08, 'left'), (-2.54, -5.08, 'right'), (5.08, -5.08, 'left'), (-5.08, -5.08, 'right'), (7.62, -5.08, 'left'), (-7.62, -5.08, 'right'), (0, -6.35, ''), (2.54, -6.35, 'left'), (-2.54, -6.35, 'right'), (5.08, -6.35, 'left'), (-5.08, -6.35, 'right'), (7.62, -6.35, 'left'), (-7.62, -6.35, 'right'), (0, -7.62, ''), (2.54, -7.62, 'left'), (-2.54, -7.62, 'right'), (5.08, -7.62, 'left'), (-5.08, -7.62, 'right'), (7.62, -7.62, 'left'), (-7.62, -7.62, 'right'), (0, -8.89, ''), (2.54, -8.89, 'left'), (-2.54, -8.89, 'right'), (5.08, -8.89, 'left'), (-5.08, -8.89, 'right'), (7.62, -8.89, 'left'), (-7.62, -8.89, 'right')]
CAND_TP = [(0, 2.4, None), (2.54, 2.4, 'left'), (-2.54, 2.4, 'right'), (5.08, 2.4, 'left'), (-5.08, 2.4, 'right'), (0, -2.4, None), (2.54, -2.4, 'left'), (-2.54, -2.4, 'right'), (5.08, -2.4, 'left'), (-5.08, -2.4, 'right'), (0, 4.8, None), (2.54, 4.8, 'left'), (-2.54, 4.8, 'right'), (5.08, 4.8, 'left'), (-5.08, 4.8, 'right'), (0, -4.8, None), (2.54, -4.8, 'left'), (-2.54, -4.8, 'right'), (5.08, -4.8, 'left'), (-5.08, -4.8, 'right'), (0, 7.2, None), (2.54, 7.2, 'left'), (-2.54, 7.2, 'right'), (5.08, 7.2, 'left'), (-5.08, 7.2, 'right'), (0, -7.2, None), (2.54, -7.2, 'left'), (-2.54, -7.2, 'right'), (5.08, -7.2, 'left'), (-5.08, -7.2, 'right')]


def place_fields(text, movable):
    """movable: {(ref, prop): (anchor_x, anchor_y, candidates, base_justify)}"""
    sheet = G.Sheet(text)
    PAD = 0.35
    def grow(b):
        return (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD)
    obstacles = [grow(G.seg_box(*w)) for w in sheet.wires()]
    obstacles += [grow(G.seg_box(*e)) for e in sheet.rect_edges()]
    obstacles += [grow(b) for b in sheet.free_text_boxes()]
    obstacles += [grow(b) for b in sheet.label_boxes()]
    for s in sheet.symbols():
        b = sheet.body_box(s)
        if b:
            obstacles.append(grow(b))
    for (ref, pn, box, _) in sheet.visible_fields():
        if (ref, pn) not in movable:
            obstacles.append(grow(box))

    chosen, unplaced = {}, []
    for (ref, pn) in sorted(movable):
        ax, ay, cands, base_j, txt, rot, mir = movable[(ref, pn)]
        pick = None
        for (dx, dy, j) in cands:
            just = base_j if j is None else (j or None)
            b = G.text_box(ax + dx, ay + dy, txt, just, rot, mir)
            if not any(G.overlaps(b, o) for o in obstacles):
                pick = (ax + dx, ay + dy, "" if j == "" else (j or base_j or ""), b)
                break
        if pick is None:
            dx, dy, j = cands[0]
            just = base_j if j is None else (j or None)
            pick = (ax + dx, ay + dy, "" if j == "" else (j or base_j or ""),
                    G.text_box(ax + dx, ay + dy, txt, just, rot, mir))
            unplaced.append((ref, pn))
        chosen[(ref, pn)] = pick[:3]
        obstacles.append(grow(pick[3]))
    return chosen, unplaced


# offsets tried when nudging a field that already collides, smallest first
NUDGE = sorted(((dx, dy) for dx in (0, 1.27, -1.27, 2.54, -2.54, 3.81, -3.81,
                                    5.08, -5.08)
                for dy in (0, 1.27, -1.27, 2.54, -2.54, 3.81, -3.81)),
               key=lambda d: abs(d[0]) + abs(d[1]))[1:]


def nudge_colliding(text, protect):
    """Move any visible field that collides with something. Returns
    {(ref, prop): (x, y)} and the list it could not clear."""
    sheet = G.Sheet(text)
    PAD = 0.05
    def grow(b):
        return (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD)
    fixed = [G.seg_box(*w) for w in sheet.wires()]
    fixed += [G.seg_box(*e) for e in sheet.rect_edges()]
    fixed += sheet.free_text_boxes() + sheet.label_boxes()
    bodies = {}
    for s in sheet.symbols():
        ref = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Reference"), "")
        b = sheet.body_box(s)
        if b:
            bodies.setdefault(ref, []).append(b)

    info = {}
    for s in sheet.symbols():
        p = G.at(s)
        mir = bool(G.kid(s, "mirror"))
        ref = next((G.a(pr, 2) for pr in G.kids(s, "property")
                    if G.a(pr, 1) == "Reference"), "")
        for pr in G.kids(s, "property"):
            eff = G.kid(pr, "effects")
            h = G.kid(eff, "hide") if eff else None
            if h and G.a(h, 1) == "yes":
                continue
            j = [G.a(x, 1) for x in G.kids(eff, "justify")] if eff else []
            just = j[0] if j and j[0] in ("left", "right") else None
            pa = G.at(pr)
            info[(ref, G.a(pr, 1))] = (pa[0], pa[1], G.a(pr, 2), just, p[2], mir)

    def box_at(key, x, y):
        _, _, txt, just, rot, mir = info[key]
        return G.text_box(x, y, txt, just, rot, mir)

    boxes = {k: box_at(k, v[0], v[1]) for k, v in info.items()}

    def clashes(key, b):
        for o in fixed:
            if G.overlaps(grow(b), o):
                return True
        for ref2, bs in bodies.items():
            if ref2 == key[0]:
                continue
            for bb in bs:
                if G.overlaps(grow(b), bb):
                    return True
        for k2, b2 in boxes.items():
            if k2 != key and G.overlaps(grow(b), b2):
                return True
        return False

    moved, stuck = {}, []
    for key in sorted(info):
        if key in protect or not clashes(key, boxes[key]):
            continue
        x0, y0 = info[key][0], info[key][1]
        for (dx, dy) in NUDGE:
            b = box_at(key, x0 + dx, y0 + dy)
            if not clashes(key, b):
                moved[key] = (x0 + dx, y0 + dy)
                boxes[key] = b
                break
        else:
            stuck.append(key)
    return moved, stuck


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


def prop_blocks(sym):
    """[(name, start, end)] for each property in a symbol block."""
    out, pos = [], 0
    while True:
        i = sym.find('(property "', pos)
        if i < 0:
            break
        e = block_end(sym, i)
        out.append((re.match(r'\(property "([^"]+)"', sym[i:e]).group(1), i, e))
        pos = e
    return out


def set_prop(sym, name, *, text=None, at=None, justify=None, show=None):
    for pname, s, e in prop_blocks(sym):
        if pname != name:
            continue
        blk = sym[s:e]
        if text is not None:
            blk = re.sub(r'\(property "%s" "[^"\\]*(?:\\.[^"\\]*)*"' % re.escape(name),
                         '(property "%s" "%s"' % (name, text), blk, count=1)
        if at is not None:
            blk = re.sub(r"\(at [-\d.]+ [-\d.]+ [-\d.]+\)",
                         "(at %s %s %d)" % (g(at[0]), g(at[1]), at[2]), blk, count=1)
        if justify is not None:
            if re.search(r"\(justify [^)]*\)", blk):
                blk = re.sub(r"\(justify [^)]*\)", "(justify %s)" % justify, blk)
            elif justify != "":
                blk = blk.replace("\t\t\t\t)\n", "\t\t\t\t)\n\t\t\t\t(justify %s)\n"
                                  % justify, 1)
        if justify == "":
            blk = re.sub(r"\n\t+\(justify [^)]*\)", "", blk)
        if show is True:
            blk = re.sub(r"\n\t+\(hide yes\)", "", blk)
        elif show is False and "(hide yes)" not in blk:
            blk = blk.replace("\t\t\t)\n\t\t)", "\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)", 1)
        return sym[:s] + blk + sym[e:]
    return sym


def prop_at(sym, name):
    for pname, s, e in prop_blocks(sym):
        if pname == name:
            m = re.search(r"\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", sym[s:e])
            j = re.search(r"\(justify ([^)]*)\)", sym[s:e])
            return (float(m.group(1)), float(m.group(2)), int(float(m.group(3))),
                    (j.group(1).split()[0] if j else None))
    return None


def each_symbol(t):
    pos = 0
    while True:
        i = t.find("\t(symbol\n", pos)
        if i < 0:
            return
        e = block_end(t, i + 1)
        yield i, e, t[i:e]
        pos = e


def sheet_text(name):
    return subprocess.check_output(
        ["git", "show", "HEAD:%s/%s.kicad_sch" % (DIR, name)], text=True)


def main():
    root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"],
                                   text=True).strip()
    os.chdir(root)
    sheets = sorted(n[:-len(".kicad_sch")] for n in os.listdir(DIR)
                    if n.endswith(".kicad_sch") and n != "faff2_cbs1.kicad_sch")
    stats = dict(power=0, tp=0, fields=0, shifted=0, placed=0, stuck=0, nudged=0)

    for name in sheets:
        t = sheet_text(name)
        movable = {}
        out, pos = [], 0
        for i, e, sym in each_symbol(t):
            m = re.search(r'\(property "Reference" "([^"]+)"', sym)
            ref = m.group(1) if m else ""
            lib = re.search(r'\(lib_id "([^"]+)"', sym).group(1)
            new = sym

            sm0 = re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", sym)
            sx0, sy0 = float(sm0.group(1)), float(sm0.group(2))
            srot0 = float(sm0.group(3))
            smir0 = bool(re.search(r"\n\t\t\(mirror ", sym))

            # --- A. power labels
            if name in POWER_LABEL_SHEETS and ref.startswith(("#PWR", "#FLG")):
                val = re.search(r'\(property "Value" "([^"]*)"', sym).group(1)
                cands = CAND_BELOW if val == "GND" else CAND_ABOVE
                new = set_prop(new, "Value", at=(sx0, sy0 + cands[0][1], 0),
                               justify="", show=True)
                movable[(ref, "Value")] = (sx0, sy0, cands, None, val,
                                           srot0, smir0)
                stats["power"] += 1

            # --- B. test point silkscreen names
            if "TestPoint" in lib and ref in TP_NAMES:
                rat = prop_at(new, "Reference")
                txt = TP_NAMES[ref]
                new = set_prop(new, "Value", text=txt,
                               at=(rat[0], rat[1] + 2.4, rat[2]),
                               justify=(rat[3] or ""), show=True)
                movable[(ref, "Value")] = (rat[0], rat[1], CAND_TP, rat[3],
                                           txt, srot0, smir0)
                stats["tp"] += 1

            # --- C. targeted field fixes
            fx = FIELD_FIXES.get(name, {}).get(ref)
            if fx:
                for pname, (px, py, prot, pj) in fx.items():
                    new = set_prop(new, pname, at=(px, py, prot), justify=pj)
                    stats["fields"] += 1

            # --- E. flag column off the block border
            sh = PWRFLAG_SHIFT.get(name)
            if sh and ref in sh["refs"]:
                dy = sh["dy"]
                sm = re.search(r"\n\t\t\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)", new)
                sx, sy, srot = (float(sm.group(1)), float(sm.group(2)),
                                int(float(sm.group(3))))
                new = (new[:sm.start()] + "\n\t\t(at %s %s %d)"
                       % (g(sx), g(sy + dy), srot) + new[sm.end():])
                for pname, s2, e2 in prop_blocks(new):
                    pa = prop_at(new, pname)
                    new = set_prop(new, pname, at=(pa[0], pa[1] + dy, pa[2]))
                stats["shifted"] += 1

            out.append(t[pos:i]); out.append(new); pos = e
        out.append(t[pos:])
        t = "".join(out)

        # --- E, continued: the flag column's wires and its one local label
        sh = PWRFLAG_SHIFT.get(name)
        if sh:
            dy = sh["dy"]
            for (x1, y1, x2, y2) in sh["wires"]:
                old = "(xy %s %s) (xy %s %s)" % (g(x1), g(y1), g(x2), g(y2))
                if old not in t:
                    sys.exit("flag wire not found: %s" % old)
                t = t.replace(old, "(xy %s %s) (xy %s %s)"
                              % (g(x1), g(y1 + dy), g(x2), g(y2 + dy)), 1)
            for (lname, lx, ly) in sh["labels"]:
                old = '(label "%s"\n\t\t(at %s %s 0)' % (lname, g(lx), g(ly))
                if old not in t:
                    sys.exit("flag label not found: %s" % lname)
                t = t.replace(old, '(label "%s"\n\t\t(at %s %s 0)'
                              % (lname, g(lx), g(ly + dy)), 1)

        # --- second pass: put every newly visible field somewhere empty
        if movable:
            chosen, unplaced = place_fields(t, movable)
            out, pos = [], 0
            for i, e, sym in each_symbol(t):
                m = re.search(r'\(property "Reference" "([^"]+)"', sym)
                r = m.group(1) if m else ""
                new = sym
                for (cref, cpn), (cx, cy, cj) in chosen.items():
                    if cref == r:
                        new = set_prop(new, cpn, at=(cx, cy, 0), justify=cj)
                out.append(t[pos:i]); out.append(new); pos = e
            out.append(t[pos:])
            t = "".join(out)
            stats["placed"] += len(chosen)
            if unplaced:
                print("  %s: no clear spot for %s" % (name, unplaced))
                stats["stuck"] += len(unplaced)

        # --- third pass: nudge any field that still collides, including ones
        # that were already colliding before this sweep
        protect = set(FIELD_FIXES.get(name, {}).keys())
        protect = {(r, pn) for r in protect for pn in FIELD_FIXES[name][r]}
        moved, stuck = nudge_colliding(t, protect)
        if moved:
            out, pos = [], 0
            for i, e, sym in each_symbol(t):
                m = re.search(r'\(property "Reference" "([^"]+)"', sym)
                r = m.group(1) if m else ""
                new = sym
                for (cref, cpn), (cx, cy) in moved.items():
                    if cref == r:
                        pa = prop_at(new, cpn)
                        new = set_prop(new, cpn, at=(cx, cy, pa[2]))
                out.append(t[pos:i]); out.append(new); pos = e
            out.append(t[pos:])
            t = "".join(out)
            print("  %s: nudged %s" % (name, sorted("%s.%s" % k for k in moved)))
            stats["nudged"] += len(moved)
        if stuck:
            print("  %s: still colliding %s" % (name, stuck))
            stats["stuck"] += len(stuck)

        with open("%s/%s.kicad_sch" % (DIR, name), "w",
                  encoding="utf-8", newline="") as f:
            f.write(t)

    print("sweep applied: %d power labels shown, %d test points named, "
          "%d fields re-placed, %d flag-column symbols shifted; "
          "%d fields auto-placed, %d with no clear spot"
          % (stats["power"], stats["tp"], stats["fields"], stats["shifted"],
             stats["placed"], stats["stuck"]))
    print("           %d pre-existing collisions nudged clear" % stats["nudged"])


if __name__ == "__main__":
    main()
