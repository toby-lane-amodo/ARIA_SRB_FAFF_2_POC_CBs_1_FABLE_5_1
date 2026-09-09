# PCB board setup — `faff2_cbs1.kicad_pcb`

Layout phase, step 1: board infrastructure only. **No component placement** — placement is
the next task and is gated on captain review (house guideline G7). Everything imported from
the schematic sits in a holding grid off-board, grouped by sheet.

Built by `tools/gen_pcb_setup.py` (board) and `tools/gen_pcb_rules.py` (net classes + DRC).
From placement onwards the board file is the master; do not re-run the generator over it.

KiCad 9 only — `kicad-cli` 9.0.8, board format `20241229`. AGENTS.md has the hard rule.

---

## 1. Captain's rulings, and where each one landed

| Ruling | Where it lives |
|---|---|
| JLCPCB standard 4-layer, stackup verified from JLC's published table (`JLC04161H-7628`) | `(setup (stackup …))` in the board — §2, **superseded by §2a** |
| Round 2: six layers, SIG/GND/PWR/PWR/GND/SIG, power off the signal layers | `JLC06161H-7628` — §2a |
| House G1: outer layers carry **all** signals **and** power as traces; both inner layers unbroken GND | layer roles in the board — §2 |
| Via 0.6 mm pad / 0.20 mm drill, no-surcharge JLC drill, reaches the recommended 0.20 mm annulus | single via definition in every net class — §3 |
| **1.0 A per via**, *not* the old 3 A figure — JLC plates ~18 µm | §3, with the derivation |
| Trace/space 6/6 mil default, wider for power | `Default`/`Signal` net class 0.1524 mm — §6 |
| Dev board, size unimportant, generous but sensible; M3 corner holes, rounded corners | 210 × 130 mm, R2, 4 × M3 — §4 |
| Actuator connectors on one side; bench connectors on the other | §5 — the placement task executes it |

---

## 2a. Stackup, round 2 — JLCPCB `JLC06161H-7628` (6 layers)

**Superseded §2 on 2026-09-09.** The captain, reviewing routing round 1:
*"The PCB looks to be pretty un-routed still. Can you press on and keep going?
If needed, remove all power connections, and only route signals for now. Then,
we can add two additional internal layers and use these for routing power."*

That authorises six layers, arranged **SIG / GND / PWR / PWR / GND / SIG**:

| # | Layer | Role | Material | Thickness mm | Dk |
|---|---|---|---|---|---|
| — | F.Mask | — | solder mask | 0.010 | |
| L1 | **F.Cu** | `mixed` — signals | copper 1 oz | 0.0350 | |
| — | dielectric 1 | prepreg | NP-155F **7628** | **0.2104** | **4.40** |
| L2 | **In1.Cu** | `power` — GND Plane L2, unbroken | copper 0.5 oz | 0.0152 | |
| — | dielectric 2 | core | NP-155F Core | 0.4000 | 4.36 |
| L3 | **In2.Cu** | `power` — PWR Plane L3, power routing | copper 0.5 oz | 0.0152 | |
| — | dielectric 3 | prepreg | NP-155F 7628 | 0.2104 | 4.40 |
| L4 | **In3.Cu** | `power` — PWR Plane L4, power routing | copper 0.5 oz | 0.0152 | |
| — | dielectric 4 | core | NP-155F Core | 0.4000 | 4.36 |
| L5 | **In4.Cu** | `power` — GND Plane L5, unbroken | copper 0.5 oz | 0.0152 | |
| — | dielectric 5 | prepreg | NP-155F 7628 | 0.2104 | 4.40 |
| L6 | **B.Cu** | `mixed` — signals | copper 1 oz | 0.0350 | |
| — | B.Mask | — | solder mask | 0.010 | |

Total **1.582 mm** including mask — JLC's 1.6 mm class.

**House G1's substance is preserved, not waived.** G1 exists so that every
signal is referenced to a solid plane; here every outer-layer signal still
faces an unbroken ground plane 0.2104 mm below it, which is the same reference
distance the 4-layer build gave. What changes is that power no longer has to
share the signal layers, which is the whole point of the ruling.

**Why `-7628` of JLC's ten 6-layer options.** Its outer prepreg is *identical*
to the 4-layer board's — 7628 glass, 0.2104 mm, Dk 4.40 — so every impedance
number already derived and already routed carries over untouched: the USB pair
stays **0.30 mm on a 0.20 mm gap for 90.6 Ω**, `SYNC_TRIG` and the two U.FL
inputs stay **0.37 mm for 50 Ω**, and round 1's hand-drawn pair does not have
to be redrawn. The alternatives all move the reference plane closer and would
have forced both geometries to narrow: `-1080` at 0.0764 mm, `-3313` at
0.0994 mm, `-2116` at 0.1164/0.1270 mm.

Same copper weights and the same no-surcharge class as before: 1 oz outer,
0.5 oz inner. Materials Nan Ya NP-155F throughout.

*Source.* JLCPCB's published impedance-template data, `templateName`
`JLC06161H-7628`, 6-layer 1.6 mm, 1 oz outer / 0.5 oz inner. As in §2, JLC's
own impedance calculator is the arbiter before fab.

Applied by `tools/gen_pcb_stack6.py`. The second ground plane moved from
`In2.Cu` to `In4.Cu` with it.

---

## 2. Stackup — JLCPCB `JLC04161H-7628` (4 layers, superseded by §2a)

4-layer, 1.6 mm nominal, 1 oz outer / 0.5 oz inner. This is JLC's default no-surcharge
4-layer build.

| # | Layer | Role (KiCad class) | Material | Thickness mm | Dk | Df |
|---|---|---|---|---|---|---|
| — | F.Mask | — | solder mask | 0.010 | | |
| L1 | **F.Cu** | `mixed` — SIG + PWR Top | copper 1 oz | 0.0350 | | |
| — | dielectric 1 | prepreg | NP-155F 7628×1 | **0.2104** | **4.4** | 0.02 |
| L2 | **In1.Cu** | `power` — GND Plane L2 | copper 0.5 oz | 0.0152 | | |
| — | dielectric 2 | core | NP-155F core | 1.0650 | 4.43 | 0.02 |
| L3 | **In2.Cu** | `power` — GND Plane L3 | copper 0.5 oz | 0.0152 | | |
| — | dielectric 3 | prepreg | NP-155F 7628×1 | **0.2104** | **4.4** | 0.02 |
| L4 | **B.Cu** | `mixed` — SIG + PWR Bottom | copper 1 oz | 0.0350 | | |
| — | B.Mask | — | solder mask | 0.010 | | |

Total 1.6062 mm including mask; 1.5862 mm copper-to-copper, which is what JLC calls "1.6 mm".
Copper finish ENIG.

*Sources.* The geometry is JLCPCB's own impedance-template data (`templateName`
`JLC04161H-7628`: top copper 0.035, prepreg `7628*1` 0.21040, core 1.065 with 0.0152 inner
copper, symmetric) — it carries **no** dielectric constants. Dk/Df are the Nan Ya **NP-155F**
values JLC's templates call up. JLC's public impedance page prints a generic "4.6" for the
core; the NP-155F figure of 4.43 is used here instead, and it is electrically irrelevant
anyway — the core sits between two GND planes and no signal crosses it.

**Only the 0.2104 mm prepreg matters for impedance**, because L2/L3 are solid GND and every
trace is on an outer layer (G1/G4). Reference plane for F.Cu is In1.Cu; for B.Cu, In2.Cu.

### Impedance-relevant geometry (F.Cu over In1.Cu, H = 0.2104 mm, Dk 4.4, t = 0.035 mm)

| Target | Geometry | Modelled |
|---|---|---|
| 50 Ω single-ended microstrip | **W = 0.37 mm** | 50.0 Ω (Hammerstad–Jensen); IPC-2141 gives 0.35 mm |
| 90 Ω differential (USB 2.0 HS) | **W = 0.30 mm, S = 0.20 mm** | 90.6 Ω, i.e. +0.6 % — spec allows ±15 % |

These are closed-form estimates (Hammerstad–Jensen with thickness correction, cross-checked
against IPC-2141). **JLC's own impedance calculator is the arbiter before fab** — if the board
is ever ordered with impedance control, re-check there and adjust the net-class widths.

Nets that want them: `/mcu/USB_DM` + `/mcu/USB_DP` (90 Ω diff); `/mcu/SYNC_TRIG` to the SMA
`J902`, and `Net-(J503-In)` / `Net-(J504-In)` to the two U.FL jacks (50 Ω).

---

## 3. Via definition and the current budget

**One via for the whole board: 0.6 mm pad / 0.20 mm drill** → annular ring **0.20 mm**, which
is exactly JLC's *recommended* figure (their absolute minimum is 0.15 mm). 0.20 mm is a
no-surcharge drill; JLC's multilayer minimum is 0.15 mm.

**1.0 A per via.** Derivation, using JLC's published average hole plating of **18 µm**:

```
barrel copper area = π · 0.20 mm · 0.018 mm = 0.0113 mm²
equivalent 1 oz (35 µm) trace width = 0.0113 / 0.035 = 0.323 mm
IPC-2221 external, 10 °C rise, 0.323 mm  ->  1.05 A
```

So 1.0 A/via is the 10 °C-rise capacity with a hair of margin. **The old 3 A figure is wrong
by about 3×** — it assumes a much heavier barrel than JLC actually plates. Size every power
via count from 1.0 A: `n = ceil(I / 1.0)`, minimum 2 on any rail that changes layer.

Worked numbers for this board: 25 W peak at 24 V (`REQ-EL-03`) is 1.04 A → **2 vias**; motor
phases at an assumed 3 A peak → **3 vias**.

Trace capacity on 1 oz outer copper (IPC-2221 external), for reference at routing:

| Width mm | 10 °C rise | 20 °C rise |
|---|---|---|
| 0.152 (6 mil) | 0.61 A | 0.83 A |
| 0.30 | 1.00 A | 1.36 A |
| 0.50 (G3 power) | 1.45 A | 1.96 A |
| 1.00 (motor) | 2.39 A | 3.24 A |

No blind, buried or micro vias — JLC's standard 4-layer process is through-via only, and the
DRC constraints forbid them.

---

## 4. Board outline and mounting

**210 × 130 mm**, external corners radiused **R2** (house rule: always radius, 2 mm typical).
Origin on the A2 page at (30, 30); drill/place origin at the board's bottom-left corner.

*Why 210 mm wide.* The width is set by the actuator connector edge, not by area. Those nine
connectors are 149.2 mm of body; at ~5 mm apart that is 189 mm, plus 11 mm at each end to
clear the corner mounting holes' 5.5 mm keepouts → 211 mm. Area is not the constraint: 408
footprints total 6562 mm² of courtyard, so 27 300 mm² of board is ~24 % utilisation — generous,
as instructed, and it leaves real room for probe access and the block-to-block routing
corridors G7 wants.

*Mounting holes.* Four **M3 NPTH**, `Amodo:MountingHole_3.2mm_M3_NO-PAD_NPTH`, centres 6 mm in
from each edge — (6,6), (204,6), (204,124), (6,124) in board coordinates. That footprint
already carries a 5.5 mm keepout (no tracks, vias, pours or footprints), which is the
screw-head courtyard the house rules ask for. They are `BOARD_ONLY | EXCLUDE_FROM_BOM |
EXCLUDE_FROM_POS_FILES`, so schematic parity does not see them as extra parts.

**Non-plated, deliberately.** Plated holes tied to GND would ground the board to the bench
through every metal standoff, giving the precision load-cell AFE a multi-point chassis return.
NPTH keeps the ground reference single-point and under the design's control. Reopen this if
the board is ever put in a shielded enclosure that needs chassis bonding.

---

## 5. Edge plan

The captain's rule: peripherals live near what they cable to — *"all connectors to actuator
(motor, encoders, etc.) on one side"*. The two long edges split accordingly. **The placement
task executes this; nothing below is placed yet.**

**Actuator edge — the 210 mm edge (9 connectors, 149.2 mm of body):**

| Ref | Part | mm | What |
|---|---|---|---|
| `J1103` | Molex Micro-Fit 1×3 | 13.8 | motor phases U/V/W |
| `J1101` | 1×6 2.54 THT | 16.0 | rotary encoder / halls A |
| `J1102` | 1×6 2.54 THT | 16.0 | rotary encoder / halls B |
| `J601` | Hirose FH12-10S FPC | 11.0 | linear encoder (IKP11 read head) |
| `J602` | Samtec FTSH-105 2×5 | 8.4 | linear encoder, second interface |
| `J501` | Phoenix 1729076 8P 5 mm | 41.0 | load cell |
| `J701` | Push-in 4-way 3.5 mm | 15.1 | temp sensors A |
| `J702` | Push-in 4-way 3.5 mm | 15.1 | temp sensors B |
| `J903` | JST XH 4-way | 12.8 | limit switches |

**Bench edge — the opposite 210 mm edge (5 connectors, 68.6 mm of body, lots of slack):**

| Ref | Part | mm | What |
|---|---|---|---|
| `J201` | KYCON KPJX-4S | 16.0 | 24 V power entry (right-angle, latching) |
| `J1001` | USB-C receptacle | 13.0 | USB data (no PD, no bus power) |
| `J902` | SMA jack THT | 9.5 | sync/trigger |
| `J1003` | Samtec SHF-107 14-way | 17.2 | SWD + USART3 debug |
| `J1002` | TSW-105 2×5 THT | 13.0 | bring-up header (**DNP**) |

**Inboard, on the top face:** the three logic-analyser headers `J502`, `J603`, `J703`
(8510-4500PL, 20.5 × 9 mm each) sit inboard with clip clearance around them, near the blocks
they observe (load cell AFE, linear encoder, temp sense) rather than on an edge. Likewise the
44 Keystone test loops, 24 test pads and 9 dual test points stay with the nets they observe —
producer-owns-the-break, DEC-0007.

Keep the 24 V/motor power chain and the switching regulators away from the load-cell AFE
corner; the analog block wants the quiet end of the board, furthest from `J201`, the inductors
and the DRV8323.

---

## 6. Net classes and DRC constraints

All in `faff2_cbs1.kicad_pro` (net classes and DRC floors live in the project file, not the
board). Every class shares the one via definition, 0.6/0.20.

| Class | Track mm | Clearance mm | Applies to |
|---|---|---|---|
| `Default` | 0.1524 | 0.1524 | everything unmatched, incl. `GND` |
| `Motor` | 1.00 | 0.1524 | `MOTOR_U/V/W`, `V24_MOT`, `VM_DRV` |
| `RF50` | 0.37 | 0.1524 | `SYNC_TRIG`, the two U.FL inputs |
| `USB_HS` | 0.30 | 0.1524 | `USB_DM`/`USB_DP`; diff pair 0.30 / 0.20 |
| `Power` | 0.50 | 0.1524 | all rails: 24 V chain, +6V0, +5V, +5VA, +3V3, +3V3A, +3V3_USB, +1V8_USB, +5V_ENC, VENC |
| `Analog` | 0.25 | 0.1524 | bridge and RTD inputs, references, load-cell and temp terminal blocks, `ENC_VREF` |
| `Signal` | 0.1524 | 0.1524 | general signals |

**Every class keeps the 6 mil clearance, deliberately.** The first cut gave `Motor` and
`RF50` 0.30 mm and `Analog`/`Power` 0.20–0.25 mm, and DRC rejected it on the *pads*, before a
single track existed: at 0.5 mm pitch the LQFP100's pads sit 0.20 mm apart and the DRV8323 and
ADS1235 QFN pads 0.25 mm apart, so any class clearance above that fails on the package itself.
A class clearance has to be satisfiable by the finest-pitch pads carrying that class's nets.
**Generous spacing between these nets is routing discipline, not a class constraint** — keep
motor phases, the SW nodes and the analog sense chains well apart when routing, and widen
locally per G1c.

DRC constraints — G12 floors where the house is stricter than JLC, JLC's capability sheet
where it binds:

| Constraint | Value mm | Source |
|---|---|---|
| min track width | 0.15 | G12 floor (JLC allows 0.09 at 1 oz) |
| min clearance | 0.15 | G12 floor |
| min via diameter | 0.60 | the single via definition |
| min through-hole diameter | 0.20 | our via drill is the smallest hole on the board |
| min annular ring | 0.20 | JLC "recommended 0.20 or above" |
| min hole-to-hole | 0.45 | JLC PTH figure (their via-to-via allowance is 0.20) |
| min hole clearance | 0.25 | |
| copper to board edge | 0.30 | JLC needs ≥ 0.20; margin for the router |
| blind/buried and micro vias | forbidden | JLC standard 4-layer is through-via only |

Silkscreen clearance is left at 0 for now — silk tidy-up belongs to the placement gate, and
turning it on here would only report grazes inside library footprints that no placement
decision can fix.

---

## 7. Deliberately not done in this step

- **No placement.** G7 is a hard gate: the captain reviews placement before any routing, so
  placement is its own task. The 408 imported footprints sit in an off-board holding grid,
  grouped by schematic sheet with a caption per group on `Cmts.User`.
- **No GND plane zones.** Establishing the two inner-layer pours is *routing step 1* in the
  house process, and each routing step is opened and closed by the engineer. Defining them now
  would only mean stale fills through the whole placement round.
- **No routing, no zones, no test-point relocation.**
- **No `docs/DECISIONS.md` entry.** The task brief scoped this to one lightweight decisions
  file; the DEC-numbered register entries for these rulings are still owed.

## 8. DRC state, and two findings to escalate

`kicad-cli pcb drc --severity-all --schematic-parity`, KiCad 9.0.8:

**Schematic parity 0.** 408 footprints, every reference, value, footprint id and DNP flag
matching the schematic, every footprint carrying its `/sheet-uuid/symbol-uuid` path. The four
mounting holes are `BOARD_ONLY` and correctly invisible to parity.

**499 unconnected items** — the entire ratsnest. The board carries **0 tracks, 0 vias and 0
zones**, so by construction every net is unrouted; 499 is KiCad's own ratsnest count for that
state, and it is the expected residual until routing. (It is lower than a naive
pads-minus-nets figure because KiCad merges physically overlapping same-net pads — the QFN
exposed-pad arrays and dual test points — and counts spanning-tree edges.)

**77 violations, in four groups. None is a placement or wiring defect:**

| n | Type | What it is |
|---|---|---|
| 40 | `silk_overlap` | reference-designator text colliding between neighbours **in the holding grid**, at the 2.5 mm cell gap. Every item is a `Reference field`. Dissolves at placement |
| 18 | `text_height` | library footprints whose reference or user text is under the 0.8 mm rule (9 references, 9 footprint texts — `U501`, `D303`, `D901`, several test points) |
| 9 | `items_not_allowed` | **escalate** — see below, `Q201` |
| 6 | `lib_footprint_mismatch` | `H1`–`H4` differ from the library by the deliberate `BOARD_ONLY` attributes; `J201` and `J1001` differ only because **KiCad itself normalises an NPTH pad's `F&B.Cu` layer set to `*.Cu`** when the footprint lands on a 4-layer board. Reproduced with a bare load-and-save, no edits — it is KiCad's round-trip, not ours |
| 4 | `annular_width` | **escalate** — see below, `U501` |

An earlier cut had 19 `clearance` violations and 33 parity issues; both are fixed, not
suppressed — see §6 for the clearance cause, and the BOM-flag note below.

*The parity fix.* KiCad takes "exclude from BOM" and DNP from the **symbol**, not from the
library footprint. Several Amodo test-point and test-loop footprints carry `exclude_from_bom`
in the library while their symbols do not, which is 33 parity mismatches. The importer now
clears the footprint flag wherever the schematic does not set it — the schematic is the
authority.

### Escalation 1 — `Amodo:VQFN RHB 32 5x5 mm 0.5 pitch` EP thermal vias are under-annulused

`U501` (ADS1235) has four PTH thermal vias in its exposed pad at **0.5 mm pad / 0.25 mm
drill → 0.125 mm annular ring**. That is below JLC's *recommended* 0.20 mm and below their
**absolute minimum of 0.15 mm**. Via-in-pad on a QFN EP is the standing house exception (G9),
so the vias themselves are fine — the annulus is not. Either the library footprint's EP vias
grow to 0.6/0.20 like every other via on this board, or the captain accepts the deviation
with JLC. **Not waived here.**

### Escalation 2 — `Amodo:DMP4013LFG7` keepout excludes its own pads

`Q201`'s footprint contains a keepout zone with `pads not_allowed` that overlaps the
footprint's own pads 1, 4 and 5 — 9 violations. A keepout meant to hold *other* parts off
applies to the host footprint's pads too. This is a library defect, not a layout one; it will
follow `Q201` everywhere it is used until the house library is fixed.

Both are library issues in read-only `AmodoKiCadLib`, which is not ours to modify — they are
recorded here for the captain to fix upstream.

## 9. Bring-up-relevant notes

- Drill/place origin is the board's **bottom-left corner** — pick-and-place and drill files
  will be relative to it.
- Nine parts are DNP and carry the `FP_DNP` attribute on the board, so they are fitted with
  real footprints and land normally: `R506`, `R507`, `R521`, `D602`, `R708`, `R709`, `J1002`,
  `R1001`, `R1107`. Assembly variants handle population — never delete them.
- The three logic-analyser headers and the 44 test loops need clip and probe access with the
  board on its jig; that is a placement requirement, not a nicety.
