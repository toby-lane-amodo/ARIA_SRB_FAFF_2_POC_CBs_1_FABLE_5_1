#!/usr/bin/env python3
"""Shared routing machinery for the FAFF 2 CBs_1 board.

Everything the routing stages need that is not stage-specific: the board
constants read from the project's own files (never carried in from another
board), an obstacle model that rasterises real pad/track/via/keep-out copper,
a two-layer A* maze router, and the track/via emitters.

The board file is the master.  These scripts *mutate* it -- they never
regenerate it, and `tools/gen_pcb_setup.py` must never be run over it again.

KiCad 9 only -- AGENTS.md.
"""
import math
import os

import pcbnew

from place_lib import PCB, PRO, BX, BY, BW, BH, mm, load, save, by_ref  # noqa: F401

# --------------------------------------------------------------------------
# Board constants.  Sources, in order of authority:
#   docs/decisions/actuator-pcb-setup.md S3/S6 and faff2_cbs1.kicad_pro.
# The via definition is per-project -- read here, never carried from another
# board (pcb-layout-style, VanClock ruling 2026-07-30).
# --------------------------------------------------------------------------
VIA_D = 0.60               # via pad diameter, mm
VIA_DRILL = 0.20           # via drill, mm  -> 0.20 mm annulus
CLEAR = 0.1524             # min clearance, every net class, mm
EDGE_CLEAR = 0.30          # copper to board edge, mm
VIA_A = 1.0                # amps per via (setup S3 derivation, JLC 18 um)

W_SIGNAL = 0.1524
W_ANALOG = 0.25
W_USB = 0.30
W_RF50 = 0.37
W_POWER = 0.50
W_MOTOR = 1.00
W_VIA_OD = VIA_D           # via -> cap-pad feed trace width (house step 2)

F = pcbnew.F_Cu
B = pcbnew.B_Cu
IN1 = pcbnew.In1_Cu
IN2 = pcbnew.In2_Cu

# Net-class widths, resolved the same way the .kicad_pro patterns do.
_CLASS_W = {
    "Motor": W_MOTOR, "RF50": W_RF50, "USB_HS": W_USB,
    "Power": W_POWER, "Analog": W_ANALOG, "Signal": W_SIGNAL,
    "Default": W_SIGNAL,
}

_MOTOR = {"/motor_drive/MOTOR_U", "/motor_drive/MOTOR_V", "/motor_drive/MOTOR_W",
          "/motor_drive/V24_MOT", "/motor_drive/VM_DRV"}
_RF50 = {"/mcu/SYNC_TRIG", "Net-(J503-In)", "Net-(J504-In)"}
_USB = {"/mcu/USB_DM", "/mcu/USB_DP"}
_POWER = {"+3V3", "+3V3A", "+5V", "+5VA", "/power_rails/+6V0", "/mcu/+3V3_USB",
          "/mcu/+1V8_USB", "/linear_encoder/+5V_ENC", "/motor_drive/VENC"}


def net_class(name):
    if name in _MOTOR:
        return "Motor"
    if name in _RF50:
        return "RF50"
    if name in _USB:
        return "USB_HS"
    if name in _POWER or name.startswith("/power_entry_24v/"):
        return "Power"
    if (name.startswith("Net-(U501B-") or name.startswith("Net-(U701-AIN")
            or name.startswith("Net-(U701-REF") or name.startswith("Net-(J501-")
            or name.startswith("Net-(J701-") or name.startswith("Net-(J702-")
            or name == "/linear_encoder/ENC_VREF"):
        return "Analog"
    return "Default"


def net_width(name):
    return _CLASS_W[net_class(name)]


# --------------------------------------------------------------------------
# Small geometry helpers
# --------------------------------------------------------------------------
def P(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def tomm(v):
    return pcbnew.ToMM(v)


def pt(v):
    return (pcbnew.ToMM(v.x), pcbnew.ToMM(v.y))


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


# --------------------------------------------------------------------------
# Emitters.  Create-if-absent only: board.Remove() mid-script poisons SWIG
# type resolution for every later wrapped return (pcb-layout-style).
# --------------------------------------------------------------------------
def add_track(board, a, b, width, layer, netcode):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b))
    t.SetWidth(mm(width))
    t.SetLayer(layer)
    t.SetNetCode(netcode)
    board.Add(t)
    return t


def add_via(board, p, netcode, top=F, bot=B):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*p))
    # KiCad 9: SetWidth MUST take the layer argument -- the no-arg overload
    # fires a blocking wx assert that hangs a headless script silently.
    v.SetWidth(F, mm(VIA_D))
    v.SetWidth(B, mm(VIA_D))
    v.SetDrill(mm(VIA_DRILL))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetTopLayer(top)
    v.SetBottomLayer(bot)
    v.SetNetCode(netcode)
    board.Add(v)
    return v


def polyline(board, pts, width, layer, netcode):
    out = []
    for a, b in zip(pts, pts[1:]):
        if dist(a, b) < 1e-6:
            continue
        out.append(add_track(board, a, b, width, layer, netcode))
    return out


# --------------------------------------------------------------------------
# Obstacle model
#
# Copper is rasterised on a fixed grid.  For a trace of width w needing
# clearance c, the centreline must stay (w/2 + c) away from foreign copper,
# so obstacles are dilated by that radius and the centreline is a point.
# Same-net copper is not an obstacle.
# --------------------------------------------------------------------------
GRID = 0.05  # mm


def _cells(v):
    return int(math.floor(v / GRID + 0.5))


class Obstacles:
    """Rasterised foreign-copper map for one board state.

    Rebuild after any batch of new copper (`refresh`).  Queries are per-net:
    `mask(net, layer, radius)` returns a boolean numpy array over the whole
    board where True == the centreline of a trace of that radius may not go.
    """

    def __init__(self, board):
        import numpy as np
        self.np = np
        self.board = board
        self.x0, self.y0 = BX - 1.0, BY - 1.0
        self.nx = _cells(BW + 2.0)
        self.ny = _cells(BH + 2.0)
        self.refresh()

    # -- rasterisation primitives ------------------------------------------
    def _rect(self, arr, x0, y0, x1, y1, pad):
        i0 = max(0, _cells(x0 - pad - self.x0))
        i1 = min(self.nx, _cells(x1 + pad - self.x0) + 1)
        j0 = max(0, _cells(y0 - pad - self.y0))
        j1 = min(self.ny, _cells(y1 + pad - self.y0) + 1)
        if i0 < i1 and j0 < j1:
            arr[i0:i1, j0:j1] = True

    def refresh(self):
        """Collect copper as (layerset, netcode, kind, geometry) records."""
        np = self.np
        self.items = []          # (net, layers, x0, y0, x1, y1, halfw, seg)
        b = self.board
        for f in b.GetFootprints():
            for p in f.Pads():
                net = p.GetNetCode()
                bb = p.GetBoundingBox()
                r = (tomm(bb.GetLeft()), tomm(bb.GetTop()),
                     tomm(bb.GetRight()), tomm(bb.GetBottom()))
                lay = set()
                if p.IsOnLayer(F):
                    lay.add(F)
                if p.IsOnLayer(B):
                    lay.add(B)
                if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH,
                                        pcbnew.PAD_ATTRIB_NPTH):
                    lay |= {F, B}
                self.items.append((net, lay, r, None))
        for t in b.GetTracks():
            net = t.GetNetCode()
            if isinstance(t, pcbnew.PCB_VIA):
                p = pt(t.GetPosition())
                hw = VIA_D / 2.0
                r = (p[0] - hw, p[1] - hw, p[0] + hw, p[1] + hw)
                self.items.append((net, {F, B}, r, None))
            else:
                a, c = pt(t.GetStart()), pt(t.GetEnd())
                hw = tomm(t.GetWidth()) / 2.0
                r = (min(a[0], c[0]) - hw, min(a[1], c[1]) - hw,
                     max(a[0], c[0]) + hw, max(a[1], c[1]) + hw)
                self.items.append((net, {t.GetLayer()}, r, (a, c, hw)))
        # rule areas that forbid tracks / vias
        self.no_track = []
        self.no_via = []
        for f in b.GetFootprints():
            for z in f.Zones():
                if not z.GetIsRuleArea():
                    continue
                bb = z.GetBoundingBox()
                r = (tomm(bb.GetLeft()), tomm(bb.GetTop()),
                     tomm(bb.GetRight()), tomm(bb.GetBottom()))
                if z.GetDoNotAllowTracks():
                    self.no_track.append((z, r))
                if z.GetDoNotAllowVias():
                    self.no_via.append((z, r))

    # -- queries -----------------------------------------------------------
    def mask(self, netcode, layer, radius, extra_nets=()):
        """True where a centreline of the given radius may not go."""
        np = self.np
        arr = np.zeros((self.nx, self.ny), dtype=bool)
        free = {netcode} | set(extra_nets)
        for net, lay, r, seg in self.items:
            if layer not in lay:
                continue
            if net in free and net != 0:
                continue
            self._rect(arr, r[0], r[1], r[2], r[3], radius)
        for _z, r in self.no_track:
            self._rect(arr, r[0], r[1], r[2], r[3], radius)
        # board edge
        arr[:_cells(BX + EDGE_CLEAR + radius - self.x0) + 1, :] = True
        arr[_cells(BX + BW - EDGE_CLEAR - radius - self.x0):, :] = True
        arr[:, :_cells(BY + EDGE_CLEAR + radius - self.y0) + 1] = True
        arr[:, _cells(BY + BH - EDGE_CLEAR - radius - self.y0):] = True
        return arr

    def via_mask(self, netcode, radius):
        """True where a via centre of the given clearance radius may not go.

        A via is on every layer, so it is blocked by foreign copper on F or B,
        by every barrel, and by the no-via rule areas.
        """
        np = self.np
        arr = np.zeros((self.nx, self.ny), dtype=bool)
        for net, lay, r, seg in self.items:
            if net == netcode and net != 0:
                continue
            self._rect(arr, r[0], r[1], r[2], r[3], radius)
        for _z, r in self.no_via:
            self._rect(arr, r[0], r[1], r[2], r[3], radius)
        for _z, r in self.no_track:
            self._rect(arr, r[0], r[1], r[2], r[3], radius)
        arr[:_cells(BX + EDGE_CLEAR + radius - self.x0) + 1, :] = True
        arr[_cells(BX + BW - EDGE_CLEAR - radius - self.x0):, :] = True
        arr[:, :_cells(BY + EDGE_CLEAR + radius - self.y0) + 1] = True
        arr[:, _cells(BY + BH - EDGE_CLEAR - radius - self.y0):] = True
        return arr

    def ij(self, x, y):
        return _cells(x - self.x0), _cells(y - self.y0)

    def xy(self, i, j):
        return (self.x0 + i * GRID, self.y0 + j * GRID)


def clear_of(board, x, y, radius, netcode, layers=(F, B), skip_hole=False):
    """True when a disc of `radius` at (x, y) touches no foreign copper.

    Rectangle distance against every pad/track/via world bbox -- the true
    distance, not a circumscribed-circle approximation, which falsely rejects
    legitimate same-net hugs (pcb-layout-style step 3).
    """
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetCode() == netcode and netcode != 0:
                continue
            on = any(p.IsOnLayer(l) for l in layers) or \
                p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            if not on:
                continue
            bb = p.GetBoundingBox()
            dx = max(tomm(bb.GetLeft()) - x, 0.0, x - tomm(bb.GetRight()))
            dy = max(tomm(bb.GetTop()) - y, 0.0, y - tomm(bb.GetBottom()))
            if math.hypot(dx, dy) < radius:
                return False
    return True


# --------------------------------------------------------------------------
# Two-layer A* maze router
# --------------------------------------------------------------------------
DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


class Router:
    """A* over (i, j, layer) with a via cost for the layer change.

    Steps are 8-connected on a GRID lattice; diagonals cost sqrt(2).  The
    search runs inside a bounding box grown around the endpoints so long runs
    stay affordable.
    """

    def __init__(self, obst):
        self.o = obst
        self.np = obst.np

    def route(self, netcode, start, goals, width, layers=(F, B),
              via_cost=8.0, margin=12.0, extra_nets=(), bend_cost=0.6,
              start_layers=None, goal_layers=None, max_nodes=4_000_000):
        """Find a path from `start` to the nearest of `goals`.

        start/goals are (x, y) mm.  Returns (segments, vias) where segments is
        a list of (layer, [(x, y), ...]) polylines, or None on failure.
        """
        import heapq
        np = self.np
        o = self.o
        r = width / 2.0 + CLEAR
        vr = VIA_D / 2.0 + CLEAR
        masks = {l: o.mask(netcode, l, r, extra_nets) for l in layers}
        vmask = o.via_mask(netcode, vr) if len(layers) > 1 else None

        # search window
        xs = [start[0]] + [g[0] for g in goals]
        ys = [start[1]] + [g[1] for g in goals]
        i0, j0 = o.ij(min(xs) - margin, min(ys) - margin)
        i1, j1 = o.ij(max(xs) + margin, max(ys) + margin)
        i0, j0 = max(0, i0), max(0, j0)
        i1, j1 = min(o.nx - 1, i1), min(o.ny - 1, j1)

        sl = tuple(start_layers or layers)
        gl = tuple(goal_layers or layers)
        si, sj = o.ij(*start)
        goal_ij = {}
        for g in goals:
            gi, gj = o.ij(*g)
            for l in gl:
                goal_ij[(gi, gj, l)] = True
        gset = set(goal_ij)

        def h(i, j):
            best = 1e18
            for g in goals:
                gi, gj = o.ij(*g)
                dx, dy = abs(i - gi), abs(j - gj)
                best = min(best, (dx + dy) + (math.sqrt(2) - 2) * min(dx, dy))
            return best

        openq = []
        gscore = {}
        came = {}
        for l in sl:
            s = (si, sj, l)
            gscore[s] = 0.0
            heapq.heappush(openq, (h(si, sj), 0.0, s, None))
        seen = 0
        end = None
        while openq:
            f, g, cur, prev = heapq.heappop(openq)
            if gscore.get(cur, 1e18) < g - 1e-9:
                continue
            if cur in came and came[cur] is not None and prev is not None \
                    and came[cur] != prev:
                pass
            seen += 1
            if seen > max_nodes:
                return None
            if cur in gset:
                end = cur
                break
            ci, cj, cl = cur
            pi = came.get(cur)
            pdir = None
            if pi is not None and pi[2] == cl:
                pdir = (ci - pi[0], cj - pi[1])
                n = max(abs(pdir[0]), abs(pdir[1])) or 1
                pdir = (pdir[0] // n if abs(pdir[0]) == n else 0,
                        pdir[1] // n if abs(pdir[1]) == n else 0)
            for dx, dy in DIRS8:
                ni, nj = ci + dx, cj + dy
                if ni < i0 or ni > i1 or nj < j0 or nj > j1:
                    continue
                if masks[cl][ni, nj]:
                    continue
                if dx and dy:
                    # do not cut corners diagonally through blocked cells
                    if masks[cl][ci + dx, cj] or masks[cl][ci, cj + dy]:
                        continue
                    step = math.sqrt(2)
                else:
                    step = 1.0
                cost = step
                if pdir is not None and (dx, dy) != pdir:
                    cost += bend_cost
                nxt = (ni, nj, cl)
                ng = g + cost
                if ng < gscore.get(nxt, 1e18) - 1e-9:
                    gscore[nxt] = ng
                    came[nxt] = cur
                    heapq.heappush(openq, (ng + h(ni, nj), ng, nxt, cur))
            if vmask is not None and not vmask[ci, cj]:
                for l in layers:
                    if l == cl:
                        continue
                    nxt = (ci, cj, l)
                    ng = g + via_cost
                    if ng < gscore.get(nxt, 1e18) - 1e-9:
                        gscore[nxt] = ng
                        came[nxt] = cur
                        heapq.heappush(openq, (ng + h(ci, cj), ng, nxt, cur))
        if end is None:
            return None

        # reconstruct
        path = [end]
        while came.get(path[-1]) is not None:
            path.append(came[path[-1]])
        path.reverse()
        return self._to_geometry(path)

    def _to_geometry(self, path):
        o = self.o
        segs = []
        vias = []
        run = [path[0]]
        for a, b in zip(path, path[1:]):
            if a[2] != b[2]:
                segs.append((a[2], [o.xy(p[0], p[1]) for p in run]))
                vias.append(o.xy(a[0], a[1]))
                run = [b]
            else:
                run.append(b)
        segs.append((run[-1][2], [o.xy(p[0], p[1]) for p in run]))
        return ([(l, _simplify(p)) for l, p in segs if len(p) > 1], vias)


def _simplify(pts):
    """Collapse collinear runs of grid steps into corner-to-corner segments."""
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[i]
        cx, cy = pts[i + 1]
        if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1e-9:
            out.append(pts[i])
    out.append(pts[-1])
    return out


# --------------------------------------------------------------------------
# Reporting helpers
# --------------------------------------------------------------------------
def net_of(board, name):
    ni = board.GetNetsByName()
    return ni[name].GetNetCode() if name in [k for k in ni.keys()] else None


def netcode(board, name):
    for code, info in board.GetNetsByNetcode().items():
        if info.GetNetname() == name:
            return code
    raise KeyError(name)


def pads_of(board, netname):
    out = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() == netname:
                out.append((f.GetReference(), p.GetNumber(), pt(p.GetPosition()), p))
    return out


def unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(True)


def refill(board):
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
