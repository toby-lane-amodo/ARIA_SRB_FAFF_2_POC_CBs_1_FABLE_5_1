# FAFF 2 CBs_1 - Schematic Review Log

Required by the `schematic-style` skill: the client's verbatim review advice lands here first,
with its resolution. Newly general rules migrate from here into the skill itself.

**Consult this log before starting schematic work.** One table per review round.

## Round 0 - skeleton (2026-09-02)

No client review yet: the schematic is a skeleton with no circuitry. This round records the
in-house instructions that already bind the schematic work, so they are not lost between rounds.

| # | Source | Point (verbatim where quoted) | Resolution |
|---|---|---|---|
| 0.1 | Captain, via firstmate | "use the Amodo KiCad library for all components… prefer existing Amodo parts; create new parts ONLY where absolutely necessary, and new parts are created in that local library (not scattered in the repo)" | Project `sym-lib-table` / `fp-lib-table` bound via `${AMODO_KICAD_LIB}`. DEC-0015; rule in `AGENTS.md` |
| 0.2 | Captain, via firstmate | New-part additions to a category file must be reported in a status line so concurrent edits can be serialised | In `AGENTS.md` under parallel block work |
| 0.3 | Captain, via firstmate | KiCad 9 only | DEC-0017 |
| 0.4 | EEE Hardware Design Standard draft | "not advisable to place test coverage on very high speed interfaces or signals" | No test points on ULPI or QSPI. DEC-0018 ruling 1; `TEST_PLAN.md §2.2` |
| 0.5 | EEE Hardware Design Standard draft | Test point type chosen per net: `TestPoint` / `TestPointHook` / `TestPointDual`; GND hooks beside signal hooks | `TEST_PLAN.md §2.1`; DEC-0018 ruling 2 |
| 0.6 | EEE Hardware Design Standard draft | Use a coaxial connector for nets you will scope or inject into repeatedly (U.FL, U.FL-to-BNC adapter in the EEE lab) | `TEST_PLAN.md §2.3`; DEC-0018 ruling 4 |
| 0.7 | `schematic-style` skill | Top sheet should be the block diagram wired with sheet pins | **Deliberate temporary deviation** — root is unwired until child sheets declare hierarchical labels. DEC-0009 |
| 0.8 | Self-check (render sweep) | Full-length sheet titles overran the A3 title-block field and clipped at the page border on `mcu` | Titles shortened to `CBs_1 - <block>`. DEC-0020 |

## Round 1 - the complete schematic, ready for review (2026-09-03)

All ten blocks are drawn, the root sheet is wired and the design is internally consistent.
**No client review has been held yet** - this round records the in-house state the pack is
submitted in, and the points the captain is asked to rule on.

### Design totals

| | |
|---|---|
| Sheets | 11 (root + 10 blocks), A3, KiCad 9 `20250114` |
| Components | 409 - `power_entry_24v` 28, `power_rails` 60, `test_debug` 10, `loadcell_afe` 59, `linear_encoder` 26, `temp_sense` 44, `nvm_calibration` 15, `ui_io` 40, `mcu` 50, `motor_drive` 77 |
| Nets | 253 |
| Sheet pins on the root | 113 over 55 net names; 70 wires, 3 junctions, 0 crossings |
| Isolation links / current breaks | 32 0R links (`TEST_PLAN §3.3`) |
| Test points | across all ten blocks per `TEST_PLAN §4` |
| Libraries | Amodo house lib via `${AMODO_KICAD_LIB}`; project-local `faff2_afe`, `faff2_motor`, `faff2_periph`, `faff2.pretty` via `${KIPRJMOD}` |

### Verification state

| Check | Result |
|---|---|
| `kicad-cli sch erc --severity-all`, nothing suppressed | **0 errors, 0 warnings** (DEC-0021) |
| Designators | 0 unannotated, 0 out of range, 0 duplicates; power symbols too (DEC-0024) |
| Footprints | all 409 components assigned; all 51 distinct footprints resolve to a library file |
| `schematic-style` overlap checker | root sheet clean; 11 findings elsewhere, every one a confirmed checker artefact (`docs/decisions/actuator-sch-integrate.md §7`) |
| Render sweep | all 11 pages at 10 px/mm |
| Review pack | `docs/review/faff2_cbs1_schematic.pdf` |

### Open points for the captain

| # | Point | Recommendation |
|---|---|---|
| 1.1 | **OQ-07 - `RAIL_PGOOD` has no MCU pin.** It drives `D303` and `TP308` inside `power_rails` and nothing else, so firmware cannot read power-good. | Allocate one of the spare MCU pins in the `.ioc` (`SPARE_PA8/PA10/PB4/PB7/PC13/PE3/PE7`). One label in each of two sheets plus a root sheet pin. DEC-0023 |
| 1.2 | **`AM26LV32CDR` (U601) is obsolete.** TI's addendum of 14-Oct-2025 in `datasheets/AM26LV32.pdf` lists the C-grade SOIC parts as Obsolete. | Move to **`AM26LV32IDR`** - same D package, -40 to 85 °C, Active. Needs a JLC stock check, so it is raised rather than made. Footprint unaffected |
| 1.3 | **88 components carry no datasheet URL.** All are Amodo house-library passives and test points whose `Datasheet` field is blank or `~` **in the read-only house library**. `schematic-style` requires a working web URL on every library part. | Upstream house-library fix. Overriding the instances locally would diverge from the house lib for no gain |
| 1.4 | **DRV8323S land pattern is `FPLifecycle draft`.** Sourced from TI 4219112/A via the RHA0040B equivalence because `SLVSDJ3D` omits the RTA drawing. | Confirm the reasoning in DEC-0025 and check the land against a real part before the first order |
| 1.5 | **A review PDF is committed** under `docs/review/`, which `schematic-style` forbids. | The integration brief asked for it explicitly; recorded as a deliberate deviation in DEC-0026. Confirm the client still reviews in the GUI |

### In-house points closed during integration

| # | Point | Resolution |
|---|---|---|
| 1.6 | Round 0 point 0.7 - "top sheet should be the block diagram wired with sheet pins", deferred as a temporary deviation | **Closed.** The root is wired: 113 sheet pins, aligned rows so 48 of the 55 nets are single straight wires. DEC-0022, closing DEC-0009 |
| 1.7 | `CONFIG_SPI_MISO` declared `output` by `motor_drive` and `tri_state` by `temp_sense`; `actuator-sch-afe.md §3` flagged it for integration | **Closed.** Both `tri_state` - three devices share the wire, each driving only while its own chip select is low |
| 1.8 | `loadcell_afe` and `temp_sense` both annotated power symbols from `#PWR001`, silently merging 19 references | **Closed.** Renumbered to the per-sheet ranges; rule written into `AGENTS.md`. DEC-0024 |
| 1.9 | `RAIL_PGOOD` exported as a hierarchical label with no consumer anywhere | **Closed** as a sheet-local label; see 1.1 for the open half. DEC-0023 |
| 1.10 | `TEST_PLAN §3.3` asked for a rail link from `power_rails` to each consumer block; the block wave drew one break per *rail* instead | **Closed.** `TEST_PLAN §3.2/§3.3` rewritten against what is drawn, with the 32 links tabulated and the bring-up steps naming the link each one opens |
| 1.11 | Four sheet notes still told the reader the root was unwired and to expect `hier_label_mismatch` | **Closed.** `motor_drive`, `mcu`, `power_entry_24v`, `test_debug` corrected |

---

## Round 1 review - the captain's pass over the drawn schematic (2026-09-03)

The captain reviewed the completed schematic sheet by sheet. His points arrived in
batches and were applied in three parallel streams; the numbering below is by
batch, not by arrival. Reasoning for every judgement call is in
[`docs/decisions/actuator-sch-review-r1.md`](../../../docs/decisions/actuator-sch-review-r1.md)
(power sheets, `motor_drive`, and the design-wide sweep),
[`actuator-rev-afe.md`](../../../docs/decisions/actuator-rev-afe.md) and
[`actuator-rev-testdebug.md`](../../../docs/decisions/actuator-rev-testdebug.md).

### Placement and drawing style

| # | Point (captain's words) | Sheet | Resolution |
|---|---|---|---|
| R1.1 | "Mirror the input power connector so that the pins come out left to right, and wires don't have to route around its body." | `power_entry_24v` | **Done.** `J201` mirrored and moved so all five pins leave rightward; no wire passes the body |
| R1.2 | "Have the input protection FET horizontal, so that pins 1 and 5 are horizontal not vertical." | `power_entry_24v` | **Done.** `Q201` at 90° - drain left, source right, gate down; the gate net no longer loops round the body |
| R1.3 | "Where you have a potential divider ... make sure they are vertically aligned." | `power_entry_24v` | **Done.** `R201`/`R202` share one column; the gate node is a 3-way tee, not a 4-way |
| R1.4 | "D201 is in parallel with C204, etc, so graphically it should also be placed vertically like C204 etc. Same for D202." | `power_entry_24v` | **Done.** Both diodes vertical; `D201`'s GND flag joins the shunt bank's line |
| R1.5 | "It would be nice if GND connections for parallel components are vertically aligned." | `power_entry_24v` | **Done.** `R206` and `C207` GND flags both at y=96.52 |
| R1.6 | "Never ever use a 4-way net connection ... Also, do not place test coverage on PSU feedback nodes." | `power_rails` | **Done.** `TP301` and `TP305` deleted - one edit satisfies both halves, because removing the test point is what leaves each feedback node a 3-way tee |
| R1.7 | "At the output of all regulators, use a dual test point, so that I can hook up an oscilloscope probe." | `power_rails` | **Done.** `TestPointDual` on all five rail outputs, hung below the rail on a stub so the pads do not straddle the wire they tap |
| R1.8 | "Series output zero ohm links for regulators should be placed horizontally, not vertically." | `power_rails` | **Done.** `R305`, `R306`, `R307`, `R312` |
| R1.9 | "Ferrite beads used for rail filtering should be placed horizontally ... to keep flow of power in one direction, without un-necessary corners." | `power_rails` | **Done.** `FB301` in line on the `+3V3` rail |
| R1.10 | "Power LEDs should also ideally be placed vertically." | `power_rails` | **Done.** `D303`, anode up out of `R314` |
| R1.11 | "R1101 and R1102 are in series, so I think the comment is wrong about fitting one vs the other. Also, the comment says R101 and R102, which I think is a mistake?" | `motor_drive` | **The refdes were wrong** - now `R1101`/`R1102`. The parts are genuinely two 0R in series, both fitted (D-MOT-14); the note is rewritten to say so and to give each link its own job |
| R1.12 | "Text overlap around C1101" | `motor_drive` | **Done.** The bulk column was on an 8.89 pitch that put `C1101`'s reference on `C1102`'s body; respaced, and `TP1103` moved out of the capacitor value row |
| R1.13 | "Same as other sheet review for sheet entry / exit labels justification. This text should not overlap the wires." | `motor_drive` | **Done.** Eight labels: seven took their wire from the left while facing left, so the wire ran through the text; `+24V_SW` ran vertically into the block title. All now face the way their wire arrives |
| R1.14 | "J601 has text overlapping component body. Check all the schematic for instance of this and fix if required." | design-wide | **Done.** `J601` by the encoder worker; the design-wide sweep found and cleared 16 more, several of which the bundled checker cannot see (see below) |
| R1.15 | "GND connections are upside down. You must never ever do this." | `temp_sense`, design-wide | **Done.** `C701`/`C702` by the temp worker; the sweep confirms **0** of the 285 power symbols is rotated or mirrored |
| R1.16 | Graphic/drawing lines shadowing electrical wires | design-wide | **Done.** One real case: `power_rails` block D's bottom border ran along the last `PWR_FLAG`'s wire. The flag column moved up 2.54; the sweep finds no other |

### Design questions answered

| # | Point | Answer |
|---|---|---|
| R1.17 | "For regulators in general, can you tend towards using the same parts as used in this design: ARIA_EITSYS_CBs_1" | `U301` swapped to that design's **LMR51610XFDBVR** with divider, inductor and PGOOD re-derived from TI SLUSEY1B. `U304` keeps the LMR33630 (its rail's 1.1 A budget exceeds the LMR51610's 1 A) and both 5 V LDOs keep the TPS7A20 (7 µV<sub>RMS</sub> against the ADPL42005's 32, on the rail carrying `REQ-FF-04`). Both exceptions stand pending the captain |
| R1.18 | "Should there be some bulk decoupling on this sheet? Also, decoupling per FET, or is this not usually done?" | Bulk was already there (210 µF at the bus entry, plus the driver's own VM bypass); **what was missing was capacitance at the bridge**, which TI asks for in as many words (SLVSDJ3D §10/§11.1). Added one 2.2 µF + 100 nF pair per half-bridge. **Not per FET** - a capacitor across one MOSFET is a snubber, not decoupling, and is a bring-up decision |
| R1.19 | "Can all of the test_debug page be implemented on the relevant circuits page?" | **Done** by a parallel worker: `test_debug.kicad_sch` no longer exists, and the standing rule is in `AGENTS.md` |
| R1.20 | "Is the intention that U501 provides / outputs the reference signal?" | Answered on the sheet by the AFE worker: **no** - the ADS1235 has no reference output; `REFP0`/`REFN0` are inputs, and what it measures against is the load cell's own excitation |
| R1.21 | "Rather than using individual test points for the digital interface, can you use the amodokicadlib header for the logic analyser?" | **Done** by the AFE worker |

### Design-wide sweep

| # | Point | Resolution |
|---|---|---|
| R1.22 | "Power labels are missing on most of the power flags on the design" | **Done.** 92 hidden rail names on `loadcell_afe`, `motor_drive` and `temp_sense` are now visible, placed to the house pattern (GND below the symbol, rail arrows above) and collision-checked. All 285 power symbols now read |
| R1.23 | "Across the schematic, can you label all of the TPs with some text for what they measure ... keep them as short as possible (< 6 characters)" | **Done.** All 83 test points named from the net each actually lands on; longest is 5 characters. Table in `actuator-sch-review-r1.md` |

## Round 3

| # | Point | Resolution |
|---|---|---|
| R3.1 | "A deeper text-overlap pass — extend detection to text against wire segments and symbol outlines including rotated and mirrored ones, sweep every sheet, fix every hit, and record the improved checker. This all needs fixing before we can proceed" | **Done.** `tools/check_text_clearance.py`, calibrated at 0.35 mm; both screenshotted cases reproduced and fixed; 60 findings to 13, then a fifth blind spot found by render (labels and bodies were obstacles, never subjects) took the sweep design-wide. Reasoning in `actuator-sch-review-r1.md` |
| R3.2 | "Replace `TP707`–`TP711` with the Amodo keyed logic-analyser header" | **Done.** `J703`, an `8510-4500PL` as on `J502`/`J603`; channel map copies `J603` pin for pin. This is `actuator-rev-afe.md` §7's own recommendation applied |
| R3.3 | "Swap both 5 V LDOs to `ADPL42005ACPZ-5.0-R7`, fixed output, and re-derive the passives from the datasheet" | **Done.** DEC-P3 superseded. Every value from `datasheets/ADPL42005.pdf` (a mirror copy — analog.com is unreachable from the build environment). `CIN` 1 µF → 10 µF is the only passive the datasheet forced. **Two items for the captain:** wiring the new `PG` pins into `RAIL_PGOOD`, and whether to raise `+5V5` now that the 6.0 V ceiling is gone |
| R3.4 | "Respace the grazing power-label placements and find the TIM1 note a clean home" | **Done.** The improved checker turned 13 into 60; 57 cleared, ERC 0/0 and node sets identical. The TIM1 note sits beside U1101's logic inputs — round 2's "nothing fits in this block" was wrong, 495 positions do. Three left, both argued out in `actuator-sch-review-r1.md`: `#PWR1131` needs 4.45 mm in a 2.54 mm bus field (**for the captain**), and `#PWR327` is a 0.13 mm graze with every direction taken |
| R3.5 | "Leave ESD off the AFE inputs" | **Done** — recorded as a closed decision |

## Round 4

| # | Point | Resolution |
|---|---|---|
| R4.0 | "Parallel components share ONE GND-flag height — sweep ALL sets of parallel capacitors and parallel parts across the design" (good: the `C1113` row; bad: `C1101`/`C1102` staggered) | **Done, and recorded as standing style** in `AGENTS.md`. `tools/gnd_rows.py` finds every breach rather than relying on the eye; four rows were out, all six flags now level |
| R4.1 | "Apply that alignment around `C315`/`C316`/`R308` — it also fixes the R308 overcrowding" | **Done.** Levelling put each flag's name 0.26 mm inside the EN divider's top resistor, so the divider column moved 2.54 mm left; both clear by 2.28 |
| R4.2 | "`PGND` pin on `U304` overlaps `C318`" | **Done.** `U301` is the same regulator wired the same way and its PGND ground hangs 1.27 mm below the pin; `U304`'s hung 6.35 mm down, into C318's lane. Matching `U301` also closed both of round 3's residual findings |
| R4.3 | "The `+5VA` bridge-excitation label/wiring falls outside the sheet boundary at the top" | **Done.** The drawing area starts at y=11.94 (measured off a render); the whole excitation cluster dropped 6.35 mm |
| R4.4 | "The rail probe header belongs on THIS sheet" | **Done.** `J1004` → **`J301`** on `power_rails`, block D. Its own note had already named this sheet as the alternative home |
| R4.5 | "`FL501`/`FL502` are connectors — re-designate as `J`" | **Done → `J503`/`J504`.** No reason survives: they are `Amodo_Connectors:CONUFL001-SMD`, U.FL coaxial connectors with connector footprints, and the library symbol's own default prefix is `J`. `FL` designates a *filter*; they sit in a filter chain, which is the only reading that explains it. `DEC-A14` |
| R4.6 | "Add a very concise text note directly next to `J501`" | **Done.** Five lines under the connector; the full table stays in the notes column |
| R4.7 | "`R601` and `R608` are the same package — keep ONE" | **Done, `R608` removed.** Reverses part of review point R6; the reasoning is better — to meter head current you replace `R601` with a shunt |
| R4.8 | "Remove `R609` entirely — `FB601` can be lifted" | **Done.** `D602` stays: a second clamp *position* for a different part is not the same argument |
| R4.9 | "`temp_sense` content crosses the top sheet boundary" | **Done.** Six rectangles across `temp_sense` and `mcu` started at y=11.43, half a millimetre above the drawing area. Nothing is above the boundary now |
| R4.10 | "Add 100R between the SWD header and the `+3V3` pin" | **Done, `R1015`** — the same series resistance `ARIA_EITSYS_CBs_1` puts on the same pin |
| R4.11 | "Swap the SWD header to the STM32 14-way version as in `ARIA_EITSYS_CBs_1`" | **Done.** `Amodo_Connectors:SAMTEC_SHF-107-01-L-D-SM`, pinout traced pin by pin from that repo's `J11`. **One deviation, an addition:** `SWO` on pin 10, which is NC there — this design has SWO (`REQ-AR-15`) and dropping it would lose a capability |
| R4.12 | "`VBUS_MON` sheet exit has wrong justification/overlap; align the nearby capacitor GNDs" | **Done.** It was the only hierarchical label on the sheet with `justify left bottom`; all fifteen siblings read back over the wire. The four capacitor grounds are level under R4.0 |
| R4.13 | "`R1128`-`R1133` use a different 100R symbol — why, and unify" | **Done.** The reason was real but does not outweigh the divergence: round 2 added `faff2_passives:RES_TF_100R_0603_H`, a pre-rotated variant, so they could lie horizontally without instance rotation. Nine other 100R use the house symbol. All six now do too, rotated 90 with field angles compensated; the local variant is deleted |

### Captain rulings folded in from round 3

| # | Ruling | Done |
|---|---|---|
| A1 | PG into `RAIL_PGOOD`: **yes** | `R317`/`R318`, 1 k each. A dead 5 V rail is now visible at `D303`/`TP308` |
| A2 | Raise `+5V5`: **yes, 6.0 V or slightly above** | 6.110 V nominal, worst-case floor 6.009 V. `DEC-P10` shows the stack |
| A3 | `#PWR1131`: drag `R1120` and its flag down, no bus reroute | Done, 7.62 mm |

### What the bundled overlap checker cannot see

The sweep found three structural blind spots in `check_overlaps.py`, all measured
against renders. It grows every text field rightward regardless of `justify right`,
mirroring or 180° rotation; it measures text at ~1.06 mm per character where the
real advance is ~1.19; and it reflects a rotated symbol's body about the origin.
`tools/sch_geom.py` models all three correctly. **Run
`tools/check_text_clearance.py --margin 0.35`** instead of either: round 3 found
a fourth and fifth blind spot that my own model shared — a field was never
compared against its own symbol's outline, and net labels and symbol bodies were
only ever obstacles, never subjects.
