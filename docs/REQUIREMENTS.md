# FAFF 2 CBs_1 - Consolidated Requirements

Consolidated, numbered requirements for the **ARIA_SRB_FAFF_2** proof-of-concept control
board (`CBs_1`). Every requirement traces to a source; values are quoted verbatim from the
source, including both design variants.

**Authority.** The Notion *Project Specification Document* is the requirements authority.
Where this file and Notion disagree, Notion wins and this file is a defect.

| Tag | Source |
|---|---|
| `SPEC` | Notion, *ARIA_SRB_FAFF_2 Document Store / Project Specification Document* |
| `ELOG` | Notion, *ARIA_SRB_FAFF_2_CBs_1 Design Log* |
| `SLOG` | Notion, *Specification Design Log* |
| `CALC` | Google Sheet *FAFF 2 EEE Prelim Calc* (extract `faff2-eee-prelim-calc.md`) |
| `BD`   | `docs/FAFF-2-Electronics-Full.svg` - FAFF 2 electronics block diagram |
| `IOC`  | `hardware/cubemx/ARIA_SRB_FAFF_2_POC_CBs_1.ioc` - STM32 pin-map authority |

**Variants.** Two build variants differing only in maximum force: **V50N** (± 50 N) and
**V10N** (± 10 N). `SPEC §2.3`.

Status key: **B** = binding on CBs_1 electronics; **C** = context (mechanical/firmware, drives
electronics indirectly); **O** = open, see [Open Questions](#open-questions).

---

## 1. Mechanical context (`REQ-ME-*`)

Not electronics deliverables, but they set the electrical operating point.

| ID | Requirement | V50N | V10N | Unit | Source | St |
|---|---|---|---|---|---|---|
| REQ-ME-01 | Displacement range | 40 | 40 | mm | SPEC §3 | C |
| REQ-ME-02 | Continuous force | ± 50 | ± 10 | N | SPEC §3 | C |
| REQ-ME-03 | Maximum actuation speed | 20 | 20 | mm/s | SPEC §3 | C |
| REQ-ME-04 | Max cycle speed (low), force control | 10 | 10 | cycles/min | SPEC §3 | C |
| REQ-ME-05 | Max cycle speed (fast), force control | 60 | 60 | cycles/min | SPEC §3 | C |
| REQ-ME-06 | Force control loop bandwidth (small signal) | 40 | 40 | Hz | SPEC §3 | B |
| REQ-ME-07 | Probe tip interchangeable, threaded socket | — | — | — | SPEC §3 | C |
| REQ-ME-08 | Ball screw lead | 5 | 5 | mm/rev | SPEC assumptions, CALC | C |

Notes on REQ-ME-04/05: 1 % max force over/undershoot (% of commanded step amplitude),
amplitude < 4 mm pk-pk at 10 cyc/min; 5 % and amplitude < 6 mm pk-pk at 60 cyc/min. `SPEC §3`.

## 2. Force feedback (`REQ-FF-*`)

| ID | Requirement | V50N | V10N | Unit | Source | St |
|---|---|---|---|---|---|---|
| REQ-FF-01 | Sensing method: load cell | Load cell | Load cell | — | SPEC §4 | B |
| REQ-FF-02 | Force measurement range | ± 50 | ± 10 | N | SPEC §4 | B |
| REQ-FF-03 | Force accuracy | 60 | 12 | mN | SPEC §4 | B |
| REQ-FF-04 | Force noise, 4800 SPS raw | < 20 | < 5 | mN pk-pk | SPEC §4 | B |
| REQ-FF-05 | Force noise, 150 SPS decimated | < 2.5 | < 0.5 | mN pk-pk | SPEC §4 | B |
| REQ-FF-06 | Force resolution, 4800 SPS raw | 2 | 0.5 | mN | SPEC §4 | B |
| REQ-FF-07 | Force resolution, 150 SPS decimated | 1 | 0.2 | mN | SPEC §4 | B |
| REQ-FF-08 | Load cell: HBK S2M, accuracy class 0.02 | — | — | — | SPEC assumptions, SLOG | B |
| REQ-FF-09 | Load cell sensitivity | 2 | 2 | mV/V | SPEC §"Force" | B |
| REQ-FF-10 | Bridge excitation voltage | 5 | 5 | V | SPEC §"Force" | B |
| REQ-FF-11 | Full-scale bridge output swing | ± 10 | ± 10 | mV | SPEC §"Force" | B |
| REQ-FF-12 | Bridge ADC: ADS1235, gain 128, 4800 SPS Sinc2 | — | — | — | CALC, ELOG, BD | B |
| REQ-FF-13 | Load cell connection: 4-wire **or** 6-wire | — | — | — | BD ("4 or 6 wire") | B |

REQ-FF-03 note (SPEC §4): "All stream rates. Dominated by load cell systematics. Averaging
does not improve accuracy. Accuracy valid at 20 ± 2 °C."

Supporting calculation (`CALC`, Force sheet), for traceability only - not itself a requirement:
input sensitivity 0.2 mV/N (V50N) / 1.0 mV/N (V10N); ADS1235 input noise 2.40 µV pk-pk at
4800 SPS Sinc2 = 12.0 / 2.4 mN pk-pk, giving 167 % / 208 % headroom against REQ-FF-04.
ADS1235 FSR 78.125 mV at gain 128 / VREF 5 V; 18-bit conservative depth gives 1.49 / 0.30 mN
ADC resolution (134 % / 168 % headroom against REQ-FF-06). Streamed output 150 SPS,
2.12 / 0.42 mN pk-pk against the 2.5 / 0.5 mN of REQ-FF-05.

## 3. Position sensing (`REQ-PS-*`)

Single specification, both variants. `SPEC §5`.

| ID | Requirement | Value | Unit | Source | St |
|---|---|---|---|---|---|
| REQ-PS-01 | Position resolution | 1 | µm | SPEC §5 | B |
| REQ-PS-02 | Position accuracy | ± 5 | µm | SPEC §5 | B |
| REQ-PS-03 | Repeatability | ± 1 | µm | SPEC §5 | B |
| REQ-PS-04 | Sensing method: optical or magnetic linear encoder | — | — | SPEC §5 | B |
| REQ-PS-05 | Linear encoder: Bogen IKP11-Z1.4-P1-V5-D1-R0.5-F1000-C1 | — | — | ELOG, BD | B |
| REQ-PS-06 | Encoder interface: RS-422 differential A/B/Z, receive to 3V3 logic | — | — | ELOG, BD, IOC | B |
| REQ-PS-07 | Encoder resolution 0.5 µm; max output 1 MHz per channel | — | — | ELOG | B |
| REQ-PS-08 | Encoder supply | 5 | V | ELOG (IKP11 "V5") | B |
| REQ-PS-09 | Encoder connector: 10-way 1.27 mm header (IKP11 "C1") | — | — | ELOG | B |
| REQ-PS-10 | Incremental encoder implies a power-on homing routine | — | — | SPEC §6, ELOG | B |

REQ-PS-05 supersedes the Renishaw ATOM DX of `SPEC` assumptions and `SLOG`: rejected on a
34-week lead time. See DEC-0003.

## 4. Electrical and electronics (`REQ-EL-*`)

Single specification, both variants. `SPEC §6`.

| ID | Requirement | Value | Unit | Source | St |
|---|---|---|---|---|---|
| REQ-EL-01 | Supply voltage | 24 | V | SPEC §6 | B |
| REQ-EL-02 | Typical power consumption (static 50 N hold) | 7 | W | SPEC §6 | B |
| REQ-EL-03 | Peak power consumption | 25 | W | SPEC §6 | B |
| REQ-EL-04 | Power connector: KPJX-4S latching circular | — | — | SPEC §6 | B |
| REQ-EL-05 | SYNC/TRIGGER: 3.3 V push-pull output, 50 Ω source terminated | — | — | SPEC §6 | B |
| REQ-EL-06 | SYNC/TRIGGER connector: SMA jack | — | — | SPEC §6 | B |
| REQ-EL-07 | Temperature measured to 1 °C at (a) the load cell and (b) the mid-point of the linear encoder measurement rail, for compensation | 1 | °C | SPEC §6 | B |
| REQ-EL-08 | Non-volatile storage for calibration and compensation data | — | — | SPEC §6 | B |
| REQ-EL-09 | Limit switches may be used for a power-on homing routine | — | — | SPEC §6 | B |
| REQ-EL-10 | Data connector: USB-C. **This port will not power the hardware.** | — | — | SPEC §6 | B |

Power budget (`CALC`, Power Budget sheet), traceability only: quiescent total **5.185 W** -
STM32 3.3 V / 0.5 A, linear encoder 5 V / 0.2 A, BLDC rotary encoder 3.3 V / 0.1 A, load cell
5 V / 15 mA, other ICs 3.3 V / 0.5 A, motor Iq 24 V / 20 mA. Motor at 50 N static: 1.229 A
phase, 0.951 W loss (driver losses neglected).

## 5. Control and communications (`REQ-CC-*`)

| ID | Requirement | Source | St |
|---|---|---|---|
| REQ-CC-01 | Operational modes: dynamic force, dynamic displacement, static force, static displacement | SPEC §7.1 | C |
| REQ-CC-02 | Device presents a USB 2.0 interface | SPEC §7.2 | B |
| REQ-CC-03 | Force and linear position streamed at up to 4800 samples per second | SPEC §7.2 | B |
| REQ-CC-04 | Device functions and data accessible via an API; any GUI uses that API | SPEC §7.2 | C |
| REQ-CC-05 | Streamable data: measured force, measured linear position | SPEC §7.2 | C |
| REQ-CC-06 | Homing routine initiated via API **or an external button** | SPEC §7.2 | B |

## 6. Environmental (`REQ-EN-*`)

| ID | Requirement | Value | Unit | Source | St |
|---|---|---|---|---|---|
| REQ-EN-01 | Operating temperature | 10 to 40 | °C | SPEC §8 | B |
| REQ-EN-02 | Storage temperature | 0 to 50 | °C | SPEC §8 | B |
| REQ-EN-03 | Humidity, non-condensing | 20 to 80 | % RH | SPEC §8 | B |

## 7. Safety (`REQ-SF-*`)

| ID | Requirement | Source | St |
|---|---|---|---|
| REQ-SF-01 | End(s) of stroke to be limit switched | SPEC §9.1 | B |
| REQ-SF-02 | Firmware to kill motor drive on limit switch actuation | SPEC §9.1 | B |
| REQ-SF-03 | Peak motor current sense limit, preventing the actuator overloading 150 % of the load cell absolute maximum. **Must be configurable per variant.** | SPEC §9.1 | B |
| REQ-SF-04 | Consider a mechanical overload stop | SPEC §9.1 | C |
| REQ-SF-05 | Hardware limit-switch trip into TIM1 BREAK, in addition to REQ-SF-02 | BD, IOC (`LIMIT_nBRK` PE6 → TIM1_BKIN2), DEC-0012 | B |
| REQ-SF-06 | Gate-driver fault trip into TIM1 BREAK | BD ("BRK input on nFAULT"), IOC (`DRV8323_nFAULT` PE15 → TIM1_BKIN) | B |

REQ-SF-05/06 are architectural additions evidenced by the block diagram and `.ioc`; they
strengthen REQ-SF-02 rather than replacing it. See DEC-0012.

## 8. Standards and compliance (`REQ-SC-*`)

| ID | Requirement | Source | St |
|---|---|---|---|
| REQ-SC-01 | Prototype only: designed to EMC best practice, **no formal EMC testing**, **no CE mark** affixed | SPEC §10 | B |

## 9. Architecture requirements derived from the block diagram and `.ioc` (`REQ-AR-*`)

These are not in `SPEC`; they are the agreed implementation of it. They are binding on the
CBs_1 design because the block diagram is the authoritative architecture.

| ID | Requirement | Source | St |
|---|---|---|---|
| REQ-AR-01 | Controller: STM32H723VET6 (LQFP100, CPN STM32H723VET6TR) | IOC, BD | B |
| REQ-AR-02 | Motor drive: DRV8323 gate driver + discrete FETs driving a 3-phase BLDC | BD, IOC | B |
| REQ-AR-03 | Motor PWM from TIM1 (3 complementary channels, break enabled) | BD, IOC | B |
| REQ-AR-04 | Phase current and DC-link (VBUS) sense into ADC1/ADC2, dual injected-simultaneous mode | BD, IOC | B |
| REQ-AR-05 | Gate driver configuration over SPI2 ("Config") | BD, IOC | B |
| REQ-AR-06 | Motor rotary encoder A/B/Z into TIM3 (encoder mode + ch3 direct); Hall sensors on GPIO | BD, IOC | B |
| REQ-AR-07 | Linear encoder A/B/Z into TIM5 (encoder mode + ch3 direct) after RS-422 → 3V3 conversion | BD, IOC | B |
| REQ-AR-08 | ADS1235 on SPI3, config + data, with nDRDY interrupt | BD, IOC | B |
| REQ-AR-09 | ADS1235 data/master clock from STM32 MCO2 | BD, IOC | B |
| REQ-AR-10 | Temperature: ADS1120 ADC, RTD or NTC probes, on SPI2 | BD, IOC | B |
| REQ-AR-11 | Calibration data in an I2C1 EEPROM | BD, IOC | B |
| REQ-AR-12 | Force-profile RAM on OCTOSPI1 in quad (QSPI) mode | BD, IOC | B |
| REQ-AR-13 | USB-C → USB3320 ULPI PHY → USB_OTG_HS (device, high speed) | BD, IOC | B |
| REQ-AR-14 | Trigger output generated by TIM15 → SMA | BD, IOC | B |
| REQ-AR-15 | Debug header carrying USART3 UART **and** SWD | BD, IOC | B |
| REQ-AR-16 | HSE from an external clock source on PH0-OSC_IN only (PH1-OSC_OUT unallocated) | IOC | B |
| REQ-AR-17 | PoC build is a larger, development-board-style board preceding miniaturisation | SLOG, plan summary | B |

## Open questions

Tracked here, resolved into `DECISIONS.md` when answered.

| ID | Question | Why it matters | Owner |
|---|---|---|---|
| OQ-01 | Is `VBUS_MON` (PC5) the motor DC-link or USB VBUS presence? Provisionally allocated to the motor DC-link - see DEC-0011. | Decides whether the divider lives in `motor_drive` or `mcu`. | Captain |
| OQ-02 | Exact rail set and topology (5 V / 3V3 / analog): switcher vs LDO per rail, and whether the ADS1235/ADS1120 analog rail is separately regulated. | Sets the `power_rails` block contents; not covered by the block diagram, which is signal-only. | `power_rails` task |
| OQ-03 | Source of the HSE external clock on PH0-OSC_IN. Candidate: share one oscillator with the USB3320 (which needs a 24 MHz reference). | A single-pin external clock cannot be a bare crystal; needs a real oscillator or a driven clock. | `mcu` task |
| OQ-04 | Probe type for the two temperature channels: RTD or NTC (the block diagram permits both). | Sets ADS1120 excitation and the probe connectors. | `temp_sense` task |
| OQ-05 | Which of BTN_1 (PE0) / BTN_2 (PE1) is the REQ-CC-06 homing button, and what the other does. | Silkscreen and firmware contract only; not blocking. | Captain / firmware |
| OQ-06 | EEPROM write-protect (`nWP`) has no `.ioc` pin allocated. Tie off, or request a pin? | Affects `nvm_calibration` and may need an `.ioc` revision. | `nvm_calibration` task |
| OQ-07 | Rail PGOOD / enable lines have no `.ioc` pins allocated. | Same as OQ-06, for `power_rails`. | `power_rails` task |
| OQ-08 | Whether V10N needs a different current-sense shunt/gain to satisfy REQ-SF-03 "configurable per variant", or whether one shunt with a firmware threshold suffices. | Decides if `motor_drive` needs a build variant. | `motor_drive` task |
