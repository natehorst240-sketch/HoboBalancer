"""Add J4, a 5-pin GPS module header, to the existing BalancerREF schematic.

Edits the current sheet in place (does not regenerate it): embeds the KiCad 10
Conn_01x05 symbol, places J4 in the notes area, wires MCU GPIO1/GPIO2 (UART1)
and GPIO13 (PPS) to it, and removes those pins' no-connect markers.
Run kicad-cli sch upgrade afterwards to normalise formatting.
"""
import sys as _sys
if '--overwrite-hand-layout' not in _sys.argv:
    raise SystemExit('BalancerREF.kicad_sch has been hand-laid-out in KiCad since 2026-09-09 (Rev C, A2 sheet). '
                     'This generator would replace that layout. Re-run with --overwrite-hand-layout only on purpose.')

import math
from pathlib import Path

from sexp_helpers import *  # noqa: F401,F403 - parse/dump/node helpers and KiCad 10 LIB

ROOT = Path(__file__).resolve().parents[1]
SHEET = '817ec478-f84e-4d27-b6f3-c983c8ad991a'
SCH = ROOT / 'BalancerREF.kicad_sch'

# MCU pins (pad number -> signal) chosen for free space beside U1 and no strap/boot-log side effects.
MCU_PINS = {'5': 'GPS_UART_TX', '6': 'GPS_UART_RX', '17': 'GPS_PPS'}  # GPIO1 TX, GPIO2 RX, GPIO13 PPS
J4_PINS = {'1': '+3V3', '2': 'GND', '3': 'GPS_UART_RX', '4': 'GPS_UART_TX', '5': 'GPS_PPS'}
J4_AT = (548.64, 104.14)
MCU_LABEL_X = 241.3  # same anchor column as the existing left-side MCU labels


def find_symbol_instance(sch, ref):
    for s in children(sch, 'symbol'):
        if any(tagged(p, 'property') and p[1] == 'Reference' and p[2] == ref for p in s):
            return s
    raise KeyError(ref)


def lib_symbol(sch, libid):
    return next(s for s in children(one(sch, 'lib_symbols'), 'symbol') if s[1] == libid)


def pin_positions(sym, x, y, angle):
    """Connection point and outward direction of every pin of a placed symbol."""
    t = math.radians(angle)
    c, s = math.cos(t), math.sin(t)
    out = {}
    for sub in children(sym, 'symbol'):
        for pin in children(sub, 'pin'):
            at = one(pin, 'at')
            num = one(pin, 'number')[1]
            pos = (round(x + c * at[1] - s * at[2], 4), round(y - s * at[1] - c * at[2], 4))
            a = math.radians(at[3] + angle)
            out[num] = (pos, (round(-math.cos(a), 4), round(math.sin(a), 4)))
    return out


def wire_node(a, b):
    assert a[0] == b[0] or a[1] == b[1], (a, b)
    return node('wire', node('pts', node('xy', *a), node('xy', *b)),
                node('stroke', node('width', 0), node('type', S('default'))), node('uuid', uid()))


def label_node(net, x, y, angle):
    return node('label', net, node('at', x, y, angle),
                node('effects', node('font', node('size', 1.27, 1.27)), node('justify', S('left'), S('bottom'))),
                node('uuid', uid()))


def text_node(t, x, y, size):
    return node('text', t, node('at', x, y, 0),
                node('effects', node('font', node('size', size, size)), node('justify', S('left'), S('top'))),
                node('uuid', uid()))


def prop_node(k, v, x, y, hide):
    e = node('effects', node('font', node('size', 1.27, 1.27)))
    p = node('property', k, v, node('at', x, y, 0), node('show_name', S('no')), node('do_not_autoplace', S('no')), e)
    if hide:
        p.insert(4, node('hide', S('yes')))
    return p


def main():
    sch = parse(SCH.read_text(encoding='utf8'))
    libs = one(sch, 'lib_symbols')
    assert not any(s[1] == 'Connector_Generic:Conn_01x05' for s in children(libs, 'symbol')), 'J4 already added'
    assert all(getprop_ref(s) != 'J4' for s in children(sch, 'symbol')), 'J4 already placed'

    # 1. Embed the KiCad 10 library symbol.
    conn = standard('Connector_Generic', 'Conn_01x05')
    conn[1] = 'Connector_Generic:Conn_01x05'
    libs.append(conn)

    # 2. MCU side: drop no-connects and add short stubs with labels.
    u1 = find_symbol_instance(sch, 'U1')
    at = one(u1, 'at')
    upins = pin_positions(lib_symbol(sch, one(u1, 'lib_id')[1]), at[1], at[2], at[3])
    additions = []
    for num, net in MCU_PINS.items():
        pos, d = upins[num]
        removed = [n for n in children(sch, 'no_connect') if tuple(one(n, 'at')[1:3]) == pos]
        assert len(removed) == 1, (num, pos, removed)
        sch.remove(removed[0])
        assert d == (-1.0, 0.0), (num, d)  # left-side pins only; label text runs right along the stub
        end = (MCU_LABEL_X, pos[1])
        additions += [wire_node(pos, end), label_node(net, end[0], end[1], 0)]

    # 3. J4 instance, modelled on the existing generic connector instances.
    x, y = J4_AT
    inst = node('symbol', node('lib_id', 'Connector_Generic:Conn_01x05'), node('at', x, y, 0), node('unit', 1),
                node('body_style', 1), node('exclude_from_sim', S('no')), node('in_bom', S('yes')),
                node('on_board', S('yes')), node('in_pos_files', S('yes')), node('dnp', S('no')), node('uuid', uid()))
    fx, fy = x + 2.54, y - 10.16
    for k, v, hide in [('Reference', 'J4', False), ('Value', 'GPS MODULE 3V3 UART', False),
                       ('Footprint', 'Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical', True),
                       ('Datasheet', '', True), ('Description', 'u-blox style GPS breakout: VCC GND TX RX PPS', True),
                       ('MPN', 'PinHeader 1x05 2.54mm', True)]:
        inst.append(prop_node(k, v, fx, fy + (2.54 if k == 'Value' else 0), hide))
    jpins = pin_positions(conn, x, y, 0)
    for num in sorted(jpins, key=int):
        inst.append(node('pin', num, node('uuid', uid())))
    inst.append(node('instances', node('project', 'BalancerREF', node('path', '/' + SHEET, node('reference', 'J4'), node('unit', 1)))))
    additions.append(inst)

    # 4. J4 wiring: labels on 1,3,4,5; pin 2 to a ground symbol dropped left of the label text.
    for num, net in J4_PINS.items():
        pos, d = jpins[num]
        assert d == (-1.0, 0.0), (num, d)
        if net == 'GND':
            # Up and out past the short +3V3 stub, ground symbol inverted above.
            corner = (530.86, pos[1])
            top = (530.86, 88.9)
            additions += [wire_node(pos, corner), wire_node(corner, top)]
            g = deepcopy(find_symbol_instance(sch, '#PWR001'))
            set_instance(g, next_power_ref(sch), top, 180)
            additions.append(g)
        elif net == '+3V3':
            end = (535.94, pos[1])
            additions += [wire_node(pos, end), label_node(net, end[0], end[1], 0)]
        else:
            end = (520.7, pos[1])
            additions += [wire_node(pos, end), label_node(net, end[0], end[1], 0)]

    # 5. Notes: move the mechanical note up and title the GPS section.
    for t in children(sch, 'text'):
        if t[1].startswith('Mechanical intent only'):
            one(t, 'at')[2] = 66.04
    additions.append(text_node('GPS MODULE (OPTIONAL) - IN-FLIGHT LOGGING', 435.61, 81.28, 2.1))
    additions.append(text_node(
        'J4: 1 VCC 3.3 V, 2 GND, 3 GPS TX -> GPIO2 (UART1 RX), 4 GPS RX <- GPIO1 (UART1 TX), 5 PPS -> GPIO13.\n'
        '3.3 V logic module only (u-blox M8/M10 class, ~30 mA). Backup/sleep via UBX over UART; no power switch.\n'
        'UART1 keeps ROM boot output off the GPS. Ground speed only; not airspeed.',
        435.61, 115.57, 1.25))

    sch.extend(additions)
    SCH.write_text(dump(sch), encoding='utf8')
    # The generator documents every unused MCU pad; these three are now used.
    import json
    unused = ROOT / 'review' / 'unused-pins.json'
    if unused.exists():
        reasons = json.loads(unused.read_text())
        for num in MCU_PINS:
            reasons.pop(f'U1.{num}', None)
        unused.write_text(json.dumps(reasons, indent=2))
    print('J4 added; MCU pins', MCU_PINS)


def getprop_ref(s):
    return next((p[2] for p in children(s, 'property') if p[1] == 'Reference'), None)


def next_power_ref(sch):
    nums = [int(getprop_ref(s)[4:]) for s in children(sch, 'symbol') if (getprop_ref(s) or '').startswith('#PWR')]
    return '#PWR' + str(max(nums) + 1).zfill(3)


def set_instance(g, ref, pos, angle=0):
    one(g, 'at')[1:4] = [pos[0], pos[1], angle]
    one(g, 'uuid')[1] = uid()
    for p in children(g, 'property'):
        if p[1] == 'Reference':
            p[2] = ref
        one(p, 'at')[1] = pos[0]
        one(p, 'at')[2] = pos[1] + (-5.08 if angle else 5.08) if p[1] == 'Value' else pos[1] + (-2.54 if angle else 2.54)
    for pin in children(g, 'pin'):
        one(pin, 'uuid')[1] = uid()
    inst = one(g, 'instances')
    proj = one(inst, 'project')
    path = one(proj, 'path')
    one(path, 'reference')[1] = ref


if __name__ == '__main__':
    main()
