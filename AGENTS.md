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
- **Rotate the instance. Never make a library variant to get an orientation** — the captain's
  ruling: *"It is perfectly acceptable to rotate a part in a schematic. Needing to rotate a part
  should not require a new library variant to be made."* Rotation carries one condition: a symbol
  property's `(at x y angle)` angle is **relative to the symbol**, so the field angles must be
  compensated (270 on a symbol at 90, 90 on one at 270) or the reference and value come out
  sideways. **Prove it in a render, every time** — 57 rotated instances across the design do this
  correctly. **No pre-rotated variant exists any more**: `RES_TF_100R_0603_H`,
  `RES_TF_39R_0603_H` and `RES_TF_0R_0603_H` are gone and `faff2_passives.kicad_sym` with them.
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

**The design now meets it in full** — 409 components, 265 nets, 0/0 — so any violation you see
is yours. The parallel-wave residuals (`hier_label_mismatch`, `label_dangling`,
`pin_not_driven`) all cleared when the root was wired; do not reintroduce them as "expected".

**Never paper over an ERC error with a PWR_FLAG or a global label.** A PWR_FLAG is a power
*output*, and the flags are already owned: `power_entry_24v` holds the ones for `GND` and
`+24V_SW`, `power_rails` the ones for `V24_LOGIC`, `+6V0`, `+5V`, `+5VA`, `+3V3` and `+3V3A`.
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
self-check.

**Never generate or commit a review PDF.** The design is reviewed in the KiCad files themselves,
never in an export — `DEC-0028`, which supersedes `DEC-0026`. Renders are yours, for checking your
own work in a scratchpad; they are not a deliverable and they do not go in the repo.

Log any new review point in `SCHEMATIC_REVIEW_LOG.md` with its resolution, and any judgement
call in `docs/DECISIONS.md`.

## Power symbol net names

**One placement, everywhere: no sideways offset, centred, 3.81 mm away** — above a
rail arrow, below a ground. That is the captain's round-2 ruling, and all 283
power symbols now follow it. The label is **pinned**: where it collides, move the
*symbol* along its own stub, move the note or the neighbouring part, or grow the
block box — never nudge the label sideways to dodge.

The mirror for ground is deliberate: "above" a GND symbol is where its wire
arrives. `tools/apply_review_r2_labels.py` applies the rule and re-solves the
placement around it; re-run it after any power-symbol move.

**The design is clean under `tools/check_text_clearance.py --margin 0.35`** — zero findings on
all ten sheets, and zero misaligned ground rows under `tools/gnd_rows.py`. Keep it that way.

## Parallel parts share one ground-flag height

Capacitors — or any parts — drawn in parallel across the same net put their GND flags at the
**same y**, so the row reads as a row. Four flags on four heights draws as a staircase; that is
the captain's round-4 ruling and `C1101`…`C1104` were the example. Where a row already agrees,
the odd one out joins it; otherwise the height that makes the bottom stub match the top one is
the right target, since `schematic-style` asks for equal stubs anyway.

**`tools/gnd_rows.py` finds every breach** — it groups two-terminal parts by upper net and body
y, splits them into visual runs, and reports any run whose flags disagree. Run it after moving
a ground: a local fix that solves one collision by dropping one flag out of line is not a fix.

## The bundled overlap checker is not the last word

`check_overlaps.py` from `schematic-style` is the first pass, not the verdict. Three blind
spots, each measured against renders and written up in `docs/decisions/actuator-sch-review-r1.md`:

- It grows **every** text field rightward from its anchor, so its box is a mirror image of the
  truth whenever the text actually renders leftward — which is what `justify right`, a
  `(mirror y)` symbol, and a symbol at 180° each do (and any two of them cancel out).
- It measures text at about **1.06 mm per character**; the real advance at size 1.27 is
  **~1.19**, so it under-measures every box by a tenth and passes real near-misses.
- It reflects a **rotated or mirrored symbol's body** about the origin, so `body-vs-*` findings
  on those are noise.

`tools/sch_geom.py` models all three correctly. **Run `tools/check_text_clearance.py --margin
0.35`** rather than either — it is the recorded successor, and round 3 found four more blind
spots that a render caught after it had already passed a sheet clean: a field was never
compared against its own symbol's outline; labels and bodies were obstacles but never
subjects; block titles are bold **1.778**, 40% wider per character than the 1.27 the model
assumed; field-against-field comparison had been dropped; and every field was centred
vertically, ignoring `top`/`bottom` justify — which turned `J902`'s reference printed through
its own value into 0.5 mm of clearance. Text needs *clearance*; a body
box is the bounding box of a triangle, so it counts only when genuinely penetrated; and text
over its **own** electrical node is not an overlap at all (`wire_nodes()`).

The rest of `tools/`: **`dump_region.py`** prints everything a sheet draws inside a rectangle —
use it before placing anything, never a partial wire dump (round 1 shorted two gate nets that
way). **`netlist_nodes.py`** is the node-set invariance proof for any geometry rework — run it
before and after, and "ERC is still clean" is not a substitute. **`sch_edit.py`** holds edit
primitives that assert they changed something, because `str.replace` says nothing when it
matches nothing.

**Still run the bundled checker as a cross-check.** On the finished sheets it reports 38 to
this one's 3 — 34 are its documented blind spots, but one was real and this one had passed
it. Neither tool is the last word; the render is.

**An `apply_review_*.py` script rebuilds its sheets from a pinned base commit, not `HEAD`.**
Rebuilding from `HEAD` works exactly once: after the script's own commit lands, `HEAD` already
contains its edits and a re-run double-applies them.

## PCB layout phase

The board is `hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_pcb`. It was created by
`tools/gen_pcb_setup.py` (stackup, layer roles, outline, mounting holes, schematic import) and
`tools/gen_pcb_rules.py` (net classes, DRC constraints). **From placement onwards the board
file is the master — never re-run those generators over it.** Full reasoning, the stackup
table and the connector edge plan: [`docs/decisions/actuator-pcb-setup.md`](docs/decisions/actuator-pcb-setup.md).

Board-wide numbers every layout task needs:

- **Stackup: JLCPCB `JLC06161H-7628`** — no-surcharge 6-layer, 1.582 mm, since round 2
  (`tools/gen_pcb_stack6.py`; `docs/decisions/actuator-pcb-setup.md` §2a). It was chosen so the
  impedance geometry carried over unchanged: the outer dielectric is the same **0.2104 mm 7628
  prepreg, Dk 4.4**. 50 Ω microstrip = 0.37 mm; 90 Ω differential (USB) = 0.30 mm wide /
  0.20 mm gap. The 4-layer `JLC04161H-7628` is superseded — do not quote it.
- **Layer roles (house G1)**: `In1.Cu` and `In4.Cu` are the **unbroken GND planes**; never split
  one (G10). `F.Cu`, `B.Cu`, `In2.Cu` and `In3.Cu` are all `mixed` and carry signals **and**
  power as traces — the inner two are stripline between the planes. `In2.Cu` also carries the
  `+3V3` pour (route1 §R2.3), so signals are kept off it by preference; `In3.Cu` is open.
  `route_lib.ROUTE_LAYERS` / `PLANES` are the single source of truth for this and **anything
  keyed `{F, B}` is a round-1 leftover** — that class of bug bit three times (route1 §R2.4).
- **One via for the whole board: 0.6 mm pad / 0.20 mm drill**, annular ring 0.20 mm — JLC's
  *recommended* annulus, on a no-surcharge drill. No blind, buried or micro vias.
- **1.0 A per via — not 3 A.** JLC plates ~18 µm, so the barrel is worth a 0.32 mm 1 oz trace
  (≈1.05 A at 10 °C rise). Power via count is `ceil(I / 1.0)`, minimum 2 on any rail that
  changes layer.
- **Trace/space default 6/6 mil** (0.1524 mm); `Power` 0.5 mm, `Motor` 1.0 mm. G12 floors are
  0.15 mm track and clearance — floors, not targets.
- Board is **210 × 130 mm**, R2 corners, four **M3 NPTH** holes 6 mm in from each corner.
  Non-plated on purpose: plated holes would chassis-ground the load-cell AFE through the
  standoffs. Drill/place origin is the board's bottom-left corner.

**`pcbnew.SaveBoard()` rewrites the sibling `.kicad_pro` wholesale**, exactly as an open KiCad
session does — it replaces the ERC configuration, the schematic settings block, the 10-sheet
list, the net classes and the DRC rules with KiCad defaults, silently and with no error. It
cost the whole DEC-0021 ERC baseline once. Snapshot the `.kicad_pro` before any `SaveBoard`
and write it back afterwards (`tools/gen_pcb_setup.py` does), run `tools/gen_pcb_rules.py`
**after** the board generator and never before, and re-run the schematic ERC after any board
save to prove the baseline survived.

**Placement round 1 is done and awaiting the captain.** All 412 footprints are placed; the
floorplan, the judgement calls, the ratsnest and decoupling numbers and five open points are in
[`docs/decisions/actuator-pcb-place1.md`](docs/decisions/actuator-pcb-place1.md). The actuator
edge (y = 160) carries the nine actuator connectors, the bench edge (y = 30) the five bench
ones; analog is bottom-left, MCU centre, power and motor the right-hand column.

The placement tools mutate the board — they never regenerate it:

| Tool | What it does |
|---|---|
| `tools/gen_pcb_place1.py` | the position/orientation table; edit it, re-run it, re-run the sweeps |
| `tools/tidy_silk.py` | re-seats every reference and label clear of pads, silk, edge and each other, and lifts 0.7 mm library text to the 0.8 mm house floor |
| `tools/check_place.py` | real-courtyard overlaps, board-edge and M3 keep-out margin, 0.25 mm grid — all three must stay at **0** |
| `tools/place_report.py` | decoupler link lengths, ratsnest per region, DRV8323 gate runs |
| `tools/place_lib.py` | shared geometry helpers and the `.kicad_pro`-safe `save()` |

Sequencing, and what is **not** done yet:

- **G7 was a hard gate and it is cleared** — the captain reviewed placement round 1 and
  approved it, which is what authorised routing. See the Routing phase section below.
- DRC after placement was **19 violations, all four library residuals from board setup §8**
  (`Q201` keepout, `U501` EP annulus, `H1`–`H4`/`J201`/`J1001` lib mismatch) plus the whole
  ratsnest as unconnected. Those 19 are still the whole residual set; schematic parity 0.
  Any other number is yours.
- **The two GND plane zones are routing step 1, not board setup** — the house process opens
  and closes each routing step with the engineer, so the pours land there.

## Routing phase

Stage order, the tool per stage and every judgement call:
[`docs/decisions/actuator-pcb-route1.md`](docs/decisions/actuator-pcb-route1.md).
`tools/route_check.py` is the proof harness — `--gnd --viainpad --power --usb
--g5 --nets`, all of them when given no flag, exit 1 on any failure.
`tools/route_lib.py` holds the obstacle model, the two-layer A* and the
emitters; the stage scripts only ever **mutate** the board.

**Run DRC with `AMODO_KICAD_LIB` set.** Without it `kicad-cli pcb drc` cannot
open the library, reports **199 `lib_footprint_issues`**, and buries the six
real `lib_footprint_mismatch` under them. The residual set is 19 and is
library-side, not routing: `Q201` keep-out (9 `items_not_allowed`), `U501` EP
annulus (4 `annular_width`), `H1`–`H4`/`J201`/`J1001` (6
`lib_footprint_mismatch`).

**The recurring failure mode is a sealed pin** — a net drawn across a pin ring
before the pins inside it were routed. No amount of retrying reaches one: it has
no lane at any width on either layer. The fix is always the same shape — rip the
sealing net, route the sealed pins first, put the sealer back, because the
sealer usually has the whole board to detour through and the pins have one lane
each. `tools/route_ripup.py` holds the plans and the doctrine. Two cost a stage
each in round 1: `+5V_ENC` across `J601`'s 10-way FPC fan, and `C1020`'s ground
stitch across `U1002`'s crystal pins.

**The maze router's heuristic weight is the first thing to check when a net
"cannot" be routed.** At the default `hw=1.3` A* is nearly admissible and
expands an enormous frontier on a full board: a 34 mm MCU run needed *three
million* node expansions against `Maze.route`'s 1.2 M ceiling, so every long
MCU net was reported unroutable when a path existed. `hw=2.0` lands the same
route in 600 k nodes at 16 % over the direct distance. The diagnostic that
separates a search problem from a board problem: route the two islands' seed
points directly with `maze.route` and a generous ceiling — if that succeeds
where `connect_net` failed, the board is fine.

**Measure a pad's escape room by the area it can FLOOD into, never by a straight
lane.** `route_sealed.py`'s eight-direction probe is a first pass and it lies in
one direction: a 0.34 mm lane that dead-ends after a millimetre grades *tight*
and is as impassable as no lane at all. `C1112.1` graded tight with 388 grid
cells — one square millimetre — of reachable space, and the A\* returns from
that in ten milliseconds having exhausted its whole frontier. `free_area()` in
`tools/route27_batch_pocket.py` is the honest measure; seed it from the island's
own copper *on the layers that copper is on*, or it takes a free ride onto an
empty inner layer and reports twenty thousand cells for a pad that cannot fit a
via. (`route_sealed`'s own two traps are still worth knowing: probe from the
pad's extent *along the direction tested*, not `max(w,h)`; and probe at the
width the pin can take — class width capped by the pad and by the pitch.)

**A fan-out field is limited by its via SLOTS, not by its stubs.** At 0.5 mm
pitch a 0.6 mm via and the 0.1524 mm floor leave no room to pass a barrel on
the straight line — 0.5286 mm needed against 0.5 mm — so a via-per-pin field on
the pin's own lane places well under half the ring and the pins it *cannot*
place are exactly the ones the fill then cannot leave. Letting the **slot** move
laterally took `route25_fanout` from 124 of 291 pins to 190; maze-routing the
**stub** without moving the slot made it *worse* (108), because a greedy jog
takes the neighbour's lane. Straight stub first, jog as fallback. Full
arithmetic: route1 §R2b.4.

**A long routing stage must bank as it goes.** `refill()` can segfault (exit
139), and a stage that saves once at the end loses everything — that cost ten
minutes of routing with nothing written. `route5_critical` saves per stage,
`route6_signals` every 25 nets, both reloading in between. Three traps that go
with it: run the stage under `python3 -u` or its progress file stays empty and
looks wedged; read the **stage's** exit code, not the wrapper shell's
(`python …; echo; grep` exits 0 whatever Python did); and
`pgrep -f 'python3 tools/routeN'` matches the shell running the `pgrep` — use
`ps -eo cmd | grep '[r]outeN'`. **Never commit while a stage is writing the
board.** A rip-and-redo stage must also rip the area it *writes*, or a second
run stacks a second via on the first.

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
