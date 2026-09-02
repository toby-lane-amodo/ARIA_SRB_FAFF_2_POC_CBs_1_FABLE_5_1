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

- **Prefer existing Amodo parts.** Search the library before drawing anything —
  e.g. `ADS1235` is already in `Amodo_ADCs.kicad_sym`.
- Create a new part **only where absolutely necessary**, and create it **in the Amodo library**
  (the correct `Amodo_<category>.kicad_sym`), never scattered in this repo.
- Adding a part to a category file during parallel work? **Report it in a status line** so
  firstmate can serialise concurrent edits to that file.

## One block per file, one owner per file

The schematic is ten hierarchical blocks, each in its own `.kicad_sch` under
`hardware/kicad/faff2_cbs1/` (DEC-0008). KiCad rewrites a whole sheet file on every save, so
**two workers in one file is a guaranteed conflict.**

- Own exactly one block file. Do not edit another block's sheet.
- The **root sheet is unwired on purpose** (DEC-0009). Do not add sheet pins or root wiring;
  that is a later integration pass, once every child declares its hierarchical labels.
- The interface list in each sheet's stub note is the **binding contract** between blocks.
  Need an interface that is not listed? Raise it — do not invent it, or two blocks will
  disagree about a shared net.
- Shared concerns that no single block owns are listed in `ARCHITECTURE.md §5`: the SPI2 bus,
  the two safety-critical TIM1 BREAK nets, analog ground/reference, and the
  producer-owns-the-break rule for test points (DEC-0007).

## Before showing or committing schematic work

ERC must be clean at **severity-all — 0 errors and 0 warnings**, with nothing suppressed. That
is the current baseline (DEC-0021) and every block must preserve it.

```sh
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib \
  kicad-cli sch erc --severity-all --exit-code-violations \
  -o /tmp/erc.rpt hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_sch
```

Then follow the rest of the `schematic-style` verification list: netlist checks for
orientation-sensitive parts, the bundled overlap checker, and a render sweep. Renders are a
self-check — **never commit review PDFs**; the client reviews in the KiCad GUI.

Log any new review point in `SCHEMATIC_REVIEW_LOG.md` with its resolution, and any judgement
call in `docs/DECISIONS.md`.

## Sharp edges

- Multi-line schematic text must use `\n` **escape sequences** in the file. A literal newline
  inside a quoted s-expression string makes KiCad fail to load the sheet, with only
  "Failed to load schematic" as the message.
- Text blocks anchored `justify left bottom` grow **upward** from the anchor and will run off
  the top of the page. Use `justify left top` for a block that should read downward.
- Sheet titles longer than roughly 50 characters overrun the A3 title-block field and clip at
  the page border (DEC-0020). Use the short `CBs_1 - <block>` form.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
