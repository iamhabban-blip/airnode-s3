"""Load KiCad library symbols, resolve 'extends', list pins."""
import copy
import os
from sexp import parse, find, first, Sym

SYMDIR = '/usr/share/kicad/symbols'
_cache = {}


def _lib(name):
    if name not in _cache:
        with open(os.path.join(SYMDIR, name + '.kicad_sym')) as f:
            _cache[name] = parse(f.read())
    return _cache[name]


def _raw(lib, name):
    for s in find(_lib(lib), 'symbol'):
        if s[1] == name:
            return s
    raise KeyError(f'{lib}:{name}')


def get_symbol(libid):
    """Return a flattened symbol S-expr named 'Lib:Name' for embedding in lib_symbols."""
    lib, name = libid.split(':')
    s = copy.deepcopy(_raw(lib, name))
    ext = first(s, 'extends')
    if ext:
        parent = copy.deepcopy(_raw(lib, ext[1]))
        # child props override parent props
        cprops = {p[1]: p for p in find(s, 'property')}
        new = [Sym('symbol'), libid]
        for item in parent[2:]:
            if isinstance(item, list) and item[0] == 'property' and item[1] in cprops:
                new.append(cprops.pop(item[1]))
            elif isinstance(item, list) and item[0] == 'symbol':
                sub = copy.deepcopy(item)
                sub[1] = sub[1].replace(ext[1], name, 1)
                new.append(sub)
            else:
                new.append(item)
        for p in cprops.values():
            new.insert(len(new) - len(find(new, 'symbol')), p)
        s = new
    else:
        s[1] = libid
    return s


def pins(sym):
    """List of dicts: number, name, type, x, y, angle, length, hidden, unit."""
    out = []
    for sub in find(sym, 'symbol'):
        unit = int(str(sub[1]).split('_')[-2])
        for p in find(sub, 'pin'):
            at = first(p, 'at')
            name = first(p, 'name')[1]
            num = first(p, 'number')[1]
            hidden = any(x == 'hide' for x in p)
            out.append(dict(number=num, name=name, type=str(p[1]), x=float(at[1]), y=float(at[2]),
                            angle=float(at[3]), length=float(first(p, 'length')[1]),
                            hidden=hidden, unit=unit))
    return out


if __name__ == '__main__':
    import sys
    s = get_symbol(sys.argv[1])
    for p in pins(s):
        print(p)
