"""Photo-style 2D renders (green mask / ENIG / white silk) composited from KiCad layer SVGs."""
import subprocess
import sys
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import binary_fill_holes, binary_dilation
import pcbnew

PCB, OUT = sys.argv[1], sys.argv[2]
TMP = '/tmp/claude-0/r2d'
os.makedirs(TMP, exist_ok=True)
S = 40.0  # px per mm
LAYERS = ['F.Cu', 'F.Mask', 'F.Silkscreen', 'B.Cu', 'B.Mask', 'B.Silkscreen', 'Edge.Cuts']
ink = {}
for L in LAYERS:
    svg = f'{TMP}/{L}.svg'
    subprocess.run(['kicad-cli', 'pcb', 'export', 'svg', '-o', svg, '-l', L, '--page-size-mode', '2',
                    '--exclude-drawing-sheet', '--black-and-white', PCB], check=True, capture_output=True)
    png = f'{TMP}/{L}.png'
    vb = open(svg).read().split('viewBox="')[1].split('"')[0].split()
    wmm = float(vb[2])
    subprocess.run(['rsvg-convert', '-w', str(int(round(wmm * S))), '-b', 'white', svg, '-o', png], check=True)
    ink[L] = np.array(Image.open(png).convert('L')) < 128

edge = ink['Edge.Cuts']
ys, xs = np.where(edge)
left, top = xs.min(), ys.min()
board = pcbnew.LoadBoard(PCB)
bb = board.GetBoardEdgesBoundingBox()
X0, Y0 = pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop())


def px(x, y):
    return ((x - X0) * S + left, (y - Y0) * S + top)


inside = binary_fill_holes(edge)
H, W = edge.shape
hole_img = Image.new('L', (W, H), 0)
hd = ImageDraw.Draw(hole_img)
items = []
for fp in board.GetFootprints():
    for p in fp.Pads():
        d = p.GetDrillSize()
        if d.x > 0:
            items.append((p.GetPosition(), pcbnew.ToMM(d.x), pcbnew.ToMM(d.y), p.GetOrientationDegrees()))
for t in board.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        items.append((t.GetPosition(), pcbnew.ToMM(t.GetDrillValue()), pcbnew.ToMM(t.GetDrillValue()), 0))
for pos, dx, dy, ang in items:
    cx, cy = px(pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y))
    if abs(ang) % 180 == 90:
        dx, dy = dy, dx
    rx, ry = dx / 2 * S, dy / 2 * S
    if abs(rx - ry) < 1e-6:
        hd.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    else:  # oval slot
        r = min(rx, ry)
        hd.rounded_rectangle([cx - rx, cy - ry, cx + rx, cy + ry], radius=r, fill=255)
holes = np.array(hole_img) > 0


def compose(side):
    cu, mask, silk = ink[f'{side}.Cu'], ink[f'{side}.Mask'], ink[f'{side}.Silkscreen']
    img = np.zeros((H, W, 3), np.float32)
    img[:] = (24, 26, 30)                                   # background
    sub = np.array((14, 78, 44), np.float32)                # soldermask over FR4
    cu_under = np.array((32, 118, 64), np.float32)          # soldermask over copper
    gold = np.array((214, 176, 92), np.float32)             # ENIG pads
    bare = np.array((176, 160, 112), np.float32)            # mask opening without copper
    white = np.array((236, 238, 232), np.float32)
    img[inside] = sub
    img[inside & cu] = cu_under
    img[inside & mask & ~cu] = bare
    img[inside & mask & cu] = gold
    silk_ok = silk & inside & ~(mask & cu)
    img[silk_ok] = white
    img[holes] = (10, 10, 12)
    # subtle edge highlight on copper features for depth
    hi = binary_dilation(cu & inside, iterations=1) & ~cu & inside & ~mask
    img[hi] = img[hi] * 0.82
    out = Image.fromarray(img.clip(0, 255).astype(np.uint8))
    # crop to board + margin
    ys, xs = np.where(inside)
    m = int(2.5 * S)
    out = out.crop((max(xs.min() - m, 0), max(ys.min() - m, 0), min(xs.max() + m, W), min(ys.max() + m, H)))
    if side == 'B':
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
    return out


top_img, bot_img = compose('F'), compose('B')
top_img.save(os.path.join(OUT, 'airnode-pcb-top.png'))
bot_img.save(os.path.join(OUT, 'airnode-pcb-bottom.png'))
gap = 60
both = Image.new('RGB', (top_img.width + bot_img.width + gap, top_img.height), (24, 26, 30))
both.paste(top_img, (0, 0)); both.paste(bot_img, (top_img.width + gap, 0))
both.save(os.path.join(OUT, 'airnode-pcb-top-bottom.png'))
print('rendered', top_img.size)
