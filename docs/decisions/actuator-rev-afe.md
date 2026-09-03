# Review-fix pass — `loadcell_afe`, `linear_encoder`, `temp_sense`, `nvm_calibration`

Design record for the schematic review-fix task `actuator-rev-afe`, 2026-09-03.
It answers the captain's round-1 review points on these four block sheets and
records the resulting netlist delta.

Files changed: `hardware/kicad/faff2_cbs1/loadcell_afe.kicad_sch`,
`linear_encoder.kicad_sch`, `temp_sense.kicad_sch`, `nvm_calibration.kicad_sch`,
`faff2_periph.kicad_sym`, and this file. `SCHEMATIC_REVIEW_LOG.md`,
`docs/DECISIONS.md` and `docs/review/faff2_cbs1_schematic.pdf` were deliberately
left alone — §8 lists what should be folded into them.

---

## 1. The review points, and what was done

| # | Captain's point | Resolution |
|---|---|---|
| R1 | "Is the intention that U501 provides / outputs the reference signal? If so, can you document this on the sheet with a text note." | **No — it is the opposite.** Answered in DEC-R1; a 15-line note now sits on `loadcell_afe` beside U501B's reference pins |
| R2 | "Rather than using individual test points for the digital interface, can you use the amodokicadlib header for the logic analyser?" | **J502** added on `loadcell_afe`; TP506–TP512 and TP514 removed. DEC-R2 |
| R3 | "J601 has text overlapping component body" | J601's reference moved above the body. DEC-R4 |
| R4 | "No pin numbers or labels on J601 library part either" | `faff2_periph:FH12-10S-0.5SH(55)` corrected: pin numbers shown, every pin named. DEC-R5 |
| R5 | "Good job on adding J602, but can you instead use the logic analyser test header instead?" | Raised as a decision (it would have dropped `REQ-PS-09`), ruled option (a) and captain-ratified: **J602 kept, J603 added**, TP602–TP607 removed. DEC-R3 |
| R6 | "5 V readhead supply needs parallel parts for R601, FB601, and D601." | **R608, R609, D602** added, all DNP. DEC-R6 |
| R7 | "C701 and C702 GND connections are upside down. You must never ever do this." | Both capacitors moved below their signal wires, grounds pointing down. DEC-R7 |
| R8 | "wire obscured by a graphical line" (`nvm_calibration`) | The SCL jog ran along a block border; moved 2.54 mm clear. DEC-R8 |

---

## 2. Decisions

### DEC-R1 — U501 does **not** provide the reference; it receives it

The review question has a definite answer, and it is worth stating plainly
because the sheet's ratiometric arrangement invites the opposite reading.

**The ADS1235 has no internal voltage reference and no reference output pin.**
`REFP0` (pin 32) and `REFN0` (pin 31) are *reference inputs* — SBAS824's pin
table calls them "Reference input 0 positive / negative", and the feature list
reads "Two Reference Inputs". The block diagram shows a reference mux, a
reference monitor and a buffer, and no reference generator.

What U501 measures against is **the load cell's own excitation**:

```
+5VA ── R508 ──▶ J501-3 EXC+ ──┐
                               ├── 350 R bridge
GND ◀── R509 ◀── J501-6 EXC- ──┘
        J501-4 SENSE+ ── R503 ──┬── C504 ─ GND
                                └──▶ U501 pin 32  REFP0   (input)
        J501-5 SENSE- ── R504 ──┬── C505 ─ GND
                                └──▶ U501 pin 31  REFN0   (input)
```

So `VREF` is the volt drop across the bridge itself, not a fixed voltage. Because
the signal and the reference come from the same source, excitation drift and
noise divide out of the conversion result — that is the whole point of the
arrangement (DEC-A5, SBAS824 §8.3.4.2), and it is why `+5VA` does not have to be
a precision reference. `R505` (100 k) is the datasheet's missing-reference
monitor: it collapses `VREF` when the cell is unplugged so the ADC's `REFL_ALM`
flag turns a disconnected cable into a reported fault.

The second reference input pair the part offers (`AIN0`/`AIN1`, "Reference input
1") is unused here — those pins are biased to AVDD through 10 k per DEC-A7.

*On the sheet:* a note headed **"REFERENCE - U501 RECEIVES IT, IT DOES NOT
PROVIDE IT"** at (172.72, 83.82), immediately below U501B's `REFP0`/`REFN0` pins.

### DEC-R2 — `loadcell_afe`: J502 replaces eight individual test points

**Part: `Amodo_Connectors:Header_Female_10-way_2-row_Straight_2.54mm_THT__KEYED_LOGIC_TEST`**
— MPN `8510-4500PL`, footprint `Amodo:8510-4500PL_LOGIC_TEST`, `SymLifecycle
reviewed`, and its own `Use With` field says "logic analyser". It is the keyed
10-way 0.1" socket for an 8-channel analyser, i.e. exactly the part the review
point asked for. Used from the house library unmodified.

`loadcell_afe` has **exactly eight** MCU-facing digital nets, and the header has
exactly eight channels, so the whole digital interface fits on one plug:

| Pin | Channel | Net | Pin | Channel | Net |
|---|---|---|---|---|---|
| 1 | CH0 | `ADS1235_SCLK` | 2 | CH1 | `ADS1235_MOSI` |
| 3 | CH2 | `ADS1235_MISO` | 4 | CH3 | `ADS1235_nCS` |
| 5 | CH4 | `ADS1235_nDRDY` | 6 | CH5 | `ADS1235_START` |
| 7 | CH6 | `ADS1235_nRESET` | 8 | CH7 | `ADS1235_CLKIN` |
| 9 | GND | `GND` | 10 | GND | `GND` |

CH0–CH3 are the SPI3 bus in the order a protocol decoder wants them (clock,
MOSI, MISO, chip select); CH4–CH6 are the control lines; CH7 is the ADC master
clock.

**Tapped on the MCU side of R511..R518**, i.e. at the same nodes the removed test
points used. Two consequences, both wanted: the 47 R series terminators still
isolate the ADC from the header's stub capacitance, and lifting one of those
links to take the ADC off the bus (DEC-A8) leaves the analyser still watching the
MCU side.

*`ADS1235_CLKIN` on CH7 is deliberate.* It is a ~7.37 MHz continuous clock, which
a 24 MSa/s hobby analyser can confirm the presence and rough rate of but not
decode. That is precisely the check DEC-A9 leaves open — the `.ioc` still has
`RCC.MCO2PinFreq_Value` at the CubeMX default 64 MHz, four times the ADS1235's
maximum — so being able to look at CLKIN at bring-up is worth a channel. It is
not "very high speed" in the sense DEC-0018 ruling 1 forbids (that ruling names
ULPI and QSPI), and it already carried a test point, so the loading is not a new
class of stub.

**Kept:** `TP513` (the `PWRDN` strap — a static level, not part of the digital
interface, and there is no ninth channel) and the `TP515`/`TP516` GND hooks (they
still serve TP513 and any scope work on the ADC side of the links).

**Removed:** `TP506`, `TP507`, `TP508`, `TP509`, `TP510`, `TP511`, `TP512`,
`TP514` — eight `TestPointHook`s. Each sat on a junction that split its signal
wire in two; the two halves were merged back into one wire and the junction
dropped, so no two-endpoint junction dots were left behind.

Two `GND` symbols (`#PWR525`, `#PWR526`) hang below pins 9 and 10.

### DEC-R3 — `linear_encoder`: J602 stays, J603 is added

The review point asked for J602 to be *replaced* by the logic-analyser header.
That was raised rather than done, because it carries three costs:

1. **J602 is the `REQ-PS-09` connector.** D-PER-01 identifies it as the "10-way
   1.27 mm header (IKP11 C1)" the requirement names. Deleting it leaves the
   requirement unmet.
2. **Pin 9 conflict.** J602 pin 9 is `+5V_ENC`; pins 9 and 10 of the
   logic-analyser socket are both named `GND` and typed `power_in`. Putting 5 V
   there is a power-output conflict in ERC and would drive an analyser's ground
   pin at 5 V through the cable.
3. **Six of J602's ten signals are the terminated 1 MHz RS-422 pairs.** D-PER-07
   and DEC-0018 ruling 1 keep those stub-free on purpose, and a 2.54 mm THT
   socket is a worse stub than the 1.27 mm shrouded header.

Ruled option (a) by firstmate and ratified by the captain ("What you have
suggested is good"): **keep J602, and put the logic-analyser header on the
signals an analyser can actually use.**

| Pin | Channel | Net | Pin | Channel | Net |
|---|---|---|---|---|---|
| 1 | CH0 | `LINEAR_ENCODER_A` | 2 | CH1 | `LINEAR_ENCODER_B` |
| 3 | CH2 | `LINEAR_ENCODER_Z` | 4 | CH3 | `ENC_SDO` |
| 5 | CH4 | `ENC_nPROG` | 6 | CH5 | *no-connect* |
| 7 | CH6 | *no-connect* | 8 | CH7 | *no-connect* |
| 9 | GND | `GND` | 10 | GND | `GND` |

`LINEAR_ENCODER_A/B/Z` are the AM26LV32 receiver outputs — native 3V3 logic
carrying the same quadrature information single-ended, which is exactly the
argument D-PER-07 already made for putting the hooks there rather than on the
pairs. `ENC_SDO` and `ENC_nPROG` are the head-configuration pair.

`CH5`–`CH7` carry **no-connect flags**. They are `input` pins, so KiCad 9 raises
`pin_not_connected` without them; there is nothing else on this sheet an
8-channel analyser can usefully sample (the remaining nets are either the RS-422
pairs or `ENC_VREF`, an analog 1.65 V mid-rail).

**Removed:** `TP602` (ENC_SDO), `TP603`/`TP604`/`TP605` (the receiver outputs),
`TP606`/`TP607` and their grounds `#PWR607`/`#PWR608` (the GND hooks — J603's
pins 9 and 10 do that job now). `TP601` stays: it is a 1.0 mm DMM pad on the 5 V
head supply, not an analyser hook, and it moved along the rail to 58.42 to make
room for R609.

Removing TP602 left the block-E `ENC_SDO` stub (one wire pair and a label) with
no purpose, so it went too; the net now reaches J601, J602 and J603.

### DEC-R4 — J601's reference text was overlapping its body

`J601`'s `Reference` field sat at (33.02, 27.58) with `justify left bottom`,
which put its text at y ≈ 24.1…27.6 while the symbol body starts at y = 26.67 —
about 0.9 mm of overlap, visible in any render. Moved to (29.21, 25.4): the text
now sits fully between the block title (which ends at y ≈ 23.4) and the body top,
left-aligned with the body's left edge.

### DEC-R5 — `FH12-10S-0.5SH(55)` had neither pin numbers nor pin names

The project-local symbol carried `(pin_numbers (hide yes))` **and** `"~"` for
every pin name, so the drawn part showed no pin identity at all — you could not
tell pin 1 from pin 10 without counting.

Corrected against the closest house exemplar, `Amodo_Connectors:FH35C-17S-0.3SHW`
(also a Hirose FFC receptacle with shell tabs), which shows both:

* the `pin_numbers` block removed, so numbers render;
* pins 1–10 named `"1"`…`"10"`, matching their numbers;
* pins 11 and 12 named `MP1` / `MP2` — the shell hold-downs. Their **numbers are
  unchanged**, because `faff2:FH12-10S-0.5SH(55).kicad_mod` has pads 11 and 12.

Naming the signal pins after their numbers rather than after the IKP11 head
functions is deliberate: `schematic-style` requires catalogue-part symbols to
stay generic, and the head pin assignment belongs in the sheet wiring, not baked
into a 10-way FFC connector. The sheet already carries the head pin order in its
block notes.

The change was applied to `faff2_periph.kicad_sym` **and** to the embedded
`lib_symbols` copy inside `linear_encoder.kicad_sch`, so no `lib_symbol_mismatch`
warning appears.

### DEC-R6 — three DNP parallel positions on the 5 V read-head supply

The review point asked for "parallel parts for R601, FB601, and D601". Two
readings were possible — parts fitted in parallel to share current, or a second
DNP footprint alongside each. The numbers rule the first one out:

| Part | Rating | Load |
|---|---|---|
| `R601` RC0603FR-070RL | 0603 0 Ω link, ≈1 A | head < 65 mA, `CALC` budget 200 mA |
| `FB601` BLM18HE601SN1D | **800 mA**, ≈0.35 Ω DC | same |
| `D601` PESD5V0U1UB | SOD523 ESD clamp, 2 pF | one hot-plugged FFC |

Nothing here is current-limited — the ferrite alone has 4× margin on the budget —
so paralleling for rating buys nothing. The second reading is also how the
captain designs elsewhere: `ARIA_EITSYS_CBs_1` uses fitted/DNP pairs throughout
(`R3` 0 Ω fitted alongside `R2` 47 Ω DNP; `R216`/`R217` a 0 Ω pair; `C149`/`C150`
a 1 µF pair), and the EEE design standard's design-for-test list asks for
"Additional strapping Rs" and "Zero ohm links for measuring power consumption".

So: **a second footprint in parallel with each, DNP by default.**

| New | Parallels | Purpose |
|---|---|---|
| `R608` 0 Ω 0603, DNP | `R601` | `R601` is the block's current break (`TEST_PLAN §3.1`). Fit a low-value shunt at `R608` and lift `R601`, and the head current can be metered **in circuit** against the 200 mA budget instead of with a meter in series. Fitting both simply halves the link resistance |
| `R609` 0 Ω 0603, DNP | `FB601` | Bypasses the ferrite. `FB601` is a lossy 600 Ω bead feeding 10 µF; if its DC drop or its resonance with `C601` upsets the head supply, or the EMC benefit needs an A/B measurement, `R609` takes the bead out of circuit with no other change |
| `D602` PESD5V0U1UB, DNP | `D601` | A second SC-79 clamp position at the connector. Populate both for more peak-pulse capability, or fit a different clamp voltage / bidirectional part here without reworking `D601`'s pads. The FFC is the one thing on this sheet that gets hot-plugged |

**None is fitted by default**, so the default build is electrically identical to
what the captain reviewed.

*Layout consequence.* `D601` moved from (96.52, 172.72) up to (96.52, 146.05),
with `D602` directly below it at (96.52, 156.21) sharing a cathode column to the
`+5V_ENC` rail and an anode column to one ground. That also **fixed a real defect
the checker had not flagged**: in its old position `D601`'s value text collided
with the `ENC_nPROG` label and its ground symbol's triangle landed on the
`ENC_nPROG` wire.

### DEC-R7 — `temp_sense` C701/C702: grounds the right way up

`C701` and `C702` sat *above* their signal wires with their `GND` symbols above
them again, so the ground triangle was drawn down through the capacitor body and
the current path ran upward into ground — the inverse of every other shunt
capacitor in the design, including `C704`/`C705`, the same filter on channel 2.

Both moved to (109.22, 35.56) and (119.38, 35.56): pin 1 now takes the signal
from above, pin 2 goes to ground below, and `#PWR704` / `#PWR705` sit under them
pointing down. The two are aligned as a pair, and the arrangement now matches
channel 2 exactly — including `C701`'s tap wire crossing the lead-B wire without
a junction, which the netlist confirms stayed a crossing and not a connection.

### DEC-R8 — `nvm_calibration`: a wire was hidden under a block border

The `I2C1_SCL` run into `U801` jogged down at x = 86.36 — **exactly the left
border of the EEPROM block's bounding box**, so a 5 mm length of electrical wire
was drawn on top of a graphical line and was indistinguishable from it.

The jog moved to x = 88.9, 2.54 mm inside the block. The two horizontal wires
still cross that border, which is normal and unavoidable — the defect was the
*parallel* overlap, not the crossing.

A sweep of all ten block sheets for wire segments lying along a rectangle edge
found one other instance, in `power_rails` — a horizontal wire at
(353.06 … 360.68, 236.22) running along that block's bottom border. **That sheet
belongs to another worker**, so it is reported here rather than fixed; see §8.

---

## 3. Netlist delta

`kicad-cli sch export netlist`, whole project, before against after. Measured
against this pass's base commit `f24d17e`, so the totals isolate *this* change;
the branch was afterwards rebased onto `main`, which had meanwhile taken
`power_entry_24v` and `power_rails` review batches of its own (post-rebase
totals: **396 components, 251 nets**).

| | Before | After |
|---|---|---|
| Components | 409 | **400** |
| Nets | 253 | **253** |
| Net names added / removed | — | **none** |

Every net that existed still exists under the same name. The complete per-net
node change:

| Net | Removed | Added |
|---|---|---|
| `+5V` | — | `R608.1` |
| `/linear_encoder/+5V_ENC` | — | `D602.1`, `R609.2` |
| `Net-(FB601-Pad1)` | — | `R608.2`, `R609.1` |
| `/linear_encoder/ENC_SDO` | `TP602.1` | `J603.4` |
| `/linear_encoder/ENC_nPROG` | — | `J603.5` |
| `/linear_encoder/LINEAR_ENCODER_A` | `TP603.1` | `J603.1` |
| `/linear_encoder/LINEAR_ENCODER_B` | `TP604.1` | `J603.2` |
| `/linear_encoder/LINEAR_ENCODER_Z` | `TP605.1` | `J603.3` |
| `/loadcell_afe/ADS1235_SCLK` | `TP511.1` | `J502.1` |
| `/loadcell_afe/ADS1235_MOSI` | `TP510.1` | `J502.2` |
| `/loadcell_afe/ADS1235_MISO` | `TP512.1` | `J502.3` |
| `/loadcell_afe/ADS1235_nCS` | `TP509.1` | `J502.4` |
| `/loadcell_afe/ADS1235_nDRDY` | `TP508.1` | `J502.5` |
| `/loadcell_afe/ADS1235_START` | `TP506.1` | `J502.6` |
| `/loadcell_afe/ADS1235_nRESET` | `TP507.1` | `J502.7` |
| `/loadcell_afe/ADS1235_CLKIN` | `TP514.1` | `J502.8` |
| `Net-(U701-AIN0{slash}REFP1)` | `C701.2` | `C701.1` |
| `Net-(U701-AIN1)` | `C702.2` | `C702.1` |
| `GND` | `C701.1`, `C702.1`, `TP606.1`, `TP607.1` | `C701.2`, `C702.2`, `D602.2`, `J502.9`, `J502.10`, `J603.9`, `J603.10` |

Reading it back: each removed test point is replaced one-for-one by a header pin
on the same net; `C701`/`C702` swap which pin faces ground; and the three DNP
parallel parts join nets that already existed. **Nothing else moved.**

Component count: `loadcell_afe` −8 test points +1 header = −7; `linear_encoder`
−6 test points −2 ground symbols +3 parallel parts +1 header +2 ground symbols =
−2. 409 − 9 = 400.

### New components

| Ref | Sheet | Part | Library | Fitted |
|---|---|---|---|---|
| `J502` | `loadcell_afe` | 8510-4500PL keyed logic-analyser socket | `Amodo_Connectors` | yes |
| `#PWR525`, `#PWR526` | `loadcell_afe` | GND | `Amodo_Symbols` | — |
| `J603` | `linear_encoder` | 8510-4500PL keyed logic-analyser socket | `Amodo_Connectors` | yes |
| `R608`, `R609` | `linear_encoder` | 0 Ω 0603 | `Amodo_Resistors` | **DNP** |
| `D602` | `linear_encoder` | PESD5V0U1UB | `Amodo_Diodes` | **DNP** |
| `#PWR619`, `#PWR620` | `linear_encoder` | GND | `Amodo_Symbols` | — |

All from the house library, none modified. Designators stay inside the per-sheet
ranges of `AGENTS.md` (`loadcell_afe` 5xx, `linear_encoder` 6xx), power symbols
included (DEC-0024): `#PWR5xx` now runs 501–526, `#PWR6xx` 601–606 and 609–620
(607/608 retired with TP606/TP607).

---

## 4. Verification

Run from the repo root, whole project.

| Check | Result |
|---|---|
| `kicad-cli sch erc --severity-all --exit-code-violations`, nothing suppressed | **0 errors, 0 warnings**, exit 0, **stderr empty** |
| Netlist export | 400 components, 253 nets, stderr empty |
| Per-net node sets, before vs after | Only the 19 rows of §3 differ; no net name added or removed |
| Designators | 0 malformed, 0 unannotated, 0 duplicates (the five repeats are multi-unit symbols) |
| Footprints | all 400 components assigned; all 52 distinct footprints resolve to a library file |
| `schematic-style` overlap checker | 11 findings on this pass's sheets — **byte-identical to the same run against the base commit**, so this pass introduced none. All confirmed artefacts (§5) |
| Render sweep | all changed areas of the four sheets swept at 10 px/mm and above |

The ERC stderr check matters: `kicad-cli sch erc` prints "Found 0 violations" even
when a sheet failed to load. Stderr was empty and the component count is right,
so every sheet parsed.

Every check above was re-run after the rebase onto `main` and still passes:
ERC 0/0 with empty stderr, 396 components, 251 nets, no duplicate designators
across any sheet.

---

## 5. The overlap checker's 11 findings

Unchanged from `HEAD` and all previously confirmed artefacts
(`actuator-sch-integrate.md §7`, `actuator-sch-afe.md §7`). Re-confirmed here for
the two on sheets this pass owns:

* **`linear_encoder`, `body-vs-wire` on U601** — the AM26LV32 is a 5-unit symbol
  and the checker merges every unit's graphics into each instance's body box, so
  unit B's box appears to swallow a wire that actually starts at unit B's own
  output pin. The finding's wire coordinates changed only because this pass
  merged that wire's two halves.
* **`loadcell_afe`, `text-vs-wire` on TP505's reference** — TP505 is a
  180°-rotated instance. KiCad flips field justification for those; the checker
  does not model the flip, so it places the text 5 mm to the *left* of where it
  renders. Checked against a 3.2× render: the text begins at x ≈ 174 and the wire
  is at x = 170.2, clear by nearly 4 mm.

---

## 6. New sheet notes

| Sheet | Note | Position |
|---|---|---|
| `loadcell_afe` | "REFERENCE - U501 RECEIVES IT, IT DOES NOT PROVIDE IT", 15 lines | (172.72, 83.82), below U501B's REFP0/REFN0 |
| `loadcell_afe` | The "TEST AND ISOLATION PROVISIONS" note's two test-point lines rewritten for J502 | (250.19, 174.62) |
| `linear_encoder` | "J603 - LOGIC-ANALYSER HEADER", 21 lines with the full channel map | (218.44, 29.21) |
| `linear_encoder` | The DNP parallel positions, 5 lines | (17.78, 183.5) |
| `linear_encoder` | Block-notes test-point paragraph rewritten for J603 | (15.24, 210.82) |
| `linear_encoder` | "GND hooks for scope / logic-analyser clips" deleted with TP606/TP607 | — |

`J502` and `J603` both carry the library's visible `Use With: logic analyser`
field **hidden on the instance** — at the chosen positions it collided with a
neighbour, and both sheets now say the same thing at length in a note. The
library part is untouched.

---

## 7. Should the same pattern go on other sheets?

Asked to note, not to apply. Two sheets have a comparable cluster of
digital-interface test points:

* **`temp_sense`** — `TP707`…`TP711` on `ADS1120_nCS`, `CONFIG_SPI_SCK`,
  `CONFIG_SPI_MOSI`, `CONFIG_SPI_MISO` and the ADS1120 `DRDY`, plus `TP712`/`TP713`
  GND hooks. That is 5 signals into 8 channels with 2 grounds — a clean fit, and
  the SPI2 bus is shared with `motor_drive`, so watching it on one plug is worth
  more here than anywhere. **Recommended.**
* **`test_debug`** — already a system-level debug connector block; a
  logic-analyser socket there would want a deliberate channel allocation across
  blocks rather than a per-sheet copy of this pattern.

`mcu`, `nvm_calibration` (2 signals) and `ui_io` do not have enough digital nets
to earn a header. `motor_drive` has the SPI2 bus and the two TIM1 break nets;
worth a look, but the break nets are safety-critical (`ARCHITECTURE.md §5`) and
should not gain a connector stub without a ruling.

One rule to carry over if the pattern spreads: **tap on the driver side of the
series terminators**, so the header stays useful when an isolation link is
lifted, and the terminator keeps the socket's stub off the receiver.

---

## 8. To fold into the shared docs

Left for the captain / a later integration pass.

* **`SCHEMATIC_REVIEW_LOG.md`** — a "Round 2" table for review points R1–R8 above,
  with these resolutions.
* **`DECISIONS.md`** — DEC-R2, DEC-R3, DEC-R5 and DEC-R6 are the judgement calls
  worth numbering. DEC-R3 in particular records that `REQ-PS-09` survived a
  review point that would have removed it.
* **`TEST_PLAN.md`** — §4 asks `loadcell_afe` for "SPI3 hooks" and
  `linear_encoder` for "TPs on each RS-422 receiver output"; both are now served
  by a logic-analyser socket rather than hooks, so the wording should say so
  (§4 names no designators, so nothing there is stale, only imprecise). §2.1's
  test-point-type selection should gain the socket as an option alongside
  `TestPoint` / `TestPointHook` / `TestPointDual`, and §2.2's "no test coverage on
  very high speed signals" ruling should record that a shared analyser header is
  the preferred form for a whole digital interface. `temp_sense`'s row is the
  candidate of §7.
* **`docs/review/faff2_cbs1_schematic.pdf`** — deliberately not regenerated by
  this pass; it needs one export once the parallel review-fix waves land.
* **Upstream house library** — nothing this time. The `FH12-10S-0.5SH(55)` fix of
  DEC-R5 is to the *project-local* `faff2_periph`, which exists because the house
  library has no FH12-10S; if it is ever promoted, promote the corrected version.
* **The power sheets** — not this pass's, so reported rather than touched:
  * `power_rails`, the wire-along-a-block-border instance found by the §2 DEC-R8
    sweep, at (353.06 … 360.68, 236.22).
  * After the rebase the overlap checker reports **6 findings on
    `power_entry_24v` (5) and `power_rails` (1)** that were not there before
    those review batches landed — J201's reference and value over the block
    border, D201 and D202 bodies straddling wires, and R207/D202 and R314/D303
    body-on-body. Unlike the 11 of §5 these are on unrotated, single-unit parts,
    where the checker is reliable, so they are worth a look before the
    design-wide sweep.
* **`AGENTS.md`** — two entries, deliberately not edited here because it is a
  shared file and the review-fix waves are running in parallel:
  1. Its ERC baseline reads "**409 components, 253 nets**, 0/0". This pass makes
     it **400 / 253**, and the other waves will move it again. The 0/0 bar itself
     is unchanged and still holds. One update at integration, not per worker.
  2. A convention worth recording once it has spread: **digital-interface debug
     access goes on `Amodo_Connectors:Header_Female_10-way_2-row_Straight_2.54mm_THT__KEYED_LOGIC_TEST`**
     (8510-4500PL), tapped on the driver side of the series terminators, rather
     than on one hook per net. `loadcell_afe` (J502) and `linear_encoder` (J603)
     use it now; §7 recommends `temp_sense` next.
