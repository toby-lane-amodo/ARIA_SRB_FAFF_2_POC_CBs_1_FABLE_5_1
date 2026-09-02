# FAFF 2 CBs_1 - Test and Bring-Up Plan

The CBs_1 proof-of-concept is a **larger, development-board-style build that precedes
miniaturisation** (`REQ-AR-17`). Its job is to retire electronics risk fast, not to fit the
final mechanical package. Every design choice below trades board area for testability, and
that trade is deliberate.

This is house doctrine, not just a project preference — the EEE Hardware Design Standard draft
(`docs/HardwareDesignStandard_DRAFT/`) says it independently: "If your PCB is very space
constrained, and timelines allow, then you should consider making a 'big' first revision of the
board… Once you have proved the hardware, you can then miniaturise at a later date."

**Governing principle: every block must be independently testable.** A block that can only be
tested with the whole board working is a block that will be debugged last and slowest.

---

## 1. Process requirements

Before the board is ordered, not after.

| # | Requirement | Source |
|---|---|---|
| 1.1 | A firmware engineer reviews the schematic before fabrication. "If a board has a µC, probably shouldn't order without a firmware [engineer] at least reviewing the project so far." | Design Standard, *Designing Something with a Microcontroller* |
| 1.2 | Firmware development starts in parallel on a dev board, not when the PCB lands. FAFF 2 has timing-critical interfaces (TIM1 PWM + break, three quadrature decoders, 4800 SPS streaming), which is exactly the case the standard calls out. | Design Standard; `SLOG` (FAFF 1 close report: "Onboard SW/FW from the start") |
| 1.3 | The `.ioc` is maintained as the single pin-map authority and re-committed whenever it changes. Any schematic change that needs a new MCU pin goes through the `.ioc` first. | DEC-0013 |
| 1.4 | Every board built gets a serial number and an entry in a Notion hardware-tracking database recording build state, tests done, and every modification. | Design Standard, *Keeping Track of Hardware* |

## 2. Test point strategy

### 2.1 Type selection

From the AmodoKiCadLib, chosen per net rather than by default (DEC-0018):

| Part | Use for | Do not use for |
|---|---|---|
| `TestPoint` | 1.0 mm SMT pad. DC rails and static pin states checked with a DMM. | Anything you will scope — needs a wire soldered on. |
| `TestPointHook` | THT loop. Nets you will attach a scope probe or logic analyser to: I2C, SPI, GPIO, fault lines. | Nets where ringing/overshoot must be measured accurately. |
| `TestPointDual` | THT, signal hole plus a spring-ground hole. Nets where **signal integrity matters** — small measurement loop, minimal probe inductance, low magnetic pickup. | Where space genuinely forbids it. |

Where `TestPointHook` is used, place **GND hooks alongside** so the scope ground clip has
somewhere to go. Prefer through-hole test points generally, per the standard.

### 2.2 Where test points are forbidden

**No test points on the ULPI bus or the OCTOSPI/QSPI bus.** The standard: test coverage on
very high speed interfaces adds stub capacitance and an impedance discontinuity, and a
conventional passive probe will load or distort the signal. ULPI runs a 60 MHz clock with
single-digit-nanosecond edges; QSPI is comparable. This **overrides** the general "test point
on every key signal" rule for these two buses. DEC-0018 ruling 1.

If one of these ever must be observed, that is a job for a switched coaxial connector and an
active probe, not a hook — and we do not currently own a suitable active probe.

### 2.3 Coaxial access

Nets we expect to scope or inject into repeatedly get a coaxial connector rather than a test
point, so test gear connects with a stock cable:

- **SYNC/TRIGGER** — already an SMA jack by specification (`REQ-EL-06`).
- **Load cell bridge output** (`SIG+`/`SIG-`) — strong U.FL candidate. This is the net whose
  noise floor decides whether `REQ-FF-04` is met, and it will be measured many times.
- **A motor phase node and the DC link** — U.FL candidates for switching-waveform work.

U.FL is probed with the U.FL-to-BNC adapter cable stocked in the EEE lab.

## 3. Rail test points, isolation links and current breaks

Ownership follows the **producer-owns-the-break** rule (DEC-0007): the block that generates a
rail owns its test point, isolation link and current break.

### 3.1 Required per rail

Every supply rail on the board gets **all three**:

1. **A test point** on the rail, close to its point of use, not just at the regulator.
2. **An isolation link** — 0R link, jumper or solder bridge — so the rail can be brought up,
   or a downstream block cut loose, independently.
3. **A current-measurement break** — a series link that can be replaced by a current meter or
   a known shunt, so each block's consumption is measurable against the `CALC` power budget.

The standard mentions 0R links for power measurement as a practice its author personally
skips. The brief for this build **requires** them, and the brief outranks the standard
(DEC-0018). They stay: the whole point of a dev-board revision is measuring what you assumed.

### 3.2 Rail inventory

Provisional — the final rail set is **OQ-02**, since the block diagram is signal-only and shows
no power blocks. Structure, not the list, is what is being committed to here.

| Rail | Source block | Feeds | Budget check against `CALC` |
|---|---|---|---|
| `+24V_IN` | `power_entry_24v` | (pre-protection) | 25 W peak, 7 W typical |
| `+24V_SW` | `power_entry_24v` | `power_rails`, `motor_drive` | motor Iq 20 mA quiescent |
| `+5V` | `power_rails` | bridge excitation, IKP11 read head | 200 mA encoder + 15 mA load cell |
| `+3V3` | `power_rails` | STM32, USB3320, DRV8323 logic, QSPI, EEPROM | 500 mA STM32 + 500 mA other ICs |
| analog rail(s) / VREF | `power_rails` | ADS1235, ADS1120 | part of the 5.185 W quiescent total |

### 3.3 Block isolation

Between power stages, and between the MCU and **each** peripheral block, provide a link that
can be opened:

- `power_entry_24v` → `power_rails`, and `power_entry_24v` → `motor_drive`: independent links,
  so the motor stage can be left unpowered while logic is brought up. This one matters most —
  it lets the whole board be exercised with no possibility of the actuator moving.
- `power_rails` → each of `mcu`, `loadcell_afe`, `linear_encoder`, `temp_sense`,
  `nvm_calibration`, `ui_io`: per-block rail links.
- MCU-to-peripheral **signal** isolation on the shared buses, so one peripheral can be removed
  from a bus that will not enumerate: SPI2 (shared by `motor_drive` and `temp_sense` —
  see `ARCHITECTURE.md §5`), SPI3, I2C1.
- The two **TIM1 BREAK** nets (`DRV8323_nFAULT`, `LIMIT_nBRK`) get links so each trip source
  can be exercised alone. These links are safety-relevant: they must be clearly marked on the
  silkscreen and must default to **fitted**.

## 4. Per-block test provisions

What each block owns. Block tasks add these while drawing.

| Block | Must provide |
|---|---|
| `power_entry_24v` | TPs on `+24V_IN`, `+24V_SW`, `PGND`; current break on `+24V_SW`; TP on `V24_MON`; reverse-polarity and fuse behaviour testable without downstream load |
| `power_rails` | TP + isolation link + current break per rail (§3); TP on each feedback node; PGOOD TPs if fitted |
| `mcu` | SWD + USART3 to `test_debug`; TPs on `NRST`, `BOOT0`, each supply pin group, HSE clock in, MCO2. **No TPs on ULPI or QSPI** (§2.2). USB-C shield/CC access |
| `motor_drive` | TPs on each gate drive output, each current-sense output, `VBUS_MON`, `nFAULT`; U.FL candidate on one phase node and the DC link; link to isolate the gate driver supply; means to spin the motor with the load cell disconnected |
| `loadcell_afe` | TPs on excitation +/-, sense +/-, `SIG+`/`SIG-` (U.FL candidate), ADC reference, `nDRDY`; SPI3 hooks; link to configure 4-wire vs 6-wire (DEC-0014); means to substitute a resistive bridge simulator for the load cell |
| `linear_encoder` | TPs on each RS-422 receiver output (`ENC_A/B/Z`) and on the 5 V read-head supply; termination fitted/removable; header pinout silkscreened; means to inject a quadrature signal without the read head |
| `temp_sense` | TPs on both probe channels and the ADC reference; SPI2 hooks; means to substitute a fixed resistor for each probe |
| `nvm_calibration` | I2C1 hooks (`SCL`, `SDA`) plus GND hooks; `nWP` TP; pull-ups on removable links |
| `ui_io` | TPs on `SYNC_TRIG` (pre- and post- source termination), `LIM_A`, `LIM_B`, `LIMIT_nBRK`, each button and LED net; means to assert each limit switch without the mechanics |
| `test_debug` | SWD + USART3 debug header (one header, per the block diagram); consolidated rail probe header; GND hooks distributed for scope clips |

## 5. Bring-up order

Each step is a gate: do not proceed until it passes. Steps 1-4 run with **every** downstream
isolation link open and the motor stage unpowered.

| # | Step | Pass criterion |
|---|---|---|
| 1 | **Bare-board and power entry.** 24 V in, all rail links open. Check protection, inrush, fusing. | `+24V_SW` correct; reverse polarity does not damage; no smoke; `V24_MON` reads correctly by DMM |
| 2 | **Rails, one at a time.** Close one rail link at a time, no load beyond the rail's own decoupling. | Each rail within tolerance; ripple acceptable; quiescent current per rail measured at its break and reconciled against `CALC` |
| 3 | **MCU alive.** Power `mcu` only. HSE clock present, reset behaves, SWD connects. | Debugger attaches; MCO2 output present at the expected frequency; blinky on `LED_1` |
| 4 | **Debug console.** USART3 over the debug header. | Characters out and in at the expected baud |
| 5 | **NVM.** Close the `nvm_calibration` link. | EEPROM reads and writes over I2C1; device ID as expected |
| 6 | **Load cell AFE.** Close the link. Use a resistive bridge simulator before a real load cell. | ADS1235 responds over SPI3; `nDRDY` toggles at 4800 SPS; **measured input-referred noise meets `REQ-FF-04`** with a shorted/simulated bridge. This is the single most important electrical result on the board |
| 7 | **Sensors.** Temperature (§4 substitute resistors), then the linear encoder with an injected quadrature signal, then with the real IKP11. | ADS1120 reads both channels to `REQ-EL-07`; TIM5 counts up and down correctly and the Z index lands where expected |
| 8 | **Safety interlocks — before any motor power.** With `+24V_SW` to `motor_drive` still **open**, assert each limit switch and each `nFAULT` source in turn and confirm TIM1 outputs go inactive. | Both BREAK paths independently force PWM inactive, verified at the gate-drive test points. **Gate for step 9** |
| 9 | **Motor drive, no mechanics.** Close the motor stage link with the motor **disconnected from the actuator**. Open loop, low duty. | Gate waveforms clean; phase currents read plausibly on all three channels; `VBUS_MON` correct; DRV8323 configures over SPI2 |
| 10 | **Motor on the actuator, no load cell in the force path.** Closed-loop position using the linear encoder; homing against the limit switches. | Homing repeatable; position tracks to `REQ-PS-01..03`; travel stops at both limits |
| 11 | **Full force loop.** Load cell in the path, current limit set per `REQ-SF-03` **before** the first move. | Static force hold within `REQ-FF-03`; current limit trips before 150 % of load cell absolute maximum |
| 12 | **Streaming and sync.** USB enumeration, 4800 SPS stream, SMA trigger output. | Enumerates as high speed; no dropped samples at 4800 SPS (`REQ-CC-03`); SYNC edge correct into 50 Ω |
| 13 | **System characterisation.** Force loop bandwidth, cycle-speed overshoot. | `REQ-ME-06` 40 Hz small-signal; overshoot within `REQ-ME-04`/`05` |

Steps 8 and 11 are the two where a mistake damages the load cell. Neither may be shortcut.

## 6. Records to produce

| Deliverable | Where |
|---|---|
| Serial-numbered build and modification state for every board | Notion hardware-tracking database (Design Standard, *Keeping Track of Hardware*) |
| Measured rail voltages and per-block currents vs the `CALC` budget | Bring-up report, step 2 |
| Measured AFE noise floor vs `REQ-FF-04` | Bring-up report, step 6 |
| Evidence that both TIM1 BREAK paths work | Bring-up report, step 8 |
| Any schematic or layout change found during bring-up | Repo, plus the hardware log |

## 7. What this plan does not yet cover

- **Rail-level detail** — count, topology and sequencing are OQ-02.
- **EMC pre-compliance.** `REQ-SC-01` says no formal testing and no CE mark. The Design
  Standard's argument still applies: EMC practice is followed to avoid intra-system problems
  ("an IC's reset pin routed too close to a switchmode supply, causing spurious reset"), not to
  pass a test. Layout-wave concern.
- **Probe-type-specific setups** for the miniaturised revision, which does not exist yet.
