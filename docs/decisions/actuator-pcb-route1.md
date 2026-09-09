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

The commutation loop itself is unchanged from step 5 and is the tightest copper
on the board: each leg's phase node is drawn high-side source to low-side drain
on `F.Cu` at 1.00 mm, the low-side source runs to its own shunt at the same
width, and the phase leaves the node on `B.Cu` through a **three-via drop on
the node itself** (3 A peak ÷ 1.0 A per via, setup §3). Keeping the phase
output on the far layer keeps the whole discontinuous d*i*/d*t* inside the
bridge and leaves `F.Cu` free for the gate runs.

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
8. **Two pins were sealed in by earlier steps, and both are fixed by
   resequencing rather than by rerouting harder.** `+5V_ENC`'s feed to
   `J601.9` was drawn across the whole 10-way FPC fan — a wall on F.Cu 1.4 mm
   above the pad tops plus two vias parked in pins 6-9's lanes — and every
   RS-422 pair came out of step 5 with its `J601` end alone in its own island.
   `C1020`'s ground stitch does the same to `U1002` pins 25/26, the USB
   crystal pair: the pad's in-line escape is due south and that is exactly
   where the two pins have to run. Both are the R3-1 hazard the house rules
   name; §5 says what each one cost.

## 10. Tooling notes worth carrying forward

* **`pgrep -f 'python3 tools/route8_drv'` matches the shell that runs the
  `pgrep`.** A wait loop written that way never sees its job finish, because it
  keeps finding itself. Use `ps -eo cmd | grep '[r]oute8_drv'` — the bracket
  keeps the pattern from matching its own command line.
* **Redirect a long stage with `python3 -u`.** Without it Python block-buffers
  stdout and the progress file stays at zero bytes for the whole run, which
  looks exactly like a wedged job.
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
count says.

## 12. What is left, and what round 2 should look at first

This is round 1: the board is routed for review, not signed off. The residue
below is listed rather than hidden, and each line says why it is where it is.

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
