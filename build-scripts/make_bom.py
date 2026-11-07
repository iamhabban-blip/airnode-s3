"""JLCPCB-style BOM + CPL from design.py and KiCad's position export."""
import csv, sys, os
from collections import OrderedDict
sys.path.insert(0, os.path.dirname(__file__))
import design as D
fab = sys.argv[1]
groups = OrderedDict()
for p in D.PARTS:
    if p['ref'].startswith('H'):
        continue  # mounting holes: not assembled
    fp = p['fp'].split(':')[1]
    key = (p['value'], fp, p.get('mpn', ''))
    groups.setdefault(key, []).append(p['ref'])
with open(os.path.join(fab, 'airnode-bom.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Comment', 'Designator', 'Footprint', 'Manufacturer Part', 'Quantity', 'LCSC Part #'])
    for (val, fp, mpn), refs in groups.items():
        refs.sort(key=lambda r: (r.rstrip('0123456789'), int(''.join(c for c in r if c.isdigit()))))
        w.writerow([val, ','.join(refs), fp, mpn, len(refs), ''])
rows = list(csv.DictReader(open(os.path.join(fab, 'airnode-pos-raw.csv'))))
with open(os.path.join(fab, 'airnode-cpl.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
    for r in rows:
        if r['Ref'].startswith('H'):
            continue
        w.writerow([r['Ref'], r['PosX'] + 'mm', r['PosY'] + 'mm', 'Top' if r['Side'] == 'top' else 'Bottom',
                    r['Rot']])
os.remove(os.path.join(fab, 'airnode-pos-raw.csv'))
print('BOM lines', len(groups), 'CPL rows', len(rows))
