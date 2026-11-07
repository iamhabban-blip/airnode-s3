"""Compare KiCad-exported netlist against design.py connectivity."""
import sys
from collections import defaultdict
from sexp import parse, find, first
import design as D

net = parse(open(sys.argv[1]).read())
nets = first(net, 'nets')
got = defaultdict(set)   # net name -> {(ref,pin)}
for n in find(nets, 'net'):
    name = first(n, 'name')[1].lstrip('/')
    for node in find(n, 'node'):
        ref = first(node, 'ref')[1]
        if ref.startswith('#'):
            continue
        got[name].add((ref, first(node, 'pin')[1]))

want = defaultdict(set)
for p in D.PARTS:
    for pin, n in p['nets'].items():
        if n is not None:
            want[n].add((p['ref'], pin))

ok = True
for name in sorted(set(want) | set(got)):
    if name.startswith('unconnected-') or name.startswith('Net-('):
        # every "unconnected" net must hold only NC pins
        for ref, pin in got[name]:
            part = next(x for x in D.PARTS if x['ref'] == ref)
            if part['nets'].get(pin) is not None:
                print('UNEXPECTED floating', ref, pin, name); ok = False
        continue
    if want[name] != got[name]:
        ok = False
        print('MISMATCH', name, 'missing', want[name] - got[name], 'extra', got[name] - want[name])
singles = [n for n, s in want.items() if len(s) < 2]
if singles:
    print('single-pin nets:', singles); ok = False
print('NETLIST MATCHES DESIGN' if ok else 'NETLIST HAS ERRORS', '-', len(want), 'nets')
