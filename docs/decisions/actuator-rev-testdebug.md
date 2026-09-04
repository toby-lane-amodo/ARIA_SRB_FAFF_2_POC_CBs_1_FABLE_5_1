# Review revision — dissolving `test_debug`, and the `mcu` / `ui_io` batches

Captain's review pass on the `CBs_1` schematic, 2026-09-03. Three batches landed
together on one branch because they all touch `mcu.kicad_sch`:

| # | Captain's words | Result |
|---|---|---|
| R1 | "Can all of the test_debug page be implemented on the relevant circuits page? I do not like breaking the test coverage out onto its own sheet." | `test_debug.kicad_sch` deleted; its three blocks moved onto `mcu` |
| R2 | "I do not like the shared clock for STM32 and USB phy. Can these have their own crystals?" | The shared 24 MHz fan-out is gone. The PHY gets its own crystal; the STM32 keeps its own oscillator |
| R3 | "This page feels a bit cramped. Feel free to use an A2 sheet if required." | `mcu` is A2 and re-laid |
| R4 | "Net labels look good, but sheet entry / exit flags do not. These should all be right justified, and you will just need to use more horizontal space." | All 47 hierarchical labels on `mcu` are right-justified in clean columns |
| R5 | "more horizontal protection diodes (D903)" · "R907 would also look better horizontal" · "unnecessary vertical resistor placement for R915" | `ui_io`: `R907` and `R915` lie along the signal, `D903` shunts straight down |
| R6 | "LIM_A and LIM_B sheet exit points have overlap. You can stretch this circuit out to the right of the sheet if you need more space." | The two exits are clear of every wire and label |

Files touched: `mcu.kicad_sch`, `ui_io.kicad_sch`, `test_debug.kicad_sch` (deleted),
`faff2_cbs1.kicad_sch` and its generator `tools/gen_root_sheet.py`, `faff2_cbs1.kicad_pro`,
`sym-lib-table`, the new `faff2_passives.kicad_sym`, `AGENTS.md`, `README.md`,
`docs/ARCHITECTURE.md`, `docs/TEST_PLAN.md`, `docs/DECISIONS.md` (one amendment), and this file.

---

## 1. R1 — `test_debug` is dissolved

### D-REV-01 — Test coverage lives on the circuit page it covers, never its own sheet

The `test_debug` sheet held three blocks. All three moved to `mcu.kicad_sch`:

| Was | Is | Refdes |
|---|---|---|
| **T1** SWD + USART3 debug header | **H** on `mcu` | `J401→J1003`, `R401→R1013`, `R402→R1014` |
| **T2** consolidated rail probe header | **`power_rails` block D** | `J402→J1004→J301` (moved off `mcu` in review round 4) |
| **T3** six GND hooks for scope clips | **K** on `mcu`, re-drawn as one row of six | `TP401..406 → TP1006..1011` |
| power symbols | — | `#PWR401..414 → #PWR1051..1064` |

*Why `mcu` for all three.* Block H is unambiguous: SWD, SWO, `MCU_nRESET` and the
USART3 console are MCU pins and nothing else. Blocks J and K are board-level:

- **J, the rail probe header**, observes `+5V`, `+3V3` and `+3V3A`. Its strictly
  correct home under producer-owns-the-break (DEC-0007) is `power_rails`, which
  produces all three and already carries a test point, an isolation link and a
  current break per rail (`TEST_PLAN §3.3`, `TP301`/`TP305`). J duplicates none of
  that — it is a one-connector DMM convenience for bring-up steps 2 and 3, and step
  3 ("MCU alive: `+3V3` and `+3V3A` up") is an `mcu`-page gate. It went to `mcu`
  because `power_rails` was locked by a parallel review worker in the same wave and
  KiCad rewrites a whole sheet on every save, so two workers in one file is a
  guaranteed conflict (`AGENTS.md`). **Open for the captain:** move J to
  `power_rails`, or retire it as duplicate coverage. The block note on the sheet
  says so, so the question cannot be lost.
- **K, the GND hooks**, are scope-clip returns for hooks that live on six different
  sheets. They belong to no one block, and distributing six of them would have
  touched every sheet in the project mid-wave. One clearly-titled row on `mcu` is
  honest; their real placement is a layout decision and the note says so.

*What did not move.* Nothing was deleted and no net changed. The six debug nets —
`SWDIO`, `SWCLK`, `SWO`, `MCU_nRESET`, `DBG_TX`, `DBG_RX` — were shared only between
`mcu` and `test_debug`, so with the header on `mcu` they became **sheet-local
labels**: the hierarchical labels on both sides were converted to plain labels and
their twelve sheet pins came off the root.

### D-REV-02 — Page numbers renumber; reference-designator ranges do not

`test_debug` was page 4. The remaining nine blocks renumber 2..10 with no gap, so
the sheet count in the title block reads correctly. That breaks the old rule that a
sheet's designator range is its page number × 100 — `loadcell_afe` is now page 4 but
keeps 5xx.

Renumbering 60-odd components across seven sheets to restore the coincidence would
churn every sheet, every review note and the whole `TEST_PLAN`, for no gain. So the
allocation becomes a **fixed table** and **4xx is retired**. Written into `AGENTS.md`
and into the root sheet's own note.

### D-REV-03 — `docs/decisions/actuator-sch-mcu.md` is left as the historical record

That file is titled "`mcu` and `test_debug`". It is the design record of the wave
that drew them and stays accurate about *why* each circuit is what it is. It is not
rewritten here; this file supersedes it on where the circuits live.

---

## 2. R2 — the two clock domains are separated

### D-REV-04 — The USB3320 gets its own crystal; the STM32 keeps its own oscillator

This overturns the shared-reference half of `D-MCU-01` / OQ-03.

**USB3320 (new block C).** `Y1002 = ECS-240-12-23G-JGN-TR`, 24 MHz, 18 pF, −40 to
+85 °C, from `Amodo_Crystals.kicad_sym`, on the PHY's internal oscillator between
`REFCLK` (pin 26) and `XO` (pin 25) — USB3320 DS Figure 5-4. `XO`'s no-connect is
removed. `REFSEL[2:0] = 111` still selects a 24 MHz reference (DS Table 5-10), so no
configuration changes.

Load caps `C1025` / `C1026` = **27 pF C0G 2%** (`CAP_MLCC_27pF_0603_2%_50V_C0G`):
C = 2 × (C_L − C_stray) = 2 × (18 − 5) = 26 pF → 27 pF standard, with C_stray taken
as 3 pF pin capacitance (DS Table 4-11 gives 3 pF typ for both `REFCLK` and `XO`)
plus ~2 pF of PCB per side.

**Open for the captain / procurement:** DS Table 4-11 asks for ESR ≤ 30 Ω and
C_L 20 pF typ. 18 pF is fine for a parallel-resonant fundamental part inside the
±500 ppm budget, but **the ECS-23G ESR must be confirmed against 30 Ω before the
first order.** The block note on the sheet carries this.

**STM32 (block B).** `Y1001` keeps its ASEMB-24.000MHZ-LY-T MEMS oscillator and now
drives `PH0-OSC_IN` alone. `R1004`, the second 33 R of the old two-load fan-out, is
removed with its wiring; `R1003` still source-terminates the single trace. A bare
crystal on the STM32 is **not possible** without an `.ioc` change: `PH0-OSC_IN` is
set to *HSE-External-Clock-Source* and `PH1-OSC_OUT` is unallocated (`REQ-AR-16`),
and the `.ioc` is the pin authority (DEC-0013). Re-pinning it is a bigger decision
than a review fix, so the STM32 keeps a driven clock — which still gives the captain
what they asked for: **the two domains share nothing.**

### The netlist delta, in full

Everything else in the project netlist is byte-identical, node set for node set.

| Net | Before | After |
|---|---|---|
| `USB_REFCLK_24M` | `R1004.2`, `U1002.26` | `C1025.1`, `U1002.26`, `Y1002.1` |
| `USB_XO_24M` | — (`U1002.25` unconnected) | `C1026.1`, `U1002.25`, `Y1002.2` |
| `Net-(Y1001-OUT)` | `R1003.2`, `R1004.1`, `TP1003.1`, `Y1001.3` | `R1003.2`, `TP1003.1`, `Y1001.3` |
| `GND` | — | gains `C1025.2`, `C1026.2` |

Components: **−`R1004`**, **+`Y1002`, `C1025`, `C1026`**. Two auto-generated net
names follow the `J401 → J1003` rename (`Net-(J401-Pin_7)` → `Net-(J1003-Pin_7)`).

This branch's own contribution: 409 → 411 components, 253 nets unchanged. Rebased onto the
other two review branches the project stands at **398 components, 251 nets** — their power
rework accounts for the rest.

---

## 3. R3 / R4 — `mcu` on A2, flags in right-justified columns

### D-REV-05 — `mcu.kicad_sch` is A2; every other sheet stays A3

DEC-0020 said A3 throughout. A2 (594 × 420) is what makes R4 possible: a
right-justified flag column needs the longest name (`LINEAR_ENCODER_A`, ~18 mm) to
sit *outside* the wire, which does not fit to the left of a port unit on A3. Only
`mcu` grows; the other nine sheets are unchanged and A3 is still the default.
DEC-0020 is amended in `docs/DECISIONS.md` rather than replaced.

### D-REV-06 — Sheet entry / exit flags: `justify right`, text outside the wire

The port-unit flags were `(at x y 0) (justify left)`: the flag sits at the wire end
and the text runs **right, along the wire**, into the pin numbers — ragged right
edges, the exact thing the captain's screenshot showed. Changing them to
`(justify right)` flips the glyph and puts the text to the **left** of the anchor,
so all names right-align on the flag column and the wire runs clear to the pin.
Anchors did not move, so no wire changed and no net changed.

Net labels were left exactly as they are ("Net labels look good") — text over the
wire, left-justified. In a port column the two now read as: right-aligned flag names
outdented to the left, net-label names sitting on the wire.

### The A2 layout

| | |
|---|---|
| `A` MCU core · `B` STM32 24 MHz HSE oscillator · `D` OCTOSPI1 PSRAM · `F` USB3320C ULPI PHY · `G` USB-C · `E` USB PHY rails | unchanged positions, x ≤ 407.67 |
| `MCU PORTS` | one band, `U1001B/C/D` at 128.27 mm pitch, label columns at unit − 22.86 |
| `MCU PORTS (cont.)` | `U1001E/F`, same treatment |
| `SPARE MCU I/O BREAKOUT`, `SHEET NOTES` | moved, notes rewritten |
| `C` USB3320 24 MHz crystal · `H` debug header · `J` rail probe header | new right column, x 411.48..581.66 |
| `K` GND hooks | bottom band, six hooks in one row |

The five port-unit clusters, the spare-I/O breakout and the sheet notes moved as
whole clusters by a fixed translation, so their internal geometry is exactly what
was reviewed.

---

## 4. R5 / R6 — `ui_io`, graphical only

### D-REV-07 — Pre-rotated horizontal passives live in `faff2_passives.kicad_sym`

`schematic-style` forbids instance rotation for orientation variants — it turns the
reference and value text sideways. The Amodo house library has no horizontal
resistor, so a project-local library was created:
`hardware/kicad/faff2_cbs1/faff2_passives.kicad_sym`, registered in `sym-lib-table`
through `${KIPRJMOD}`, holding `RES_TF_39R_0603_H` and `RES_TF_0R_0603_H` — the
Amodo symbols rotated +90° at source, with reference above and value below.

**For the captain:** these belong upstream in `Amodo_Resistors.kicad_sym` as house
horizontal variants; every project that draws an in-line series resistor needs them.
The library is read-only to us, so they are project-local for now.

### What changed on the sheet

- **SYNC / TRIGGER OUT.** The signal now runs one way, left to right, along
  y = 25.40: `U901A` pin 4 → `TP901` → `R907` (horizontal) → `TP902` → `D903` tee →
  `J902` SMA. `R907` used to drop the signal 10 mm down and back out again.
  `D903` shunts straight down off the line, body horizontal, ground below its anode.
- **END-OF-STROKE LIMITS.** `U902A` moved 20.32 mm right. `LIM_A` and `LIM_B` exit
  on clear stubs — the `+3V3` riser that ran through the `LIM_A` text is now at
  x = 152.40, and the two AND-gate input risers at 157.48 and 160.02, all well clear
  of both labels. `R915` is horizontal and in line: `U902A` pin 4 → `R915` →
  `R916` pull-up tee → `TP905` → `LIMIT_nBRK`, one direction throughout.
- One stale sheet note ("ERC reports `power_pin_not_driven` until that sheet lands")
  corrected — the project has been clean at severity-all since the root was wired.

**The `ui_io` netlist is identical, net for net and node for node.**

---

## 5. Verification

| Check | Result |
|---|---|
| `kicad-cli sch erc --severity-all --exit-code-violations`, nothing suppressed | **0 errors, 0 warnings**, exit 0 |
| Sheet load (stderr checked, netlist component count) | 398 components after rebase — no silent truncation |
| Netlist equivalence | every net's node set identical apart from the four rows in §2, after mapping the `test_debug → mcu` refdes renames |
| Designators | 0 unannotated, 0 out of range, 0 duplicates; `#PWR1001..1066` on `mcu` |
| Footprints | all 398 assigned; all 53 distinct footprints resolve to a library file |
| `schematic-style` overlap checker | `mcu` clean, `ui_io` clean, root clean. Every remaining finding is in a sheet this branch did not touch — the confirmed checker artefacts of `actuator-sch-integrate.md §7`, plus whatever the other two review branches left |
| Render sweep | all 10 pages |

The review PDF was **deliberately not regenerated** by this pass. Overtaken by
`DEC-0028`: no review PDF exists and none is to be generated.

## 6. Left for the captain

1. ~~**`J1004`, the rail probe header** — move to `power_rails`, or retire it as~~
   **Closed, review round 4: moved to `power_rails` as `J301`,** into block D,
   which already carries `RAIL_PGOOD`, `D303` and `TP308`. The rails, their
   isolation links and their current breaks are all on that sheet; the header
   only observes them. Original wording:
   duplicate coverage of `TP301`/`TP305`? (D-REV-01)
2. **`Y1002` ESR** — confirm the ECS-23G against the USB3320's ≤ 30 Ω before the
   first order. (D-REV-04)
3. **`faff2_passives.kicad_sym`** — the two horizontal resistors want to be house
   parts in `Amodo_Resistors.kicad_sym`. (D-REV-07)
4. **DEC numbers** — D-REV-01..07 need real `DEC-00xx` numbers in
   `docs/DECISIONS.md`. They are not minted here because three review branches were
   in flight at once and would have raced for the same numbers. The one exception is
   DEC-0020, amended in place because "A3 sheets throughout" would otherwise be
   flatly wrong.
