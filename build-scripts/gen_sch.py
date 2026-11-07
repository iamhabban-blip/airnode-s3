"""Generate airnode.kicad_sch (KiCad 7 format) from design.py."""
import uuid
import sys
from collections import defaultdict
from sexp import Sym as S, dump, find, first
from libs import get_symbol, pins
import design as D

PROJECT = 'airnode'
NS = uuid.UUID('6f1c0d2e-0000-4000-8000-a1a1a1a1a1a1')


def U(*key):
    return str(uuid.uuid5(NS, '/'.join(map(str, key))))


ROOT = U('root')
STUB = 2.54
FONT = [S('font'), [S('size'), 1.27, 1.27]]

# outward direction (screen coords, y down) per lib pin angle
OUT = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}
LABEL_ANGLE = {(-1, 0): 180, (1, 0): 0, (0, 1): 270, (0, -1): 90}
# rotation so a power symbol's body points outward
GND_ROT = {(0, 1): 0, (0, -1): 180, (1, 0): 90, (-1, 0): 270}
UP_ROT = {(0, -1): 0, (0, 1): 180, (-1, 0): 90, (1, 0): 270}

items = []
lib_cache = {}
pwr_count = [0]
flg_count = [0]


def r2(v):
    return round(v, 4)


def lib(libid):
    if libid not in lib_cache:
        lib_cache[libid] = get_symbol(libid)
    return lib_cache[libid]


def prop(name, value, x, y, ang=0, hide=False, justify=None, key=None):
    eff = [S('effects'), FONT]
    if justify:
        eff.append([S('justify')] + [S(j) for j in justify])
    if hide:
        eff.append(S('hide'))
    return [S('property'), name, value, [S('at'), r2(x), r2(y), ang], eff]


def symbol_instance(libid, ref, value, x, y, rot=0, fp='', extra=None, in_bom=True, key=None):
    sym = lib(libid)
    uid = U('sym', key or ref)
    props = []
    lprops = {p[1]: p for p in find(sym, 'property')}
    for pname, pval in (('Reference', ref), ('Value', value), ('Footprint', fp), ('Datasheet', None)):
        lp = lprops.get(pname)
        at = first(lp, 'at') if lp else None
        lx, ly = (float(at[1]), float(at[2])) if at else (0, 0)
        hide = pname in ('Footprint', 'Datasheet') or (lp is not None and S('hide') in first(lp, 'effects'))
        if pval is None:
            pval = lp[2] if lp else '~'
        jus = None
        if lp is not None:
            j = first(first(lp, 'effects'), 'justify')
            jus = [str(t) for t in j[1:]] if j else None
        lang = float(at[3]) if at and len(at) > 3 else 0
        props.append(prop(pname, pval, x + lx, y - ly, lang, hide, jus))
    for k, v in (extra or {}).items():
        props.append(prop(k, v, x, y, 0, True))
    pin_entries = []
    seen = set()
    for p in pins(sym):
        if p['number'] in seen:
            continue
        seen.add(p['number'])
        pin_entries.append([S('pin'), p['number'], [S('uuid'), U('pin', key or ref, p['number'])]])
    node = [S('symbol'), [S('lib_id'), libid], [S('at'), r2(x), r2(y), rot], [S('unit'), 1],
            [S('in_bom'), S('yes' if in_bom else 'no')], [S('on_board'), S('yes')], [S('dnp'), S('no')],
            [S('uuid'), uid]] + props + pin_entries + [
        [S('instances'), [S('project'), PROJECT,
                          [S('path'), '/' + ROOT, [S('reference'), ref], [S('unit'), 1]]]]]
    items.append(node)
    return uid


def wire(x1, y1, x2, y2):
    items.append([S('wire'), [S('pts'), [S('xy'), r2(x1), r2(y1)], [S('xy'), r2(x2), r2(y2)]],
                  [S('stroke'), [S('width'), 0], [S('type'), S('default')]],
                  [S('uuid'), U('w', x1, y1, x2, y2)]])


def label(net, x, y, d):
    ang = LABEL_ANGLE[d]
    jus = [S('left'), S('bottom')] if ang in (0, 90) else [S('right'), S('bottom')]
    items.append([S('label'), net, [S('at'), r2(x), r2(y), ang], [S('fields_autoplaced')],
                  [S('effects'), FONT, [S('justify')] + jus], [S('uuid'), U('lbl', net, x, y)]])


def power_symbol(net, x, y, d):
    libid = D.POWER_NETS[net]
    is_gnd = net == 'GND'
    rot = (GND_ROT if is_gnd else UP_ROT)[d]
    pwr_count[0] += 1
    ref = '#PWR%03d' % pwr_count[0]
    # value text placed beyond body in outward direction, always horizontal
    if d[0]:
        vx, vy, jus = x + d[0] * 4.2, y + 0.5, ['left' if d[0] > 0 else 'right']
    else:
        vx, vy, jus = x, y + d[1] * (5.0 if is_gnd else 4.0), None
    uid = U('sym', ref)
    sym = lib(libid)
    node = [S('symbol'), [S('lib_id'), libid], [S('at'), r2(x), r2(y), rot], [S('unit'), 1],
            [S('in_bom'), S('yes')], [S('on_board'), S('yes')], [S('dnp'), S('no')],
            [S('uuid'), uid],
            prop('Reference', ref, x, y, 0, True),
            prop('Value', net, vx, vy, 90 if rot in (90, 270) else 0, False, jus),
            prop('Footprint', '', x, y, 0, True),
            prop('Datasheet', '', x, y, 0, True),
            [S('pin'), '1', [S('uuid'), U('pin', ref)]],
            [S('instances'), [S('project'), PROJECT,
                              [S('path'), '/' + ROOT, [S('reference'), ref], [S('unit'), 1]]]]]
    items.append(node)


def pwr_flag(x, y, rot):
    flg_count[0] += 1
    ref = '#FLG%02d' % flg_count[0]
    sym = lib('power:PWR_FLAG')
    node = [S('symbol'), [S('lib_id'), 'power:PWR_FLAG'], [S('at'), r2(x), r2(y), rot], [S('unit'), 1],
            [S('in_bom'), S('yes')], [S('on_board'), S('yes')], [S('dnp'), S('no')],
            [S('uuid'), U('sym', ref)],
            prop('Reference', ref, x, y, 0, True),
            prop('Value', 'PWR_FLAG', x + 1.27, y + (-5.08 if rot == 0 else 5.08), 0, False),
            prop('Footprint', '', x, y, 0, True),
            prop('Datasheet', '~', x, y, 0, True),
            [S('pin'), '1', [S('uuid'), U('pin', ref)]],
            [S('instances'), [S('project'), PROJECT,
                              [S('path'), '/' + ROOT, [S('reference'), ref], [S('unit'), 1]]]]]
    items.append(node)


def no_connect(x, y):
    items.append([S('no_connect'), [S('at'), r2(x), r2(y)], [S('uuid'), U('nc', x, y)]])


def text(s, x, y, size=1.27, bold=False):
    f = [S('font'), [S('size'), size, size]]
    if bold:
        f.append(S('bold'))
    items.append([S('text'), s, [S('at'), r2(x), r2(y), 0],
                  [S('effects'), f, [S('justify'), S('left'), S('bottom')]], [S('uuid'), U('txt', s)]])


def rect(x1, y1, x2, y2, key):
    items.append([S('rectangle'), [S('start'), r2(x1), r2(y1)], [S('end'), r2(x2), r2(y2)],
                  [S('stroke'), [S('width'), 0.254], [S('type'), S('dash')]],
                  [S('fill'), [S('type'), S('none')]], [S('uuid'), U('rect', key)]])


# ---------------- build ----------------
sym_uuid = {}
for part in D.PARTS:
    x, y = part['at']
    extra = {}
    if part.get('mpn'):
        extra['MPN'] = part['mpn']
    sym_uuid[part['ref']] = symbol_instance(part['lib'], part['ref'], part['value'], x, y,
                                            fp=part['fp'], extra=extra)
    done_pos = set()
    pending_pwr = []  # (net, ex, ey, d, pin coordinate along side)
    for p in pins(lib(part['lib'])):
        num = p['number']
        if num not in part['nets'] and part['nets']:
            print('WARNING: pin not assigned', part['ref'], num, file=sys.stderr)
            continue
        if not part['nets']:
            continue
        net = part['nets'][num]
        px, py = x + p['x'], y - p['y']
        key = (round(px, 3), round(py, 3))
        if key in done_pos:
            continue
        done_pos.add(key)
        if net is None:
            if not p['hidden']:
                no_connect(px, py)
            continue
        d = OUT[int(p['angle'])]
        stub = 12.7 if (net in D.POWER_NETS and d[0] and part['ref'].startswith('J')) else STUB
        ex, ey = px + d[0] * stub, py + d[1] * stub
        wire(px, py, ex, ey)
        if net in D.POWER_NETS:
            pending_pwr.append((net, ex, ey, d, px, py))
        else:
            label(net, ex, ey, d)
    # merge adjacent same-net power pins on one side into a single symbol
    side_all = defaultdict(list)  # (d, fixed coord) -> [(along, net)]
    for p in pins(lib(part['lib'])) if part['nets'] else []:
        d = OUT[int(p['angle'])]
        px, py = x + p['x'], y - p['y']
        fixed = round(px if d[0] else py, 3)
        along = round(py if d[0] else px, 3)
        side_all[(d, fixed)].append((along, part['nets'].get(p['number'])))
    groups = defaultdict(list)
    for net, ex, ey, d, px, py in pending_pwr:
        fixed = round(px if d[0] else py, 3)
        groups[(net, d, fixed)].append((round(ey if d[0] else ex, 3), ex, ey))
    for (net, d, fixed), pts in groups.items():
        pts.sort()
        clusters = [[pts[0]]]
        for pt in pts[1:]:
            lo, hi = clusters[-1][-1][0], pt[0]
            between = [n for a, n in side_all[(d, fixed)] if lo < a < hi]
            if all(n == net for n in between):
                clusters[-1].append(pt)
            else:
                clusters.append([pt])
        for cl in clusters:
            for a, b in zip(cl, cl[1:]):
                wire(a[1], a[2], b[1], b[2])
            for mid in cl[1:-1]:
                items.append([S('junction'), [S('at'), r2(mid[1]), r2(mid[2])], [S('diameter'), 0],
                              [S('color'), 0, 0, 0, 0], [S('uuid'), U('j', mid[1], mid[2])]])
            if d[0] != 0:  # horizontal stubs: GND hangs from lowest, rails from highest
                anchor = cl[-1] if net == 'GND' else cl[0]
            else:
                anchor = cl[0]
            power_symbol(net, anchor[1], anchor[2], d)

# power flags
for net, (x, y) in D.PWR_FLAGS:
    if net == 'GND':
        # flag above (body up), GND symbol below (body down)
        pwr_flag(x, y, 0)
        wire(x, y, x, y + 2.54)
        power_symbol('GND', x, y + 2.54, (0, 1))
    else:
        power_symbol(net, x, y, (0, -1))
        wire(x, y, x, y + 2.54)
        pwr_flag(x, y + 2.54, 180)

for t, x1, y1, x2, y2 in D.BLOCKS:
    rect(x1, y1, x2, y2, t)
    text(t, x1 + 1.27, y1 + 3.81, 2.0, True)
for (x, y), s in D.NOTES:
    text(s, x, y, 1.27)

# ---- point everything at the project-local 'airnode' libraries ----
import copy as _copy
LOCAL = 'airnode'
local_syms = []
for k in sorted(lib_cache):
    s = lib_cache[k]
    s[1] = LOCAL + ':' + k.split(':')[1]
    loc = _copy.deepcopy(s)
    loc[1] = k.split(':')[1]
    local_syms.append(loc)
for it in items:
    if it[0] == 'symbol':
        lid = first(it, 'lib_id')
        lid[1] = LOCAL + ':' + lid[1].split(':')[1]
        for pr in find(it, 'property'):
            if pr[1] == 'Footprint' and ':' in pr[2]:
                pr[2] = LOCAL + ':' + pr[2].split(':')[1]
with open(sys.argv[1].replace('.kicad_sch', '.kicad_sym').replace('airnode.kicad_sym', 'airnode.kicad_sym'), 'w') as f:
    f.write(dump([S('kicad_symbol_lib'), [S('version'), 20220914], [S('generator'), S('kicad_symbol_editor')]]
                 + local_syms) + '\n')

lib_symbols = [S('lib_symbols')] + [lib_cache[k] for k in sorted(lib_cache)]

sch = [S('kicad_sch'), [S('version'), 20230121], [S('generator'), S('eeschema')],
       [S('uuid'), ROOT], [S('paper'), 'A3'],
       [S('title_block'), [S('title'), 'AirNode S3 - ESP32-S3 Environmental Sensor Node'],
        [S('date'), '2026-11-07'], [S('rev'), 'A'], [S('company'), 'Muhammad Habban'],
        [S('comment'), 1, 'USB-C powered, native USB, BME280 + Qwiic I2C, 2-layer 1.6mm'],
        [S('comment'), 2, 'Drawn in KiCad 7']],
       lib_symbols] + items + [
    [S('sheet_instances'), [S('path'), '/', [S('page'), '1']]]]

with open(sys.argv[1], 'w') as f:
    f.write(dump(sch) + '\n')

import json
with open(sys.argv[1] + '.uuids.json', 'w') as f:
    json.dump(sym_uuid, f, indent=1)
print('ok', len(items), 'items')
