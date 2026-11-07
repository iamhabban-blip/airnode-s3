"""Stage 2: 2-layer grid A* router (45-degree, via-aware) + GND vias + pours.

Clearance is enforced with a Euclidean distance transform of all foreign copper,
so every routed centreline keeps >= clearance + width/2 (+ margin) from other nets.
"""
import heapq
import math
import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt
import pcbnew
import shapely

PCB = sys.argv[1]
MM, TO = pcbnew.FromMM, pcbnew.ToMM
G = 0.1                     # grid (mm)
CLR = 0.2                   # copper clearance
MARGIN = 0.012               # router safety margin over the rule
EDGE = 0.3                  # copper to edge
VIA_D, VIA_DR = 0.6, 0.3
VIA_COST, BOT_FACTOR = 28.0, 2.6
WIDTH = {'VBUS': 0.4, 'VBUS_IN': 0.4, '+3V3': 0.3, 'GND': 0.3, 'USB_DP': 0.2, 'USB_DN': 0.2}
DEFAULT_W = 0.2
ORDER = ['USB_DP', 'USB_DN', 'VBUS_IN', 'CC1', 'CC2', 'VBUS', '+3V3', 'I2C_SDA', 'I2C_SCL']

board = pcbnew.LoadBoard(PCB)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = round(TO(bb.GetLeft()) + 0.05, 3) - 0.05, round(TO(bb.GetTop()) + 0.05, 3)
NX, NY = int(round(TO(bb.GetWidth()) / G)) + 1, int(round(TO(bb.GetHeight()) / G)) + 1
LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]


def to_px(x, y):
    return ((x - X0) / G, (y - Y0) / G)


def to_mm(i, j):
    return (X0 + i * G, Y0 + j * G)


def poly_pts(outline):
    return [to_px(TO(outline.CPoint(k).x), TO(outline.CPoint(k).y)) for k in range(outline.PointCount())]


# ---------------- collect geometry ----------------
pads = []   # dict(net, layers:[0/1], poly:[pts px], center:(i,j), smd, ref)
holes = []  # (cx, cy, r_px) non-plated holes
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            c = p.GetPosition()
            holes.append((*to_px(TO(c.x), TO(c.y)), (TO(p.GetDrillSize().x) / 2) / G))
            continue
        lays = [k for k, L in enumerate(LAYERS) if p.IsOnLayer(L)]
        if not lays:
            continue
        ps = pcbnew.SHAPE_POLY_SET()
        p.TransformShapeToPolygon(ps, LAYERS[lays[0]], 0, MM(0.005))
        c = p.GetPosition()
        o = ps.Outline(0)
        pads.append(dict(net=p.GetNetname(), layers=lays, poly=poly_pts(o),
                         poly_mm=[(TO(o.CPoint(k).x), TO(o.CPoint(k).y)) for k in range(o.PointCount())],
                         center=to_px(TO(c.x), TO(c.y)), smd=p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD,
                         ref=fp.GetReference(), num=p.GetNumber()))

keepouts = []
for fp in board.GetFootprints():
    for z in fp.Zones():
        if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
            keepouts.append(poly_pts(z.Outline().Outline(0)))

# board interior mask
edge_img = Image.new('L', (NX, NY), 0)
ed = ImageDraw.Draw(edge_img)
r = 2.0 / G
ed.rounded_rectangle([0, 0, NX - 1, NY - 1], radius=r, fill=255)
inside = np.array(edge_img) > 0
edge_dist = distance_transform_edt(inside) * G
ko_img = Image.new('L', (NX, NY), 0)
for k in keepouts:
    ImageDraw.Draw(ko_img).polygon(k, fill=255)
ko_dist = distance_transform_edt(np.array(ko_img) == 0) * G

segments = []  # (net, layer, (x1,y1), (x2,y2) mm, width)
vias = []      # (net, (x,y) mm)


def raster(exclude_net, layer, own=False):
    """Raster of copper on layer belonging to nets != exclude_net (or == if own)."""
    img = Image.new('L', (NX, NY), 0)
    d = ImageDraw.Draw(img)
    sel = (lambda n: n == exclude_net) if own else (lambda n: n != exclude_net or n == '')
    for p in pads:
        if layer in p['layers'] and sel(p['net']):
            d.polygon(p['poly'], fill=255)
    if not own:
        for (cx, cy, rr) in holes:
            rr2 = rr + 0.05 / G
            d.ellipse([cx - rr2, cy - rr2, cx + rr2, cy + rr2], fill=255)
    for net, L, a, b, w in segments:
        if L == layer and sel(net):
            pa, pb = to_px(*a), to_px(*b)
            d.line([pa, pb], fill=255, width=max(1, int(round(w / G))))
            rr = w / 2 / G
            for q in (pa, pb):
                d.ellipse([q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr], fill=255)
    for net, (x, y) in vias:
        if sel(net):
            q = to_px(x, y)
            rr = VIA_D / 2 / G
            d.ellipse([q[0] - rr, q[1] - rr, q[0] + rr, q[1] + rr], fill=255)
    return np.array(img) > 0


def geom(exclude_net, layer):
    """Exact Shapely geometry (mm) of foreign copper on a layer."""
    parts = []
    for p in pads:
        if layer in p['layers'] and (p['net'] != exclude_net or p['net'] == ''):
            parts.append(shapely.Polygon(p['poly_mm']))
    for (cx, cy, rr) in holes:
        x, y = to_mm(cx, cy)
        parts.append(shapely.Point(x, y).buffer(rr * G + 0.05, 16))
    for n, L, a, b, w in segments:
        if L == layer and n != exclude_net:
            parts.append(shapely.LineString([a, b]).buffer(w / 2, 8) if a != b else shapely.Point(a).buffer(w / 2, 8))
    for n, (x, y) in vias:
        if n != exclude_net:
            parts.append(shapely.Point(x, y).buffer(VIA_D / 2, 16))
    g = shapely.union_all(parts)
    shapely.prepare(g)
    return g


def exact_dist(net, L):
    """EDT estimate everywhere, refined with exact distances near every threshold we use."""
    dist = distance_transform_edt(~raster(net, L)) * G
    lo, hi = CLR + 0.05 - 0.2, CLR + VIA_D / 2 + 0.25
    jj, ii = np.where((dist > lo) & (dist < hi))
    if len(ii):
        g = geom(net, L)
        xs = X0 + ii * G
        ys = Y0 + jj * G
        dist[jj, ii] = shapely.distance(g, shapely.points(xs, ys))
    return dist


def masks(net, w):
    """free[layer] for track centreline; via_ok for via centre."""
    free, dists = [], []
    for L in (0, 1):
        dist = exact_dist(net, L)
        dists.append(dist)
        free.append((dist >= CLR + w / 2 + MARGIN) & (edge_dist >= EDGE + w / 2 + MARGIN)
                    & (ko_dist >= w / 2 + MARGIN))
    own_smd = raster(net, 0, own=True)
    own_d = distance_transform_edt(~own_smd) * G
    via_ok = ((dists[0] >= CLR + VIA_D / 2 + MARGIN) & (dists[1] >= CLR + VIA_D / 2 + MARGIN)
              & (edge_dist >= EDGE + VIA_D / 2 + MARGIN) & (ko_dist >= VIA_D / 2 + MARGIN)
              & (own_d >= 0.15))
    # keep vias off other vias' holes (hole-to-hole 0.25)
    return free, via_ok


DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]


def astar(starts, goal_fn, h_fn, free, via_ok, allow_bottom=True):
    """starts: list of (i,j,L). Returns list of states (i,j,L)."""
    openh = []
    g = {}
    parent = {}
    for (i, j, L) in starts:
        s = (i, j, L, 8)
        g[s] = 0.0
        heapq.heappush(openh, (h_fn(i, j), 0.0, s))
    n_exp = 0
    while openh:
        f, gc, s = heapq.heappop(openh)
        if gc > g.get(s, 1e18):
            continue
        i, j, L, dprev = s
        if goal_fn(i, j, L):
            path = [s]
            while path[-1] in parent:
                path.append(parent[path[-1]])
            return [(a, b, c) for a, b, c, _ in reversed(path)]
        n_exp += 1
        if n_exp > 3500000:
            return None
        lf = 1.0 if L == 0 else BOT_FACTOR
        for k, (dx, dy) in enumerate(DIRS):
            if dprev != 8:
                turn = min((k - dprev) % 8, (dprev - k) % 8)
                if turn > 2:
                    continue
                tp = (0.0, 0.4, 3.0)[turn]
            else:
                tp = 0.0
            ni, nj = i + dx, j + dy
            if not (0 <= ni < NX and 0 <= nj < NY) or not free[L][nj, ni]:
                continue
            ng = gc + (1.4142 if dx and dy else 1.0) * lf + tp
            ns = (ni, nj, L, k)
            if ng < g.get(ns, 1e18):
                g[ns] = ng
                parent[ns] = s
                heapq.heappush(openh, (ng + h_fn(ni, nj), ng, ns))
        if allow_bottom and via_ok[j, i]:
            nl = 1 - L
            if free[nl][j, i]:
                ns = (i, j, nl, 8)
                ng = gc + VIA_COST
                if ng < g.get(ns, 1e18):
                    g[ns] = ng
                    parent[ns] = s
                    heapq.heappush(openh, (ng + h_fn(i, j), ng, ns))
    return None


def emit(net, path, w):
    """Convert grid path to track segments + vias."""
    pts = path
    # vias
    for a, b in zip(pts, pts[1:]):
        if a[2] != b[2]:
            vias.append((net, to_mm(a[0], a[1])))
    # split by layer, merge collinear
    run = [pts[0]]
    out = []

    def flush(run):
        if len(run) < 2:
            return
        L = run[0][2]
        anchors = [run[0]]
        for k in range(1, len(run) - 1):
            d1 = (run[k][0] - run[k - 1][0], run[k][1] - run[k - 1][1])
            d2 = (run[k + 1][0] - run[k][0], run[k + 1][1] - run[k][1])
            if d1 != d2:
                anchors.append(run[k])
        anchors.append(run[-1])
        for a, b in zip(anchors, anchors[1:]):
            segments.append((net, L, to_mm(a[0], a[1]), to_mm(b[0], b[1]), w))

    for s in pts[1:]:
        if s[2] != run[-1][2]:
            flush(run)
            run = [s]
        else:
            run.append(s)
    flush(run)


def pad_cells(p, free, rad=1):
    ci, cj = int(round(p['center'][0])), int(round(p['center'][1]))
    out = []
    for L in p['layers']:
        for di in range(-rad, rad + 1):
            for dj in range(-rad, rad + 1):
                i, j = ci + di, cj + dj
                if 0 <= i < NX and 0 <= j < NY and free[L][j, i]:
                    out.append((i, j, L))
    return out


# Hand-designed USB-C escape: D+ pads (A6,B6) joined by a loop under the pad row,
# D- pads (B7,A7) joined by a bridge above it, both then exit upward.
def _j1(num):
    p = next(p for p in pads if p['ref'] == 'J1' and p['num'] == num)
    return to_mm(*p['center'])


_a6, _b6, _a7, _b7 = _j1('A6'), _j1('B6'), _j1('A7'), _j1('B7')
PY, HALF = _a6[1], 0.575                      # pad centre row, half pad length
LOOP = PY + HALF + 0.1 + CLR + 0.04           # under-pad loop for D+
BRIDGE = PY - HALF - 0.1 - CLR - 0.06         # over-pad bridge for D-
EXIT = BRIDGE - 0.7
PRE = {
    'USB_DP': dict(pads={'A6', 'B6'}, exit=(_b6[0], EXIT), segs=[
        (_a6, (_a6[0], LOOP)), ((_a6[0], LOOP), (_b6[0], LOOP)), ((_b6[0], LOOP), _b6), (_b6, (_b6[0], EXIT))]),
    'USB_DN': dict(pads={'B7', 'A7'}, exit=(_b7[0], EXIT), segs=[
        (_b7, (_b7[0], BRIDGE)), ((_b7[0], BRIDGE), (_a7[0], BRIDGE)), ((_a7[0], BRIDGE), _a7),
        ((_b7[0], BRIDGE), (_b7[0], EXIT))]),
}


def route_net(net):
    w = WIDTH.get(net, DEFAULT_W)
    ps = [p for p in pads if p['net'] == net]
    pre = PRE.get(net)
    if pre:
        for a, b in pre['segs']:
            segments.append((net, 0, a, b, w))
        ps = [p for p in ps if not (p['ref'] == 'J1' and p['num'] in pre['pads'])]
    # merge pads sharing a centre (stacked/duplicate)
    uniq = []
    for p in ps:
        if not any(abs(p['center'][0] - q['center'][0]) < 3 and abs(p['center'][1] - q['center'][1]) < 3
                   and set(p['layers']) & set(q['layers']) and p['ref'] == q['ref'] for q in uniq):
            uniq.append(p)
    ps = sorted(uniq, key=lambda p: (p['center'][0] + p['center'][1]))
    if len(ps) < (1 if pre else 2):
        return 0
    free, via_ok = masks(net, w)
    if pre:
        ex = to_px(*pre['exit'])
        tree = [(int(round(ex[0])), int(round(ex[1])), 0)]
        remaining = ps[:]
    else:
        tree = pad_cells(ps[0], free)
        if not tree:
            tree = pad_cells(ps[0], free, rad=3)
        remaining = ps[1:]
    fails = 0
    while remaining:
        # nearest remaining pad to tree
        tcx = np.mean([t[0] for t in tree]); tcy = np.mean([t[1] for t in tree])
        remaining.sort(key=lambda p: math.hypot(p['center'][0] - tcx, p['center'][1] - tcy))
        tgt = remaining.pop(0)
        cells = set(pad_cells(tgt, free)) or set(pad_cells(tgt, free, rad=3))
        if not cells:
            print('  !! no free cell at', tgt['ref'], tgt['num'], net); fails += 1
            continue
        if set(cells) & set(tree):
            tree += list(cells); continue
        tc = tgt['center']
        h = lambda i, j: max(abs(i - tc[0]), abs(j - tc[1])) + 0.414 * min(abs(i - tc[0]), abs(j - tc[1]))
        path = astar(tree, lambda i, j, L: (i, j, L) in cells, h, free, via_ok)
        if path is None:
            print('  !! failed', net, '->', tgt['ref'], tgt['num']); fails += 1
            continue
        emit(net, path, w)
        tree += path + list(cells)
        # refresh masks for own vias/tracks not needed (own net), keep going
    return fails


def gnd_vias():
    """Give every SMD GND pad on F.Cu a short trace to its own via into the B.Cu plane."""
    net, w = 'GND', WIDTH['GND']
    fails = 0
    done_centres = []
    for p in pads:
        if p['net'] != net or not p['smd'] or 0 not in p['layers']:
            continue
        if any(math.hypot(p['center'][0] - c[0], p['center'][1] - c[1]) < 6 for c in done_centres):
            continue  # pads of same group share a via (e.g. stacked)
        free, via_ok = masks(net, w)
        start = pad_cells(p, free) or pad_cells(p, free, rad=3)
        if not start:
            print('  !! GND pad blocked', p['ref'], p['num']); fails += 1; continue
        c = p['center']
        minr = (0.55 + VIA_D / 2) / G

        def goal(i, j, L):
            return L == 0 and via_ok[j, i] and math.hypot(i - c[0], j - c[1]) >= minr
        path = astar(start, goal, lambda i, j: 0.0, free, via_ok, allow_bottom=False)
        if path is None:
            print('  !! GND via failed', p['ref'], p['num']); fails += 1; continue
        emit(net, path, w)
        vias.append((net, to_mm(path[-1][0], path[-1][1])))
        done_centres.append(c)
    return fails


nets_all = sorted({p['net'] for p in pads if p['net']})
order = ORDER + sorted([n for n in nets_all if n not in ORDER and n != 'GND'],
                       key=lambda n: -len([p for p in pads if p['net'] == n]))
total_fail = 0
for n in order:
    f = route_net(n)
    total_fail += f
    print('routed', n, 'fails', f, 'segs', len(segments), 'vias', len(vias))
    if n == 'I2C_SCL':   # power + sensor bus first, then every GND pad gets its plane via, then signals
        total_fail += gnd_vias()
print('GND vias done; total fails', total_fail, 'segments', len(segments), 'vias', len(vias))

# ---------------- write to board ----------------
netinfo = {n: board.FindNet(n) for n in nets_all}
for net, L, a, b, w in segments:
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1]))); t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
    t.SetWidth(MM(w)); t.SetLayer(LAYERS[L]); t.SetNet(netinfo[net])
    board.Add(t)
for net, (x, y) in vias:
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y))); v.SetDrill(MM(VIA_DR)); v.SetWidth(MM(VIA_D))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetNet(netinfo[net])
    board.Add(v)
pcbnew.SaveBoard(PCB, board)
print('SAVED', total_fail)
