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

Settled by the block wave; the structure below is what is actually drawn. `power_rails` feeds
its logic branch from **`V24_LOGIC`**, a second protected branch out of `power_entry_24v`
independent of the motor branch, so the motor stage can be left dead while logic is brought up.

| Rail | Source block | Feeds | Break / link | Budget check against `CALC` |
|---|---|---|---|---|
| `+24V_IN` | `power_entry_24v` | (pre-protection) | — | 25 W peak, 7 W typical |
| `+24V_SW` | `power_entry_24v` | `motor_drive` only | `R203` | motor Iq 20 mA quiescent |
| `V24_LOGIC` | `power_entry_24v` | `power_rails` | `R204` | logic branch, ~5.8 W in |
| `+6V0` | `power_rails` | pre-regulator for `+5V` / `+5VA` | `R305` | 6.110 V nominal, sheet-local, never leaves `power_rails` (`DEC-P10`) |
| `+5V` | `power_rails` | IKP11 read head | `R306` | ~115 mA |
| `+5VA` | `power_rails` | ADS1235 AVDD + bridge excitation, ADS1120 AVDD | `R307` | ~30 mA |
| `+3V3` | `power_rails` | STM32, USB3320, DRV8323 logic, QSPI, EEPROM | `R312` | ~1.1 A |
| `+3V3A` | `power_rails` | MCU VDDA / VREF+, ADS1235 and ADS1120 DVDD | `FB301` | ~10 mA |

### 3.3 Block isolation

**What the block wave actually drew**, reconciled at integration. The original plan here asked
for a rail link from `power_rails` to each consumer block; that is *not* what landed, and the
reason is sound. Every block takes the same global rail net, so per-consumer links inside
`power_rails` would need per-block rail names and would have broken the frozen block contracts.
The rule adopted instead: **`power_rails` owns one break per rail (§3.2), and a block that wants
its own supply break fits a 0R at its own supply entry, inside its own sheet.**

Thirty-two 0R links are drawn across the project. The ones that matter for bring-up:

| Link | Sheet | Opens |
|---|---|---|
| `R203` | `power_entry_24v` | the whole 24 V motor branch — **the one that keeps the actuator dead** |
| `R204` | `power_entry_24v` | the 24 V logic branch into `power_rails` |
| `R305` `R306` `R307` `R312` `FB301` | `power_rails` | one rail each, per §3.2 |
| `R1101` + `R1102` | `motor_drive` | the motor bus at the block, in series with `R203` |
| `R1114` | `motor_drive` | the DRV8323 gate-driver supply `VM_DRV`, leaving the bus up |
| `R1106` / `R1107` | `motor_drive` | rotary-encoder supply select, 3V3 or 5 V |
| `R601` | `linear_encoder` | the 5 V read-head feed — its current break |
| `R1012` | `mcu` | `+3V3_USB` |
| `R506`-`R510` | `loadcell_afe` | the 4-wire / 6-wire build (DEC-0014) |
| `R520` / `R521` | `loadcell_afe` | ADS1235 `CLKIN` source select |
| `R708`-`R711` | `temp_sense` | the 3-wire RTD build on each probe channel |

Signal isolation on the shared buses, so one peripheral can be taken off a bus that will not
enumerate:

| Link | Bus | Takes off |
|---|---|---|
| `R801` / `R802` | I2C1 | the EEPROM, with the bus left pulled up |
| `R1116` / `R1117` | SPI2 | the DRV8323's `SCLK` / `SDI` |

SPI3 has no series link: `loadcell_afe` is the only device on it, so opening the bus and
opening the block's own supply are the same test.

The two **TIM1 BREAK** nets each have their own break — `R1119` on `DRV8323_nFAULT` in
`motor_drive`, `R915` on `LIMIT_nBRK` in `ui_io` — so each trip source can be exercised alone.
These links are safety-relevant: they must be clearly marked on the silkscreen and default to
**fitted**. Both are.

## 4. Per-block test provisions

What each block owns. Block tasks add these while drawing.

| Block | Must provide |
|---|---|
| `power_entry_24v` | TPs on `+24V_IN`, `+24V_SW`, `PGND`; current break on `+24V_SW`; TP on `V24_MON`; reverse-polarity and fuse behaviour testable without downstream load |
| `power_rails` | TP + isolation link + current break per rail (§3); TP on each feedback node; PGOOD TPs if fitted; the consolidated rail probe header `J301`, moved here from `mcu` in review round 4 |
| `mcu` | The SWD + USART3 debug header (block H, `J1003`, now the STM32 14-way IDC part) and the GND hooks for scope clips (K) — test coverage lives on the page it covers, so these are not a sheet of their own. TPs on `NRST`, `BOOT0`, each supply pin group, HSE clock in, MCO2. **No TPs on ULPI or QSPI** (§2.2). USB-C shield/CC access |
| `motor_drive` | TPs on each gate drive output, each current-sense output, `VBUS_MON`, `nFAULT`; U.FL candidate on one phase node and the DC link; link to isolate the gate driver supply; means to spin the motor with the load cell disconnected |
| `loadcell_afe` | TPs on excitation +/-, sense +/-, `SIG+`/`SIG-` (U.FL candidate), ADC reference, `nDRDY`; SPI3 hooks; link to configure 4-wire vs 6-wire (DEC-0014); means to substitute a resistive bridge simulator for the load cell |
| `linear_encoder` | TPs on each RS-422 receiver output (`ENC_A/B/Z`) and on the 5 V read-head supply; termination fitted/removable; header pinout silkscreened; means to inject a quadrature signal without the read head |
| `temp_sense` | TPs on both probe channels and the ADC reference; `J703` carries the whole SPI2 interface on one keyed logic-analyser plug; means to substitute a fixed resistor for each probe |
| `nvm_calibration` | I2C1 hooks (`SCL`, `SDA`) plus GND hooks; `nWP` TP; pull-ups on removable links |
| `ui_io` | TPs on `SYNC_TRIG` (pre- and post- source termination), `LIM_A`, `LIM_B`, `LIMIT_nBRK`, each button and LED net; means to assert each limit switch without the mechanics |

## 5. Bring-up order

Each step is a gate: do not proceed until it passes. **`R203` stays open until step 9** — the
motor branch is dead, so nothing can move, for every step up to and including the safety-
interlock gate.

The logic rails are global (§3.3), so steps 3 onward do not switch blocks on one at a time:
each rail comes up once at step 2 and every consumer on it is live from then on. What is
switched per block is the bus or supply link the block owns, and each step below names it.

| # | Step | Pass criterion |
|---|---|---|
| 1 | **Bare-board and power entry.** 24 V in, all rail links open. Check protection, inrush, fusing. | `+24V_SW` correct; reverse polarity does not damage; no smoke; `V24_MON` reads correctly by DMM |
| 2 | **Rails, one at a time.** With `R203` open (motor branch dead), close `R204`, then one rail break at a time - `R305`, `R306`, `R307`, `R312`, `FB301`. | Each rail within tolerance; ripple acceptable; quiescent current per rail measured at its own break and reconciled against `CALC`; `RAIL_PGOOD` LED `D303` lights and `TP308` reads high |
| 3 | **MCU alive.** `+3V3` and `+3V3A` up. HSE clock present at `TP1003`, reset behaves at `TP1002`, SWD connects on `J1003`. | Debugger attaches; MCO2 output present at the expected frequency; blinky on `LED_1` |
| 4 | **Debug console.** USART3 over the debug header. | Characters out and in at the expected baud |
| 5 | **NVM.** `R801` / `R802` fitted. | EEPROM reads and writes over I2C1; device ID as expected. Lift either link to prove the bus survives the device being removed |
| 6 | **Load cell AFE.** `+5VA` and `+3V3A` up (step 2). Use a resistive bridge simulator before a real load cell. | ADS1235 responds over SPI3; `nDRDY` toggles at 4800 SPS; **measured input-referred noise meets `REQ-FF-04`** with a shorted/simulated bridge. This is the single most important electrical result on the board |
| 7 | **Sensors.** Temperature (§4 substitute resistors) - with `R1116` / `R1117` open the ADS1120 has SPI2 to itself. Then the linear encoder with an injected quadrature signal, then with the real IKP11; meter the read head at `R601`. | ADS1120 reads both channels to `REQ-EL-07`; read-head current inside the `CALC` allowance; TIM5 counts up and down correctly and the Z index lands where expected |
| 8 | **Safety interlocks — before any motor power.** With `R203` still **open**, assert each limit switch and each `nFAULT` source in turn and confirm TIM1 outputs go inactive. Open `R915`, then `R1119`, to exercise each trip source alone. | Both BREAK paths independently force PWM inactive, verified at the gate-drive test points. **Both links refitted before step 9.** Gate for step 9 |
| 9 | **Motor drive, no mechanics.** Configure the DRV8323 over SPI2 with `R1114` open (gate-driver supply down) before closing `R203`; then unplug `J1103` so the motor is **disconnected from the actuator**. Open loop, low duty. | Gate waveforms clean; phase currents read plausibly on all three channels; `VBUS_MON` correct; DRV8323 configures over SPI2 |
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

- **`RAIL_PGOOD` at the MCU.** OQ-07 has still allocated no pin, so power-good is observable
  only at `D303` and `TP308` inside `power_rails` (DEC-0023). Firmware cannot read it.
- **EMC pre-compliance.** `REQ-SC-01` says no formal testing and no CE mark. The Design
  Standard's argument still applies: EMC practice is followed to avoid intra-system problems
  ("an IC's reset pin routed too close to a switchmode supply, causing spurious reset"), not to
  pass a test. Layout-wave concern.
- **Probe-type-specific setups** for the miniaturised revision, which does not exist yet.
