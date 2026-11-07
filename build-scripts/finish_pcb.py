"""Stage 3: GND pours, stitching vias, silkscreen, zone fill, DRC report."""
import sys
import math
import pcbnew

PCB, DRC_OUT = sys.argv[1], sys.argv[2]
MM, TO = pcbnew.FromMM, pcbnew.ToMM
V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))
X0, Y0, W, H = 100.0, 100.0, 44.0, 54.0

board = pcbnew.LoadBoard(PCB)
gnd = board.FindNet('GND')

# remove previous zones / stitching (idempotent re-runs)
for z in list(board.Zones()):
    board.Remove(z)


def add_zone(layer):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(gnd)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in [(X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H)]:
        ol.Append(MM(x), MM(y))
    z.SetLocalClearance(MM(0.25))
    z.SetMinThickness(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
    z.SetThermalReliefGap(MM(0.3))
    z.SetThermalReliefSpokeWidth(MM(0.4))
    z.SetZoneName('GND_' + ('TOP' if layer == pcbnew.F_Cu else 'BOT'))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z


zf = add_zone(pcbnew.F_Cu)
zb = add_zone(pcbnew.B_Cu)
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())

# ---------------- stitching vias ----------------
import shapely


def filled_poly(z, layer):
    ps = z.GetFilledPolysList(layer)
    polys = []
    for k in range(ps.OutlineCount()):
        o = ps.Outline(k)
        outer = [(TO(o.CPoint(i).x), TO(o.CPoint(i).y)) for i in range(o.PointCount())]
        holes = []
        for h in range(ps.HoleCount(k)):
            hh = ps.Hole(k, h)
            holes.append([(TO(hh.CPoint(i).x), TO(hh.CPoint(i).y)) for i in range(hh.PointCount())])
        polys.append(shapely.Polygon(outer, holes))
    return shapely.union_all(polys)


ft, bt = filled_poly(zf, pcbnew.F_Cu), filled_poly(zb, pcbnew.B_Cu)
both = ft.intersection(bt)
courtyards = []
for fp in board.GetFootprints():
    for side in (pcbnew.F_CrtYd,):
        cy = fp.GetCourtyard(side)
        if cy.OutlineCount():
            o = cy.Outline(0)
            pts = [(TO(o.CPoint(i).x), TO(o.CPoint(i).y)) for i in range(o.PointCount())]
            if len(pts) >= 3:
                p = shapely.Polygon(pts)
                # the module courtyard includes its antenna keep-out; keep only the body
                if fp.GetReference() == 'U1':
                    p = p.intersection(shapely.box(X0, 106.5, X0 + W, 126.0))
                courtyards.append(p.buffer(0.3))
blocked = shapely.union_all(courtyards)
existing = [(TO(v.GetPosition().x), TO(v.GetPosition().y)) for v in board.GetTracks()
            if v.GetClass() == 'PCB_VIA']
VD = 0.6
added = 0
step = 3.0
y = Y0 + 1.5
while y < Y0 + H:
    x = X0 + 1.5
    while x < X0 + W:
        c = shapely.Point(x, y).buffer(VD / 2 + 0.05, 16)
        if both.contains(c) and not blocked.intersects(c) and \
                all(math.hypot(x - ex, y - ey) > 1.2 for ex, ey in existing):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(V(x, y)); v.SetDrill(MM(0.3)); v.SetWidth(MM(VD))
            v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetNet(gnd)
            board.Add(v)
            existing.append((x, y)); added += 1
        x += step
    y += step
print('stitching vias', added)

# ---------------- silkscreen ----------------


def silk(text, x, y, size=1.0, layer=pcbnew.F_SilkS, bold=False, just=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(text); t.SetPosition(V(x, y)); t.SetLayer(layer)
    t.SetTextSize(V(size, size)); t.SetTextThickness(MM(size * (0.2 if bold else 0.15)))
    t.SetBold(bold)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    if just:
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT if just < 0 else pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(t)


for d in list(board.GetDrawings()):
    if d.GetClass() == 'PCB_TEXT':
        board.Remove(d)


silk('AirNode S3', 106.6, 102.6, 1.1, bold=True)
silk('rev A', 137.6, 102.6, 0.9)
silk('SW1 RST', 111.6, 135.6, 0.8)
silk('SW2 BOOT', 132.4, 135.6, 0.8)
silk('Qwiic', 140.6, 127.4, 0.8)

# bottom-side pin legends and info
for k, lab in enumerate(['GND', 'TX', 'RX', '3V3']):
    silk(lab, 138.2, 108.0 + k * 2.54, 0.8, pcbnew.B_SilkS, just=-1)
for k, lab in enumerate(['3V3', 'IO4', 'IO5', 'IO6', 'IO7', 'IO15', 'IO16', 'GND']):
    silk(lab, 105.8, 108.0 + k * 2.54, 0.8, pcbnew.B_SilkS, just=+1)
silk('AirNode S3', 122.0, 133.0, 1.6, pcbnew.B_SilkS, bold=True)
silk('ESP32-S3 environmental sensor node', 122.0, 135.6, 0.8, pcbnew.B_SilkS)
silk('Muhammad Habban  2026', 122.0, 137.6, 0.8, pcbnew.B_SilkS)

filler.Fill(board.Zones())
board.BuildConnectivity()
pcbnew.SaveBoard(PCB, board)
ok = pcbnew.WriteDRCReport(board, DRC_OUT, pcbnew.EDA_UNITS_MILLIMETRES, True)
print('drc written', ok)
