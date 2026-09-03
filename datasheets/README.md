# Datasheets

Collect datasheets for the parts below as blocks are designed. Keep the manufacturer's own PDF
where possible, named `<MPN>.pdf`.

Note that KiCad symbols must carry a **working web URL** in their Datasheet field (pressing `d`
in KiCad opens it) — these local copies are for offline reference, not a substitute.

## Collected

| File | Part | Block | Revision |
|---|---|---|---|
| `250721_IKP11_technical_data_sheet.pdf` | Bogen IKP11 | `linear_encoder` | rev 3.7, 2025-07-21 (supersedes the rev linked below) |
| `LMR51610.pdf` | TI LMR51606/LMR51610 buck | `power_rails` | SLUSEY1B, Dec 2023 - added for the `U301` swap, review round 1 batch 2 |

## Fixed parts

✅ = collected, see above.

| Part | Block | Notes |
|---|---|---|
| STM32H723VET6 | `mcu` | LQFP100. Datasheet + RM0468 reference manual. CPN `STM32H723VET6TR` |
| USB3320 | `mcu` | USB 2.0 ULPI transceiver |
| DRV8323 | `motor_drive` | 3-phase gate driver, SPI variant, 3 integrated current-sense amplifiers |
| TI ADS1235 | `loadcell_afe` | 24-bit bridge ADC. **Symbol already exists in `Amodo_ADCs.kicad_sym`** |
| TI ADS1120 | `temp_sense` | 16-bit ADC with PGA and IDACs, for RTD/NTC |
| HBK S2M | `loadcell_afe` | Load cell, 10 N and 50 N variants. Datasheet + wiring diagram (4- and 6-wire) |
| Bogen IKP11 ✅ | `linear_encoder` | `IKP11-Z1.4-P1-V5-D1-R0.5-F1000-C1`. Local: `250721_IKP11_technical_data_sheet.pdf` (rev 3.7). Web: [technical data sheet](https://www.bogen-magnetics.com/media/450/t-file/240802_IKP11_technical_data_sheet-1.pdf) — note that URL serves the older 2024-08-02 revision |
| Bogen LMS-I1-L70-W5-A03-K | (mechanical) | Magnetic scale, adhesive backed, ±3 µm accuracy class |
| KPJX-4S | `power_entry_24v` | Latching circular power connector, 4-way |

## To be selected

| Part | Block | Notes |
|---|---|---|
| QSPI RAM / memory | `mcu` | For force profiles, on OCTOSPI1 in quad mode |
| I2C EEPROM | `nvm_calibration` | Calibration and compensation data |
| Power FETs (×6) | `motor_drive` | 24 V, sized around 1.229 A phase working point |
| Rail regulators | `power_rails` | Set undecided — see OQ-02 |
| RS-422 receiver | `linear_encoder` | 3 channels (A/B/Z), 5 V in → 3V3 logic out |
| Temperature probes (×2) | `temp_sense` | RTD or NTC — see OQ-04 |
| USB-C receptacle, SMA jack | `mcu`, `ui_io` | |
| ESD protection devices | interfaces | USB-C, SMA, encoder, limit switch inputs |

## Explicitly NOT needed

**USB-PD / CYPD-class controllers.** FAFF 1 used a CYPD3177-class part; FAFF 2 has a dedicated
24 V supply and the USB-C port carries data only. Do not collect these. See DEC-0001, DEC-0002.
