#!/usr/bin/env python3
"""Shared routing machinery for the FAFF 2 CBs_1 board.

Everything the routing stages need that is not stage-specific: the board
constants read from the project's own files (never carried in from another
board), an obstacle model that rasterises the real pad / track / via / hole /
keep-out copper, a two-layer A* maze router, and the track/via emitters.

The board file is the master.  These scripts *mutate* it -- they never
regenerate it, and `tools/gen_pcb_setup.py` must never be run over it again.

KiCad 9 only -- AGENTS.md.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from place_lib import PCB, PRO, BX, BY, BW, BH, mm, save, by_ref  # noqa: E402,F401

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
HOLE_CLEAR = 0.25          # copper to hole, mm
HOLE2HOLE = 0.45           # hole to hole, mm
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
IN3 = pcbnew.In3_Cu
IN4 = pcbnew.In4_Cu

# Round 2 restacked the board to six layers, SIG / GND / PWR / PWR / GND / SIG.
# ROUTE_LAYERS is every layer copper may be *routed* on -- the two outer signal
# layers and the two inner power layers; PLANES is the two that stay whole.
# Everything below that used to key a dict on {F, B} keys it on ROUTE_LAYERS
# instead, so the same machinery serves either stackup: on the 4-layer board
# In2/In3 simply never appear.
ROUTE_LAYERS = (F, B, IN2, IN3)
PLANES = (IN1, IN4)
ALL_CU = (F, B, IN1, IN2, IN3, IN4)

_CLASS_W = {
    "Motor": W_MOTOR, "RF50": W_RF50, "USB_HS": W_USB,
    "Power": W_POWER, "Analog": W_ANALOG, "Signal": W_SIGNAL,
    "Default": W_SIGNAL,
}

# The three low-side source nets -- Net-(Q1102-S_3) and friends -- are
# deliberately NOT here, even though the FET-source-to-shunt half of each one
# carries the leg's full 3 A.  The other half of the same net is that leg's
# Kelvin tap into the DRV, and a class width applies to the whole net: put them
# in Motor and route4c widens the sense tap to 1.00 mm, which is the opposite
# of what a Kelvin tap wants.  The power half is sized where the distinction
# can actually be made -- route4c's bridge test, which sizes a segment with the
# rail's real load behind it from the current and leaves a one-pad branch at
# the class floor.  They are in route_check's via budget at 3.0 A regardless.
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


def load():
    b = pcbnew.LoadBoard(PCB)
    for f in b.GetFootprints():
        f.BuildCourtyardCaches()
    return b


def netcode(board, name):
    for code, info in board.GetNetsByNetcode().items():
        if info.GetNetname() == name:
            return code
    raise KeyError(name)


def pad_bbox(p):
    bb = p.GetBoundingBox()
    return (tomm(bb.GetLeft()), tomm(bb.GetTop()),
            tomm(bb.GetRight()), tomm(bb.GetBottom()))


def pad_copper_layers(p):
    """{F, B} the pad actually has copper on.  Paste-only pads have none."""
    out = set()
    if p.IsOnLayer(F):
        out.add(F)
    if p.IsOnLayer(B):
        out.add(B)
    return out


def is_hole(p):
    return p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)


# --------------------------------------------------------------------------
# Emitters.  Create-if-absent only: board.Remove() mid-script poisons SWIG
# type resolution for every later wrapped return (pcb-layout-style).
# --------------------------------------------------------------------------
def add_track(board, a, b, width, layer, nc):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b))
    t.SetWidth(mm(width))
    t.SetLayer(layer)
    t.SetNetCode(nc)
    board.Add(t)
    return t


def add_via(board, p, nc):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(*p))
    # KiCad 9: SetWidth MUST take the layer argument -- the no-arg overload
    # fires a blocking wx assert that hangs a headless script silently.
    v.SetWidth(F, mm(VIA_D))
    v.SetWidth(B, mm(VIA_D))
    v.SetDrill(mm(VIA_DRILL))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetTopLayer(F)
    v.SetBottomLayer(B)
    v.SetNetCode(nc)
    board.Add(v)
    return v


def polyline(board, pts, width, layer, nc):
    out = []
    for a, b in zip(pts, pts[1:]):
        if dist(a, b) < 1e-6:
            continue
        out.append(add_track(board, a, b, width, layer, nc))
    return out


# --------------------------------------------------------------------------
# Obstacle model
#
# Copper is rasterised on a fixed grid.  For a trace of width w needing
# clearance c, the centreline must stay (w/2 + c) away from foreign copper, so
# obstacles are dilated by that radius and the centreline is a point.
# Same-net copper is not an obstacle.
# --------------------------------------------------------------------------
GRID = 0.05        # mm
BUCKET = 4.0       # mm, spatial index cell
RESERVED = -1      # pseudo-net for a corridor held for a later stage


SEG_STEP = 0.15    # obstacle box pitch along a diagonal track


def _seg_obstacle_boxes(a, c, hw):
    """A track as axis-aligned obstacle boxes.

    An axis-aligned segment IS its bbox, so it takes one box.  A diagonal's
    bbox is far bigger than the copper -- at 45 deg a single box over-blocks
    by 0.4 mm, which quietly walls off legal lanes -- so it is chopped at
    SEG_STEP.
    """
    if abs(a[0] - c[0]) < 1e-9 or abs(a[1] - c[1]) < 1e-9:
        return [(min(a[0], c[0]) - hw, min(a[1], c[1]) - hw,
                 max(a[0], c[0]) + hw, max(a[1], c[1]) + hw)]
    n = max(1, int(dist(a, c) / SEG_STEP) + 1)
    out = []
    for s in range(n):
        t0, t1 = s / n, (s + 1) / n
        x0 = a[0] + (c[0] - a[0]) * t0
        y0 = a[1] + (c[1] - a[1]) * t0
        x1 = a[0] + (c[0] - a[0]) * t1
        y1 = a[1] + (c[1] - a[1]) * t1
        out.append((min(x0, x1) - hw, min(y0, y1) - hw,
                    max(x0, x1) + hw, max(y0, y1) + hw))
    return out


class Obstacles:
    def __init__(self, board):
        import numpy as np
        self.np = np
        self.board = board
        self.x0, self.y0 = BX - 2.0, BY - 2.0
        self.nx = int(round((BW + 4.0) / GRID))
        self.ny = int(round((BH + 4.0) / GRID))
        self.refresh()

    # ---- indexing --------------------------------------------------------
    def ij(self, x, y):
        return (int(math.floor((x - self.x0) / GRID + 0.5)),
                int(math.floor((y - self.y0) / GRID + 0.5)))

    def xy(self, i, j):
        return (round(self.x0 + i * GRID, 4), round(self.y0 + j * GRID, 4))

    def _index(self):
        self.buckets = {}
        for k, it in enumerate(self.items):
            x0, y0, x1, y1 = it[2]
            for bi in range(int(x0 // BUCKET), int(x1 // BUCKET) + 1):
                for bj in range(int(y0 // BUCKET), int(y1 // BUCKET) + 1):
                    self.buckets.setdefault((bi, bj), []).append(k)

    def refresh(self):
        """items: (netcode, frozenset(layers), (x0,y0,x1,y1), kind)

        kind: 'cu' normal copper, 'hole' a drilled hole (needs HOLE_CLEAR and
        blocks vias on every layer).
        """
        items = []
        b = self.board
        for f in b.GetFootprints():
            for p in f.Pads():
                lay = pad_copper_layers(p)
                if lay:
                    items.append((p.GetNetCode(), frozenset(lay),
                                  pad_bbox(p), "pad"))
                if is_hole(p):
                    q = pt(p.GetPosition())
                    r = max(tomm(p.GetDrillSizeX()),
                            tomm(p.GetDrillSizeY())) / 2.0
                    items.append((p.GetNetCode(), frozenset((F, B)),
                                  (q[0] - r, q[1] - r, q[0] + r, q[1] + r),
                                  "hole"))
        for t in b.GetTracks():
            nc = t.GetNetCode()
            if isinstance(t, pcbnew.PCB_VIA):
                q = pt(t.GetPosition())
                hw = VIA_D / 2.0
                items.append((nc, frozenset((F, B)),
                              (q[0] - hw, q[1] - hw, q[0] + hw, q[1] + hw), "cu"))
                hr = VIA_DRILL / 2.0
                items.append((nc, frozenset((F, B)),
                              (q[0] - hr, q[1] - hr, q[0] + hr, q[1] + hr), "hole"))
            else:
                a, c = pt(t.GetStart()), pt(t.GetEnd())
                hw = tomm(t.GetWidth()) / 2.0
                for box in _seg_obstacle_boxes(a, c, hw):
                    items.append((nc, frozenset((t.GetLayer(),)), box, "cu"))
        self.items = items
        self._index()
        # rule areas
        self.rules = []          # (allow_track, allow_via, bbox)
        for f in b.GetFootprints():
            for z in f.Zones():
                if not z.GetIsRuleArea():
                    continue
                bb = z.GetBoundingBox()
                r = (tomm(bb.GetLeft()), tomm(bb.GetTop()),
                     tomm(bb.GetRight()), tomm(bb.GetBottom()))
                self.rules.append((not z.GetDoNotAllowTracks(),
                                   not z.GetDoNotAllowVias(), r))

    def _add(self, item):
        self.items.append(item)
        k = len(self.items) - 1
        x0, y0, x1, y1 = item[2]
        for bi in range(int(x0 // BUCKET), int(x1 // BUCKET) + 1):
            for bj in range(int(y0 // BUCKET), int(y1 // BUCKET) + 1):
                self.buckets.setdefault((bi, bj), []).append(k)

    def add_seg(self, a, c, hw, layer, nc):
        for box in _seg_obstacle_boxes(a, c, hw):
            self._add((nc, frozenset((layer,)), box, "cu"))

    def reserve_pin_escapes(self, board, pitch_max=0.75, length=0.8):
        """Hold every fine-pitch pin's own escape lane open.

        An IC's pin ring is escape lanes wall to wall (R3-1).  Nothing stops a
        foreign net's trace running straight down one of them -- step 2's
        VM_DRV link did exactly that along U1101 pin 5's only lane, and pin 5
        then had nowhere to go.  Each lane is reserved *with its own pin's
        netcode*, so the pin's own net may use it and no other net may cross
        the ring.  Returns the number of lanes held.
        """
        n = 0
        for f in board.GetFootprints():
            pads = [p for p in f.Pads() if pad_copper_layers(p)]
            if len(pads) < 8:
                continue
            cs = [pt(p.GetPosition()) for p in pads]
            pitch = min((dist(a, b) for i, a in enumerate(cs)
                         for b in cs[i + 1:]), default=99)
            if pitch > pitch_max:
                continue
            c = pt(f.GetPosition())
            for p in pads:
                nc = p.GetNetCode()
                if not nc or p.GetNetname().startswith("unconnected-"):
                    continue
                bb = pad_bbox(p)
                w, h = bb[2] - bb[0], bb[3] - bb[1]
                if abs(w - h) < 0.05:
                    continue
                q = pt(p.GetPosition())
                if w > h:
                    u = (math.copysign(1.0, (q[0] - c[0]) or 1.0), 0.0)
                    hw = h / 2.0
                    d0 = w / 2.0
                else:
                    u = (0.0, math.copysign(1.0, (q[1] - c[1]) or 1.0))
                    hw = w / 2.0
                    d0 = h / 2.0
                a = (q[0] + u[0] * d0, q[1] + u[1] * d0)
                b = (q[0] + u[0] * (d0 + length), q[1] + u[1] * (d0 + length))
                self.reserve([a, b], hw, nc)
                n += 1
        return n

    def reserve(self, pts, hw, nc=RESERVED):
        """Block a corridor on both layers for a net not routed yet.

        Reservations live only in this obstacle model, never on the board, so
        a later stage that rebuilds the model sees clear board again.  They
        exist so the house step order (planes, feeds, ground, then signals)
        cannot drop a ground stitch across a controlled-impedance corridor
        that step 5 has to have.
        """
        for a, b in zip(pts, pts[1:]):
            n = max(1, int(dist(a, b) / 0.4))
            for k in range(n):
                t0, t1 = k / n, (k + 1) / n
                x0 = a[0] + (b[0] - a[0]) * t0
                y0 = a[1] + (b[1] - a[1]) * t0
                x1 = a[0] + (b[0] - a[0]) * t1
                y1 = a[1] + (b[1] - a[1]) * t1
                self._add((nc, frozenset((F, B)),
                           (min(x0, x1) - hw, min(y0, y1) - hw,
                            max(x0, x1) + hw, max(y0, y1) + hw), "cu"))

    def add_via_at(self, q, nc):
        hw = VIA_D / 2.0
        self._add((nc, frozenset((F, B)),
                   (q[0] - hw, q[1] - hw, q[0] + hw, q[1] + hw), "cu"))
        hr = VIA_DRILL / 2.0
        self._add((nc, frozenset((F, B)),
                   (q[0] - hr, q[1] - hr, q[0] + hr, q[1] + hr), "hole"))

    # ---- masks -----------------------------------------------------------
    def _near(self, win, pad):
        i0, j0, i1, j1 = win
        x0 = self.x0 + i0 * GRID - pad
        y0 = self.y0 + j0 * GRID - pad
        x1 = self.x0 + i1 * GRID + pad
        y1 = self.y0 + j1 * GRID + pad
        out = set()
        for bi in range(int(x0 // BUCKET), int(x1 // BUCKET) + 1):
            for bj in range(int(y0 // BUCKET), int(y1 // BUCKET) + 1):
                out.update(self.buckets.get((bi, bj), ()))
        return out

    def _paint(self, arr, win, r, pad):
        i0, j0, _i1, _j1 = win
        a = max(0, int(math.floor((r[0] - pad - self.x0) / GRID + 0.5)) - i0)
        c = min(arr.shape[0],
                int(math.floor((r[2] + pad - self.x0) / GRID + 0.5)) - i0 + 1)
        d = max(0, int(math.floor((r[1] - pad - self.y0) / GRID + 0.5)) - j0)
        e = min(arr.shape[1],
                int(math.floor((r[3] + pad - self.y0) / GRID + 0.5)) - j0 + 1)
        if a < c and d < e:
            arr[a:c, d:e] = True

    def track_mask(self, win, nc, layer, radius, free_nets=()):
        np = self.np
        i0, j0, i1, j1 = win
        arr = np.zeros((i1 - i0 + 1, j1 - j0 + 1), dtype=bool)
        free = set(free_nets) | ({nc} if nc else set())
        big = max(radius, radius - CLEAR + HOLE_CLEAR)
        for k in self._near(win, big + 0.1):
            n, lay, r, kind = self.items[k]
            if n in free:
                # same-net copper is not an obstacle, and neither is a same-net
                # PTH barrel -- a trace landing on a through-hole pad covers
                # its own hole by construction
                continue
            if kind == "hole":
                self._paint(arr, win, r, radius - CLEAR + HOLE_CLEAR)
                continue
            if layer not in lay:
                continue
            self._paint(arr, win, r, radius)
        for ok_t, _ok_v, r in self.rules:
            if not ok_t:
                self._paint(arr, win, r, radius)
        self._edges(arr, win, radius)
        return arr

    def via_mask(self, win, nc, free_nets=()):
        """Where a via centre may not sit."""
        np = self.np
        i0, j0, i1, j1 = win
        arr = np.zeros((i1 - i0 + 1, j1 - j0 + 1), dtype=bool)
        free = set(free_nets) | ({nc} if nc else set())
        rc = VIA_D / 2.0 + CLEAR
        rh = VIA_DRILL / 2.0 + HOLE2HOLE
        for k in self._near(win, max(rc, rh) + 0.1):
            n, lay, r, kind = self.items[k]
            if kind == "hole":
                self._paint(arr, win, r, rh)
                continue
            if kind == "pad":
                # no via-in-pad (G9); the QFN-EP array is placed explicitly
                self._paint(arr, win, r, VIA_D / 2.0 - 0.05)
            if n in free:
                continue
            self._paint(arr, win, r, rc)
        for _ok_t, ok_v, r in self.rules:
            if not ok_v:
                self._paint(arr, win, r, VIA_D / 2.0)
        self._edges(arr, win, VIA_D / 2.0 + EDGE_CLEAR - CLEAR + CLEAR)
        return arr

    def _edges(self, arr, win, radius):
        i0, j0, i1, j1 = win
        lo_i = int(math.floor((BX + EDGE_CLEAR + radius - self.x0) / GRID + 0.5))
        hi_i = int(math.floor((BX + BW - EDGE_CLEAR - radius - self.x0) / GRID + 0.5))
        lo_j = int(math.floor((BY + EDGE_CLEAR + radius - self.y0) / GRID + 0.5))
        hi_j = int(math.floor((BY + BH - EDGE_CLEAR - radius - self.y0) / GRID + 0.5))
        if lo_i - i0 > 0:
            arr[:max(0, lo_i - i0), :] = True
        if hi_i - i0 + 1 < arr.shape[0]:
            arr[max(0, hi_i - i0 + 1):, :] = True
        if lo_j - j0 > 0:
            arr[:, :max(0, lo_j - j0)] = True
        if hi_j - j0 + 1 < arr.shape[1]:
            arr[:, max(0, hi_j - j0 + 1):] = True
        # the board's R2 corners, only when the window actually reaches one
        for cx, cy, sx, sy in ((BX + 2, BY + 2, -1, -1),
                               (BX + BW - 2, BY + 2, 1, -1),
                               (BX + 2, BY + BH - 2, -1, 1),
                               (BX + BW - 2, BY + BH - 2, 1, 1)):
            ci, cj = self.ij(cx, cy)
            if not (i0 - 50 <= ci <= i1 + 50 and j0 - 50 <= cj <= j1 + 50):
                continue
            rr = 2.0 - EDGE_CLEAR - radius
            for di in range(0, int(2.5 / GRID)):
                for dj in range(0, int(2.5 / GRID)):
                    x = cx + sx * di * GRID
                    y = cy + sy * dj * GRID
                    if math.hypot(x - cx, y - cy) <= rr:
                        continue
                    ii = self.ij(x, y)[0] - i0
                    jj = self.ij(x, y)[1] - j0
                    if 0 <= ii < arr.shape[0] and 0 <= jj < arr.shape[1]:
                        arr[ii, jj] = True


# --------------------------------------------------------------------------
# Two-layer A* maze router
# --------------------------------------------------------------------------
DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
SQ2 = math.sqrt(2.0)


class Maze:
    def __init__(self, obst):
        self.o = obst

    def window(self, pts, margin):
        o = self.o
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        i0, j0 = o.ij(min(xs) - margin, min(ys) - margin)
        i1, j1 = o.ij(max(xs) + margin, max(ys) + margin)
        return (max(0, i0), max(0, j0), min(o.nx - 1, i1), min(o.ny - 1, j1))

    def route(self, nc, starts, goals, width, layers=(F, B), margin=10.0,
              via_cost=14.0, bend_cost=0.4, free_nets=(), hw=1.3,
              max_nodes=1_200_000, goal_rects=None, start_rects=None,
              layer_bias=None):
        """starts/goals: [(x, y)] mm.  goal_rects/start_rects: extra copper
        rectangles per layer, {layer: [(x0,y0,x1,y1)]}, that also count."""
        import heapq
        import numpy as np
        o = self.o
        r = width / 2.0 + CLEAR
        win = self.window(list(starts) + list(goals), margin)
        i0, j0, i1, j1 = win
        W, H = i1 - i0 + 1, j1 - j0 + 1
        masks = {l: o.track_mask(win, nc, l, r, free_nets) for l in layers}
        vmask = o.via_mask(win, nc, free_nets) if len(layers) > 1 else None

        gmask = {l: np.zeros((W, H), dtype=bool) for l in layers}
        self._mark(gmask, win, goal_rects, layers)
        smask = {l: np.zeros((W, H), dtype=bool) for l in layers}
        self._mark(smask, win, start_rects, layers)

        # open all start cells that are legal
        openq = []
        gscore = {}
        came = {}
        for l in layers:
            free = smask[l] & ~masks[l]
            idx = np.argwhere(free)
            for ii, jj in idx:
                s = (int(ii), int(jj), l)
                gscore[s] = 0.0
                heapq.heappush(openq, (0.0, 0.0, s))
        if not openq:
            return None

        # the heuristic is evaluated per expansion, so cap how many goal
        # points it scans -- keep the ones nearest the start
        if len(goals) > 16:
            sx = sum(p[0] for p in starts) / len(starts)
            sy = sum(p[1] for p in starts) / len(starts)
            goals = sorted(goals, key=lambda g: (g[0] - sx) ** 2
                           + (g[1] - sy) ** 2)[:16]
        gpts = [o.ij(*g) for g in goals]
        gpts = [(a - i0, b - j0) for a, b in gpts]

        def h(i, j):
            best = 1e18
            for gi, gj in gpts:
                dx, dy = abs(i - gi), abs(j - gj)
                best = min(best, (dx + dy) + (SQ2 - 2) * min(dx, dy))
            return best * hw

        bias = layer_bias or {}
        seen = 0
        end = None
        while openq:
            f, g, cur = heapq.heappop(openq)
            if g > gscore.get(cur, 1e18) + 1e-9:
                continue
            ci, cj, cl = cur
            if gmask[cl][ci, cj]:
                end = cur
                break
            seen += 1
            if seen > max_nodes:
                return None
            prev = came.get(cur)
            pdir = None
            if prev is not None and prev[2] == cl:
                dx, dy = ci - prev[0], cj - prev[1]
                n = max(abs(dx), abs(dy)) or 1
                pdir = (dx // n, dy // n)
            m = masks[cl]
            for dx, dy in DIRS8:
                ni, nj = ci + dx, cj + dy
                if ni < 0 or nj < 0 or ni >= W or nj >= H:
                    continue
                if m[ni, nj]:
                    continue
                if dx and dy:
                    if m[ci + dx, cj] or m[ci, cj + dy]:
                        continue
                    step = SQ2
                else:
                    step = 1.0
                cost = step * (1.0 + bias.get(cl, 0.0))
                if pdir is not None and (dx, dy) != pdir:
                    cost += bend_cost
                nxt = (ni, nj, cl)
                ng = g + cost
                if ng + 1e-9 < gscore.get(nxt, 1e18):
                    gscore[nxt] = ng
                    came[nxt] = cur
                    heapq.heappush(openq, (ng + h(ni, nj), ng, nxt))
            if vmask is not None and not vmask[ci, cj]:
                for l in layers:
                    if l == cl:
                        continue
                    if masks[l][ci, cj]:
                        continue
                    nxt = (ci, cj, l)
                    ng = g + via_cost
                    if ng + 1e-9 < gscore.get(nxt, 1e18):
                        gscore[nxt] = ng
                        came[nxt] = cur
                        heapq.heappush(openq, (ng + h(ci, cj), ng, nxt))
        if end is None:
            return None
        path = [end]
        while came.get(path[-1]) is not None:
            path.append(came[path[-1]])
        path.reverse()
        return self._geom(path, win)

    def _mark(self, masks, win, rects, layers):
        """Mark copper rectangles, per layer.  Never across layers -- a goal
        marked on the wrong layer ends a route in mid-air (track_dangling)."""
        o = self.o
        i0, j0, i1, j1 = win
        for l, rs in (rects or {}).items():
            if l not in masks:
                continue
            for r in rs:
                a = max(0, int(math.floor((r[0] - o.x0) / GRID + 0.5)) - i0)
                c = min(masks[l].shape[0],
                        int(math.floor((r[2] - o.x0) / GRID + 0.5)) - i0 + 1)
                d = max(0, int(math.floor((r[1] - o.y0) / GRID + 0.5)) - j0)
                e = min(masks[l].shape[1],
                        int(math.floor((r[3] - o.y0) / GRID + 0.5)) - j0 + 1)
                if a < c and d < e:
                    masks[l][a:c, d:e] = True

    def _geom(self, path, win):
        o = self.o
        i0, j0, _, _ = win
        segs, vias = [], []
        run = [path[0]]
        for a, b in zip(path, path[1:]):
            if a[2] != b[2]:
                segs.append((a[2], [o.xy(p[0] + i0, p[1] + j0) for p in run]))
                vias.append(o.xy(a[0] + i0, a[1] + j0))
                run = [b]
            else:
                run.append(b)
        segs.append((run[0][2], [o.xy(p[0] + i0, p[1] + j0) for p in run]))
        return ([(l, simplify(p)) for l, p in segs if len(p) > 1], vias)


def simplify(pts):
    if len(pts) < 3:
        return list(pts)
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        ax, ay = out[-1]
        bx, by = pts[i]
        cx, cy = pts[i + 1]
        if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1e-9:
            out.append(pts[i])
    out.append(pts[-1])
    return out


def emit(board, res, width, nc, obst=None):
    """Write a Maze.route() result to the board."""
    segs, vias = res
    tracks = []
    for layer, pts in segs:
        tracks += polyline(board, pts, width, layer, nc)
    for v in vias:
        add_via(board, v, nc)
    return tracks, vias


def route_len(res):
    tot = 0.0
    for _l, pts in res[0]:
        for a, b in zip(pts, pts[1:]):
            tot += dist(a, b)
    return tot


# --------------------------------------------------------------------------
# Net-level connection driver
# --------------------------------------------------------------------------
def pad_nodes(board, netname):
    """Pads of a net, merged into nodes where they physically overlap."""
    pads = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != netname:
                continue
            if not pad_copper_layers(p):
                continue
            pads.append((f.GetReference(), p))
    nodes = []
    used = [False] * len(pads)
    for i, (ref, p) in enumerate(pads):
        if used[i]:
            continue
        grp = [(ref, p)]
        used[i] = True
        changed = True
        while changed:
            changed = False
            for j, (r2, q) in enumerate(pads):
                if used[j]:
                    continue
                for _r, m in grp:
                    a, b_ = pad_bbox(m), pad_bbox(q)
                    if (a[0] <= b_[2] and b_[0] <= a[2]
                            and a[1] <= b_[3] and b_[1] <= a[3]):
                        grp.append((r2, q))
                        used[j] = True
                        changed = True
                        break
        nodes.append(grp)
    return nodes


TARGET_INSET = 0.15
TARGET_CENTRE_MAX = 2.0


def pad_target_rect(p):
    """Where a trace may legally terminate on this pad.

    Small pads take their centre -- a trace that stops on a pad edge is a
    connection KiCad has to argue itself into; one that runs to the centre is
    unambiguous.  Big pads (EPs, shells, terminal blocks) take the bbox inset
    by TARGET_INSET so the router does not walk their whole length.
    """
    x0, y0, x1, y1 = pad_bbox(p)
    if (x1 - x0) <= TARGET_CENTRE_MAX and (y1 - y0) <= TARGET_CENTRE_MAX:
        c = pt(p.GetPosition())
        return (c[0] - 0.03, c[1] - 0.03, c[0] + 0.03, c[1] + 0.03)
    a = min(TARGET_INSET, (x1 - x0) / 2 - 0.02)
    b = min(TARGET_INSET, (y1 - y0) / 2 - 0.02)
    return (x0 + a, y0 + b, x1 - a, y1 - b)


def node_geom(grp):
    """(centre, target-rects per layer, representative points) for a group."""
    rects = {l: [] for l in ROUTE_LAYERS}
    pts = []
    for _ref, p in grp:
        tr = pad_target_rect(p)
        for l in pad_copper_layers(p):
            rects[l].append(tr)
        pts.append(pt(p.GetPosition()))
    cx = sum(q[0] for q in pts) / len(pts)
    cy = sum(q[1] for q in pts) / len(pts)
    return (cx, cy), rects, pts


def emit_result(board, obst, res, width, nc):
    """Write a route to the board AND into the live obstacle model."""
    segs, vias = res
    for layer, pts in segs:
        for a, b in zip(pts, pts[1:]):
            if dist(a, b) < 1e-6:
                continue
            add_track(board, a, b, width, layer, nc)
            obst.add_seg(a, b, width / 2.0, layer, nc)
    for v in vias:
        add_via(board, v, nc)
        obst.add_via_at(v, nc)


def seg_boxes(a, b, hw, step=None):
    """A segment as a chain of small boxes that lie strictly INSIDE the trace.

    The bbox of a 45 deg segment is mostly *not* on the trace, and even a
    chain of full-width boxes pokes out at the corners -- a goal built from
    either lets a route stop a hair beside the copper it meant to join (DRC
    `track_dangling`).  Half-width boxes on a half-width pitch cannot.
    """
    h = max(0.03, hw / 2.0)
    n = max(1, int(dist(a, b) / h))
    out = []
    for k in range(n + 1):
        t = k / n
        x = a[0] + (b[0] - a[0]) * t
        y = a[1] + (b[1] - a[1]) * t
        out.append((x - h, y - h, x + h, y + h))
    return out


def board_net_rects(board, nc, hw_extra=0.0):
    """Every existing copper rectangle of a net, per layer, chain-boxed."""
    out = {l: [] for l in ROUTE_LAYERS}
    for t in board.GetTracks():
        if t.GetNetCode() != nc:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            q = pt(t.GetPosition())
            hw = VIA_D / 2.0 / 1.5      # inscribed square of the via pad
            for l in ROUTE_LAYERS:
                out[l].append((q[0] - hw, q[1] - hw, q[0] + hw, q[1] + hw))
        else:
            hw = tomm(t.GetWidth()) / 2.0 + hw_extra
            if t.GetLayer() in out:
                out[t.GetLayer()] += seg_boxes(pt(t.GetStart()),
                                               pt(t.GetEnd()), hw)
    return out


def seg_rects(res, hw):
    out = {l: [] for l in ROUTE_LAYERS}
    for layer, pts in res[0]:
        for a, b in zip(pts, pts[1:]):
            out.setdefault(layer, [])
            out[layer] += seg_boxes(a, b, hw)
    for v in res[1]:
        for l in ROUTE_LAYERS:
            out[l].append((v[0] - VIA_D / 2, v[1] - VIA_D / 2,
                           v[0] + VIA_D / 2, v[1] + VIA_D / 2))
    return out


# --------------------------------------------------------------------------
# Geometric connectivity, per net
#
# pcbnew's Python binding does not expose the ratsnest usefully, and the
# proofs need more than a count: which pads are in which island, and whether a
# net's connectivity leans on a single via.  So build it from the copper.
# --------------------------------------------------------------------------
class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def net_items(board, net):
    """[(kind, ref, layers, obstacle boxes, goal boxes)] for one net.

    Obstacle boxes cover the copper; goal boxes lie strictly inside it, so a
    route that lands on one is really on the copper.
    """
    out = []
    for f in board.GetFootprints():
        for p in f.Pads():
            if p.GetNetname() != net:
                continue
            lay = pad_copper_layers(p)
            if not lay:
                continue
            if is_hole(p):
                lay = set(ALL_CU)
            out.append(("pad", f"{f.GetReference()}.{p.GetNumber()}",
                        frozenset(lay), [pad_bbox(p)],
                        [pad_target_rect(p)]))
    for t in board.GetTracks():
        if t.GetNetname() != net:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            q = pt(t.GetPosition())
            hw = VIA_D / 2.0
            g = hw / 1.5
            out.append(("via", f"{q[0]:.3f},{q[1]:.3f}",
                        frozenset(ALL_CU),
                        [(q[0] - hw, q[1] - hw, q[0] + hw, q[1] + hw)],
                        [(q[0] - g, q[1] - g, q[0] + g, q[1] + g)]))
        else:
            a, b = pt(t.GetStart()), pt(t.GetEnd())
            hw = tomm(t.GetWidth()) / 2.0
            out.append(("track", f"{a[0]:.2f},{a[1]:.2f}-{b[0]:.2f},{b[1]:.2f}",
                        frozenset((t.GetLayer(),)),
                        _seg_obstacle_boxes(a, b, hw),
                        seg_boxes(a, b, hw)))
    return out


def _touch_graph(items, plane_layers=()):
    """Union-find over items whose boxes overlap on a shared layer."""
    uf = _UF(len(items))
    cell = 2.0
    buckets = {}
    for i, it in enumerate(items):
        for bx in it[3]:
            for gi in range(int(bx[0] // cell), int(bx[2] // cell) + 1):
                for gj in range(int(bx[1] // cell), int(bx[3] // cell) + 1):
                    buckets.setdefault((gi, gj), set()).add(i)
    for _key, ids in buckets.items():
        ids = sorted(ids)
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                i, j = ids[x], ids[y]
                if uf.find(i) == uf.find(j):
                    continue
                if not (items[i][2] & items[j][2]):
                    continue
                if _boxes_touch(items[i][3], items[j][3]):
                    uf.union(i, j)
    if plane_layers:
        reach = [i for i, it in enumerate(items) if it[2] & set(plane_layers)]
        for i in reach[1:]:
            uf.union(reach[0], i)
    return uf


def _boxes_touch(a, b):
    for p in a:
        for q in b:
            if (p[0] <= q[2] + 1e-6 and q[0] <= p[2] + 1e-6
                    and p[1] <= q[3] + 1e-6 and q[1] <= p[3] + 1e-6):
                return True
    return False


def net_islands(board, net, plane=False):
    items = net_items(board, net)
    uf = _touch_graph(items, (IN1, IN2) if plane else ())
    groups = {}
    for i, it in enumerate(items):
        groups.setdefault(uf.find(i), []).append(it)
    return list(groups.values())


def net_is_whole(board, net, plane=False):
    isl = net_islands(board, net, plane)
    with_pads = [g for g in isl if any(k == "pad" for k, *_ in g)]
    return len(with_pads) <= 1


def island_geoms(board, net):
    """(root -> goal geometry, pad name -> root) for one net's copper."""
    items = net_items(board, net)
    uf = _touch_graph(items)
    isl, pad_root = {}, {}
    for i, it in enumerate(items):
        r = uf.find(i)
        d = isl.setdefault(r, dict({l: [] for l in ROUTE_LAYERS},
                                    **{"pts": []}))
        for l in it[2]:
            if l in d:
                d[l] += it[4]
        b0 = it[4][0]
        d["pts"].append(((b0[0] + b0[2]) / 2.0, (b0[1] + b0[3]) / 2.0))
        if it[0] == "pad":
            pad_root[it[1]] = r
    return isl, pad_root


def _pad_has_copper(board, pad, nc):
    bb = pad_bbox(pad)
    for t in board.GetTracks():
        if t.GetNetCode() != nc:
            continue
        if isinstance(t, pcbnew.PCB_VIA):
            q = pt(t.GetPosition())
            r = VIA_D / 2.0
            box = (q[0] - r, q[1] - r, q[0] + r, q[1] + r)
        else:
            a, c = pt(t.GetStart()), pt(t.GetEnd())
            hw = tomm(t.GetWidth()) / 2.0
            box = (min(a[0], c[0]) - hw, min(a[1], c[1]) - hw,
                   max(a[0], c[0]) + hw, max(a[1], c[1]) + hw)
        if (box[0] <= bb[2] and bb[0] <= box[2]
                and box[1] <= bb[3] and bb[1] <= box[3]):
            return True
    return False


def escape_pass(board, obst, pitch_max=1.35, min_pads=6, length=0.9,
                verbose=True):
    """Fan every fine-pitch pin out of its package's ring before area routing.

    An IC's pin ring is escape lanes wall to wall, and any trace that crosses
    above the ring caps every lane it passes.  Two real examples: the +6V0 tie
    across U302's top row sealed pin 7 in, and C304's VCC link boxed U301's FB
    pin into a closed pocket -- in both cases no later router could get the pin
    out at any width, on either layer.  Pulling every pin that still needs
    routing one lane-length into open board *first* makes that impossible: the
    stub is real copper, so a crossing trace has to go round it, and every
    later hop starts from the stub end because `connect_net` and `link` seed
    from the whole island, not from the pad.

    Runs on any package of `min_pads` or more at `pitch_max` or finer, which
    takes in the SOIC-8s and SOT23-6s as well as the QFNs and the LQFP100 --
    U301's FB pin is on a 1.27 mm pitch part.
    """
    split = set()
    for f in board.GetFootprints():
        for p in f.Pads():
            n = p.GetNetname()
            if not n or n == "GND" or n.startswith("unconnected-"):
                continue
            if n in split:
                continue
            if len(pad_nodes(board, n)) > 1 and not net_is_whole(board, n):
                split.add(n)
    made = 0
    for f in board.GetFootprints():
        pads = [p for p in f.Pads() if pad_copper_layers(p)]
        if len(pads) < min_pads:
            continue
        cs = [pt(p.GetPosition()) for p in pads]
        pitch = min((dist(a, b) for i, a in enumerate(cs) for b in cs[i + 1:]),
                    default=99)
        if pitch > pitch_max:
            continue
        c = pt(f.GetPosition())
        for p in pads:
            net = p.GetNetname()
            if net not in split:
                continue
            bb = pad_bbox(p)
            w, h = bb[2] - bb[0], bb[3] - bb[1]
            if abs(w - h) < 0.05:
                continue
            q = pt(p.GetPosition())
            if w > h:
                u = (math.copysign(1.0, (q[0] - c[0]) or 1.0), 0.0)
                tw, d0 = h, w / 2.0
            else:
                u = (0.0, math.copysign(1.0, (q[1] - c[1]) or 1.0))
                tw, d0 = w, h / 2.0
            tw = max(W_SIGNAL, round(min(tw, 0.30), 4))
            nc = p.GetNetCode()
            if _pad_has_copper(board, p, nc):
                continue          # already fanned out, or already routed
            end = None
            for L in (length, 0.7, 0.55, 0.4, 0.3):
                e = (round(q[0] + u[0] * (d0 + L), 3),
                     round(q[1] + u[1] * (d0 + L), 3))
                if seg_ok(obst, q, e, tw, nc, F):
                    end = e
                    break
            if end is None:
                continue
            add_track(board, q, end, tw, F, nc)
            obst.add_seg(q, end, tw / 2.0, F, nc)
            made += 1
    if verbose:
        print(f"   {made} fine-pitch pins fanned out of their pin ring")
    return made


def connect_net(board, obst, maze, netname, width=None, layers=(F, B),
                skip_nodes=(), verbose=True, min_width=None, **kw):
    """Route a net until every pad is in one island.

    Works on *islands*, and merges the closest pair of them each round rather
    than growing one tree from a fixed seed.  That matters: U301's FB divider
    has three islands, and the pin the seed happened to land on could not be
    reached from either resistor -- with pairwise merging the two resistors
    join first and the pair then reaches the pin.

    A pin its own decoupler link already reaches is recorded as connected, not
    re-routed (a 0.5 mm rail trace cannot even start on a 0.5 mm-pitch pad),
    and a hop only ever targets copper genuinely joined to what it grows from.
    Each hop is searched between the closest pair of points on the two
    islands, so the window stays small even on a board-spanning rail.
    """
    nc = netcode(board, netname)
    w = width if width is not None else net_width(netname)
    nodes = [g for g in pad_nodes(board, netname)
             if not any(r in skip_nodes for r, _ in g)]
    if len(nodes) < 2:
        return []
    isl, pad_root = island_geoms(board, netname)
    node_root = {}
    for bi, g in enumerate(nodes):
        for ref, p in g:
            r = pad_root.get(f"{ref}.{p.GetNumber()}")
            if r is not None:
                node_root[bi] = r
                break
    comps = {}
    for bi, r in node_root.items():
        c = comps.setdefault(r, dict(
            {l: list(isl[r][l]) for l in ROUTE_LAYERS},
            **{"pts": list(isl[r]["pts"]), "nodes": []}))
        c["nodes"].append(bi)
    keys = list(comps)
    if len(keys) < 2:
        return []

    ladder = [x for x in (w, 0.30, 0.20, W_SIGNAL)
              if x <= w and x >= (min_width or W_SIGNAL)] or [w]
    fails = []
    while len(keys) > 1:
        pairs = []
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                pa, pb, d = _closest(comps[a]["pts"], comps[b]["pts"])
                pairs.append((d, a, b, pa, pb))
        pairs.sort(key=lambda t: t[0])
        placed = False
        for _d, a, b, pa, pb in pairs:
            res, ww = None, ladder[0]
            for ww in ladder:
                res = maze.route(nc, [pa], [pb], ww, layers=layers,
                                 start_rects={l: comps[a][l]
                                              for l in ROUTE_LAYERS},
                                 goal_rects={l: comps[b][l]
                                             for l in ROUTE_LAYERS},
                                 **kw)
                if res is not None:
                    break
            if res is None:
                continue
            emit_result(board, obst, res, ww, nc)
            r = seg_rects(res, ww / 2.0)
            for l in ROUTE_LAYERS:
                comps[a][l] += comps[b][l] + r.get(l, [])
            comps[a]["pts"] += comps[b]["pts"] + [
                (round((q[0] + q[2]) / 2, 3), round((q[1] + q[3]) / 2, 3))
                for l in ROUTE_LAYERS for q in r.get(l, [])]
            comps[a]["nodes"] += comps[b]["nodes"]
            del comps[b]
            keys.remove(b)
            placed = True
            break
        if not placed:
            for k in keys[1:]:
                for bi in comps[k]["nodes"]:
                    ref, pd = nodes[bi][0]
                    fails.append(f"{ref}.{pd.GetNumber()}")
            break
    if fails and verbose:
        print(f"    ! {netname}: unrouted {sorted(set(fails))}")
    return fails


def _closest(pa, pb):
    """Closest pair of points between two lists (sampled if very large)."""
    A = pa if len(pa) <= 400 else pa[::max(1, len(pa) // 400)]
    B = pb if len(pb) <= 400 else pb[::max(1, len(pb) // 400)]
    best = (A[0], B[0], dist(A[0], B[0]))
    for x in A:
        for y in B:
            d = dist(x, y)
            if d < best[2]:
                best = (x, y, d)
    return best


def repair(board, nets, widths=None, tries=(dict(via_cost=45, margin=25),
                                            dict(via_cost=30, margin=45))):
    """Retry nets a stage could not finish, on a freshly built model.

    The incremental obstacle model a stage carries is rebuilt from the board
    here, which also re-derives every reservation and fan-out, so a net that
    lost a race against another net's copper gets a second, unprejudiced
    attempt.
    """
    out = []
    for net in nets:
        obst = Obstacles(board)
        obst.reserve_pin_escapes(board)
        maze = Maze(obst)
        w = (widths or {}).get(net, net_width(net))
        done = False
        for kw in tries:
            f = connect_net(board, obst, maze, net, width=w, verbose=False,
                            **kw)
            if not f:
                done = True
                break
        if not done:
            out.append(net)
    return out


def seg_ok(obst, a, b, width, nc, layer=F, samples=None):
    """True when a `width` trace from a to b clears all foreign copper."""
    r = width / 2.0 + CLEAR
    win = (min(obst.ij(a[0], a[1])[0], obst.ij(b[0], b[1])[0]) - 20,
           min(obst.ij(a[0], a[1])[1], obst.ij(b[0], b[1])[1]) - 20,
           max(obst.ij(a[0], a[1])[0], obst.ij(b[0], b[1])[0]) + 20,
           max(obst.ij(a[0], a[1])[1], obst.ij(b[0], b[1])[1]) + 20)
    m = obst.track_mask(win, nc, layer, r)
    n = samples or max(2, int(dist(a, b) / (GRID / 2)) + 1)
    for k in range(n + 1):
        t = k / n
        x = a[0] + (b[0] - a[0]) * t
        y = a[1] + (b[1] - a[1]) * t
        i, j = obst.ij(x, y)
        if m[i - win[0], j - win[1]]:
            return False
    return True


DETOUR = 3.0        # a route longer than this x the straight line is a hint
                    # that the layer it was pinned to was the wrong one


def pad_group(board, ref, num):
    out = []
    for f in board.GetFootprints():
        if f.GetReference() != ref:
            continue
        for p in f.Pads():
            if p.GetNumber() == num and pad_copper_layers(p):
                out.append((ref, p))
    if not out:
        raise KeyError(f"{ref}.{num}")
    return out


def group_min_dim(g):
    bs = [pad_bbox(p) for _r, p in g]
    bb = (min(b[0] for b in bs), min(b[1] for b in bs),
          max(b[2] for b in bs), max(b[3] for b in bs))
    return min(bb[2] - bb[0], bb[3] - bb[1])


ISLAND_NEAR = 8.0   # mm -- how much of an island counts as "this node"


def _near_box(bx, c, r):
    return (abs((bx[0] + bx[2]) / 2 - c[0]) <= r
            and abs((bx[1] + bx[3]) / 2 - c[1]) <= r)


def _with_island(ng, isl, pad_root, grp, radius=ISLAND_NEAR):
    """Widen a node's start/goal geometry to the island copper *near* it.

    Near, not all of it: GND's island is the whole board, and handing the
    router thousands of goal points makes its heuristic O(n) per expansion and
    its search window the entire outline.
    """
    for ref, p in grp:
        r = pad_root.get(f"{ref}.{p.GetNumber()}")
        if r is None:
            continue
        c = ng[0]
        return (c,
                {l: [b for b in isl[r][l] if _near_box(b, c, radius)]
                    + ng[1][l] for l in ROUTE_LAYERS},
                [q for q in isl[r]["pts"] if abs(q[0] - c[0]) <= radius
                 and abs(q[1] - c[1]) <= radius] + ng[2])
    return ng


def link(board, obst, maze, net, a, b, w, layers=(F,), margin=12,
         allow_layer_change=True, max_len=None, **kw):
    """Route one deliberate pad-to-pad hop.

    Tries the layer it was asked for first.  If that fails, or comes back more
    than DETOUR x the straight-line distance -- which is how a trunk ends up
    slicing diagonally across a whole block -- it re-tries with both layers
    and keeps whichever is shorter.
    """
    nc = netcode(board, net)
    ga, gb = pad_group(board, *a), pad_group(board, *b)
    width = max(W_SIGNAL, round(min(w, group_min_dim(ga),
                                    group_min_dim(gb)), 4))
    na, nb = node_geom(ga), node_geom(gb)
    direct = dist(na[0], nb[0])
    isl, pad_root = island_geoms(board, net)
    na = _with_island(na, isl, pad_root, ga)
    nb = _with_island(nb, isl, pad_root, gb)
    best = None
    ladder = [x for x in (width, 0.30, 0.20, W_SIGNAL) if x <= width] or [width]
    for lay in ([layers] + ([(F, B)] if allow_layer_change and
                            tuple(layers) != (F, B) else [])):
        for ww in ladder:
            res = None
            for m in (margin, margin * 2, margin * 4):
                res = maze.route(nc, na[2], nb[2], ww, layers=lay,
                                 start_rects=na[1], goal_rects=nb[1],
                                 margin=m, **kw)
                if res is not None:
                    break
            if res is None:
                continue
            ln = route_len(res)
            if best is None or ww > best[3] or (ww == best[3] and ln < best[1]):
                best = (res, ln, lay, ww)
            break
        if best and best[1] <= max(DETOUR * direct, direct + 8.0):
            break
    if best is None:
        return None, width, 0, direct
    if max_len is not None and best[1] > max_len:
        # a route this long is no longer the thing that was asked for: a
        # "Kelvin" return of 27 mm is just a wire, and it walls off a gate
        # corridor on the way.  Drop it rather than emit it.
        return None, width, 0, direct
    emit_result(board, obst, best[0], best[3], nc)
    return best[1], best[3], len(best[0][1]), direct


def unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(True)


def refill(board):
    """Refill every zone.  Connectivity first -- ZONE_FILLER's island removal
    reads it, and a stale graph drops copper that is really connected."""
    board.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    board.BuildConnectivity()
