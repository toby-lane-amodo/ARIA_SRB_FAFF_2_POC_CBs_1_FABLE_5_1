#!/usr/bin/env python3
"""Build hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_pcb from the schematic netlist.

Board-setup step of the layout phase: stackup, layer roles, outline, mounting holes
and the schematic import.  No real placement -- every imported footprint lands in a
holding grid off-board, grouped by schematic sheet, for the placement task to consume.

The committed .kicad_pcb is the artifact; this script is the record of how it was
made.  It regenerates the whole board, so do not hand-edit the board and then re-run
it -- from placement onwards the board file itself is the master.

Rulings encoded here are recorded in docs/decisions/actuator-pcb-setup.md.
KiCad 9 only -- see AGENTS.md.

Usage:  AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib python3 tools/gen_pcb_setup.py
"""

import os
import re
import subprocess
import sys

import pcbnew

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRJ = os.path.join(REPO, "hardware", "kicad", "faff2_cbs1")
SCH = os.path.join(PRJ, "faff2_cbs1.kicad_sch")
PCB = os.path.join(PRJ, "faff2_cbs1.kicad_pcb")
AMODO = os.environ.get("AMODO_KICAD_LIB", "/mnt/c/Amodo/AmodoKiCadLib")
FPLIB = {"Amodo": os.path.join(AMODO, "Amodo.pretty"), "faff2": os.path.join(PRJ, "faff2.pretty")}

# --- board geometry (docs/decisions/actuator-pcb-setup.md) -----------------------
BW, BH = 210.0, 130.0          # board size, mm -- set by the actuator connector edge
BX, BY = 30.0, 30.0            # board top-left on the page
CORNER_R = 2.0                 # house rule: radius external corners, 2 mm typical
HOLE_INSET = 6.0               # M3 hole centre from each edge (5.5 mm keepout clears)
MOUNT_FP = "Amodo:MountingHole_3.2mm_M3_NO-PAD_NPTH"
EDGE_W = 0.1                   # Edge.Cuts line width
PAGE = "A2"                    # board + holding grid both need to be visible

# --- holding grid ----------------------------------------------------------------
GRID_X0 = BX
GRID_Y0 = BY + BH + 25.0       # clear of the board
GRID_W = 540.0                 # usable width on the A2 page
CELL_GAP = 2.5                 # courtyard-to-courtyard gap inside the grid
SHEET_GAP = 12.0               # vertical gap between sheet groups
SNAP = 0.25                    # house soft placement grid

SHEET_ORDER = [
    "power_entry_24v", "power_rails", "loadcell_afe", "linear_encoder",
    "temp_sense", "nvm_calibration", "ui_io", "mcu", "motor_drive",
]

# --- JLCPCB JLC04161H-7628, 4 layer 1.6 mm, 1 oz outer / 0.5 oz inner ------------
# Geometry is JLCPCB's own published impedance template; Dk/Df are the Nan Ya
# NP-155F values those templates call up.  Sources in the decisions file.
DIELECTRIC = [
    # (name, type, thickness mm, material, epsilon_r, loss_tangent)
    ("dielectric 1", "prepreg", 0.2104, "NP-155F 7628", 4.4, 0.02),
    ("dielectric 2", "core", 1.065, "NP-155F Core", 4.43, 0.02),
    ("dielectric 3", "prepreg", 0.2104, "NP-155F 7628", 4.4, 0.02),
]
CU_OUTER, CU_INNER = 0.035, 0.0152
MASK_T = 0.01
COPPER_FINISH = "ENIG"


def mm(v):
    return pcbnew.FromMM(v)


def vec(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def snap(v):
    return round(v / SNAP) * SNAP


# ---------------------------------------------------------------------------------
# netlist
# ---------------------------------------------------------------------------------

def export_netlist(dest):
    env = dict(os.environ, AMODO_KICAD_LIB=AMODO)
    env.setdefault("AMODO_3D", os.path.join(AMODO, "3D"))
    r = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr", "-o", dest, SCH],
        capture_output=True, text=True, env=env,
    )
    if r.returncode != 0:
        sys.exit(f"netlist export failed:\n{r.stdout}\n{r.stderr}")
    # AGENTS.md: a sheet that failed to load still exits 0 -- check stderr too.
    if "Failed to load" in (r.stderr + r.stdout):
        sys.exit(f"schematic failed to load:\n{r.stderr}")
    return dest


def parse_netlist(path):
    s = open(path).read()
    comps = []
    for b in re.split(r"\n    \(comp ", s.split("(components", 1)[1])[1:]:
        def get(p, d=None):
            m = re.search(p, b)
            return m.group(1) if m else d
        comps.append({
            "ref": get(r'^\(ref "([^"]+)"\)'),
            "value": get(r'\n      \(value "([^"]*)"\)', ""),
            "footprint": get(r'\n      \(footprint "([^"]*)"\)', ""),
            "sheetfile": get(r'\(property \(name "Sheetfile"\) \(value "([^"]*)"\)\)', ""),
            "sheetname": get(r'\(property \(name "Sheetname"\) \(value "([^"]*)"\)\)', ""),
            "sheetpath": get(r'\(sheetpath \(names "([^"]*)"\)', "/"),
            "sheettstamps": get(r'\(sheetpath \(names "[^"]*"\) \(tstamps "([^"]*)"\)\)', "/"),
            "tstamp": get(r'\n      \(tstamps "([^"]+)"\)\)', ""),
            "dnp": 'name "dnp"' in b,
            "exclude_bom": 'name "exclude_from_bom"' in b,
        })
    nets = []
    for b in re.split(r"\n    \(net ", s.split("(nets", 1)[1])[1:]:
        name = re.search(r'\(name "([^"]+)"\)', b).group(1)
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', b)
        nets.append((name, nodes))
    return comps, nets


# ---------------------------------------------------------------------------------
# board construction
# ---------------------------------------------------------------------------------

def add_outline(board):
    """Rounded-rect board outline on Edge.Cuts (house rule: 2 mm external radius)."""
    x0, y0, x1, y1, r = BX, BY, BX + BW, BY + BH, CORNER_R

    def seg(ax, ay, bx, by):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(vec(ax, ay))
        s.SetEnd(vec(bx, by))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(EDGE_W))
        board.Add(s)

    def arc(cx, cy, sx, sy, ex, ey):
        """90 degree corner arc: midpoint sits on the centre-to-corner bisector."""
        dx, dy = (sx - cx) + (ex - cx), (sy - cy) + (ey - cy)
        n = (dx * dx + dy * dy) ** 0.5
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(vec(sx, sy), vec(cx + dx / n * r, cy + dy / n * r), vec(ex, ey))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(EDGE_W))
        board.Add(s)

    seg(x0 + r, y0, x1 - r, y0)                      # top
    seg(x1, y0 + r, x1, y1 - r)                      # right
    seg(x1 - r, y1, x0 + r, y1)                      # bottom
    seg(x0, y1 - r, x0, y0 + r)                      # left
    arc(x0 + r, y0 + r, x0, y0 + r, x0 + r, y0)      # top-left
    arc(x1 - r, y0 + r, x1 - r, y0, x1, y0 + r)      # top-right
    arc(x1 - r, y1 - r, x1, y1 - r, x1 - r, y1)      # bottom-right
    arc(x0 + r, y1 - r, x0 + r, y1, x0, y1 - r)      # bottom-left


_FP_CACHE = {}


def load_fp(fpid):
    """Load a library footprint, cached.

    FootprintLoad re-enumerates the whole .pretty on every call -- ~3.6 s against
    the 773-footprint Amodo library on the WSL /mnt/c mount.  Caching the 55
    distinct footprints and duplicating turns 25 minutes into three.
    """
    if fpid not in _FP_CACHE:
        lib, name = fpid.split(":", 1)
        fp = pcbnew.FootprintLoad(FPLIB[lib], name)
        if fp is None:
            sys.exit(f"footprint not found: {fpid}")
        fp.SetFPID(pcbnew.LIB_ID(lib, name))
        _FP_CACHE[fpid] = fp
    return _FP_CACHE[fpid].Duplicate()


def courtyard_bbox(fp):
    """Real courtyard extents -- the skill forbids bbox guesses.

    Returns (bbox, had_courtyard).
    """
    fp.BuildCourtyardCaches()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        poly = fp.GetCourtyard(layer)
        if poly.OutlineCount():
            return poly.BBox(), True
    return fp.GetBoundingBox(False, False), False


def add_mounting_holes(board):
    holes = []
    corners = [(HOLE_INSET, HOLE_INSET), (BW - HOLE_INSET, HOLE_INSET),
               (BW - HOLE_INSET, BH - HOLE_INSET), (HOLE_INSET, BH - HOLE_INSET)]
    for i, (dx, dy) in enumerate(corners, start=1):
        fp = load_fp(MOUNT_FP)
        fp.SetPosition(vec(BX + dx, BY + dy))
        fp.SetReference(f"H{i}")
        fp.SetValue(MOUNT_FP.split(":", 1)[1])
        # Board-only, so schematic parity does not see them as extra footprints.
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY
                         | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        board.Add(fp)
        holes.append(fp)
    return holes


def import_schematic(board, comps):
    """Place every schematic footprint in an off-board holding grid, grouped by sheet."""
    by_sheet = {}
    for c in comps:
        by_sheet.setdefault(c["sheetname"] or "root", []).append(c)
    unknown = sorted(set(by_sheet) - set(SHEET_ORDER))

    def sort_key(c):
        m = re.match(r"^([^\d]+)(\d+)$", c["ref"])
        return (m.group(1), int(m.group(2))) if m else (c["ref"], 0)

    placed, no_courtyard = [], []
    y = GRID_Y0
    for sheet in SHEET_ORDER + unknown:
        group = sorted(by_sheet.get(sheet, []), key=sort_key)
        if not group:
            continue
        txt = pcbnew.PCB_TEXT(board)
        txt.SetText(f"{sheet}  ({len(group)} parts)")
        txt.SetPosition(vec(GRID_X0, y - 5.0))
        txt.SetLayer(pcbnew.Cmts_User)
        txt.SetTextSize(pcbnew.VECTOR2I(mm(3.0), mm(3.0)))
        txt.SetTextThickness(mm(0.4))
        txt.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        board.Add(txt)

        x, row_h = GRID_X0, 0.0
        for c in group:
            fp = load_fp(c["footprint"])
            bb, ok = courtyard_bbox(fp)
            if not ok:
                no_courtyard.append((c["ref"], c["footprint"]))
            w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
            if x + w > GRID_X0 + GRID_W:
                x, y, row_h = GRID_X0, y + row_h + CELL_GAP, 0.0
            # offset so the courtyard's top-left lands on the cell origin
            off_x = pcbnew.ToMM(fp.GetPosition().x - bb.GetLeft())
            off_y = pcbnew.ToMM(fp.GetPosition().y - bb.GetTop())
            fp.SetPosition(vec(snap(x + off_x), snap(y + off_y)))
            fp.SetReference(c["ref"])
            fp.SetValue(c["value"])
            fp.SetSheetname(c["sheetpath"])
            fp.SetSheetfile(c["sheetfile"])
            fp.SetPath(pcbnew.KIID_PATH(c["sheettstamps"] + c["tstamp"]))
            # KiCad takes DNP and "exclude from BOM" from the SYMBOL, not from the
            # library footprint -- so the library's own exclude_from_bom has to be
            # cleared where the schematic does not set it, or schematic parity flags
            # every test point and test loop.
            attrs = fp.GetAttributes() & ~pcbnew.FP_EXCLUDE_FROM_BOM
            if c["exclude_bom"]:
                attrs |= pcbnew.FP_EXCLUDE_FROM_BOM
            if c["dnp"]:
                attrs |= pcbnew.FP_DNP
            fp.SetAttributes(attrs)
            board.Add(fp)
            placed.append(fp)
            x += w + CELL_GAP
            row_h = max(row_h, h)
        y += row_h + SHEET_GAP
    return placed, no_courtyard, y


def assign_nets(board, nets):
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    missing = []
    for name, nodes in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        for ref, pin in nodes:
            fp = fps.get(ref)
            if fp is None:
                missing.append((ref, pin, "no such footprint"))
                continue
            pads = [p for p in fp.Pads() if p.GetNumber() == pin]
            if not pads:
                missing.append((ref, pin, "no such pad"))
                continue
            for p in pads:
                p.SetNet(ni)
    return missing


# ---------------------------------------------------------------------------------
# post-save text surgery -- BOARD_STACKUP is not wrapped in the KiCad 9 SWIG bindings
# ---------------------------------------------------------------------------------

def stackup_block():
    L = []
    a = L.append
    a('\t\t(stackup')

    def layer(name, typ, thickness=None, material=None, er=None, df=None):
        a(f'\t\t\t(layer "{name}"')
        a(f'\t\t\t\t(type "{typ}")')
        if thickness is not None:
            a(f'\t\t\t\t(thickness {thickness})')
        if material is not None:
            a(f'\t\t\t\t(material "{material}")')
        if er is not None:
            a(f'\t\t\t\t(epsilon_r {er})')
        if df is not None:
            a(f'\t\t\t\t(loss_tangent {df})')
        a('\t\t\t)')

    layer("F.SilkS", "Top Silk Screen")
    layer("F.Paste", "Top Solder Paste")
    layer("F.Mask", "Top Solder Mask", MASK_T)
    layer("F.Cu", "copper", CU_OUTER)
    layer(*DIELECTRIC[0][:2], DIELECTRIC[0][2], DIELECTRIC[0][3], DIELECTRIC[0][4], DIELECTRIC[0][5])
    layer("In1.Cu", "copper", CU_INNER)
    layer(*DIELECTRIC[1][:2], DIELECTRIC[1][2], DIELECTRIC[1][3], DIELECTRIC[1][4], DIELECTRIC[1][5])
    layer("In2.Cu", "copper", CU_INNER)
    layer(*DIELECTRIC[2][:2], DIELECTRIC[2][2], DIELECTRIC[2][3], DIELECTRIC[2][4], DIELECTRIC[2][5])
    layer("B.Cu", "copper", CU_OUTER)
    layer("B.Mask", "Bottom Solder Mask", MASK_T)
    layer("B.Paste", "Bottom Solder Paste")
    layer("B.SilkS", "Bottom Silk Screen")
    a(f'\t\t\t(copper_finish "{COPPER_FINISH}")')
    a('\t\t\t(dielectric_constraints no)')
    a('\t\t)')
    return "\n".join(L) + "\n"


def patch_stackup(path):
    t = open(path).read()
    if "(stackup" in t:
        sys.exit("board already carries a stackup block -- refusing to double-apply")
    # PAGE_INFO is not wrapped in the KiCad 9 bindings either
    if '(paper "A4")' not in t:
        sys.exit("anchor not matched: paper size")
    t = t.replace('(paper "A4")', f'(paper "{PAGE}")', 1)
    anchor = "\t(setup\n"
    if anchor not in t:
        sys.exit("anchor not matched: (setup block")
    t = t.replace(anchor, anchor + stackup_block(), 1)
    # board thickness = sum of the stackup, not the 1.6 nominal
    total = 2 * CU_OUTER + 2 * CU_INNER + sum(d[2] for d in DIELECTRIC) + 2 * MASK_T
    old = "\t\t(thickness 1.6)\n"
    if old not in t:
        sys.exit("anchor not matched: general/thickness")
    t = t.replace(old, f"\t\t(thickness {round(total, 4)})\n", 1)
    open(path, "w").write(t)
    return total


def main():
    scratch = os.environ.get("SCRATCH", "/tmp")
    comps, nets = parse_netlist(export_netlist(os.path.join(scratch, "faff2_nl.net")))
    nodes = sum(len(n) for _, n in nets)
    print(f"netlist: {len(comps)} components, {len(nets)} nets, {nodes} nodes")

    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(4)
    # G1: outer layers carry signals AND power; both inner layers are GND planes.
    board.SetLayerType(pcbnew.F_Cu, pcbnew.LT_MIXED)
    board.SetLayerType(pcbnew.B_Cu, pcbnew.LT_MIXED)
    board.SetLayerName(pcbnew.In1_Cu, "GND Plane L2")
    board.SetLayerName(pcbnew.In2_Cu, "GND Plane L3")
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)

    add_outline(board)
    holes = add_mounting_holes(board)
    placed, no_courtyard, grid_bottom = import_schematic(board, comps)
    missing = assign_nets(board, nets)
    if missing:
        for m in missing[:20]:
            print("  UNMAPPED NODE:", m)
        sys.exit(f"{len(missing)} netlist nodes could not be mapped to pads")
    if no_courtyard:
        print(f"  WARNING: {len(no_courtyard)} footprints have no courtyard: {no_courtyard[:5]}")

    # drill/place origin at the board's bottom-left corner
    board.GetDesignSettings().SetAuxOrigin(vec(BX, BY + BH))
    board.GetDesignSettings().SetGridOrigin(vec(BX, BY + BH))

    # pcbnew.SaveBoard() rewrites the sibling .kicad_pro WHOLESALE with KiCad
    # defaults -- it silently destroys the ERC configuration, the schematic settings
    # and the 10-sheet list, as well as any net classes and DRC rules already there.
    # Snapshot it and put it back.  Run tools/gen_pcb_rules.py AFTER this script.
    pro = os.path.join(PRJ, "faff2_cbs1.kicad_pro")
    saved = open(pro, "rb").read() if os.path.exists(pro) else None
    pcbnew.SaveBoard(PCB, board)
    if saved is not None:
        if open(pro, "rb").read() != saved:
            open(pro, "wb").write(saved)
            print("  restored faff2_cbs1.kicad_pro (SaveBoard had overwritten it)")
    total = patch_stackup(PCB)
    print(f"saved {PCB}")
    print(f"  {len(placed)} imported footprints + {len(holes)} mounting holes")
    print(f"  board {BW} x {BH} mm, holding grid ends at y={grid_bottom:.1f} mm")
    print(f"  stackup total thickness {total:.4f} mm")


if __name__ == "__main__":
    main()
