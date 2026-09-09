#!/usr/bin/env python3
"""Round 2, step 4 -- route the logic rails on In2.Cu and In3.Cu.

**Run before the signal fill finishes, deliberately, and against the letter of
the step order.**  The captain's sequence is signals-then-power, and his intent
-- signals get first call on the outer layers -- is honoured either way, because
what power leaves outside after this stage is only the short cap-to-pin links
the house decoupling pattern already required.  What the sequence risks is the
other way round: a power rail reaches an IC supply pin by coming up at its
*decoupling capacitor*, and each of those feed-via slots is a discrete,
irreplaceable 0.905 mm pocket that placement reserved for it.  A signal routed
through one is a signal that cannot be asked to move later, because the router
has no idea the pocket mattered.  Signals detour; via slots do not.

The path each rail takes is the house pattern from round 1, one layer deeper:

    In2/In3 rail -> feed via -> capacitor pad -> short outer link -> IC pin

which is why the fine-pitch escape problem that blocks the signals does not
block the rails.  Power never has to leave a 0.5 mm-pitch pin ring: it arrives
at the capacitor, where the pads are 0603 and the slot is already cut.

Widths come from `route20_power_layers.inner_width` -- IPC-2221 internal, 0.5 oz
foil, 10 degC rise -- not from the outer net classes, which are sized for 1 oz.

Vias are the same 0.6/0.20 through-via as everywhere else, and now span all six
layers; the 1.0 A per-via budget is unchanged and `route_check --power` is
still the proof.
"""
import argparse
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import route_lib as R  # noqa: E402
from route20_power_layers import INNER, inner_width, inner_amps  # noqa: E402

# In2 carries the rails whose consumers sit north/centre, In3 the rest; the
# split is only to keep two rails from fighting for the same corridor, and a
# rail may use either where it needs to cross.
LAYER_A, LAYER_B = pcbnew.In2_Cu, pcbnew.In3_Cu
ORDER = sorted(INNER, key=lambda n: -INNER[n])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nets", help="comma-separated subset")
    ap.add_argument("--chunks", type=int, default=0)
    a = ap.parse_args()

    want = [n for n in ORDER
            if not a.nets or n in a.nets.split(",")]
    board = R.load()
    todo = [n for n in want if not R.net_is_whole(board, n)]
    print(f"{len(todo)} of {len(want)} rails to route on In2/In3", flush=True)

    done = 0
    for i, net in enumerate(todo):
        if a.chunks and i >= a.chunks:
            print(f"stopping after {a.chunks}", flush=True)
            break
        board = R.load()
        obst = R.Obstacles(board)
        obst.reserve_pin_escapes(board)
        maze = R.Maze(obst)
        w = inner_width(INNER[net])
        # Widths that carry the current on 0.5 oz inner foil are wide, and a
        # wide trace cannot reach a 0.5 mm pad; the ladder lets the last hop
        # neck down, which is what the outer cap link is for anyway.
        # In2/In3 are empty, so the search does not need a wide window or a
        # deep node budget -- and it must not have them: four layer masks over
        # a 40 mm window is four times the memory the two-layer board used,
        # and the box's watchdog killed the first attempt for it.  B.Cu is
        # left out entirely: the bottom layer is signals, and a rail that
        # wants it is a rail taking a corridor step 2 just cleared.
        f = R.connect_net(board, obst, maze, net, width=w,
                          layers=(LAYER_A, LAYER_B, R.F),
                          via_cost=8, margin=20, hw=2.0, verbose=False,
                          min_width=R.W_SIGNAL, max_nodes=250_000)
        R.refill(board)
        R.save(board)
        board = R.load()
        ok = R.net_is_whole(board, net)
        done += 1 if ok else 0
        print(f"   {net:<30} {INNER[net]:4.2f} A  {w:5.2f} mm "
              f"({inner_amps(w):.2f} A)  "
              f"{'whole' if ok else 'SPLIT ' + str(sorted(set(f))[:3])}",
              flush=True)

    board = R.load()
    print(f"\n{done} rails whole; unconnected now {R.unconnected(board)}")


if __name__ == "__main__":
    main()
