# Project agent memory

FAFF 2 `CBs_1` — proof-of-concept control board electronics for the ARIA_SRB_FAFF_2 linear
actuator. This is a **KiCad hardware project**, not a software one.

Start with [`README.md`](README.md) for the repo map, then the doc set:

| Read this | For |
|---|---|
| [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) | Numbered requirements (`REQ-*`), both variants, and the open questions (`OQ-*`) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Block architecture and the **MCU pin allocation table** — quote it rather than opening CubeMX |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Every judgement call (`DEC-*`), dated, with reasoning. Add to it; never renumber |
| [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md) | Test points, isolation links, current breaks, bring-up order |
| [`hardware/kicad/faff2_cbs1/SCHEMATIC_REVIEW_LOG.md`](hardware/kicad/faff2_cbs1/SCHEMATIC_REVIEW_LOG.md) | Client and in-house review points with resolutions — **read before schematic work** |
| [`docs/decisions/actuator-sch-integrate.md`](docs/decisions/actuator-sch-integrate.md) | The wired root sheet: its layout rule, the interface reconciliations, and the design-wide audit |
| [`docs/decisions/actuator-rev-testdebug.md`](docs/decisions/actuator-rev-testdebug.md) | The captain's first review pass: why `test_debug` is gone, why `mcu` is A2, the split clocks |

## Authorities — do not contradict these

1. **Notion, *Project Specification Document*** (TERN - University of Cambridge /
   ARIA_SRB_FAFF_2 / ARIA_SRB_FAFF_2 Document Store) — the requirements authority.
   `docs/REQUIREMENTS.md` consolidates it; where they disagree, Notion wins.
2. **`docs/FAFF-2-Electronics-Full.svg`** — the block diagram; authoritative on which blocks
   exist and how they interconnect. It is signal-architecture only and shows no power blocks.
3. **`hardware/cubemx/ARIA_SRB_FAFF_2_POC_CBs_1.ioc`** — the MCU part (STM32H723VET6) and
   every MCU-side pin assignment and net name. Need a pin that is not there? Change the `.ioc`
   first and re-commit it.
4. **`docs/HardwareDesignStandard_DRAFT/`** — the in-house EEE design standard.
   Precedence: **project spec > this standard > general practice** (DEC-0018).

The FAFF 1 block diagram is superseded and reference-only. FAFF 2 has no stepper, no USB-PD,
no bus power and no barrel jack.

## Skills are mandatory, not optional

- **Schematic work** (`.kicad_sch`, `.kicad_sym`, ERC, netlists): invoke `/schematic-style`
  **before the first edit**.
- **PCB work** (`.kicad_pcb`, `.kicad_mod`, footprints, routing, stackup, DRC): invoke
  `/pcb-layout-style` **before the first board or footprint edit**.

## Sheet sizes

A3 everywhere **except `mcu`, which is A2** — a right-justified sheet-entry flag column needs
the room (DEC-0020 as amended). Sheet titles use the short `CBs_1 - <block>` form.

## KiCad 9 only

`kicad-cli` 9.0.8; schematic format version `20250114`. Never open or save these files with any
other KiCad major version — KiCad 8 cannot read them, and a newer version would silently
migrate the format for everyone else. DEC-0017.

**An open KiCad session silently reverts on-disk edits** and rewrites `.kicad_pro` wholesale on
save. Check for `*.lck` files before editing project settings.

## Amodo house library

All components come from the Amodo library at `/mnt/c/Amodo/AmodoKiCadLib` (WSL) /
`C:\Amodo\AmodoKiCadLib` (Windows), bound through project-level `sym-lib-table` and
`fp-lib-table` via `${AMODO_KICAD_LIB}`. **`AMODO_3D` must be set too** — the Amodo footprints
reference their 3D models through it. `README.md` has the setup table; DEC-0015 the rationale.

**AmodoKiCadLib is read-only reference. Never modify it and never push it.**

- **Prefer existing Amodo parts.** Search the library before drawing anything —
  e.g. `ADS1235` is already in `Amodo_ADCs.kicad_sym`.
- A part you must **create or correct** lives project-locally, in
  `hardware/kicad/faff2_cbs1/faff2_<block>.kicad_sym` (and `faff2.pretty/` for footprints),
  registered in the project `sym-lib-table` / `fp-lib-table` through `${KIPRJMOD}`. Record why
  in the block's decisions file so the captain can fix the house library upstream.
- **Never instance-rotate a symbol** to make it horizontal — it turns the reference and value
  text sideways. Pre-rotated variants live in `faff2_passives.kicad_sym` (`RES_TF_*_H` so far);
  add to it rather than rotating an instance. `schematic-style`; `actuator-rev-testdebug.md`.
- Some Amodo symbols are **uncommitted local additions** to that working copy — `ADS1235` is
  one. `git checkout --` on a file there deletes them. Do not run git operations in that
  library; it is not ours to manage.

## One block per file, one owner per file

The schematic is **nine** hierarchical blocks, each in its own `.kicad_sch` under
`hardware/kicad/faff2_cbs1/` (DEC-0008): `power_entry_24v`, `power_rails`, `loadcell_afe`,
`linear_encoder`, `temp_sense`, `nvm_calibration`, `ui_io`, `mcu`, `motor_drive`. KiCad
rewrites a whole sheet file on every save, so **two workers in one file is a guaranteed
conflict.**

**Test coverage lives on the circuit page it covers, never on a sheet of its own.** Test
points, probe headers, scope hooks and debug connectors belong to the block whose nets they
observe — that is the captain's standing ruling, and why `test_debug.kicad_sch` no longer
exists (`docs/decisions/actuator-rev-testdebug.md`). Do not recreate it, in any form.

- Own exactly one block file. Do not edit another block's sheet.
- The **root sheet is wired** (DEC-0022, closing DEC-0009): 101 sheet pins, every cross-block
  net a real wire. Regenerate it with `tools/gen_root_sheet.py` rather than hand-editing —
  the nine sheet-symbol uuids are hard-coded there because every child's symbol instances
  reference them. A new hierarchical label in a block needs a matching sheet pin added there.
- The interface list in each sheet's stub note is the **binding contract** between blocks.
  Need an interface that is not listed? Raise it — do not invent it, or two blocks will
  disagree about a shared net.
- Shared concerns that no single block owns are listed in `ARCHITECTURE.md §5`: the SPI2 bus,
  the two safety-critical TIM1 BREAK nets, analog ground/reference, and the
  producer-owns-the-break rule for test points (DEC-0007).

## Before showing or committing schematic work

ERC must be clean at **severity-all — 0 errors and 0 warnings**, with nothing suppressed. That
is the DEC-0021 baseline and the end state.

**The design now meets it in full** — 398 components, 251 nets, 0/0 — so any violation you see
is yours. The parallel-wave residuals (`hier_label_mismatch`, `label_dangling`,
`pin_not_driven`) all cleared when the root was wired; do not reintroduce them as "expected".

**Never paper over an ERC error with a PWR_FLAG or a global label.** A PWR_FLAG is a power
*output*, and the flags are already owned: `power_entry_24v` holds the ones for `GND` and
`+24V_SW`, `power_rails` the ones for `V24_LOGIC`, `+5V5`, `+5V`, `+5VA`, `+3V3` and `+3V3A`.
No other sheet may add one to those nets. A hierarchical label with only one endpoint is an ERC
error too — if nothing consumes a net yet, keep it sheet-local (DEC-0023), don't invent a
consumer.

**Reference designators are allocated per sheet, 100 apart, from a fixed table — not from the
page number**, which shifted when `test_debug` went: `power_entry_24v` 201+, `power_rails`
301+, `loadcell_afe` 501+, `linear_encoder` 601+, `temp_sense` 701+, `nvm_calibration` 801+,
`ui_io` 901+, `mcu` 1001+, `motor_drive` 1101+. **4xx is retired** — never reuse it.
**Power symbols and PWR_FLAGs follow the same ranges** (`#PWR5xx`, `#PWR7xx`, …) — DEC-0024.
Designators must be unique across the whole project; two blocks both
starting at `U1`, or both at `#PWR001`, do not raise an ERC error, they silently merge into one
component in the netlist.

```sh
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib \
  kicad-cli sch erc --severity-all --exit-code-violations \
  -o /tmp/erc.rpt hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_sch
```

Then follow the rest of the `schematic-style` verification list: netlist checks for
orientation-sensitive parts, the bundled overlap checker, and a render sweep. Renders stay a
self-check; the client reviews in the KiCad GUI. The **one** committed PDF is
`docs/review/faff2_cbs1_schematic.pdf`, the captain's review pack — regenerate it with
`kicad-cli sch export pdf` after any schematic change, never hand-edit it, and add no others
(DEC-0026, a deliberate deviation from `schematic-style`).

Log any new review point in `SCHEMATIC_REVIEW_LOG.md` with its resolution, and any judgement
call in `docs/DECISIONS.md`.

## Sharp edges

- Multi-line schematic text must use `\n` **escape sequences** in the file. A literal newline
  inside a quoted s-expression string makes KiCad fail to load the sheet, with only
  "Failed to load schematic" as the message.
- Text blocks anchored `justify left bottom` grow **upward** from the anchor and will run off
  the top of the page. Use `justify left top` for a block that should read downward.
- Sheet titles longer than roughly 50 characters overrun the A3 title-block field and clip at
  the page border (DEC-0020). Use the short `CBs_1 - <block>` form. Title-block **comments**
  clip the same way past roughly 70 characters.
- Every wire end and pin must sit on the **1.27 mm grid**, or ERC reports `endpoint_off_grid`.
- A stub that lands mid-wire does **not** connect, junction dot or not — split the wire at the
  junction point. The tell is `pin_not_connected` on a part that looks wired.
- **An invalid token truncates a sheet silently.** KiCad stops parsing at the bad token,
  keeps everything before it and drops the rest — no error, and the plotter still renders
  what survived. The tell is a component count well below what the sheet contains, or wires
  that ERC calls dangling for no visible reason. `(justify center)` is the trap: KiCad's
  justify tokens are only `left`/`right`/`top`/`bottom`/`mirror`, and centred text is
  expressed by **omitting** `justify`. Check with `kicad-cli sch export netlist` and count
  components before trusting a clean ERC.
- Inside a schematic's `lib_symbols`, the parent symbol is named `Lib:Name` but its unit
  sub-symbols keep the **bare** library name (`RES_TF_10k_0603_1_1`, not
  `Amodo_Resistors:RES_TF_10k_0603_1_1`). Prefixing them gives "Failed to load schematic".
- A child sheet's own `(uuid …)` must **not** equal the uuid of its sheet symbol in the root.
- A symbol instance's `(instances (project … (path "…")))` must start at the **root** sheet
  uuid: `/<root-uuid>/<sheet-uuid>`, not `/<sheet-uuid>`. With the short form KiCad still
  shows the right references, but the pins drop out of hierarchical connectivity and ERC
  invents `wire_dangling` / `label_dangling` / `pin_not_driven` on wiring that is correct.
  It only shows up when ERC is run from the root, never on the sheet standalone.
- `kicad-cli sch erc` prints **"Found 0 violations" when the sheet failed to load** — the
  "Failed to load schematic" line goes to stderr. Never read a clean ERC without also
  checking stderr, or the component count from a netlist export.
- The `schematic-style` overlap checker reports a false `body-vs-wire` on **multi-unit**
  symbols: it merges every unit's graphics into each instance's body box, so one unit's body
  appears at another unit's position. Confirm against the single unit's own extents before
  moving anything.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
