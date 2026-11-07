"""Copy every footprint + 3D model the design uses into project-local libraries.

airnode.pretty      footprints (ESP32 module thermal vias opened to 0.3 mm for JLC 2-layer)
airnode.3dshapes    STEP models referenced via ${KIPRJMOD}
fp-lib-table        project table pointing at the local library
"""
import os
import re
import shutil
import sys
import design as D

OUT = sys.argv[1]  # project dir
FP = '/usr/share/kicad/footprints/'
M3 = '/usr/share/kicad/3dmodels/'
pretty = os.path.join(OUT, 'airnode.pretty')
shapes = os.path.join(OUT, 'airnode.3dshapes')
for d in (pretty, shapes):
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)

done = set()
for p in D.PARTS:
    lib, name = p['fp'].split(':')
    if name in done:
        continue
    done.add(name)
    src = open(os.path.join(FP, lib + '.pretty', name + '.kicad_mod')).read()
    # DFM: Espressif's 0.2 mm thermal vias -> 0.3 mm (JLCPCB standard 2-layer minimum)
    if name == 'ESP32-S3-WROOM-1':
        src, n = re.subn(r'\(size 0\.6 0\.6\) \(drill 0\.2\)', '(size 0.6 0.6) (drill 0.3)', src)
        print('ESP32 thermal vias opened:', n)
        # antenna-end silkscreen pulled 0.5 mm inside the module so it never crosses the board edge
        src = src.replace('(start -9.2 -12.9) (end -9.2 -6.7)', '(start -9.2 -12.4) (end -9.2 -6.7)')
        src = src.replace('(start 9.2 -12.9) (end 9.2 -6.7)', '(start 9.2 -12.4) (end 9.2 -6.7)')
        src = src.replace('(start -9.2 -12.9) (end 9.2 -12.9)', '(start -9.2 -12.4) (end 9.2 -12.4)')

    def fix_model(m):
        path = m.group(1)
        rel = re.sub(r'^\$\{KICAD\d_3DMODEL_DIR\}/', '', path)
        step = os.path.splitext(rel)[0] + '.step'
        if os.path.exists(os.path.join(M3, step)):
            shutil.copy(os.path.join(M3, step), shapes)
            return '(model "${KIPRJMOD}/airnode.3dshapes/%s"' % os.path.basename(step)
        print('  no 3D model for', name)
        return m.group(0)
    src = re.sub(r'\(model "?(\$\{KICAD\d_3DMODEL_DIR\}[^"\s]+)"?', fix_model, src)
    open(os.path.join(pretty, name + '.kicad_mod'), 'w').write(src)

open(os.path.join(OUT, 'fp-lib-table'), 'w').write(
    '(fp_lib_table\n  (version 7)\n  (lib (name "airnode")(type "KiCad")(uri "${KIPRJMOD}/airnode.pretty")'
    '(options "")(descr "AirNode S3 project footprints"))\n)\n')
open(os.path.join(OUT, 'sym-lib-table'), 'w').write(
    '(sym_lib_table\n  (version 7)\n  (lib (name "airnode")(type "KiCad")(uri "${KIPRJMOD}/airnode.kicad_sym")'
    '(options "")(descr "AirNode S3 project symbols"))\n)\n')
print('footprints', len(done), 'models', len(os.listdir(shapes)))
