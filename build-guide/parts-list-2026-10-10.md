# Hand-assembly parts list, boards ordered 2026-10 (carrier 37 footprints, head 31)

Pad maps: `BalancerCarrier-pads-top.png`, `BalancerREF_OptHead-pads-top.png`,
`BalancerREF_OptHead-pads-bottom.png`. Red pad = pad 1 (pin 1, cathode, or gate).

## BalancerCarrier, all top side

| Ref | Part | Package | Pad 1 / notes |
|---|---|---|---|
| U1 | Unexpected Maker FeatherS3[D] (Adafruit 6399) on Sullins PRPC016SAAN-RC headers | 16 + 12 pin rows, 2.54 mm | Red hole = pin 1 (VBAT). Cut one 16-pin header to 12. |
| U2 | TI LM1815MX/NOPB | SOIC-14 | Red pad = pin 1 |
| U3 | TI SN74LVC1G132DBVR | SOT-23-5 | Red pad = pin 1 |
| U4 | TI SN74LVC1G123DCTR | SSOP-8 0.65 mm | Red pad = pin 1 |
| U5 | ST IIS3DWBTR | LGA-14 | Red pad = pin 1; see datasheet dot |
| J3 | two solder-wire pads for the VR pickup lead | 3.6 mm pitch | Square pad = pin 1 (MAG+) |
| J4 | TE 825434-5, 1x5 header | 2.54 mm | Square hole = pin 1 |
| J5 | JST SM07B-GHS-TB | GH 1.25 mm, 7 way + 2 tabs | Red pad = pin 1; solder both big tabs |
| LED1 | Lite-On LTST-C190GKT green | 0603 | Red pad = cathode (K) |
| SW1 | Same Sky TS02-66-60-BK-260-SCR-D | 6 mm tactile, through-hole | 4 pins, no polarity. Right side of board, not where the silkscreen says |
| R5, R6 | Yageo RC1206FR-0710KL 10k | 1206 | |
| R7 | Yageo RC0603FR-07150KL 150k 1% | 0603 | |
| R8 | Yageo RC0603FR-071M6L 1.6M | 0603 | |
| R9 | Yageo RC0603FR-075K6L 5.6k | 0603 | |
| R10, R14 | Yageo RC0603FR-0710KL 10k | 0603 | |
| R11, R15 | Yageo RC0603FR-071KL 1k | 0603 | |
| R12, R13 | Stackpole RMCF0603FT100K 100k | 0603 | |
| C2 | Murata GRM2165C1H102JA01D 1 nF C0G | 0805 | |
| C3 | Samsung CL21B334KBFNNNE 330 nF | 0805 | |
| C4 | Murata GRM2195C1H103JA01D 10 nF C0G | 0805 | |
| C5 | Murata GRM2165C1H471JA01D 470 pF C0G | 0805 | |
| C6 | Samsung CL21B103KBANNNC 10 nF X7R (C0G preferred) | 0805 | |
| C7, C8, C11, C12, C14 | Samsung CL21B104KBCNNNC 100 nF | 0805 | |
| C9 | Samsung CL21A106MPFNNNE 10 uF 10 V | 0805 | |
| H1 to H5 | M2 mounting holes | | no part |

## BalancerREF_OptHead

Top side:

| Ref | Part | Package | Pad 1 / notes |
|---|---|---|---|
| D1 | Cree XPEBRD-L1-0000-00501 red LED | XP-E2 3.45 mm | Red pad = cathode (K); centre pad is thermal, solder it |
| PD1 | ams OSRAM SFH 2440 photodiode | DIL SMD 4.5 x 4 mm | Red pad = cathode (K); check the cathode mark on the part |
| Q1 | Alpha and Omega AO3400A | SOT-23 | Red pad = gate (pin 1) |
| U4 | ST TS3021IYLT comparator | SOT-23-5 | Red pad = pin 1 |
| U8 | TI TLV9062IDR op amp | SOIC-8 | Red pad = pin 1 |
| J5 | JST SM07B-GHS-TB | GH 1.25 mm, 7 way + 2 tabs | Red pad = pin 1; solder both big tabs |
| R18 | Panasonic ERJ-8BQF3R9V 3.9 ohm 0.5 W | 1206 | must stay 1206 |
| R21 | Yageo RC0603FR-074K99L 4.99k | 0603 | |
| R22, R24, R25, R27 | Yageo RC0603FR-0710KL 10k | 0603 | |
| R23 | Yageo RC0603FR-07240KL 240k | 0603 | |
| R26 | Panasonic ERJ-3EKF2202V 22k | 0603 | |
| R28 | Yageo RC0603FR-07470KL 470k | 0603 | |
| R32 | Yageo RC0603FR-0733RL 33 ohm | 0603 | |
| C20 | Taiyo Yuden LMK325BJ107MM-T 100 uF 10 V | 1210 | |
| C21 | KEMET C0805C470J5GACTU 47 pF C0G | 0805 | |
| C22 | Samsung CL21B103KBANNNC 10 nF | 0805 | |
| C23, C24, C25 | Samsung CL21B104KBCNNNC 100 nF | 0805 | |
| FID1 to FID3 | fiducials | | no part |
| H1 to H4 | M2 mounting holes | | no part |

Bottom side:

| Ref | Part | Package |
|---|---|---|
| R19 | Panasonic ERJ-3EKF1000V 100 ohm | 0603 |
| R20 | Stackpole RMCF0603FT100K 100k | 0603 |

Off-board for the head: Ledil FA10887_TINA-RS lens over D1, retroreflective tape on the blade.
