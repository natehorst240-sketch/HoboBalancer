"""Replace embedded J1/RV1 library symbols with the KiCad 10 library copies.

KiCad 10 renamed the USB-C shield pin/pad from S1 to SH and added simulation
properties to R_Potentiometer, so the KiCad 9 copies embedded in the schematic
no longer match the installed library (ERC lib_symbol_mismatch) and the shield
pin would not map to the KiCad 10 footprint pad.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIB = Path('C:/Program Files/KiCad/10.0/share/kicad/symbols')
TARGETS = [('Connector', 'USB_C_Receptacle_USB2.0_16P'), ('Device', 'R_Potentiometer')]
PIN_RENAMES = {'J1': {'S1': 'SH'}}
BACKSLASH = chr(92)


def block(text, start):
    """Return end index (exclusive) of the s-expression starting at text[start] == '('."""
    depth = 0
    i = start
    in_str = False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == BACKSLASH:
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError('unbalanced s-expression')


def find_symbol(text, name):
    m = re.search(r'\(symbol\s+"%s"' % re.escape(name), text)
    if not m:
        raise KeyError(name)
    return m.start(), block(text, m.start())


def main():
    sch_path = ROOT / 'BalancerREF.kicad_sch'
    sch = sch_path.read_text(encoding='utf8')
    for lib, name in TARGETS:
        libtext = (LIB / f'{lib}.kicad_sym').read_text(encoding='utf8')
        a, b = find_symbol(libtext, name)
        new = libtext[a:b].replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
        if '(extends ' in new:
            raise SystemExit(f'{name} is a derived symbol; not handled')
        s, e = find_symbol(sch, f'{lib}:{name}')
        sch = sch[:s] + new + sch[e:]
        print(f'replaced {lib}:{name}: {e - s} -> {len(new)} chars')
    for ref, renames in PIN_RENAMES.items():
        m = re.search(r'\(property "Reference" "%s"' % ref, sch)
        s = sch.rfind('(symbol', 0, m.start())
        e = block(sch, s)
        inst = sch[s:e]
        for old, newp in renames.items():
            n = len(re.findall(r'\(pin "%s"' % old, inst))
            inst = re.sub(r'\(pin "%s"' % old, f'(pin "{newp}"', inst)
            print(f'{ref}: renamed instance pin {old}->{newp} ({n} occurrence)')
        sch = sch[:s] + inst + sch[e:]
    sch_path.write_text(sch, encoding='utf8')
    print('written', sch_path)


if __name__ == '__main__':
    main()
