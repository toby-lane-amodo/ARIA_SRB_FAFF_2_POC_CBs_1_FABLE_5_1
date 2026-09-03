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
