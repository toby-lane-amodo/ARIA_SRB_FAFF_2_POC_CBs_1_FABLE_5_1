# ARIA_SRB_FAFF_2_POC_CBs_1

Electronics for **FAFF 2** — a linear actuator with force feedback, built as an OEM-style
module for soft-material characterisation. `CBs_1` is the proof-of-concept control board.

A BLDC turns a 5 mm/rev ball screw. A load cell between the screw and an interchangeable probe
tip measures applied force; a magnetic linear encoder measures displacement directly. An
STM32H723 closes a force or displacement control loop and streams force and position to a host
over USB at up to 4800 SPS.

Two build variants, differing only in maximum force: **V50N** (± 50 N) and **V10N** (± 10 N).

> **This board is deliberately larger than the final product.** It is a development-board-style
> build that precedes miniaturisation, so that every block can be brought up and measured
> independently. See [`docs/TEST_PLAN.md`](docs/TEST_PLAN.md).

## Status

**Schematic complete and integrated**, awaiting client review. All ten blocks are drawn, the
root sheet is wired, and the design is internally consistent: 409 components, 253 nets,
113 sheet pins, **0 ERC errors and 0 warnings** at `--severity-all` with nothing suppressed.
Every component has a footprint that resolves.

The review pack is [`docs/review/faff2_cbs1_schematic.pdf`](docs/review/faff2_cbs1_schematic.pdf);
the open points the captain is asked to rule on are in
[`hardware/kicad/faff2_cbs1/SCHEMATIC_REVIEW_LOG.md`](hardware/kicad/faff2_cbs1/SCHEMATIC_REVIEW_LOG.md),
round 1. **PCB layout is the next wave**; no board file exists yet.

## Repository map

```
README.md                        this file
AGENTS.md                        conventions every session needs
docs/
  REQUIREMENTS.md                numbered requirements, traceable to the spec, both variants
  ARCHITECTURE.md                block architecture, MCU resource allocation, open gaps
  DECISIONS.md                   every judgement call, dated, with reasoning
  TEST_PLAN.md                   test points, isolation, current breaks, bring-up order
  FAFF-2-Electronics-Full.svg    THE block diagram (authoritative architecture)
  HardwareDesignStandard_DRAFT/  captain's in-house EEE design standard (verbatim draft)
  decisions/                     one record per schematic task, incl. actuator-sch-integrate.md
  review/                        the schematic review pack PDF (regenerate, never hand-edit)
hardware/
  kicad/faff2_cbs1/              the KiCad 9 project - see below
  cubemx/                        the STM32CubeMX .ioc - THE MCU pin-map authority
tools/                           re-runnable generators for the root sheet and the DRV8323S land
datasheets/                      collected datasheets (see its README for the shopping list)
```

## The KiCad project

`hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_pro` — **KiCad 9 only** (DEC-0017).

| Sheet | Block |
|---|---|
| `faff2_cbs1.kicad_sch` | root - the block map, wired: 113 sheet pins (DEC-0022) |
| `power_entry_24v.kicad_sch` | 24 V in on KPJX-4S, protection |
| `power_rails.kicad_sch` | 24 V → 5 V / 3V3 / analog rails |
| `mcu.kicad_sch` | STM32H723VET6, USB3320 ULPI PHY, USB-C, QSPI RAM |
| `motor_drive.kicad_sch` | DRV8323 + FETs, current sense, motor + encoder connectors |
| `loadcell_afe.kicad_sch` | ADS1235 bridge ADC, 5 V excitation |
| `linear_encoder.kicad_sch` | RS-422 receiver, Bogen IKP11 header |
| `temp_sense.kicad_sch` | ADS1120, two RTD/NTC probe channels |
| `nvm_calibration.kicad_sch` | I2C EEPROM for calibration data |
| `ui_io.kicad_sch` | buttons, LEDs, SMA SYNC out, limit switches |
| `test_debug.kicad_sch` | SWD + UART debug header, rail probe header |

**One block per file, one owner per file.** See `AGENTS.md`.

### Setting up the Amodo library (required before opening the project)

The project's `sym-lib-table` and `fp-lib-table` reference the house library through path
variables. Set **both**, in KiCad → *Preferences* → *Configure Paths*:

| Variable | Windows (captain's KiCad) | WSL / Linux |
|---|---|---|
| `AMODO_KICAD_LIB` | `C:\Amodo\AmodoKiCadLib` | `/mnt/c/Amodo/AmodoKiCadLib` |
| `AMODO_3D` | `C:\Amodo\AmodoKiCadLib\3D` | `/mnt/c/Amodo/AmodoKiCadLib/3D` |

`AMODO_3D` is needed separately because the Amodo footprints already reference their 3D models
through it. Without these the symbols and footprints will not resolve. See DEC-0015.

### Checking the schematic

```sh
AMODO_KICAD_LIB=/mnt/c/Amodo/AmodoKiCadLib \
  kicad-cli sch erc --severity-all --exit-code-violations \
  -o /tmp/erc.rpt hardware/kicad/faff2_cbs1/faff2_cbs1.kicad_sch
```

Currently **0 errors, 0 warnings**, with no severity suppressed (DEC-0021). Keep it that way.

## Source documents

The project document store lives in Notion, at
**TERN - University of Cambridge / ARIA_SRB_FAFF_2 / ARIA_SRB_FAFF_2 Document Store**:

| Document | Role |
|---|---|
| *Project Specification Document* | **The requirements authority.** `docs/REQUIREMENTS.md` consolidates it; where they disagree, Notion wins |
| *ARIA_SRB_FAFF_2_CBs_1 Design Log* | Electronics decisions and part selection rationale |
| *ARIA_SRB_FAFF_2_CBs_1 Block Diagram* | Excalidraw source of `docs/FAFF-2-Electronics-Full.svg` |
| *ARIA_SRB_FAFF_2 Handover Document* | Project handover |
| Specification Design Log | How the spec numbers were derived |

Also referenced: the Google Sheet **FAFF 2 EEE Prelim Calc** (force/noise budget, BLDC sizing,
power budget) and **FAFF2 Plan and Budget** (work-package phasing).

## Key parts

STM32H723VET6 · DRV8323 gate driver · USB3320 ULPI PHY · TI ADS1235 bridge ADC · TI ADS1120
temperature ADC · HBK S2M load cell (10 N / 50 N) · Bogen IKP11 magnetic linear encoder ·
KPJX-4S power connector. BLDC deliberately not fixed (DEC-0004).
