"""Stage 1: build placed, unrouted board + export Specctra DSN for Freerouting."""
import json
import os
import re
import sys
import pcbnew
import design as D

PROJ = sys.argv[1]            # e.g. ../project/airnode
FPDIR = None  # set from project dir: local airnode.pretty
MM = pcbnew.FromMM
V = lambda x, y: pcbnew.VECTOR2I(MM(x), MM(y))

X0, Y0, W, H = 100.0, 100.0, 44.0, 54.0
R_CORNER = 2.0

# ref: (x, y, rotation_deg, layer)
PLACE = {
    'U1': (122.0, 112.75, 0), 'J4': (103.5, 108.0, 0), 'J3': (140.5, 108.0, 0),
    'J2': (140.6, 122.5, 90),
    'C4': (109.0, 108.8, 90), 'C3': (109.0, 112.3, 90), 'R3': (109.0, 116.0, 90), 'C5': (109.0, 119.0, 90),
    'SW1': (111.6, 132.2, 0), 'SW2': (132.4, 132.2, 0), 'R4': (129.4, 127.7, 0),
    'D2': (118.6, 130.0, 0), 'R6': (118.6, 132.2, 0), 'D1': (125.4, 130.0, 0), 'R5': (125.4, 132.2, 0),
    'J1': (122.0, 150.9, 0), 'U3': (122.0, 140.6, 270), 'R1': (117.3, 142.5, 90), 'R2': (126.7, 142.5, 90),
    'U2': (134.0, 140.0, 0), 'C1': (130.0, 140.0, 90), 'C2': (138.5, 140.0, 90), 'F1': (134.0, 146.0, 0),
    'U4': (109.0, 145.5, 0), 'C6': (112.0, 145.5, 90), 'R7': (113.0, 141.0, 0), 'R8': (113.0, 139.0, 0),
    'H1': (104.0, 131.0, 0), 'H2': (140.0, 131.0, 0), 'H3': (104.0, 150.0, 0), 'H4': (140.0, 150.0, 0),
}

# explicit silkscreen reference positions (None = hidden)
REF_POS = {'H1': None, 'H2': None, 'H3': None, 'H4': None,
           'R6': (118.6, 133.7), 'R5': (125.4, 133.7), 'D2': (118.6, 128.6), 'D1': (125.4, 128.6),
           'R7': (110.4, 141.0), 'R8': (110.4, 139.0), 'SW2': None, 'SW1': None,
           'R4': (131.9, 127.7)}

NETCLASSES = {
    'Default': dict(track=0.2, clearance=0.2, via=0.6, drill=0.3),
    'Power': dict(track=0.4, clearance=0.2, via=0.6, drill=0.3, nets=['VBUS', 'VBUS_IN']),
    'Rail': dict(track=0.3, clearance=0.2, via=0.6, drill=0.3, nets=['+3V3', 'GND']),
    'USB': dict(track=0.2, clearance=0.2, via=0.6, drill=0.3, nets=['USB_DP', 'USB_DN']),
}


def write_project():
    classes = []
    patterns = []
    for name, c in NETCLASSES.items():
        classes.append({"name": name, "clearance": c['clearance'], "track_width": c['track'],
                        "via_diameter": c['via'], "via_drill": c['drill'],
                        "microvia_diameter": 0.3, "microvia_drill": 0.1,
                        "diff_pair_width": 0.3, "diff_pair_gap": 0.2, "diff_pair_via_gap": 0.25,
                        "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)",
                        "schematic_color": "rgba(0, 0, 0, 0.000)", "wire_width": 6, "bus_width": 12})
        for n in c.get('nets', []):
            patterns.append({"netclass": name, "pattern": n})
    pro = {
        "board": {"design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2,
                         "silk_line_width": 0.15, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0,
                         "silk_text_thickness": 0.15},
            "rules": {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5,
                      "min_through_hole_diameter": 0.3, "min_copper_edge_clearance": 0.3,
                      "min_hole_to_hole": 0.25, "min_silk_clearance": 0.0, "min_hole_clearance": 0.25,
                      "min_via_annular_width": 0.1, "solder_mask_to_copper_clearance": 0.0},
            "track_widths": [0.0, 0.2, 0.3, 0.5], "via_dimensions": [{"diameter": 0.0, "drill": 0.0},
                                                                    {"diameter": 0.6, "drill": 0.3}],
        }},
        "meta": {"filename": "airnode.kicad_pro", "version": 1},
        "net_settings": {"classes": classes, "meta": {"version": 3},
                         "net_colors": None, "netclass_assignments": None,
                         "netclass_patterns": patterns},
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[re.search(r'\(uuid "?([0-9a-f-]+)"?\)', open(PROJ + '.kicad_sch').read()).group(1), ""]],
        "text_variables": {}
    }
    json.dump(pro, open(PROJ + '.kicad_pro', 'w'), indent=2)


def outline(board):
    x1, y1, x2, y2, r = X0, Y0, X0 + W, Y0 + H, R_CORNER
    segs = [((x1 + r, y1), (x2 - r, y1)), ((x2, y1 + r), (x2, y2 - r)),
            ((x2 - r, y2), (x1 + r, y2)), ((x1, y2 - r), (x1, y1 + r))]
    for a, b in segs:
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        board.Add(s)
    for cx, cy, sx, sy in [(x1 + r, y1 + r, x1, y1 + r), (x2 - r, y1 + r, x2 - r, y1),
                           (x2 - r, y2 - r, x2, y2 - r), (x1 + r, y2 - r, x1 + r, y2)]:
        a = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        a.SetCenter(V(cx, cy)); a.SetStart(V(sx, sy)); a.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
        a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(MM(0.1))
        board.Add(a)


def main():
    write_project()
    board = pcbnew.NewBoard(PROJ + '.kicad_pcb')
    board.SetCopperLayerCount(2)
    tb = board.GetTitleBlock()
    tb.SetTitle('AirNode S3 - ESP32-S3 Environmental Sensor Node'); tb.SetRevision('A')
    tb.SetDate('2026-11-07'); tb.SetCompany('Muhammad Habban')
    outline(board)

    uuids = json.load(open(PROJ + '.kicad_sch.uuids.json'))
    nets = {}
    for p in D.PARTS:
        for n in p['nets'].values():
            if n and n not in nets:
                ni = pcbnew.NETINFO_ITEM(board, n)
                board.Add(ni)
                nets[n] = ni
    for p in D.PARTS:
        lib, name = p['fp'].split(':')
        fp = pcbnew.FootprintLoad(os.path.join(os.path.dirname(PROJ), 'airnode.pretty'), name)
        fp.SetReference(p['ref']); fp.SetValue(p['value'])
        fp.SetFPID(pcbnew.LIB_ID('airnode', name))
        fp.SetPath(pcbnew.KIID_PATH('/' + uuids[p['ref']]))
        if p.get('mpn'):
            fp.SetProperty('MPN', p['mpn'])
        x, y, rot = PLACE[p['ref']]
        board.Add(fp)
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            n = p['nets'].get(pad.GetNumber())
            if n:
                pad.SetNet(nets[n])
        fp.Reference().SetTextSize(V(0.8, 0.8)); fp.Reference().SetTextThickness(MM(0.12))
        if p['ref'] in REF_POS:
            rp = REF_POS[p['ref']]
            if rp is None:
                fp.Reference().SetVisible(False)
            else:
                fp.Reference().SetPosition(V(*rp)); fp.Reference().SetTextAngleDegrees(0)
    board.BuildConnectivity()
    pcbnew.SaveBoard(PROJ + '.kicad_pcb', board)
    ok = pcbnew.ExportSpecctraDSN(board, PROJ + '.dsn')
    print('saved; dsn export', ok)


main()
