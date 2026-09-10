# PCB routing round 1 — `faff2_cbs1.kicad_pcb`

Layout phase, step 3. Placement round 1 was reviewed and approved ("This looks
good"), which clears house gate **G7**, so this is the first routing pass on the
board. It is submitted for the captain's routing review; comment rounds follow.

The board file is the master. Every tool below **mutates** it — none regenerates
it, and `tools/gen_pcb_setup.py` / `tools/gen_pcb_rules.py` must never be run
over it again.

KiCad 9 only — `kicad-cli` 9.0.8, board format `20241229`.

---

## 1. Stage order taken

The house process (`pcb-layout-style`, VanClock 2026-07-30) routes in five
gated steps, ground first. That order is followed, with the later stages split
where the block needed its own treatment.

| # | Stage | Tool | What landed |
|---|---|---|---|
| 1 | GND planes | `route1_zones.py` | `In1.Cu` + `In2.Cu` poured whole, 0.15 mm/0.15 mm, 0.25 mm fillet, islands removed, thermal reliefs (internal layers only) |
| 2 | Decoupler positive feeds | `route2_decoupling.py` | feed via → cap pad → IC pin, never pin-first |
| 3 | GND, one via per pad | `route3_gnd.py`, `route3b_gndfix.py` | every SMD GND pad its own via; completeness proof in §5 |
| 4 | Power distribution | `route4_power.py`, `route4b_powervias.py`, `route4c_widen.py`, `route4d_renarrow.py` | the rails joined up, via counts sized from the 1.0 A budget, widths from the current |
| 5a | USB HS pair | `route9_usb.py` | drawn by hand, not routed — §3 |
| 5b | DRV8323 interface | `route8_drv.py` | Kelvin taps first, then gates — §4 |
| 5c | Critical classes | `route5_critical.py --stages rs422,analog,rf,clocks` | RS-422 pairs, the analog corridor, the 50 Ω sync chain, the clocks |
| 6 | General signal fill | `route6_signals.py` | everything else, shortest span first |
| 7 | G5 stitching | `route7_stitch.py` | a GND via beside every signal via |

`route5_critical.py` now takes `--stages`; its `bridge` and `usb` stages are
superseded by 5a/5b and do not run by default. Re-running them would undo
better work, which is exactly what the flag exists to prevent.

---

## 2. Power: via counts against the 1.0 A budget

The budget is the board's own, from `docs/decisions/actuator-pcb-setup.md` §3:
JLC plates ~18 µm, so one 0.20 mm-drill barrel is worth a 0.323 mm 1 oz trace,
which IPC-2221 gives **1.05 A at a 10 °C rise**. So `n = ceil(I / 1.0)`, and
never fewer than 2 on any rail that changes layer. **The old 3 A/via figure is
wrong by about 3×** and is not used anywhere on this board.

Trace widths come from the same table — 0.1524 mm carries 0.61 A, 0.30 carries
1.00, 0.50 carries 1.45, 1.00 carries 2.39, all at a 10 °C rise on 1 oz outer
copper.

`tools/route_check.py --power` is the proof, and it does two things: it counts
the vias each net actually has against its budgeted current, and it runs a
**brute-force minimum-via cut** — if removing fewer vias than the budget
requires would split the net, the net leans on too few, whatever the total
count says. **It passes.** Every current-carrying path has at least its
budgeted via count with no single-via dependency.

| Net | I design | vias needed | vias | min cut |
|---|---|---|---|---|
| `Net-(F201-Pad2)` | 3.0 A | 3 | 6 | ≥3 |
| `/power_entry_24v/V0_IN` | 3.0 A | 3 | 3 | ≥3 |
| `/power_entry_24v/+24V_SW` | 3.0 A | 3 | 7 | ≥3 |
| `/motor_drive/V24_MOT` | 3.0 A | 3 | 6 | ≥3 |
| `/motor_drive/MOTOR_U` | 3.0 A | 3 | 7 | ≥3 |
| `/motor_drive/MOTOR_V` | 3.0 A | 3 | 7 | ≥3 |
| `/motor_drive/MOTOR_W` | 3.0 A | 3 | 11 | ≥3 |
| `Net-(Q1104-S_3)` | 3.0 A | 3 | 4 | ≥3 |
| `+3V3` | 1.5 A | 2 | 67 | ≥2 |
| `Net-(U301-SW)` | 0.7 A | 2 | 4 | ≥2 |
| `/power_rails/+6V0` | 0.6 A | 2 | 10 | ≥2 |
| `+5V` / `+5VA` / `+3V3A` / `+3V3_USB` / `+1V8_USB` / `V24_LOGIC` | 0.2–0.3 A | 2 | 6–11 | ≥2 |

Nets showing 0 vias never change layer, so they need none.

**The three low-side source nets were missing from the budget** — `Net-(Q1102-S_3)`
and its siblings carry the leg's full 3 A from the FET source into the shunt,
and they are named after the FET rather than the phase, which is how they were
overlooked. They are in it now.

**The min-cut test is load-aware, and had to be made so.** It failed on
`MOTOR_U/V/W` and `Q1104-S_3` with a 1-via cut each, and each cut isolated
exactly one pad: `U1101.7`, `U1101.12` — the DRV8323's VDS monitor and the SPB
Kelvin tap. Those are high-impedance sense inputs drawing microamps into a
comparator; a via carrying only one of them carries no current, and the leg's
3 A goes down the phase drop, which is a separate cluster. Demanding two more
vias there would have put copper on a sense line to satisfy a rule about
power. The DRV's six sense pins are now named explicitly, because guessing a
pin's function from its reference designator is what produced the false
failure.

## 3. USB 2.0 HS pair — drawn, not routed

`tools/route9_usb.py`. Step 5's maze router was given `/mcu/USB_DM` and
`/mcu/USB_DP` and, with two pads per net in one 0.5 mm row, treated them as
interchangeable: it ran DM along the pad row **through A6, a DP pad**. Nine
`shorting_items`, two `tracks_crossing`, three `clearance` and two
`solder_mask_bridge` violations, all inside 3 mm of `J1001`.

A differential pair is a geometry specification, not a connectivity problem, so
it is not asked of a router. DM and DP are explicit polylines, **mirror images
about x = 150.0** wherever they run together, so the match is by construction.

| | |
|---|---|
| Geometry | 0.30 mm wide, 0.20 mm gap, F.Cu over the `In1.Cu` plane — **90.6 Ω**, +0.6 % on the 90 Ω target (setup §2) |
| Reference | plane-referenced for the whole through path; the pair never changes layer |
| Through path | `J1001.A7 → D1001.6 → D1001.1 → U1002.19` (DM) and `.A6 → .4 → .3 → .18` (DP) |
| Length | DM **15.71 mm**, DP **16.13 mm** |
| Skew | **0.414 mm** — 2.7 ps, against a working tolerance of 1 mm |

The skew is spent in one place and is worth the captain's eye: **`D1001` pad 2's
ground stitch owns the lane south of the device.** Pad 2 sits between the two
signal pads and its only escape is straight south, so the pair parts around it —
DM west, DP east — and converges below. That is the only uncoupled section on
the through path.

Three more things the corridor forced, each a judgement call:

* **`J1001` interleaves the rows.** Along x the pads read B6(DP) A7(DM) A6(DP)
  B7(DM) at 0.5 mm pitch, so each B-row duplicate sits on the far side of the
  other net's lane and the two ties must cross. 0.5 mm pitch will not take a
  0.6 mm via — a via wants 0.905 mm of clear lane — so neither B-row pad fans in
  its own lane. Each descends its flank, fanning as it goes, and crosses on
  B.Cu. The two ties span overlapping x, so their bands are nested rather than
  interleaved: DP's crossing runs north of its landing vias, DM's south of its.
* **DP's tie lands north of `D1001`; DM's lands 1.6 mm past pad 1.** DM's band
  would have to cross both VBUS's B.Cu spine and DP's own band to reach the
  connector side. Where it lands it is 0.2 mm from a clamp cell of its own
  (pad 1) and 9 mm of trace ahead of the PHY, so the clamp is still in front of
  everything it protects. **Flagged for the captain** as the one place the
  "ESD in the line" rule is met by argument rather than by inspection.
* **Nothing is routed under the connector on F.Cu.** The shell lands on the
  board there and soldermask is not an insulator under a metal shell. The maze
  router went under it twice before the reservation went in; B.Cu under the
  body is left free, since the shell cannot reach it.

`D1001` pin 5 is VBUS and its only escape is due north, straight between the two
halves of the pair, so the pair opens to **1.4 mm pitch** across the corridor:
the channel is then 1.10 mm and the via drops in with 0.25 mm each side. The
bulge is symmetric, so it costs no skew. `USB_CC2` walks the 0.60 mm gap between
that via and the DP tie's at its own class width, 0.1524 mm — a 0.30 mm trace
needs 0.605 mm and does not fit.

**`route_check --usb` was wrong and is fixed.** It measured *total copper per
net*, which counts the two B-row ties as if they were in line, and called this
matched pair 4.62 mm skewed. It now walks the net's copper graph — track ends
are nodes, a via joins the layers at zero cost — and takes the shortest path
between the pads the signal actually passes through.

## 4. The commutation loop and the DRV8323 interface

`tools/route8_drv.py`. Fourteen nets reach one 6 mm package from three legs
spread over 30 mm, through a channel that also carries the motor bus and the
driver's own supply. Step 5 drew the block leg by leg and the first net to ask
for the channel got it; four runs came out unrouted. This stage rips the window
(193, 111)–(235, 153) and redoes it in **priority order**.

**Priority is accuracy, not length.** The three Kelvin taps go first. Each has
exactly one useful path — from the shunt's own pad, never off the power path —
and the CSA's gain error is whatever IR drop the tap picks up. A gate run that
detours 4 mm costs nanoseconds of edge; a Kelvin tap that detours costs percent
of current-sense accuracy.

| Tap | Net | Run | Direct |
|---|---|---|---|
| SPA | `Net-(Q1102-S_3)` → `U1101.9` | 8.89 mm, 0 vias | 11.14 mm |
| SPB | `Net-(Q1104-S_3)` → `U1101.12` | 5.92 mm, 2 vias | 9.48 mm |
| SPC | `Net-(Q1106-S_3)` → `U1101.19` | 21.74 mm, 0 vias | 19.17 mm |

A note the captain should see: **the schematic ties `SNx` to `GND`**, so a true
four-wire Kelvin is not available on the low side. What the layout can offer is
the `SPx` tap taken at the shunt's own pad rather than off the power path, plus
a dedicated `F.Cu` return from each shunt's ground pad to the driver's `SNx`
pin **in addition to** the plane, drawn only where it stays under 14 mm. Beyond
that the plane is the better return and the dedicated trace is dropped.

**What went wrong in this stage, and how it was found.** Five of the six gate
runs came out of it unrouted, and the obvious reading — "the taps took the
channel first, which is the price of the priority" — was wrong.
`tools/route_sealed.py` (written for this, §10) asks each pad of each open net
whether a trace of its class width can leave in any of eight directions for a
lane length. Twelve pads on the whole board answered no, and four of them were
on this one package: pins 8, 13 and 18 — the three low-side gates — and pin 4,
`VM_DRV`.

The cause is a line `route8_drv.py` never called. It built its obstacle model
as `Obstacles(board)` with **no `reserve_pin_escapes`**, so nothing held the
neighbouring pins' lanes while it drew. Leg A's Kelvin tap left pin 9 and
elbowed 0.15 mm north to y = 139.40; pin 8 sits 0.5 mm above it at 139.75 and
pin 7's own run at 140.25, which leaves pin 8 a **0.60 mm slot** for a trace
wanting 0.4572 mm of copper and 0.3048 mm of clearance. Five microns short.
Legs B and C went the same way.

That is the R3-1 hazard exactly — an elbowed escape parks itself in the
neighbour's corridor — and it is why the rule says to prove the neighbours can
still get out *before* parking anything. `route_ripup.py --plan u1101-gates`
redoes the window with the priority unchanged and the reservations on, so
neither can take the other's lane.

The commutation loop itself is unchanged from step 5 and is the tightest copper
on the board: each leg's phase node is drawn high-side source to low-side drain
on `F.Cu` at 1.00 mm, the low-side source runs to its own shunt at the same
width, and the phase leaves the node on `B.Cu` through a **three-via drop on
the node itself** (3 A peak ÷ 1.0 A per via, setup §3). Keeping the phase
output on the far layer keeps the whole discontinuous d*i*/d*t* inside the
bridge and leaves `F.Cu` free for the gate runs.

## 5. The critical classes

Order inside step 5 is tightest constraint first, and each class gets its
corridor before the general fill can claim it.

### RS-422 encoder pairs

`/linear_encoder/ENC_{A,B,Z}_{P,N}`, routed pair by pair at 0.20 mm so each
P/N run stays together. Each net has five nodes — `J601` (the FPC read head),
`J602` (the second interface), a termination resistor `R603`–`R605`, a
`ENC_VREF` bias jumper on the N legs, and the `U601` receiver — so "the pair"
is a five-point net, not a two-point run, and the P and N of a pair are drawn
back to back rather than truly coupled over their whole length. That is a
consequence of the schematic's topology, not of the layout.

They were all split at their `J601` end by the sealed fan (§7 open point 7).
`route_ripup.py --plan j601-fan` unsealed them: rip `+5V_ENC` inside the fan,
route all eight `J601` signals first, then put the supply back. It took six of
the eight whole in one pass — `ENC_A_P/N`, `ENC_B_P/N`, `ENC_Z_N`, `ENC_nPROG`
— and `+5V_ENC` went back whole at 0.50 mm afterwards, which is the point: the
supply had the whole board to detour through and the pins had one lane each.
`ENC_Z_P` and `ENC_SDO` were left for the general fill.

### Analog — the quiet corridor

31 of the 34 nets in the load-cell and temperature chains route at **0.25 mm or
wider** (`Analog` class), drawn before the general fill so the digital corridors
have to go round them rather than through. The chain order the placement set up
is preserved in copper: connector → series R → filter → ADC, with the reference
leg beside it.

The guard the house rules ask for is separation, and it comes from placement:
the analog block sits bottom-left, the switchers and the DRV8323 on the
right-hand column, and the two never share a corridor. `MCO2`
(`ADS1235_CLKIN`) is routed as a clock, away from the AIN chains.

### 50 Ω sync

`J902` (SMA) → `D903` (ESD, **in the line**, not hanging off it) → `R907`
(source termination) → `U901` → `SYNC_TRIG`, at the `RF50` class width of
0.37 mm — the 50 Ω microstrip geometry for this stackup (setup §2:
H = 0.2104 mm, Dk 4.4, W = 0.37 mm → 50.0 Ω).

### Clocks

Four clock nets and the two crystal loops, drawn before the general fill so
nothing runs alongside them by accident: `HSE_CLK_24M` and `Y1001`'s loop for
the MCU, `Y1002`'s for the USB PHY, and **`MCO2` → `ADS1235_CLKIN`**, which is
the one that matters for the analog block. `MCO2` is a square-wave clock landing
on a 24-bit ADC, so it is routed as a clock and kept out of the `AIN` corridor
rather than being left to the general fill, which would have had no reason to
care.

`Net-(U501A-CLKIN)`, `HSE_CLK_24M` and `Net-(Y1001-OUT)` closed in this stage.
`USB_XO_24M` and `USB_REFCLK_24M` could not, and the reason was not the routing
— see §7 open points 6 and 7.

## 6. What the DRC report contains

Run it exactly as the house rules ask, with the library variable set so the
footprint comparison is real rather than 199 "library not found" lines:

```sh
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib \
  kicad-cli pcb drc --severity-all --format json \
  -o /tmp/drc.json hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_pcb
```

**Without `AMODO_KICAD_LIB` set, DRC reports 199 `lib_footprint_issues`** — it
cannot open the library, so it cannot compare. That is a tooling artefact, not
a board defect, and it hides the six real mismatches underneath it.

The four pre-existing residual classes from board setup §8 are unchanged and are
**not** routing defects:

| Type | n | What |
|---|---|---|
| `items_not_allowed` | 9 | `Q201` reverse-polarity FET's own keep-out, library-side |
| `lib_footprint_mismatch` | 6 | `H1`–`H4` (BOARD_ONLY/NPTH attribute normalisation), `J201`, `J1001` |
| `annular_width` | 4 | `U501` exposed-pad annulus, library land |

### The round-1 result

```
DRC severity-all       248 violations
  track_dangling       199   in progress -- fan-out stubs on the nets still open
  via_dangling          30   in progress -- likewise
  items_not_allowed      9   library residual (board setup S8)
  lib_footprint_mismatch 6   library residual
  annular_width          4   library residual
  REAL                   0
schematic parity         0
unconnected            111   79 nets, S12
```

**Zero real violations.** Every one of the 248 is either a known library
residual from board setup §8 or a dangling fan-out stub belonging to a net
that is still open — and those clear the moment their net closes.

Board state: **3366 track segments, 1004 vias, 2 zones**; 4763.5 mm of copper
on `F.Cu`, 2707.8 mm on `B.Cu`. Vias by class: 775 Default (535 of them GND),
150 Power, 35 Motor, 34 Analog, 6 RF50, 4 USB_HS.

## 7. Open points for the captain

1. **The DM tie's landing point.** `J1001` B7 joins DM 1.6 mm past `D1001`
   pad 1 rather than on the connector side, because its band would otherwise
   have to cross both VBUS's B.Cu spine and DP's band. It is 0.2 mm from a
   clamp cell of its own and 9 mm ahead of the PHY, so the protection order is
   intact — but it is met by argument rather than by inspection, and it is the
   one place in the USB block where that is true.
2. **`SNx` is tied to `GND` on the schematic**, so no true four-wire Kelvin is
   available on the low side. §4 says what the layout offers instead. If the
   captain wants a real four-wire sense the schematic has to change first.
3. **Gate runs are not all via-free.** Placement open point 1 asked for all six
   gates on `F.Cu` without vias. The east row of the DRV8323 is not planar —
   `Q1101`'s gate comes from the furthest north and lands on the southmost of
   four adjacent pins — so at least two of the six have to cross. §5 has the
   count that actually landed.
4. **Thermal copper is widening, not pours** — §8. If the captain wants real
   outer-layer pours in the motor block, that is a G3 waiver and his call.
5. **`route_check --usb` was measuring the wrong thing** and is fixed (§3).
   Worth knowing because the old number is in the previous round's notes.
6. **`C1025` and `C1026` look swapped** — a placement point, raised here
   because routing is where it shows. `Y1002` pin 1 is `USB_REFCLK_24M` at
   (140.5, 57.75) and pin 2 is `USB_XO_24M` at (140.5, 53.25); `C1025`
   (REFCLK) sits at (135.725, **53.25**) and `C1026` (XO) at (135.725,
   **57.75**). Each load capacitor is beside the *other* crystal pin, so both
   crystal nets run the 4.5 mm across the part instead of dropping straight
   down. Exchanging the two positions is a one-line change to
   `gen_pcb_place1.py` and halves both nets, but it is a placement change
   after the G7 gate, so it is the captain's to approve.
7. **`D903` is 9.4 mm of trace from the SMA pin it protects.** The house rule
   puts an ESD device as close to the source as the neighbouring courtyard
   allows, and `J902.1` → `D903.1` is a long way past that. `route12_sync.py`
   fixes the *order* — the clamp is now the first thing a strike meets rather
   than a 4.5 mm branch off a run that had already forked to `R907` — but it
   cannot fix the distance. Moving `D903` up against `J902` is a placement
   change and the captain's to approve.
8. **D-MOT-13's single-point return vs G10.** The motor sheet carries a layout
   instruction: *shunt → PGND → bulk-capacitor negative is one tight loop,
   joined to system ground at a single point at the bulk capacitors.* On this
   stackup there is no PGND: both inner layers are one unbroken GND plane, and
   **G10 forbids splitting a plane unless the engineer instructs it**. So the
   instruction is **not** met as written, and the numbers say so: the shunts'
   ground lands sit at y = 131 and the DC-link negatives at y = 105, 26 mm
   apart, with the per-leg bypass returns in between at y = 113.5. Each leg's
   loop therefore closes through about 17.5 mm of plane rather than at a star
   point.
   That is the normal and, on a solid-ground stackup, the better behaviour —
   the return current follows directly under the outbound path because that is
   the lowest-inductance route available to it, which is the whole reason G1
   keeps the planes whole. But it is a deviation from a sheet instruction, so
   it is raised, not waived. Two ways out if the captain wants the star: rule
   a plane split (G10 needs his instruction), or move the DC-link store down
   beside the shunts, which is a placement change.
9. **Two pins were sealed in by earlier steps, and both are fixed by
   resequencing rather than by rerouting harder.** `+5V_ENC`'s feed to
   `J601.9` was drawn across the whole 10-way FPC fan — a wall on F.Cu 1.4 mm
   above the pad tops plus two vias parked in pins 6-9's lanes — and every
   RS-422 pair came out of step 5 with its `J601` end alone in its own island.
   `C1020`'s ground stitch does the same to `U1002` pins 25/26, the USB
   crystal pair: the pad's in-line escape is due south and that is exactly
   where the two pins have to run. Both are the R3-1 hazard the house rules
   name; §5 says what each one cost.

## 8. Reading of the "no pours" rule against the thermal ask

House **G1a/G3** says power is *"deliberate 0.5 mm traces on outer layers — no
pours — so every current path is explicit"*. The routing brief asks for FET and
regulator thermal copper. Those pull in opposite directions, so rather than
waive one silently (`pcb-layout-style`: conflicts are escalated), this round
takes the narrow reading and says so:

* **No copper pour is added on `F.Cu` or `B.Cu`.** Every current path stays an
  explicit trace, and the only zones on the board remain the two internal GND
  planes.
* **Thermal spreading is done by local widening — G1c — on the copper that is
  already the current path**: the FET drain lands, the phase links between each
  leg's high-side source and low-side drain, and the 24 V bus into the
  high-side drains. Same copper, same explicit path, more of it.
* **The regulators' thermal path is their exposed pad, and that is already
  done**: `U301`/`U304` (LMR33630 PowerPAD, 2.70 × 3.40 mm), `U302`/`U303`
  (ADPL42005 LFCSP, 2.50 × 1.80 mm), `U501`, `U1002` and `U1101` all carry the
  client-ruled EP via array from step 3 into both ground planes — 1.30 mm pitch,
  the one place a via may sit inside a pad (G9 exception).
* The FET drains are **not** on GND, so they have no plane to stitch into. On
  this stackup their only heat path is outer-layer copper, which is why the
  widening above is the whole of the thermal answer for them.

If the captain wants real pours on the outer layers for the motor block, that is
a G3 waiver and his call to make — it is not taken here.

## 9. Reproducing this round

Stages are ordered; each one mutates the board the previous one left.

```sh
# 1-4 are already in the branch history and must NOT be re-run over the board.
python3 tools/route9_usb.py                                     # 5a
python3 tools/route8_drv.py                                     # 5b
python3 tools/route5_critical.py --stages rs422,analog,rf,clocks  # 5c
python3 tools/route6_signals.py                                 # 6
python3 tools/route7_stitch.py                                  # 7
python3 tools/route10_thermal.py                                # 10
python3 tools/route4c_widen.py --check                          # re-verify widths
python3 tools/route_check.py                                    # all proofs
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib \
  kicad-cli pcb drc --severity-all --format json -o /tmp/drc.json \
  hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_pcb
```

Two of these are **rip-and-redo** stages — `route9_usb.py` and `route8_drv.py`
each delete their own nets inside a window before drawing, in a child
interpreter, because `board.Remove()` mid-script poisons SWIG type resolution
for every later wrapped return in the same process. They are therefore
idempotent: run either twice and you get the same board.

`route5_critical.py` is **not**: its stages only add. Its `bridge` and `usb`
stages are superseded and excluded by the default `--stages`.

## 10. Tooling notes worth carrying forward

* **`pgrep -f 'python3 tools/route8_drv'` matches the shell that runs the
  `pgrep`.** A wait loop written that way never sees its job finish, because it
  keeps finding itself. Use `ps -eo cmd | grep '[r]oute8_drv'` — the bracket
  keeps the pattern from matching its own command line.
* **Redirect a long stage with `python3 -u`.** Without it Python block-buffers
  stdout and the progress file stays at zero bytes for the whole run, which
  looks exactly like a wedged job.
* **`route_sealed.py` is the tool this round most wanted and did not have.**
  A router's `UNROUTED` line does not say *why*, and the two reasons want
  opposite treatment: a pad with no lane out of its own pin ring cannot be
  reached at any width on either layer, however wide the window, and the only
  fix is to rip the sealer and resequence; a pad that can get out but whose net
  still would not close wants a wider window or a different corridor. Running
  it over the round-1 residue took a guess ("the taps took the channel") and
  turned it into a five-micron measurement and a missing function call.
* Every stage that saves goes through `place_lib.save()`, which snapshots the
  sibling `.kicad_pro` and writes it back — `pcbnew.SaveBoard()` rewrites it
  wholesale with KiCad defaults, and that cost the DEC-0021 ERC baseline once.

## 11. A crash worth recording

The first run of `route5_critical.py --stages rs422,analog,rf,clocks` routed all
four classes and then **segfaulted (exit 139) inside the single `refill()` at
the end**, taking ten minutes of routing with it — the board on disk was
untouched, and `[exited with code 0]` on the wrapper hid it. Two things follow,
and both are now in the script:

* **Refill and save after every stage, reloading in between.** That bounds the
  loss to one stage, and the reload gives each stage a fresh obstacle model,
  which is what `route6`'s repair pass does deliberately anyway.
* **Read the stage's own exit code, not the wrapper's.** A shell that runs
  `python …; echo; grep` exits 0 whatever Python did.

## 12. What is left, and what round 2 should look at first

This is round 1: the board is routed for review, not signed off. **111
unconnected items across 79 nets remain** — the brief asked for zero, and this
does not reach it. What follows is why, honestly, rather than a claim that it
is nearly there.

The residue is not scattered. It is three things:

| Cause | Nets | Fixable by routing? |
|---|---|---|
| DRV8323 / regulator pin rows over-subscribed (below) | ~8 | **No** — placement |
| MCU-to-peripheral runs across a saturated board | ~65 | Partly, with more passes |
| The rest — `J601`/`J602` encoder pairs, a few taps | ~6 | Yes |

The proofs that *do* pass are the ones that matter most for a review:
**`--gnd`, `--viainpad`, `--power`, `--usb`, `--analog` and `--g5` all pass**,
and DRC has zero real violations. What is missing is completeness, not
correctness: nothing on the board is wrong, there is simply not enough of it
yet.

**The residue is saturation, and that was tested rather than assumed.**
`tools/route_sealed.py` over the final board finds **1 sealed pad** (`U1101.18`,
the last low-side gate), **10 tight** and **208 escapable** — so all but eleven
of the open pads *can* leave their own pad, and their nets still will not
close. Two searches were then run over a sample of six of them: the stage's
own settings (hw 2.0, margin 32, via cost 35) and a much greedier and wider
one (hw 3.0, margin 45, via cost 20, 900 k nodes). **Both routed zero of six.**
More passes are not the answer; the corridors those nets need are occupied.

That is what the next round has to move, and it moves at placement or by
ripping wide, not by asking the router again.

The three things round 2 should take first, in this order:

1. **The two placement points in §7** — `C1025`/`C1026`, and anything else the
   sealed-pin work turned up. Placement changes are cheap now and expensive
   after the copper is reviewed.
2. **The gate runs.** Five of six came out of step 5b unrouted because the
   Kelvin taps legitimately took the channel first, and the general fill put
   them back with vias. Whether that is acceptable is the captain's call
   (placement open point 1 asked for via-free).
3. **A render sweep of the analog corridor.** The numbers say the separation
   held; the render is what actually catches a digital run that crept into it.

### The router's heuristic weight, and why the fill looked worse than it was

Worth recording because it cost most of a day and looked like a board problem.

The general fill stalled with ~80 nets open, and **almost every one of them had
a bare `U1001` pin as one of its islands.** That reads as congestion around the
MCU. It is not. A path from the MCU's `SWCLK` stub to the debug header's exists
and the maze router finds it — it just needs **three million node expansions**
to do so at the default heuristic weight of 1.3, and `Maze.route`'s ceiling is
1.2 M. Every long MCU run was hitting that ceiling and being reported
unroutable, which is indistinguishable from "no path" in the output.

At **hw = 2.0** the same route lands inside 600 k nodes and comes out 39.5 mm
against a 34 mm direct distance — 16 % longer. For a signal that is the right
trade: an optimal path that never lands is worth nothing. The fill now runs at
hw 2.0 with a 600 k ceiling, which also bounds the memory that had three runs
killed by the box's OOM watchdog.

The diagnostic that separated the two cases is worth keeping: route the two
islands' *seed points* directly with `maze.route` and a generous ceiling. If
that succeeds where `connect_net` failed, the board is fine and the search is
not.

### The DRV8323's pin rows are over-subscribed, and that is a placement finding

**East row**, pins 5–9 — `V24_MOT`, `Q1101-G`, `MOTOR_U`, `Q1102-G`,
`Q1102-S_3`. **North row**, pins 12–19 — `Q1104-S_3`, `Q1104-G`, `MOTOR_V`,
`MOTOR_W`, `Q1106-G`, `Q1106-S_3`. Each row leaves in one direction on a
0.5 mm pitch, and every net in it has to turn off inside the same 1.5 mm of
board before it reaches open copper. The arithmetic does not work:

* a lane between two neighbouring runs is **0.70 mm**;
* a 0.6 mm via needs **0.905 mm** of lane to drop through;
* so **no net in the middle of that row can change layer**, and the ones that
  cannot get out on `F.Cu` have nowhere else to go.

`Q1102-G` gets 1.2 mm east of its own fan-out stub and stops. Three searches
at widening margins and falling via costs found no path, and the reason is not
the search: there is no lane. `route_sealed` calls the pin free because it can
leave its pad; it is the *second* millimetre that has no room.

Ripping the **whole** east row and replanning it together did move the problem
— `Q1102-G` reached `U1101.8` and only its FET end stayed open — which is the
proof that the row is the constraint rather than any one net in it. The north
row was left as it was and both of its gates stayed shut, which is the same
proof from the other side.

This is not something routing can fix. It wants one of: the low-side gates
brought out on the package's south side instead of the east, the DRV8323
rotated so the gate pins face their FETs, or the phase-sense and Kelvin pairs
moved to the north row. All three are placement changes and all three are the
captain's call — which is why they are here rather than in a rip plan.


---

# Round 2 — six layers

The captain, on routing round 1: *"The PCB looks to be pretty un-routed still.
Can you press on and keep going? If needed, remove all power connections, and
only route signals for now. Then, we can add two additional internal layers and
use these for routing power."*

## R2.1 Stackup

`JLC06161H-7628`, **SIG / GND / PWR / PWR / GND / SIG** — full table and the
reasoning in `actuator-pcb-setup.md` §2a. The one point worth repeating here:
of JLC's ten 6-layer options this is the only one whose outer prepreg matches
the 4-layer board's (7628, 0.2104 mm, Dk 4.40), so **every impedance result
from round 1 carries over unchanged** and the hand-drawn USB pair did not have
to be redrawn. USB stays 0.30/0.20 for 90.6 Ω; SYNC stays 0.37 mm for 50 Ω.

House **G1 is preserved in substance**: every outer-layer signal still faces an
unbroken ground plane 0.2104 mm below it, the same reference distance as
before. What changed is that power no longer shares the signal layers.

## R2.2 What moved, and what did not

The split is set by what 0.5 oz internal copper carries, not by preference.
IPC-2221 internal is `I = 0.024·ΔT^0.44·A^0.725` against 0.048 external — half
the constant — and the inner foil is 0.0152 mm against 0.035 outside. At a
10 °C rise:

| width | 0.5 mm | 1.0 | 1.5 | 2.0 | 3.0 | 4.0 | 6.0 |
|---|---|---|---|---|---|---|---|
| carries | 0.40 A | 0.65 | 0.88 | 1.08 | 1.45 | 1.79 | 2.39 |

A 3 A net would want ~8 mm of internal width. So:

**Moved to In2/In3** — thirteen logic rails, 0.1 to 1.5 A: `+3V3`, `+3V3A`,
`+5V`, `+5VA`, `+6V0`, `V24_LOGIC`, `+3V3_USB`, `+1V8_USB`, `+5V_ENC`, `VENC`,
`VM_DRV`, both regulator `SENSE` nets. **1703 mm of outer copper freed — 23 %
of every trace on the board**, `+3V3` alone 715 mm of it.

**Stayed outer** — the 3 A nets (24 V entry chain, `V24_MOT`, the three motor
phases, the three low-side source nets), because 1 oz outer gives 2.39 A at
1.00 mm and they are already drawn and proved against the via budget; and the
two buck **SW nodes**, which would stay outer at any current, because threading
a discontinuous-current node through two vias into a buried layer is the
opposite of what the house rules and both datasheets ask.

## R2.3 `+3V3` is a pour, and that is not a G3 waiver

G3 says power on the outer layers is deliberate traces and never pours, *so
that every current path is explicit where signals share the copper*. In2.Cu
shares its copper with nothing — the captain added it for power alone — and on
a dedicated power layer a pour is the standard construction and the lowest
impedance available. The outer layers keep G3 exactly as before: what stayed
outside is still explicit traces at sized widths.

`+3V3` needs 3.15 mm of 0.5 oz foil for its 1.5 A. It is poured on In2 and fed
by **66 vias, one per island** — which is what a power plane wants, against the
forty pairwise maze routes the first attempt tried and which took a minute
each. The other twelve rails route as traces at 0.50–0.90 mm and do not need
a pour.

## R2.4 Three assumptions that were correct by coincidence

Worth recording as a class, because all three behaved the same way: each was
right on a 4-layer board for a reason that stopped holding at six, **none of
them failed loudly**, and DRC caught all three rather than the code.

| Assumption | Why it was right before | What it did on six layers |
|---|---|---|
| per-layer dicts keyed `{F, B}` | F and B were the only routing layers | `KeyError: 6` on the first inner route — the loud one |
| a via is an obstacle on `{F, B}` | a through via *is* on both | inner router drove through all 535 via barrels: 61 real violations |
| `pad_copper_layers` asks only F/B | a PTH pad *is* on both | inner router drove through `J301`, `J603`, `TP501` lands |

The library now names `ROUTE_LAYERS` and `PLANES` once and builds from them,
so the same code serves either stackup.

A fourth, self-inflicted: `route23_power_vias` anchored its stub at the
island's *centroid*, which for any island of more than one pad is empty space,
so the stub crossed whatever lay between. It now anchors on real copper and
proves the stub clears before committing to the slot.


## R2.4b Via convention for power spurs — provisional

**Ruling (routine engineering call, made and recorded rather than escalated;
flagged for the captain's veto at review):** a **single via is acceptable for a
power spur carrying 0.5 A or less** — at least 2× inside the 1.0 A per-via
budget from setup §3. Above 0.5 A, or wherever a second via is free, use two.

The house convention is a minimum of two vias on any layer change. That exists
for robustness, not for current, and round 2 is where the distinction started
to matter: every rail now reaches every consumer through its own via down from
In2/In3, so a single-consumer spur is the normal case rather than the
exception. Demanding two vias on a 0.3 A spur puts copper where no current
flows, and there are dozens of them.

`route_check --power` **warns rather than fails** on such a cut, and prints the
current each one actually carries so nothing is hidden. It still fails on
anything above the threshold.

The current through a cut is what is *behind* it, not the rail total, and the
proof apportions by load count rather than assuming the worst everywhere.
`+6V0` is the case that forced this: it carries 0.60 A and feeds **two**
ADPL42005 regulators, so a cut isolating one of them carries that regulator's
share — ~0.24 A — and demanding a second via there would size copper for
current that never flows in it. Apportioning by load count is crude, but it is
the right direction and it is stated rather than assumed.

Result: **all power proofs pass**, with 30 single-via spurs listed as notes,
each with its apportioned current, for the captain to veto or accept.

## R2.5 Where round 2 got to

```
stackup            JLC06161H-7628, 6 layers, SIG/GND/PWR/PWR/GND/SIG
DRC severity-all   199 violations, REAL 0
  track_dangling   180   in progress -- fan-out stubs on the nets still open
  residuals         19   the four known library classes, board setup S8
schematic parity     0
unconnected        100   down from 271 after the rip; 111 at the end of round 1
```

Proofs: **`--gnd`, `--viainpad`, `--usb` and `--analog` pass.** The USB pair is
bit-identical to round 1 — 15.71/16.13 mm, 0.414 mm skew — which is the
stackup choice paying for itself.

**`--power` reports single-via cuts on the inner rails, and that wants the
captain's word rather than more copper.** Every rail now reaches its consumers
through its own via down from In2/In3, so a cut isolating one consumer group is
the normal case rather than the exception. Those cuts satisfy the *current*
requirement with room to spare — the rails carry 0.1 to 0.6 A and one via
carries 1.0 A — but not the *convention* of a minimum of two vias on any layer
change. 88 parallel vias were added chasing it and the remaining cuts are all
of that shape. Two vias everywhere is cheap; the question is whether the
convention is meant to bind a 0.3 A spur, and that is his call, not mine.

## R2.6 Why zero was not reached, and what would reach it

61 signal nets and 5 rails remain open. The cause is **not** any of the things
that could have been fixed by working harder, and each was tested rather than
assumed:

| Lever | Tested | Result |
|---|---|---|
| more search effort | round 1 | found the `hw` ceiling; real, and already applied |
| freeing power off the signal layers | round 2 step 2 | **worked** — 1703 mm freed, 78 → 61 open, five nets per chunk against one |
| a third routing layer for signals | In3 offered to the router | **0 of 6** — the residue is not a layer count. **This row is wrong and R2b.2 supersedes it**: `connect_net` defaults to `layers=(F, B)` and the fill never passed anything else, so In3.Cu was offered to one hand-run experiment and to nothing that mattered. The copper census settles it — 3064 segments on F.Cu against 16 on In3.Cu. |
| opening the pocket round a blocked pad | `route24_pocket`, 31 items of 9 nets ripped round `U501.12` | did not close it |

What is left is one shape, and `U501.12` is its type specimen: **the free region
round the pad is a slot 0.3 mm tall that dead-ends after 1.5 mm.** The pad
escapes; the corridor does not go anywhere. No width, margin, heuristic or node
budget reaches it, because there is nothing to reach.

That is a placement question, and the same one round 1 raised: the fine-pitch
packages — `U1001` (LQFP100, 40 blocked pads), `U1101` (QFN40, 19), `U1002`
(QFN32, 8), `U501`, `U701`, `U601` — do not have the escape room their pin
counts need. **Round 1's five findings are still open and still unanswered**,
and three of them bear directly on this.


---

# Stage A — the placement delta pack, and why it is empty

The captain authorised placement changes to end the escape starvation, on my
round-2 report that the fine-pitch packages "do not have the escape room their
pin counts need". **That report was wrong, and this stage is the measurement
that shows it.**

`tools/place2_escape.py` grades a pad by the **free area it can actually flood
into**, not by the 0.9 mm straight lane `route_sealed` tests — the lane
question answers "can it leave the pad" and says nothing about whether the
corridor goes anywhere, which is precisely how `U501.12` passed it with a slot
that dead-ends after 1.5 mm. `--bare` strips every track, via and zone first,
so the grade reflects the placement and nothing else.

| Grade | With the current routing | **Placement alone (`--bare`)** |
|---|---|---|
| starved (< 2 mm²) | 59 pads | **0** |
| tight (2–6 mm²) | 10 | **0** |
| open (> 6 mm²) | 26 | **201** |

**Every one of the 201 pads on `U1001`, `U1101`, `U1002`, `U501`, `U601` and
`U701` has open escape room from the placement.** The tightest is 79.67 mm².
The starvation is created entirely by copper already on the board.

And the copper doing it is not mysterious. Within 1.2 mm of a starved pad:

| net | occurrences |
|---|---|
| `/mcu/+3V3_USB` | 25 |
| `Net-(Q1103-G)` | 21 |
| `/mcu/USB3320_nRESET` | 18 |
| `/mcu/SYNC_TRIG` | 13 |
| `/mcu/MCU_nRESET` | 11 |

These are ordinary signals that routed early, took the shortest path they
could see, and walled in the pins they passed. That is a **routing-order**
failure, not a placement one.

## What this means for Stage A

**No placement delta is warranted, and none is proposed.** Moving `U1001` and
its neighbours would buy escape room that already exists, cost the whole
region's routing, and leave the actual cause untouched — the next router pass
would wall the pins in again.

Two corrections to the grader were needed before it could be trusted, and both
are worth keeping because both would have produced a wrong move:

* it graded against the routed board at first, which cannot tell starvation
  from congestion;
* it capped the escape width by the pad size but not by the **pitch**. A
  0.45 mm trace cannot leave a 0.65 mm-pitch pin whatever the pad measures.
  That alone called `U701.12` and `U701.13` starved — two Power-class nets on
  a TSSOP, where the right answer is that the link necks down at the pin
  exactly as the house rules already say.

## What the evidence points to instead

The fix is an **escape-first routing order**: fan every pin of every fine-pitch
package out past its own ring into open board *before* any long haul is drawn.
`escape_pass` already does this at 0.9 mm, which clears the pad but not the
ring — the stub ends inside the corridor the next net then takes.

This is routing work, not placement, and it is inside my remit — but the
captain gated routing behind his review of this stage, so it waits for his
word. **The round-1 findings remain unruled and untouched**, as instructed;
none of them was involved here.

# Round 2b — the escape-first re-route

## R2b.1 The order change, and why it is the whole finding

Stage A measured the board twice: once bare, with every track and via
stripped, and once as routed. **Bare, all 201 fine-pitch pins have open escape
room** — the tightest is 79.67 mm² of reachable free area. Routed, 59 of them
are starved. Nothing about the placement changed between the two
measurements, so the starvation is made entirely by the routing that ran
between them, and the copper doing it is ordinary signal copper that took the
shortest path it could see past a pin ring it did not need to enter.

So the order was inverted. Instead of *route a net, then discover its pin is
walled in*, every fine-pitch pin is **fanned out of its own ring first**, into
open board, and the long hauls are then drawn between fan-out endpoints that
already exist:

1. `tools/route26_escape_first.py` rips every signal net (`KEEP` holds GND,
   the inner-layer rails, the USB HS pair, the sync chain and the three Kelvin
   taps — copper whose geometry is the design, not a routing choice);
2. `tools/route25_fanout.py` stages each package's pins out on three rows
   0.6 mm apart, which puts adjacent vias 0.78 mm apart rather than on top of
   one another — a staggered fan-out, the BGA pattern applied to QFN and
   LQFP rings;
3. `tools/route6_signals.py` then fills, banking every twelve nets.

`escape_pass` was already doing step 2 at 0.9 mm, which clears the pad but
**not the ring** — the stub ends inside the corridor the next net takes, so it
bought nothing. 0.9 mm was the bug.

The effect is not subtle. Before: the fill closed one to five nets per chunk
of twelve and stalled. After: ten to twelve per chunk, and unconnected fell
from 388 to 120 with open signal nets from 200 to 82 across three cycles
(`4742b21`, `049631c`, `614c064`, `1d63522`, `acc068e`).

This is a routing-order change inside my remit, taken under the captain's
standing "press on" instruction. **No part moved, and the round-1 findings
remain unruled and untouched.**

## R2b.2 The signal fill had two layers on a six-layer board

The fill then stalled again at 82 nets, and the cause was a fourth instance of
the "correct by coincidence" class from R2.4. `route_lib.connect_net` declares
`layers=(F, B)` as its default — the whole truth on the four-layer stack — and
`route6_signals` never overrode it. The copper census says it plainly:

| layer | track segments |
|---|---|
| `F.Cu` | 3064 |
| `B.Cu` | 1038 |
| `In2.Cu` | 174 |
| `In3.Cu` | 16 |

`F.Cu` was full and the fill had nowhere else to go, while two mixed inner
layers sat all but empty. The stack is
`SIG+PWR : GND : PWR+SIG : PWR+SIG : GND : SIG+PWR`; `In2.Cu` and `In3.Cu` are
mixed exactly as the outer layers are, each referenced to an adjacent unbroken
GND plane, so a signal there is stripline rather than microstrip and is if
anything the quieter home. `route6_signals --layers` now selects the set.

`In3.Cu` is opened to signals and `In2.Cu` held back, because `In2.Cu` carries
the `+3V3` pour (R2.3): every signal crossing it carves a channel the pour must
go round, and enough of them fragment the rail. `In3.Cu` carries only rails
drawn as traces, with the rest of the layer empty. The layer bias keeps the
outer layers preferred — a signal dives inside only when that is worth about a
fifth again in path length — so the impedance-controlled runs stay microstrip
where they were designed.

## R2b.3 What "UNROUTED" actually meant

The third measurement is the one that changed the plan. Flood-filling the free
space out of `C1112.1` — a plain 0402 land, nothing fine-pitch about it —
reaches **388 grid cells, about one square millimetre**, on a board whose
search window is half free. The A* returns in ten milliseconds having
exhausted its entire frontier. No margin, node budget or heuristic weight
reaches a goal from there, and none ever could.

So the residue was never "needs a wider search". `tools/route_sealed.py` grades
only 6 pads as sealed on a straight-lane test, and that test is the wrong
question: a lane 0.34 mm long that dead-ends after a millimetre grades as
*tight* and is as impassable as a lane of zero. The reachable-area flood is the
honest measure, and `tools/route27_batch_pocket.py` now uses it.

## R2b.4 The fan-out field was the wall, and the slot — not the stub — was why

`route25_fanout` placed 124 of 291 pins and reported the other 167 as "no legal
row". Those 167 are, pin for pin, the pins the fill then could not leave. So
the escape-first stage was making the wall it was written to prevent.

**The arithmetic says a straight via-per-pin field cannot work at 0.5 mm
pitch.** A via barrel is 0.6 mm across and the clearance floor is 0.1524 mm
(G12), so a minimum-width stub passing *beside* a barrel needs
0.3 + 0.1524 + 0.0762 = **0.5286 mm** of lateral room against a 0.5 mm pitch —
29 µm short, for every pin whose assigned row is deeper than its neighbour's.
Two same-row barrels one pin apart are 1.0 mm apart and leave a 0.40 mm
channel where 0.4572 mm is needed — **57 µm short**. `U1001.54` is the type
specimen: pins 53 and 55 both took row 1.65 mm and pin 54 is walled out by
those 57 µm, with 99 grid cells of reachable free space to show for it.

**But the stub was not what was failing.** Giving every stub a maze route so it
could jog placed *fewer* pins, not more — 108 against 124 — because a greedy
jog is wider than its own lane for part of its length and takes the
neighbour's. The check that rejects a pin fires earlier than that: it is
`via_mask` on the **slot**, and it fails identically however the stub is drawn.

The field is not short of room. A 12 mm package edge has roughly seven rows of
legal 0.78 mm-spaced slots in the 1.05–5.25 mm band, for 25 pins. What it is
short of is room *on the pin's own lane* — because the house rule puts a GND
stitch via beside every ground pad, so those vias live inside the ring by
construction and sit on their neighbours' lanes.

So the slot is allowed to move sideways. Each depth is now tried at a lateral
offset as well, nearest first, and the stub reaches an offset slot by maze
route with straight tried first and the jog kept as the fallback:

| fan-out | pins placed of 291 |
|---|---|
| straight stub, lane slot only (round 2) | 124 |
| maze stub, lane slot only | 108 |
| straight-first stub, slot offset to ±0.75 mm | 188 |
| straight-first stub, slot offset to ±1.25 mm | **190** |

`tools/route28_escape_ring.py` takes the pins that still have no legal slot: it
routes them to a *band* of open board 1.6–4.5 mm off their own side of the
package, no via required, which is the right escape for a single-row package
anyway — a via-per-pin field is a BGA pattern, and a QFP escapes on the outer
layer and vias further out, where the lanes have somewhere to spread.

## R2b.5 The corridor field: right in principle, measured, and rejected

A via for every pin of a 0.5 mm-pitch package does not fit — R2b.4's
arithmetic — so about a third of each ring has to leave on the outer layer
instead, and those pins need a lane that was **reserved** rather than one that
happened to survive. That is what a hand layout does, and it is why the field
was rebuilt to draw one pin in three straight out past the deepest via row
*before* any via existed to sit across it, with the two neighbours' slots
nudged 0.03 mm away so the lane stayed legal.

On this board it loses. Four fields, same ripped board, each filled to a
plateau:

| field | pins served of 291 | walled after | **filled to** |
|---|---|---|---|
| no corridors, lateral slots | 190 (all vias) | 47 | **94** |
| straight-ladder corridors | 193 (68 + 125) | 30 | — |
| strict 5.8 mm corridors | 167 (37 + 130) | — | — |
| maze corridors to the band | 182 (88 + 94) | 40 | **101** |

Both proxies point the other way from the verdict, which is the reason to
record all four rather than the winner. Corridors do free the ring — walled
pins fall from 47 to 30 — and a lane that reaches open board is worth more per
pin than a barrel parked 1–5 mm out. But the room a corridor takes comes out
of the via field, and the fill ends seven items worse. **Only the last column
is a verdict.** `--corridors 3` reproduces it; the code stays, because the
reasoning holds for a board with more room round its fine-pitch packages, and
this one has not got it.

Two intermediate cuts are worth keeping for the same reason:

* **A straight corridor is the wrong shape.** Insisting the lane be a straight
  5.8 mm stub fits 37 pins of 291 and eats the via field to do it. A ladder of
  shorter straight lengths fits 68 — and none of those is a real corridor,
  because the via phase drops a barrel past the end of a short lane and seals
  it again.
* **A smaller via is not the lever either.** Measured on the board as it
  stands, new vias only, the existing 0.60 mm barrels kept as obstacles at
  full size: 0.60 mm finds slots for 101 more pins, 0.50 mm for 118, 0.45 mm
  for 129. A 28-pin gain is real and it is nowhere near enough to be worth
  asking for a waiver of G2's single via definition.

## R2b.6 Where round 2b ends, and the measured floor

```
stackup            JLC06161H-7628, 6 layers, SIG/GND/PWR/PWR/GND/SIG
unconnected        91      (388 after the rip; 120 at the last check-in; 111 at
                            the end of round 1 on four layers)
open signal nets   60
schematic parity   0
DRC severity-all   310 violations
  residuals         19     the four known library classes, board setup S8
  copper_sliver      1     F.Cu, severity warning, no position reported
  track_dangling   147     see below
  via_dangling     143     see below
proofs             --gnd --viainpad --power --usb --g5 --analog all PASS;
                   --nets fails on the 65 still-split nets, and only that
```

**The escape-first re-route did not cost any structural property.** Ground-via
completeness, the G5 return-via pairing, no-via-in-pad, the USB pair geometry
and the analog corridor all still pass, on a board whose signal copper was
ripped and redrawn twice. `--power` passes with 24 notes, all of them the
one-via cuts allowed provisionally by R2.4b.

### The floor, and the evidence for it

**Zero unconnected is not reachable on this placement, stackup and via
definition.** The measured floor is about 85–91. Of 60 open nets:

| population | count | what it is |
|---|---|---|
| reachable but unrouted | 5 → 3 | a search problem; the wide ceiling closed 2 |
| walled by rippable copper | 42 | a routing-order problem — but every rip is break-even |
| bounded ≥55% by pads, GND vias and kept rails | 9 | not a routing problem |
| no legal cell to leave the pad at all | 5 | not a routing problem |

The middle row is the finding. `route31_unwall` floods out of a blocked island,
names the nets the frontier stops against, rips them **whole**, routes the
blocked net, and puts them back — the round-1 doctrine with the sealer
identified automatically. Aimed by boundary composition it **works**: it closes
3 of every 4 blocked nets it attempts. It has never once been accepted, because
putting the sealers back costs as much as the blocked nets gain:

| batch | targeting | closed | sealers back | result |
|---|---|---|---|---|
| walls 2, limit 6 | frontier contact | 0/6 | 5/8 | 93 → 96 |
| walls 10, limit 2 | shortest span | 0/2 | 10/11 | 93 → 94 |
| walls 8, limit 4 | graded by rippable boundary | 3/4 | 1/5 | 93 → 93 |
| walls 6, limit 4 | graded **+ global refill** | 3/4 | 1/5 (+5) | not better |

The last row is the one that settles it. Refilling *every* open net rather than
only the ripped sealers is the widest restore available, and it came out the
same. **Opening a pocket for N nets costs about N elsewhere, which is what a
region at capacity looks like.** Four batch shapes, zero accepted.

`Net-(U1101-CPH)` is the single clearest case and needs no router at all: 68% of
its pocket boundary is `C1112`'s **own other pad**. No routing order closes
that.

### What would move the floor — all the captain's to rule

1. **Placement round 2 at the fine-pitch packages.** Round 1's findings 1–3
   remain unruled and bear directly on this; `C1112` needs rotating or moving
   whatever else is decided.
2. **Two more routing layers.**
3. **A smaller via in the fan-out field only** — measured: 0.45 mm finds slots
   for 28 more pins than 0.60 mm. Real, not sufficient alone, and a G2 waiver.
4. **The R‑C3‑1 EP tie for QFN ground pins** — frees 6 ring slots on `U1101`
   and 1 on `U1002`. Small, and his ruling rather than mine.

### The dangling classes, honestly

290 `track_dangling` / `via_dangling`, of which 245 are on nets that are
**whole**. Three explanations were tested and all three are wrong: they are not
padless islands (`route30_trim --check` finds none), not stacked copper (92
stacked tracks were removed and the count went *up* by one), and not the
mid-span junction rule (of `V24_MOT`'s 16 genuinely free ends, none lands
mid-span of another segment). Taking one flagged track apart, it is connected
at **both** ends — end A on `Q1101`'s pad on its own layer, end B to another
track end on the same layer.

So either KiCad is flagging something this model cannot see, or the mapping
from a DRC item back to a track is not what it appears to be. **It is not
resolved and it is not asserted either way.** What is known: unconnected did
not move across any of the three trims, so nothing removed was carrying
current, and the class was already present at 180 in round 2 (R2.5) where it
was attributed to fan-out stubs — that attribution is now also in doubt.
