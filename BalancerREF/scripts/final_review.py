from pathlib import Path
import subprocess,json,hashlib,shutil
import pymupdf as fitz
ROOT=Path(__file__).resolve().parents[1]
cli=Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')
def run(*args):subprocess.run([str(cli),*map(str,args)],cwd=ROOT,check=True)
run('sch','erc','BalancerREF.kicad_sch','-o','review/erc.rpt','--severity-all','--exit-code-violations')
run('sch','erc','BalancerREF.kicad_sch','-o','review/erc.json','--format','json','--severity-all','--exit-code-violations')
run('sch','export','netlist','BalancerREF.kicad_sch','-o','review/BalancerREF.net')
subprocess.run(['python',str(ROOT/'scripts/verify_netlist.py')],cwd=ROOT,check=True)
run('sch','export','pdf','BalancerREF.kicad_sch','-o','review/BalancerREF.pdf')
d=fitz.open(ROOT/'review/BalancerREF.pdf');assert len(d)==1
p=d[0];p.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(ROOT/'review/overview.png')
for name,rect in [('power',(29,36,568,148)),('accel',(29,151,275,239)),('opt',(29,242,275,370)),('mag',(284,151,568,239)),('mcu',(284,242,568,370))]:
 p.get_pixmap(matrix=fitz.Matrix(2,2),clip=fitz.Rect(*[v*72/25.4 for v in rect])).save(ROOT/'review'/f'{name}.png')
assert not list(ROOT.glob('*.kicad_pcb'))
hashes={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'BalancerREF.kicad_sch',ROOT/'BalancerREF.kicad_sym',ROOT/'review/erc.rpt',ROOT/'review/BalancerREF.pdf',ROOT/'review/connectivity-check.txt']}
(ROOT/'review/SHA256.json').write_text(json.dumps(hashes,indent=2))
print('Final KiCad 10.0.3 verification complete; one sheet, no PCB, no ERC exclusions.')

shutil.copy2(ROOT/'review/BalancerREF.pdf',ROOT/'BalancerREF-Schematic-RevC.pdf')
shutil.copy2(ROOT/'review/overview.png',ROOT/'BalancerREF-Schematic.png')
