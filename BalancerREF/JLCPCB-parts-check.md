# JLCPCB / LCSC assembly check, Rev F BOM

Stock figures marked with a date are from LCSC/JLCPCB listings on that day; everything
else is unchecked. Re-check before ordering. "Basic" parts carry no per-part feeder fee;
everything else is "extended" (about $3 per unique part). Resistors are 0603 and
capacitors 0805 (C20 is 1210) in the current schematic; both sizes are JLCPCB basic for
common values.

| Ref | Part | LCSC / JLCPCB | Action |
|---|---|---|---|
| U1 | ESP32-S3-MINI-1-N8 | C2913206, ~2000 in stock, ~$3.14 (2026-09-09) | order as is (extended) |
| U2 | IIS3DWBTR | C717702, in stock, ~$16 (2026-09-09) | order as is (extended) |
| U3 | LM1815MX/NOPB | C2878578, only 3 in stock, ~$2.78 (2026-09-09) | consign from Digi-Key, or accept quantity risk |
| U4 | TS3021IYLT (head) | not listed; TS3021ILT C1509142 in stock (2026-09-09) | substitute TS3021ILT: same SOT-23-5 pinout, non-automotive grade |
| U5 | BQ24075RGTR | not checked | verify at order time; QFN-16, expected extended |
| U6 | TPS63031DSKR | C15516, ~6k in stock, ~$0.62 (2026-09-09) | order as is |
| U7 | SRV05-4MR6T1G | C604719, only 20 in stock, ~$1.94 (2026-09-09) | order early or consign; any SRV05-4 equivalent in SOT-23-6 with the same pinout is acceptable |
| U8 | TLV9062IDR (head) | not checked | verify at order time |
| U9 | SN74LVC1G132DBVR | not checked | verify at order time. NOT the 1G08: the circuit depends on Schmitt inputs and NAND polarity |
| U10 | SN74LVC1G123DCTR | C123302, in stock, ~$0.14 (2026-09-09) | order as is |
| Q1 (head), Q4 | AO3400A / AO3401A | JLCPCB basic | order as is |
| D1 (head) | XPEBRD-L1 (Cree XP-E2 red) | not carried by LCSC | consign from Digi-Key, or hand-place after assembly |
| D3 | SMF5.0A | expected extended | verify at order time |
| PD1 (head) | BPW34S | LCSC stocks VBPW34S C145262 (2026-09-09), Vishay's current PN for the same SMD part | use VBPW34S; same footprint |
| J1 | USB4105-GF-A | USB4105-GF-A-120 C5184243 and -060 C3025063 in stock (2026-09-09) | use -120 or -060: same connector, different packaging quantity |
| J2 | JST B2B-PH-K-S | JLCPCB basic | order as is |
| J4 | 1x05 2.54 header | basic | order as is or hand-solder |
| J5 (both boards) | JST SM07B-GHS-TB | not checked | verify at order time |
| L1 | DFE201612PD-1R5M=P2 | not checked | verify; many 2016 1.5 uH alternatives exist if not |
| SW1 | Wurth 450301014042 | not expected at LCSC | hand-solder (through-hole) or consign |
| SW2, SW3 | 6 mm tactile | many basic options | choose an LCSC basic tactile matching the assigned footprint |
| R3, R35, R36 | 3.57k 1%, 1.6k, 10k (charger set resistors) | basic 0603 | order as is; R3 must be 1% |
| R13, R14 | 10k 1206 pulse | basic 1206 | order as is |
| R18 (head) | 3R9 1206 0.5 W | basic 1206 | order as is (was 3R0 before Rev F) |
| C20 (head) | 100 uF 10 V 1210 | verify | 10 V rating is deliberate: SYS_SW can reach 5.5 V |
| TP1-3, 7, 9, 10 | test pads | no part | none |

**Practical order plan:** let JLCPCB place everything they stock, hand-solder or consign
D1, SW1, and if quantity is short, U3 and U7. Upload the exported BOM and CPL to their
tool for the definitive basic/extended split; this table is a pre-check, not a quote.
