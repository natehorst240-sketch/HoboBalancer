# Balancer Rev A schematic

The single A1 sheet contains 111 physical components (104 plus the U9 display buck section added 2026-09-08), with real KiCad wire segments and explicit junctions within circuits. Local net labels connect the sections. The separate Hirose microSD socket is removed; the Newhaven module provides microSD. USB-C is charge-only and J5 is the SWD interface. The board file has not been updated from this schematic.

## Display supply

DS1 J2.2 VIN is powered from U9, a TPS62260DDCR 600 mA buck on +5V, output +3V3_DISP = 0.6 x (1 + R32 453k / R33 100k) = 3.32 V, with L3 2.2 uH (DFE322520FD-2R2M), C43 10 uF in, C44 10 uF out, C45 22 pF feed-forward. The NHD-2.8C-CSXP-BREAKOUT datasheet specifies VDD 3.0-3.6 V, 200 mA typical / 280 mA maximum; 5 V must not be applied.

The display signal map uses WRX, J1.3, for LCD D/C. J1.2 is left open because it is the clock alias; J2.13 supplies SCK. For 4-wire SPI, close module R2/R3/R5 and open R1/R4/R6 per the current manufacturer interface table. Touch and card-detect are unused.

## Electrical implementation

- U8 pin 21 is VDDA, not VDD. It and VREF+ pin 20 connect to +3V3_A. MCU VDD pins 24/36/48 and VBAT pin 1 connect to +3V3, with decouplers provided. NRST is the PG10/NRST pin.
- Q1 SST507 is 1.8 mA nominal. Pins 2 and 3 are wired together to ACCEL_ICP. C1 is the specified 1 uF / 50 V AC-coupling part. BAT54S D1 clamps only the ADC-side signal after the OPA2320 and R5; no low-voltage TVS is placed on the raw ICP line. The second BAT54S from the original placement list is omitted because the supplied Rev A circuit uses one.
- The VCM divider capacitors are parallel to ground. The OPA2320 includes both follower circuits and its power unit. C4 connects differentially across ADC inputs 3 and 4. ADC pins 7-10 are explicitly NC, and CAP has 220 nF to GND.
- X1 drives the ADC clock and MCU HSE through separate 33 ohm resistors. MCU firmware must enable HSE bypass and TIM2_CH1 on PA0, and compensate ADC/analog filter delay when calculating phase.
- All analog and digital grounds use one electrical GND net. The analog region is annotated AGND; there is no split ground island or conflicting AGND net.
- BQ24074 EN1 connects to OUT and EN2 to ground for USB500 mode. The 10 kohm TS resistor disables battery temperature sensing as specified. The power switch is after OUT, allowing charging while the instrument is switched off.
- F1 uses Bourns MF-MSMF010-2, 100 mA hold / 300 mA trip, 1812. FB2 filters the tach supply. External button pullups and two LED series resistors are included.

## Footprints and purchasing details

All 100 PCB components have footprints with matching symbol-pin and footprint-pad number sets. Parts-footprint-map.csv lists the current references, values, MPNs, and footprints; RevA-pin-connections.csv lists every physical symbol pin and its connection or NC status.

The specified ICs, oscillator, inductors, diode, ferrites, AC-coupling capacitor, USB connector, and 24 V bulk capacitors retain their selected manufacturer parts. Newly specified generic resistors, capacitors, LEDs, buttons, and headers have package footprints but still require purchasing MPN selection. Resistors use 0805 with a 1% selection requirement. Capacitors use 0805, or 1210 for the generic 10/22 uF parts; select parts that meet the stated voltage, dielectric and effective capacitance requirements. C23/C24 are the selected C2012X7R1H225K125AC 2.2 uF / 50 V parts.

J1/J2 are panel-mounted MS3112E8-4S solder-cup receptacles, BT1 is the off-board Adafruit battery, and SW1 is the off-board power switch. They are included in the BOM and excluded from PCB placement. No PCB land pattern exists for those panel receptacles; the board-to-panel harness landing arrangement still needs mechanical selection. J4 is the battery's JST-PH board mate; J6 is the switch's board header. Verify the actual pack's red BAT+ and black GND wires against J4 before mating. Select SW1 for at least 1 A DC.

DS1's custom footprint represents the module mating interface with two 1x20 headers and four mounting holes, viewed from the display side. Pad numbers J1.1-J1.20 and J2.1-J2.20 identify the module's separate headers. Header drill/pad sizes are 1.0/1.8 mm for 2.54 mm pitch, mounting holes 3.2 mm, row separation 78.70 mm, and module envelope 69.03 x 85.20 mm. Final header purchasing and standoff clearance remain mechanical integration choices. The inductor land patterns follow Murata's drawings; SS14FL uses MCC DO-221AC, not SMA/SOD-123F.

## Verification

KiCad 10.0.3 successfully opens, renders, and exports the schematic. An exported netlist was compared against the authored pin-to-net manifest, checking missing pins, opens, unintended connected NC pins, and shorts between intended nets. No discrepancies were found. ERC reports zero errors and zero warnings as of 2026-09-08; the earlier DISPLAY_VIN_PENDING warning is resolved because DS1 J2.2 now connects to +3V3_DISP from U9. No ERC exclusions were added to hide circuit findings. The buck section was added with `.codex-parts/add_display_buck.py`; the prior state is in Balancer-backups/before-display-buck-20260908-060647. Matching pin/pad numbers verifies connectivity compatibility; it does not replace final mechanical, power/thermal, or bench validation.

Checks and source downloads are retained in .codex-parts. The schematic and project state before this installation are backed up at Balancer-backups/before-rev-a-install-20260906-183830.

## Manufacturer references

- [STM32G491 datasheet](https://www.st.com/resource/en/datasheet/stm32g491ce.pdf)
- [ADS131M02 datasheet](https://www.ti.com/lit/ds/symlink/ads131m02.pdf)
- [OPA2320 datasheet](https://www.ti.com/lit/ds/symlink/opa320.pdf)
- [Newhaven exact module datasheet](https://newhavendisplay.com/content/specs/NHD-2.8C-CSXP-BREAKOUT.pdf)
- [Newhaven exact module product page](https://newhavendisplay.com/tft-breakout-module-with-sunlight-readable-2-8-inch-ips-tft-display-capacitive-touchscreen/)
- [DSS MicroVib cable pinouts](https://www.dssmicro.com/faqs/faq_mv1_cable_repair_pinouts.htm)
- [ECS oscillator](https://ecsxtal.com/store/pdf/ECS-2520MVLC.pdf)
- [BQ24074 datasheet](https://www.ti.com/lit/ds/symlink/bq24074.pdf)
- [TPS61023 datasheet](https://www.ti.com/lit/ds/symlink/tps61023.pdf)
- [TPS61041 datasheet](https://www.ti.com/lit/ds/symlink/tps61041.pdf)
- [74LVC1G17 datasheet](https://www.diodes.com/datasheet/download/74LVC1G17.pdf)
- [USB4105 drawing](https://gct.co/files/drawings/usb4105.pdf)
- [Bourns resettable fuse](https://bourns.com/docs/product-datasheets/mf-msmf.pdf)
- [Murata LQH32PN land pattern](https://search.murata.co.jp/Ceramy/image/img/P02/JELF243A-0061.pdf)
- [Murata DFE322520FD land pattern](https://pim.murata.com/asset/pim4/inductor/J(E)TE243A-9104_PDF_INDUCTOR)
- [Adafruit battery](https://www.adafruit.com/product/258)
