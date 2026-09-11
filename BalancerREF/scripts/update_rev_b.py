from pathlib import Path
p=Path(__file__).resolve().parent/'build_schematic.py'
s=p.read_text()
s=s.replace('CHARGE WITH SW1 OFF','CHARGES WITH SW1 ON OR OFF').replace('Rev A','Rev B').replace("node('rev','A')","node('rev','B')").replace('BAT_SW','SYS_SW').replace('C1-C20:','C1-C21:')
s=s.replace("place('SW1',('Switch','SW_SPST'),231.14,48.26,value='POWER',field=(231.14,39.37))\nroute('SW1',1,(223.52,48.26),(223.52,63.5));port('SW1',2,'SYS_SW',12.7)\n",'')
s=s.replace('No load sharing: switch OFF for charge termination.\\nUSB programming: battery fitted, switch ON.','Charging independent of SW1; see power sharing.\\nUSB programming: switch ON; battery optional.')
s=s.replace('VBUS_SENSE','SUPPLY_SENSE').replace('GPIO12 VBUS detect','GPIO12 supply ADC')
s=s.replace("rail('USB_VBUS',35.56,223.52)","rail('SYS_SW',35.56,223.52)")
s=s.replace('# VBUS divider for USB attach detection (not an unpowered supply connection).','# Switched supply divider: cannot back-power the MCU when SW1 is OFF.')
s=s.replace('USB attach detection: about VBUS / 2.','Supply ADC: SYS_SW / 2; dead when OFF.')
block="""
# Microchip AN1149 directional power sharing: PMOS D=BAT, S=SYS.
box('USB / BATTERY POWER SHARING',431.8,137.16,147.32,121.92)
place('D2',('Device','D_Schottky'),515.62,170.18,180,'PMEG4010CEH','Diode_SMD:D_SOD-123F',field=(515.62,158.75))
wire((444.5,160.02),(487.68,160.02),(487.68,170.18),p('D2',2));label('USB_VBUS',444.5,160.02)
route('D2',1,(556.26,170.18),(556.26,200.66))
place('Q3',('Transistor_FET','AO3401A'),515.62,203.2,90,'AO3401A',field=(515.62,186.69))
wire((444.5,200.66),p('Q3',3));label('BAT',444.5,200.66)
route('Q3',2,(556.26,200.66));label('SYS',556.26,200.66)
route('Q3',1,(487.68,208.28),(487.68,160.02))
place('R27',('Device','R'),487.68,226.06,value='1k',fp='Resistor_SMD:R_0603_1608Metric')
route('R27',1,(487.68,208.28));route('R27',2,(487.68,241.3));gnd(487.68,241.3)
place('C21',('Device','C'),538.48,226.06,value='10u 10V',fp='Capacitor_SMD:C_0805_2012Metric',field=(530.86,223.52))
route('C21',1,(538.48,200.66));route('C21',2,(538.48,241.3));gnd(538.48,241.3)
place('SW1',('Switch','SW_SPST'),556.26,223.52,270,'POWER',field=(568.96,216))
route('SW1',1,(556.26,200.66));route('SW1',2,(556.26,236.22),(563.88,236.22));label('SYS_SW',563.88,236.22)
text('USB supplies puck + charger; battery takes over without USB.\\nSW1 switches puck only. Q3: drain=BAT, source=SYS.',439.42,248.92,1.25)

"""
s=s.replace('# Final typography:',block+'# Final typography:')
p.write_text(s)
p=p.with_name('verify_netlist.py');s=p.read_text().replace("R11.1',","Q3.1 D2.2 R27.1',")
s=s.replace("J2.1 SW1.1 TP3.1","J2.1 Q3.3 TP3.1").replace("'BAT_SW':'SW1.2","'SYS':'D2.1 Q3.2 SW1.1 C21.1',\n'SYS_SW':'R11.1 SW1.2")
s=s.replace("SW4.1 '+'", "SW4.1 R27.2 '+'").replace('range(1,21)','range(1,22)').replace('VBUS_SENSE','SUPPLY_SENSE')
p.write_text(s)
p=p.with_name('final_review.py');s=p.read_text().replace('import subprocess,json,hashlib','import subprocess,json,hashlib,shutil').replace("[('power',","[('power-sharing',(431,137,580,260)),('power',")
s += "\nshutil.copy2(ROOT/'review/BalancerREF.pdf',ROOT/'BalancerREF-Schematic.pdf')\nshutil.copy2(ROOT/'review/overview.png',ROOT/'BalancerREF-Schematic.png')\n"
p.write_text(s)
