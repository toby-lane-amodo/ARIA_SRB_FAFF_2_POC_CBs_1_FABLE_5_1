# FAFF 2 CBs_1 - Electronics Architecture

The electronics block architecture for the `ARIA_SRB_FAFF_2` proof-of-concept control board,
as evidenced by the specification, the block diagram, the CBs_1 electronics design log, the
preliminary calculations, and the CubeMX starting point.

**Read `docs/REQUIREMENTS.md` first.** Requirement IDs (`REQ-*`) and decision IDs (`DEC-*`,
`OQ-*`) referenced here are defined there and in `docs/DECISIONS.md`.

## 1. Authorities

| Rank | Artefact | Authority over |
|---|---|---|
| 1 | Notion *Project Specification Document* | All requirements. |
| 2 | `docs/FAFF-2-Electronics-Full.svg` | Block-level architecture: which blocks exist and how they interconnect. |
| 3 | `hardware/cubemx/ARIA_SRB_FAFF_2_POC_CBs_1.ioc` | The MCU part and every MCU-side pin assignment and net name. |
| 4 | Notion *CBs_1 Design Log* | Part selections and their rationale. |
| 5 | `faff2-eee-prelim-calc.md` (Google Sheet extract) | The numbers behind the spec. |

The predecessor `ARIA_FAFF_CBs_1-block-diagram-v0.1.drawio` (FAFF 1) is **superseded** and is
reference only. FAFF 1 used a stepper motor, USB-PD power negotiation (CYPD3177-class), a
barrel-jack alternate input and a power-OR stage. **None of those are in FAFF 2** - see DEC-0001
and DEC-0002.

## 2. System context

A linear actuator for soft-material characterisation. A BLDC turns a 5 mm/rev ball screw; a
load cell between the screw and an interchangeable probe tip measures applied force; a magnetic
linear encoder measures displacement directly. The board closes a force or displacement control
loop and streams force and position to a host over USB.

Off-board, on the actuator (`BD`: "Linear Actuator Mech Parts"): the BLDC and its rotary
encoder/Hall sensors, the IKP11 read head and its magnetic scale, and the HBK S2M load cell.
Everything else is on CBs_1.

Control rates: ADC sampling 4800 SPS, closed-loop force bandwidth 40 Hz spec (48 Hz by the
calculation's 100:1 sample ratio), host stream decimated to 150 SPS. `REQ-ME-06`, `REQ-CC-03`.

## 3. Block architecture

```
                                                          [ off-board, on the actuator ]
  KPJX-4S 24 V ──▶ power_entry_24v ──▶ power_rails ──▶ (all blocks)
                         │ V24_MON            │
                         │                    │ +24V_SW
                         ▼                    ▼
                        mcu ◀──────────── motor_drive ──▶ J-MOT ─▶ BLDC
                   STM32H723VET6      DRV8323 + 6 FETs
                         │            phase I, VBUS, FET temp
                         │            ◀── J-MENC ── rotary encoder A/B/I + Halls
                         │
     ┌───────────────────┼────────────────────┬───────────────┬──────────────┐
     │ SPI3              │ TIM5               │ SPI2          │ I2C1         │ GPIO/TIM15
     ▼                   ▼                    ▼               ▼              ▼
 loadcell_afe      linear_encoder        temp_sense     nvm_calibration    ui_io
   ADS1235          RS-422 rx             ADS1120         EEPROM        buttons, LEDs,
     │                  │                     │                          SMA SYNC,
     ▼                  ▼                     ▼                          limit switches
  J-LC ─▶ S2M      J-ENC ─▶ IKP11      J-T1 (load cell)                       │
                                       J-T2 (encoder rail mid)                │ LIMIT_nBRK
                                                                              ▼
     mcu also carries: USB3320 ULPI PHY ──▶ USB-C (data only)          TIM1 BREAK
                       OCTOSPI1 quad ──▶ force-profile RAM             (motor kill)
                       SWD + USART3 ──▶ test_debug
```

### 3.1 Block responsibilities

| Sheet file | Block | Responsibility | Chief evidence |
|---|---|---|---|
| `power_entry_24v.kicad_sch` | Power entry | 24 V in on KPJX-4S; protection, fusing, inrush, TVS, filtering; `V24_MON` divider | REQ-EL-01..04 |
| `power_rails.kicad_sch` | Power rails | +24V_SW → +5V, +3V3, analog rail(s) + reference; per-rail isolation links and current breaks | REQ-EL-02/03, CALC power budget |
| `mcu.kicad_sch` | Controller | STM32H723VET6, clocks, reset, boot, SWD; USB3320 ULPI PHY + USB-C; OCTOSPI1 quad RAM | REQ-AR-01/12/13/16 |
| `motor_drive.kicad_sch` | Motor drive | DRV8323 + 6 FETs, phase current sense, DC-link sense, FET temp, motor + rotary-encoder connectors | REQ-AR-02..06 |
| `loadcell_afe.kicad_sch` | Load cell AFE | ADS1235 bridge ADC, 5 V excitation, 4-/6-wire load cell interface | REQ-FF-08..13, REQ-AR-08/09 |
| `linear_encoder.kicad_sch` | Linear encoder | RS-422 A/B/Z receiver → 3V3, IKP11 header, 5 V read-head supply | REQ-PS-05..09, REQ-AR-07 |
| `temp_sense.kicad_sch` | Temperature | ADS1120 + two RTD/NTC probe channels | REQ-EL-07, REQ-AR-10 |
| `nvm_calibration.kicad_sch` | NVM | I2C1 EEPROM for calibration and compensation data | REQ-EL-08, REQ-AR-11 |
| `ui_io.kicad_sch` | User I/O | Buttons, LEDs, SMA SYNC out, limit switch inputs incl. the hardware brake path | REQ-EL-05/06/09, REQ-CC-06, REQ-SF-01/05 |
| `test_debug.kicad_sch` | Test & debug | SWD + USART3 debug header, consolidated rail probe header, cross-block links | REQ-AR-15, TEST_PLAN |

### 3.2 MCU resource allocation

From the `.ioc` — the authority. Quoted here so block workers need not open CubeMX.

**Motor drive (TIM1, ADC1/2, SPI2)**
| Net | Pin | Function |
|---|---|---|
| `MOTOR_PWM_AH/AL` | PE9 / PE8 | TIM1_CH1 / CH1N |
| `MOTOR_PWM_BH/BL` | PE11 / PE10 | TIM1_CH2 / CH2N |
| `MOTOR_PWM_CH/CL` | PE13 / PE12 | TIM1_CH3 / CH3N |
| `DRV8323_nFAULT` | PE15 | TIM1_BKIN - hardware trip |
| `LIMIT_nBRK` | PE6 | TIM1_BKIN2 - hardware trip |
| `MOTOR_I_A/B/C` | PA6 / PC4 / PA7 | ADC INP3 / INP4 / INP7 |
| `MOTOR_FETTEMP` | PA4 | ADC INP18 |
| `VBUS_MON` | PC5 | ADC INP8 (see OQ-01) |
| `DRV8323_EN/CAL/nCS` | PD10 / PD5 / PD7 | GPIO out |
| `MOTOR_ENCODER_A/B/I` | PC6 / PC7 / PC8 | TIM3 CH1 / CH2 / CH3 |
| `HALL1/2/3` | PE14 / PD14 / PD15 | GPIO in |

**Load cell AFE (SPI3)**
| Net | Pin | Function |
|---|---|---|
| `ADS1235_SCLK/MISO/MOSI` | PC10 / PC11 / PD6 | SPI3 |
| `ADS1235_nCS` | PA15 | SPI3_NSS (hardware NSS) |
| `ADS1235_nDRDY` | PD1 | EXTI1 |
| `ADS1235_START` | PC12 | GPIO out |
| `ADS1235_nRESET` | PD0 | GPIO out |
| `ADS1235_CLKIN` | PC9 | RCC_MCO2 - ADC master clock |

**Linear encoder (TIM5)**: `LINEAR_ENCODER_A/B/Z` = PA0 / PA1 / PA2. TIM5 encoder mode TI12 on
A/B; CH3 input capture on Z.

**Shared config bus (SPI2, "CONFIG_SPI")**: `CONFIG_SPI_SCK` PA9, `CONFIG_SPI_MISO` PB14,
`CONFIG_SPI_MOSI` PB15. Chip selects: `DRV8323_nCS` PD7, `ADS1120_nCS` PD3.
**Three blocks share this bus** - see §5.

**NVM (I2C1)**: `EEPROM_SCL` PB8, `EEPROM_SDA` PB9.

**Force-profile RAM (OCTOSPI1, quad)**: `QSPI_P1_CLK` PB2, `QSPI_P1_nCS` PB6,
`QSPI_P1_IO0..IO3` PD11 / PD12 / PE2 / PD13.

**USB (USB_OTG_HS, ULPI, device HS)**: `ULPI_D0..D7` = PA3, PB0, PB1, PB10, PB11, PB12, PB13,
PB5; `ULPI_CK` PA5; `ULPI_STP` PC0; `ULPI_DIR` PC2_C; `ULPI_NXT` PC3_C;
`USB3320_nRESET` PE4.

**User I/O**: `BTN_1/2` PE0 / PE1; `LED_1/2` PA12 / PA11; `SYNC_TRIG` PE5 (TIM15_CH1);
`LIM_A` PD2 (EXTI2), `LIM_B` PD4 (EXTI4).

**Debug**: SWDIO PA13, SWCLK PA14, SWO PB3; `DBG_TX` PD8, `DBG_RX` PD9 (USART3).

**Clock**: `PH0-OSC_IN` in *HSE external clock source* mode. `PH1-OSC_OUT` is **not**
allocated, so the HSE input must be a driven clock, not a bare crystal (OQ-03). CubeMX
currently shows PLL source HSI and SYSCLK 64 MHz - that is the untouched CubeMX default, not a
designed clock tree, and it will change.

77 of 100 pins are allocated. Spare pins exist for the gaps in §6.

## 4. Power architecture

24 V enters on the KPJX-4S latching circular connector (REQ-EL-04). There is **no USB-PD, no
bus power and no alternate barrel-jack input** - all three were FAFF 1 features (DEC-0001,
DEC-0002). USB-C carries USB 2.0 data only.

Budget: 5.185 W quiescent, 25 W peak (REQ-EL-03), 7 W typical at a static 50 N hold
(REQ-EL-02). The 5 V rail feeds bridge excitation and the IKP11 read head; 3V3 feeds the MCU,
USB3320, DRV8323 logic, QSPI and EEPROM; the ADS1235 and ADS1120 need a quiet analog rail and
reference.

**Awaiting evidence.** The block diagram is signal-architecture only and shows **no power
blocks at all**. Rail count, topology (switcher vs LDO), sequencing and the analog-rail
strategy are therefore **not** externally specified - they are OQ-02, to be decided by the
`power_rails` task and recorded in `DECISIONS.md`.

## 5. Cross-block concerns

Things no single block owns. A block worker who changes one of these must say so.

1. **SPI2 is shared** by `motor_drive` (DRV8323), `temp_sense` (ADS1120) and, by proximity,
   any future config peripheral. Bus loading, series termination and the stub topology are a
   joint concern. Chip selects are per-peripheral, so only the three bus wires are shared.
2. **The TIM1 BREAK path is safety-critical.** Two independent sources trip it: `DRV8323_nFAULT`
   (PE15, BKIN) from `motor_drive`, and `LIMIT_nBRK` (PE6, BKIN2) from `ui_io`. Neither block
   may change the polarity or the drive type of its break net unilaterally. REQ-SF-05/06.
3. **Analog ground and reference strategy** spans `power_rails`, `loadcell_afe` and
   `temp_sense`. The 40 nV-scale signals of the load cell path (SLOG) set the bar.
4. **Motor FET temperature** (`MOTOR_FETTEMP`, PA4, internal ADC) belongs to `motor_drive`, not
   to `temp_sense`. `temp_sense` owns only the two ADS1120 precision channels of REQ-EL-07.
   DEC-0011.
5. **Test points and isolation links** follow the producer-owns-the-break rule: whichever block
   generates a rail or signal owns its test point, isolation link and current break. DEC-0007.

## 6. What is still awaiting evidence

Facts this architecture does **not** yet fix, and what would fix them.

| Gap | Blocked on | Tracked as |
|---|---|---|
| Rail set, topology, sequencing, analog-rail strategy | Block diagram is signal-only; needs a design decision | OQ-02 |
| HSE external clock source | `mcu` task decision, possibly shared with USB3320 | OQ-03 |
| `VBUS_MON` allocation (motor DC-link vs USB VBUS) | Captain confirmation | OQ-01 |
| Temperature probe type (RTD vs NTC) | `temp_sense` task decision | OQ-04 |
| EEPROM `nWP`, rail PGOOD/enable pins | No `.ioc` pins allocated; may need an `.ioc` revision | OQ-06, OQ-07 |
| Per-variant current-limit implementation | `motor_drive` task decision | OQ-08 |
| Root-sheet interconnect wiring | Child sheets must declare hierarchical labels first | DEC-0009 |
| BLDC part number | Deliberately open - all candidates share this design | DEC-0004 |
| Load cell 4-wire vs 6-wire build | Support both; 6-wire is the accuracy option | DEC-0014 |

## 7. Superseded FAFF 1 features

For reviewers who know the predecessor. Do not carry these across.

| FAFF 1 | FAFF 2 | Why |
|---|---|---|
| Stepper motor drive | BLDC, DRV8323 + FETs | Stepper resonances and gearbox poles; BLDC pole separation pushes resonances far higher (SLOG) |
| USB-PD controller (CYPD3177-class) | None | Dedicated 24 V supply; USB is data only (REQ-EL-10) |
| Barrel jack alternate input + power OR | Single KPJX-4S 24 V input | REQ-EL-04 |
| STM32H7 (unspecified) | STM32H723VET6, pinned | `.ioc` (DEC-0013) |
| Renishaw ATOM DX linear encoder | Bogen IKP11, RS-422 | 34-week ATOM DX lead time (DEC-0003) |
