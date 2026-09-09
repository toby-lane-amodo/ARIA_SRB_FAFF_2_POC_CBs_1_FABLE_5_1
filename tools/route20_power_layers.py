#!/usr/bin/env python3
"""Round 2, step 2 -- take the movable power rails off the signal layers.

The captain: *"If needed, remove all power connections, and only route signals
for now."*  Not every power net can go, though, and the split is set by what
0.5 oz internal copper will carry, not by preference.

**Internal capacity is the whole argument.**  IPC-2221 for an *internal*
conductor is `I = 0.024 · dT^0.44 · A^0.725`, against 0.048 for an external
one -- half the constant -- and JLC's inner foil is 0.0152 mm against 0.035
outside.  At a 10 degC rise, the same rise the rest of this board is sized to,
that gives:

    0.5 mm -> 0.40 A     1.5 mm -> 0.88 A     3.0 mm -> 1.45 A
    1.0 mm -> 0.65 A     2.0 mm -> 1.08 A     4.0 mm -> 1.79 A

So a 3 A net would need roughly **8 mm of internal width**.  That settles it:

* **The 3 A nets stay outer.**  The 24 V entry chain, `V24_MOT`, the three
  motor phases and the three low-side source nets.  Outer 1 oz carries 2.39 A
  at 1.00 mm and they are already drawn and proved against the via budget;
  moving them would cost width the inner layers cannot give.
* **The switcher SW nodes stay outer too**, and would even if they carried
  microamps.  `U301-SW`, `U304-SW` and the two boot/output nodes beside them
  are the discontinuous-current nodes of the two buck regulators; the house
  rules keep them as small as possible and their datasheets keep them local.
  Threading a switching node through two vias into a buried layer is the
  opposite of that.
* **Everything else moves**: the logic rails.  1703 mm of outer copper, 23 %
  of every trace on the board, freed for signals -- and `+3V3` alone is 715 mm
  of it.

`--check` reports without touching the board.
"""
import argparse
import json
import math
import os
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import route_lib as R  # noqa: E402

CU_INNER_MM = 0.0152          # JLC 0.5 oz inner foil
MIL = 0.0254

# Rails that move to In2.Cu / In3.Cu, with their design current (A).
INNER = {
    "+3V3": 1.5,
    "+3V3A": 0.2,
    "+5V": 0.3,
    "+5VA": 0.3,
    "/power_rails/+6V0": 0.6,
    "/power_entry_24v/V24_LOGIC": 0.3,
    "/mcu/+3V3_USB": 0.3,
    "/mcu/+1V8_USB": 0.2,
    "/linear_encoder/+5V_ENC": 0.3,
    "/motor_drive/VENC": 0.3,
    "/motor_drive/VM_DRV": 0.1,
    "Net-(U302-SENSE)": 0.3,
    "Net-(U303-SENSE)": 0.3,
}

# Rails that stay on F.Cu / B.Cu, and why.
OUTER = {
    "/power_entry_24v/V24_IN": "3 A entry",
    "Net-(F201-Pad2)": "3 A entry",
    "Net-(Q201-D)": "3 A entry",
    "/power_entry_24v/V24_PROT": "3 A entry",
    "/power_entry_24v/V0_IN": "3 A entry return",
    "/power_entry_24v/+24V_SW": "3 A entry",
    "Net-(R1101-Pad2)": "3 A motor bus",
    "/motor_drive/V24_MOT": "3 A motor bus",
    "/motor_drive/MOTOR_U": "3 A phase, switching",
    "/motor_drive/MOTOR_V": "3 A phase, switching",
    "/motor_drive/MOTOR_W": "3 A phase, switching",
    "Net-(Q1102-S_3)": "3 A leg return",
    "Net-(Q1104-S_3)": "3 A leg return",
    "Net-(Q1106-S_3)": "3 A leg return",
    "Net-(U301-SW)": "buck switching node",
    "Net-(U304-SW)": "buck switching node",
    "Net-(C306-Pad1)": "buck output, local to the SW loop",
    "Net-(C320-Pad1)": "buck output, local to the SW loop",
}

IN_LAYERS = (pcbnew.In2_Cu, pcbnew.In3_Cu)


def inner_amps(w_mm, dT=10.0):
    """IPC-2221 internal conductor: what `w_mm` of 0.5 oz inner foil carries."""
    a_mil2 = (w_mm / MIL) * (CU_INNER_MM / MIL)
    return 0.024 * dT ** 0.44 * a_mil2 ** 0.725


def inner_width(amps, dT=10.0):
    """Narrowest internal width that carries `amps`, rounded up to 0.05 mm."""
    w = 0.5
    while inner_amps(w, dT) < amps and w < 12.0:
        w += 0.05
    return round(w, 2)


CHILD = '''
import json, sys
sys.path.insert(0, {here!r})
import pcbnew, route_lib as R
nets = set({nets})
b = pcbnew.LoadBoard(R.PCB)
outer = (pcbnew.F_Cu, pcbnew.B_Cu)
doomed = [t for t in b.GetTracks()
          if t.GetNetname() in nets
          and (isinstance(t, pcbnew.PCB_VIA) or t.GetLayer() in outer)]
for t in doomed:
    b.Remove(t)
print(json.dumps({{"removed": len(doomed)}}))
R.refill(b)
R.save(b)
'''


def rip(nets):
    src = CHILD.format(here=HERE, nets=json.dumps(sorted(nets)))
    out = subprocess.run([sys.executable, "-c", src], capture_output=True,
                         text=True)
    if out.returncode != 0:
        print(out.stdout, out.stderr, file=sys.stderr)
        raise SystemExit("rip failed")
    for line in out.stdout.splitlines():
        if line.strip().startswith("{"):
            return json.loads(line.strip())["removed"]
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    print("== internal capacity, 0.5 oz inner foil, IPC-2221, 10 degC rise")
    for w in (0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0):
        print(f"   {w:4.1f} mm -> {inner_amps(w):5.2f} A")

    print("\n== rails moving to In2.Cu / In3.Cu")
    board = R.load()
    held = 0.0
    for t in board.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            continue
        if t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu) \
                and t.GetNetname() in INNER:
            held += R.tomm(t.GetLength())
    for net, amps in sorted(INNER.items(), key=lambda kv: -kv[1]):
        print(f"   {net:<30} {amps:4.2f} A -> {inner_width(amps):5.2f} mm "
              f"internal")
    print(f"   {held:.0f} mm of outer copper freed")

    print("\n== rails staying on the signal layers")
    for net, why in OUTER.items():
        print(f"   {net:<30} {why}")

    if a.check:
        return
    n = rip(set(INNER))
    print(f"\nripped {n} items (all vias, and F.Cu/B.Cu traces) of "
          f"{len(INNER)} rails")
    board = R.load()
    print("unconnected now:", R.unconnected(board))


if __name__ == "__main__":
    main()
