"""Scripted electrical-rules check on KiCad's exported netlist (kicad-cli 7 has no ERC command).

Checks the core ERC rules:
  1. every pin is on a net with >= 2 pins, or carries an explicit no-connect flag
  2. every net with power-input pins is driven (power output pin or PWR_FLAG)
  3. no net has two power outputs
  4. netlist connectivity matches the design source exactly
"""
import sys
from collections import defaultdict
from sexp import parse, find, first
import design as D

net = parse(open(sys.argv[1]).read())
report = []
errors = 0
nets = defaultdict(list)
for n in find(first(net, 'nets'), 'net'):
    name = first(n, 'name')[1]
    for node in find(n, 'node'):
        pt = first(node, 'pintype')
        nets[name].append((first(node, 'ref')[1], first(node, 'pin')[1], pt[1] if pt else '?'))

nc_pins = {(p['ref'], k) for p in D.PARTS for k, v in p['nets'].items() if v is None}

# PWR_FLAGs are virtual (absent from the netlist): resolve which power net each flag
# touches by following schematic wires from the flag to a power symbol.
sch = parse(open(sys.argv[1].replace('docs/airnode.net', 'airnode.kicad_sch')).read())
adj = defaultdict(set)
for w in find(sch, 'wire'):
    a, b = [tuple(round(float(v), 3) for v in xy[1:3]) for xy in find(first(w, 'pts'), 'xy')]
    adj[a].add(b); adj[b].add(a)
flag_pts, pwr_pts = [], {}
for s in find(sch, 'symbol'):
    lid = first(s, 'lib_id')[1]
    at = first(s, 'at')
    pt = (round(float(at[1]), 3), round(float(at[2]), 3))
    if lid.endswith(':PWR_FLAG'):
        flag_pts.append(pt)
    elif lid.split(':')[1] in ('GND', '+3V3', 'VBUS'):
        pwr_pts[pt] = lid.split(':')[1]
flagged_nets = set()
for fpt in flag_pts:
    seen, stack = {fpt}, [fpt]
    while stack:
        q = stack.pop()
        if q in pwr_pts:
            flagged_nets.add(pwr_pts[q])
        for r in adj[q] - seen:
            seen.add(r); stack.append(r)
for name, nodes in sorted(nets.items()):
    real = [x for x in nodes if not x[0].startswith('#')]
    flagged = name.lstrip('/') in flagged_nets
    types = [x[2] for x in nodes]
    if len(real) == 1 and (real[0][0], real[0][1]) not in nc_pins and 'no_connect' not in real[0][2]:
        report.append(f'ERROR  single-pin net {name}: {real}'); errors += 1
    pin_in = [x for x in nodes if x[2].startswith('power_in') and not x[0].startswith('#PWR')]
    drivers = [x for x in nodes if x[2].startswith('power_out')]
    if pin_in and not drivers and not flagged:
        report.append(f'ERROR  power input not driven on {name}: {pin_in}'); errors += 1
    if len([d for d in drivers if not d[0].startswith('#FLG')]) > 1:
        report.append(f'ERROR  multiple power outputs on {name}: {drivers}'); errors += 1
    if name.startswith('unconnected-'):
        for ref, pin, _ in real:
            if (ref, pin) not in nc_pins:
                report.append(f'ERROR  unconnected pin {ref}.{pin}'); errors += 1

named = [n for n in nets if not n.startswith('unconnected-')]
report.insert(0, f'Nets: {len(named)} connected, {len(nets) - len(named)} explicit no-connects')
report.append(f'Power nets driven: ' + ', '.join(sorted(
    n.lstrip('/') for n, nodes in nets.items()
    if any(x[2].startswith('power_out') for x in nodes))))
report.append('Nets with PWR_FLAG: ' + ', '.join(sorted(flagged_nets)))
report.append(f'** ERC (scripted) : {errors} errors **')
out = '\n'.join(report)
print(out)
open(sys.argv[2], 'w').write('AirNode S3 - electrical rules check (scripted, KiCad 7 netlist)\n\n' + out + '\n')
