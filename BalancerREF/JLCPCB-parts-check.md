# JLCPCB / LCSC assembly check, Rev C BOM (checked 2026-09-09)

Stock figures are from LCSC/JLCPCB listings on the day; re-check before ordering. "Basic" parts carry no per-part feeder fee; everything else is "extended" (about $3 per unique part). Passives were moved to 0805 on 2026-09-09 (28 resistors and LED1; capacitors were already 0805/1210); 0805 R/C are JLCPCB basic parts.

| Ref | Part | LCSC / JLCPCB | Action |
|---|---|---|---|
| U1 | ESP32-S3-MINI-1-N8 | C2913206, ~2000 in stock, ~$3.14 | order as is (extended) |
| U2 | IIS3DWBTR | C717702, in stock, ~$16 | order as is (extended) |
| U3 | LM1815MX/NOPB | C2878578, only 3 in stock, ~$2.78 | consign from Digi-Key, or accept quantity risk |
| U4 | TS3021IYLT | not listed; TS3021ILT C1509142 in stock (~100k) | substitute TS3021ILT: same SOT-23-5 pinout and specs, non-automotive grade |
| U5 | MCP73831T-2ACI/OT | C424093, ~11k in stock, ~$0.39 | order as is |
| U6 | TPS63031DSKR | C15516, ~6k in stock, ~$0.62 | order as is |
| U7 | SRV05-4MR6T1G | C604719, only 20 in stock, ~$1.94 | order early or consign; any SRV05-4 equivalent in TSOP-6 with the same pinout is acceptable |
| U8 | TLV9062IDR | not checked; common TI part, expected extended | verify at order time |
| U9 | SN74LVC1G08DBVR | common; expected basic or extended | verify at order time |
| U10 | SN74LVC1G123DCTR | C123302, in stock, ~$0.14 | order as is |
| Q1 / Q3, Q4 | AO3400A / AO3401A | JLCPCB basic parts | order as is |
| D1 | XPEBRD-L1 (Cree XP-E2 red) | not carried by LCSC | consign from Digi-Key, or hand-place after assembly (one 3535 part) |
| D2 | PMEG4010CEH | expected extended | verify at order time |
| D3 | SMF5.0A | expected extended | verify at order time |
| PD1 | BPW34S | LCSC stocks VBPW34S C145262 (~3.9k, ~$0.27), Vishay's current PN for the same SMD part | use VBPW34S; same footprint |
| J1 | USB4105-GF-A | out of stock; USB4105-GF-A-120 C5184243 (~1.2k) and -060 C3025063 in stock | use -120 or -060: same connector, different packaging quantity |
| J2 | JST B2B-PH-K-S | JLCPCB basic | order as is |
| J4 | 1x05 2.54 header | basic | order as is or hand-solder |
| SW1 | Wurth 450301014042 | not expected at LCSC | hand-solder (through-hole) or consign |
| SW2-4 | 6 mm tactile | many basic options | choose an LCSC basic tactile matching the assigned footprint |
| L1 | DFE201612PD-1R5M=P2 | not checked | verify; many 2016 1.5 uH alternatives exist if not |
| R13, R14, R18 | 1206 pulse / 3R0 0.5 W | basic 1206 resistors | order as is |
| TP1-14 | test pads | no part | none |

**Practical order plan:** let JLCPCB place everything they stock, hand-solder or consign D1, SW1, and if quantity is short, U3 and U7. Upload the exported BOM and CPL to their tool for the definitive basic/extended split; this table is a pre-check, not a quote.
