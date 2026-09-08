# PCB placement, round 1 — `faff2_cbs1.kicad_pcb`

Layout phase, step 2. **Placement only — no routing.** The board carries 0 tracks, 0 vias and
0 zones, exactly as board setup left it; G7 is a hard gate and the captain reviews placement
before any track is drawn.

Built by `tools/gen_pcb_place1.py` (positions + orientations) and `tools/tidy_silk.py`
(reference-designator and label placement). Verified by `tools/check_place.py` and
`tools/place_report.py`. The board file is the master — those scripts mutate it, they do not
regenerate it, and `tools/gen_pcb_setup.py` must never be run over it again.

KiCad 9 only — `kicad-cli` 9.0.8, board format `20241229`.

---

## 1. Verification state

| Check | Result |
|---|---|
| `kicad-cli pcb drc --severity-all --schematic-parity` | **19 violations, all four pre-existing library issues from board setup §8** |
| schematic parity | **0** |
| unconnected items | 499 — the whole ratsnest, the expected pre-routing residual |
| real-courtyard overlaps (`check_place.py`) | **0** across all 412 footprints |
| courtyard off-board / inside an M3 keep-out | **0** |
| 0.25 mm placement grid | **0** off-grid |
| silkscreen (`silk_overlap`, `silk_over_copper`, `silk_edge_clearance`, `text_height`) | **0** |

The 19 residuals are unchanged from board setup and are **not** placement defects:

* 9 `items_not_allowed` — `Q201`'s `Amodo:DMP4013LFG7` carries a keepout that excludes its own
  pads. Library defect, escalation 2 of the setup file.
* 4 `annular_width` — `U501`'s VQFN EP thermal vias are 0.5/0.25 (0.125 mm annulus). Library
  defect, escalation 1 of the setup file.
* 6 `lib_footprint_mismatch` — `H1`–`H4`'s deliberate `BOARD_ONLY` attributes, and KiCad's own
  normalisation of the NPTH pad layer set on `J201`/`J1001`.

Silkscreen went from 149 overlaps at first placement to zero. Every reference designator and
every test-point name was re-seated by `tidy_silk.py` against real pad, silk-graphic, text and
board-edge extents, and 0.7 mm library text was lifted to the 0.8 mm house floor **on the
board** — the Amodo library is read-only.

---

## 2. Region map

Board is 210 × 130 mm, page coordinates x 30…240, y 30…160. Actuator edge is the **bottom**
(y = 160), bench edge the **top** (y = 30), executing §5 of `actuator-pcb-setup.md`.

```
  y 30 ── BENCH EDGE ──  J1002    J902    J1003          J1001        J201
        ┌───────────────────────────────────────────┬──────────────────────┐
   45   │  ui_io: LEDs, buttons,   │ mcu debug R's  │  power_entry_24v     │
   60   │  SMA buffer, J901        │ U1003 SRAM     │  F201 L201 Q201 D201 │
        │                          ├────────────────┤  C204 bulk           │
   70   │        SW901/902         │  U1001 LQFP100 │──────────────────────┤
        │                          │  + decoupling  │  power_rails         │
   85   │            nvm (U801)    │  Y1001 HSE     │  U301+L301 -> +6V0   │
        │                          │  USB: U1002    │  U302 +5V  U303 +5VA │
   98   ├──────────┬───────┬───────┤  Y1002 U1004   │  U304+L302 -> +3V3   │
  105   │ loadcell │ temp  │ linear│  D1001 J1001   ├──────────────────────┤
        │ J502     │ J703  │ J603  │                │  motor_drive         │
  120   │ U501     │ U701  │ U601  │  ui_io limits  │  C1101/C1102 DC link │
        │ ADS1235  │ADS1120│AM26LV │  U902 SW903/4  │  bridge W | V | U    │
  140   │ input    │ input │ term  │  J903 feeds    │  U1101 DRV8323S      │
  155   │ filters  │filters│       │                │  encoder R's         │
        └──────────┴───────┴───────┴────────────────┴──────────────────────┘
  y 160 ── ACTUATOR EDGE ──  J501  J701 J702  J601 J602  J903  J1101 J1102 J1103
```

Both edges are executed exactly as the setup file's tables specify. Connector front faces are
lined up: bench edge on y = 31.5, actuator edge on y = 158.5.

**Separation achieved.** The load-cell AFE (`U501`, x ≈ 66, y ≈ 127) is 160 mm from `J201`,
150 mm from `L301`/`L302` and 145 mm from `U1101` — diagonally opposite corners, which is the
maximum this outline allows. `temp_sense` sits beside it. The two switching regulators and the
whole 24 V/motor chain occupy the right-hand column only.

---

## 3. The judgement calls

### P1-01 — The MCU is at 0° because the `.ioc` pin map puts it there

`U1001` at 0° lands, edge by edge: **left** → ADS1235 SPI (pins 77–82, 87), `ADS1120_nCS`,
EEPROM I²C, buttons, SWCLK/SWO — all of which live west and south-west; **right** → the six
TIM1 PWM outputs, the three motor current senses, `DRV8323_nFAULT`, `VBUS_MON`, `HALL1` —
all of which live east; **top** → SWDIO, DBG_TX/RX, QSPI, the motor encoder channels, the
LEDs — the debug header sits directly above it; **bottom** → the three linear-encoder
channels, VDDA, `SYNC_TRIG`, `LIMIT_nBRK` — the linear-encoder block is directly below.

That is not a choice, it is what `ARIA_SRB_FAFF_2_POC_CBs_1.ioc` already decided; no pin was
re-assigned. The one net that pays for it is `ULPI_D7` (pin 91, west edge) which has to reach
the PHY on the east side; the other eleven ULPI lines leave the south and east edges toward
`U1002`.

### P1-02 — The motor bridge is three vertical legs with the driver below

Current reads top to bottom: DC-link store → `V24_MOT` rail across the high-side drains →
`Q_high` → phase node → `Q_low` → shunt → GND plane. Three legs at 15 mm pitch, **W, V, U left
to right**, which is the order the DRV8323's own pinout wants: at 180° its top edge presents
phase C on the left and phase B on the right, and phase A on its right edge.

`U1101` is directly below the shunt row so that SPI, ENABLE, `nFAULT` and the three current
senses all leave **west** into the MCU corridor, and the six PWM inputs leave **south** into
the free band above `J1102`.

The shunt Kelvin pairs (`SPx`/`SNx`) are the shortest connection in the block — the shunt row
sits 2 mm above the driver. `RT1101`, the FET thermistor, is inside the FET field between legs
W and V.

**Per-leg bypass**: each leg has its own 2.2 µF + 100 nF pair in the channel beside its
high-side drain (worst supply-pad link 8.3 mm, with the GND pad facing an open channel where
its own via lands). The two 100 µF cans and the 10 µF/100 nF ceramics sit directly above the
drain row on the `V24_MOT` rail.

### P1-03 — Motor phases will drop to `B.Cu` to reach `J1103`

The phase nodes are in the middle of each leg; `Q_low`, the shunt and the driver are between
them and the connector. Each phase therefore drops to `B.Cu` at its node and runs south to
`J1103`. That is safe: the discontinuous di/dt is inside the bridge (rail → high FET → phase,
phase → low FET → shunt → GND), while the phase output into the motor inductance is
continuous, so vias there cost nothing. At 3 A peak and 1.0 A/via that is 3 vias per phase.

`TP1115`/`TP1118`/`TP1121` (TestPointDual, D-MOT-12) sit on the switch nodes in the channels
next to their own legs.

### P1-04 — The switcher input capacitors got the pin pair, and the SW nodes are short

The most critical placement on the board, per the house rules. `C303` and `C317` (220 nF)
straddle each LMR33630's **adjacent VIN/GND pin pair** side by side: **2.81 mm on the supply
link and 2.80 mm on the ground return**, on both bucks. `C301`/`C302` and `C315`/`C316`
(10 µF) sit immediately outboard on the same row.

The inductors are oriented by pad net, not by body: `L301`'s SW terminal is **3.76 mm** from
`U301` pin 8 and `L302`'s is **3.44 mm** from `U304` pin 8, with the output pad facing away.
The bootstrap caps take the north slot (`C305`, `C319`: 5.24 mm to BOOT, 4.08 mm to SW) —
the inductor is 13.7 mm wide and there is no slot that gives both the SW node and the BOOT cap
their first choice. The SW node won.

### P1-05 — `FB301`, `C323` and `C324` are placed at the MCU, not in `power_rails`

`+3V3A` has exactly one consumer: `U1001` VDDA/VREF+ (pins 20/21). Placement by function
(client ruling P2-6) puts the ferrite and its output capacitors at the load, so the 110 mm run
from the rail block carries **unfiltered** `+3V3` and the filter sits where it works. Local
`C1010`/`C1011` (100 nF) and `C1012`/`C1013` (1 µF) stay on the VDDA pins as the datasheet
asks.

`TP307` and `J301` pin 3 keep their place in the rail-probe cluster; they carry no current, so
the tap length costs nothing.

**This is a schematic sheet-membership mismatch and it is open point 3 below** — P2-6 says the
schematic follows the placement, and correcting a `power_rails` sheet is not this task's to
make.

### P1-06 — The analog input filters hug the connector-to-ADC path

`loadcell_afe`: `J501` → `R501`/`R502` (100 Ω) → the `C501`/`C502`/`C503` differential filter
→ `U501` AIN0/AIN1, in a straight line north from the terminal block, with the reference leg
(`R503`/`R504`, `C504`/`C505`/`C506`) beside it and `TP502`/`TP503`/`TP504`/`TP505` on the
taps. `U501` is at **180°** so its analog inputs face `J501` and its SPI faces the MCU.
`J503`/`J504` (U.FL noise-floor taps) sit on the AIN nodes.

`temp_sense` mirrors it: `J701`/`J702` → 100 Ω series → the RC filters → `U701`, with the 5 k
reference resistor `R707` in the same row and the three-wire option links `R708`/`R709`
between the two connectors.

### P1-07 — Test access is placed, not left over

The three logic-analyser headers sit inboard in one row at y ≈ 110 — `J502` (load cell, x 57),
`J703` (temp, x 100), `J603` (linear encoder, x 133) — each below its own block, each with
more than 10 mm of clear board on both sides for the clip body. The 44 Keystone loops, 24 test
pads and 9 dual test points stay with the nets they observe (producer-owns-the-break,
DEC-0007): rail dual-TPs in `power_rails`, phase and gate observation in the bridge channels,
`GND` hook rows in every block. None sits under a connector or inside a courtyard, and every
name is legible at ≥ 0.8 mm.

`SW903`/`SW904` (assert each limit without the mechanics) and `SW1001` (reset) are on open
board. `J1002`, the DNP bring-up header, is fitted with a real footprint on the bench edge.

---

## 4. Numbers for the review

**Decoupling.** 63 two-pad capacitors sit on a rail that an IC pin also carries; **median
supply-pad link 4.52 mm**. The MCU's own six VDD/VSS pairs are 3.5–4.2 mm on *both* the supply
link and the ground return, so each is a loop rather than a stub. The five longest are
explained, not accidental:

| Cap | mm | Why it is acceptable |
|---|---|---|
| `C324`, `C323` | 13.1, 10.2 | `+3V3A` **filter output** caps at `FB301`, not pin decouplers; the VDDA pins have `C1010`–`C1013` at 3.8–4.5 mm |
| `C1110` | 12.6 | 10 µF `VM_DRV` **bulk**; the 100 nF `C1109` is at 6.9 mm and `C1111` (VCP) at 7.8 mm |
| `C1104`, `C1103` | 11.3, 10.5 | DC-link ceramics on the `V24_MOT` rail; each leg has its own 2.2 µF + 100 nF at ≤ 8.3 mm |
| `C601`, `C602` | 11.2, 10.0 | `+5V_ENC` store for the read head — the load is at the far end of a cable, so connector-pin proximity buys nothing |

**Ratsnest** (spanning tree per net over per-part pad positions, `GND` excluded):

| Region | links | total mm | mean mm | crossings |
|---|---|---|---|---|
| `power_entry_24v` | 28 | 212 | 7.6 | 10 |
| `power_rails` | 66 | 614 | 9.3 | 54 |
| `loadcell_afe` | 71 | 668 | 9.4 | 105 |
| `linear_encoder` | 45 | 516 | 11.5 | 96 |
| `temp_sense` | 50 | 364 | 7.3 | 48 |
| `nvm_calibration` | 15 | 115 | 7.6 | 21 |
| `ui_io` | 36 | 253 | 7.0 | 16 |
| `mcu` | 93 | 1624 | 17.5 | 217 |
| `motor_drive` | 113 | 1125 | 10.0 | 160 |
| cross-region | 73 | | | |

Read the crossing count as a rough signal, not a verdict — it counts every pair of spanning-tree
segments that cross, and two layers plus the planes dissolve most of them. The two high
numbers are both structural: `mcu` because an LQFP100 with a frozen `.ioc` pin map cannot have
its nets sorted (mean link 17.5 mm is the ULPI bus and the QSPI reaching around the package),
and `motor_drive` because the six gate nets and three Kelvin pairs necessarily cross the
bridge's own rails. `ui_io`, `temp_sense` and `power_entry_24v` are near-planar.

**DRV8323 gate runs** (straight line, driver pad to FET gate pad):

| | GHA | GLA | GHB | GLB | GHC | GLC |
|---|---|---|---|---|---|---|
| mm | 26.7 | 19.7 | 20.6 | 13.1 | 24.8 | 18.3 |

---

## 5. Open points for the captain

1. **Gate-run length, 13–27 mm.** With three legs in a row and the driver below, the high-side
   gates have to clear their own low-side FET and shunt, so nothing shorter is reachable in
   this topology. All six runs stay on `F.Cu` and via-free, in the clear channels between
   legs, and the schematic fits no series gate resistors (D-MOT-04). At 20 kHz and ≤ 2 A this
   is judged acceptable; if it is not, the fix is to **fold the bridge into an L** — legs W and
   V above the driver and leg U to its right, which is what the RTA0040 pinout is drawn for —
   at the cost of a bridge that no longer reads as three identical legs. Say the word and it
   is a placement-round-2 change, not a rework.
2. **Connector front faces are inferred, not documented.** `J201` (KPJX-4S), `J1001` (USB-C,
   placed at 180° so the opening faces the board edge), `J501` (Phoenix 1729076) and
   `J701`/`J702` (push-in 4-way) carry no orientation note in the Amodo library, so the mating
   face was read off the fab and silk outlines. `J501` in particular is symmetric front-to-back
   and its wire entry could be either way. Worth one check against the real parts before
   routing.
3. **`FB301`/`C323`/`C324` are physically in the MCU block** (P1-05). Under client ruling P2-6
   the schematic should follow — they belong on the `mcu` sheet, not `power_rails`. That is a
   schematic change and this task does not own that sheet.
4. **Whitespace, top-left.** Roughly 50 × 55 mm is empty between the UI cluster and the
   load-cell block. It is deliberate — the analog corner wants distance and the three
   logic-analyser headers want clip room — but if the captain would rather shrink the outline
   or spread the crowded right-hand column into it, that is a one-round change.
5. **`J1103` sits 25 mm below the phase nodes** (P1-03), so the three phases route on `B.Cu`.
   If the captain would rather keep every phase on `F.Cu`, `J1103` has to come inboard, off
   the actuator edge.

---

## 6. Deliberately not done

* **No routing.** No tracks, no vias.
* **No GND plane zones** — the two inner-layer pours are routing step 1, opened and closed by
  the engineer.
* **No review PDF or plot.** The captain reviews the board in KiCad; renders were scratchpad
  only (DEC-0028).
* **No library edits.** The two escalations from board setup are still open upstream; text
  height was fixed on the board instances, never in `AmodoKiCadLib`.
* **No `docs/DECISIONS.md` entry.** As with board setup, the task is scoped to this one
  decisions file; the DEC-numbered register entries for the layout-phase rulings are still
  owed, and now cover both steps.
