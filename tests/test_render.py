import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from app import config as C
from app.models import Project, DATA_DIR, new_piece_for_order
from app import layout as L
from app import render as R

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out")


def make_photo(path, w=800, h=1000, bg=(200, 220, 240), fg=(240, 180, 120)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    d.ellipse((w // 2 - 150, 80, w // 2 + 150, 380), fill=fg)       # cabeza
    d.rounded_rectangle((w // 2 - 220, 400, w // 2 + 220, h - 50), radius=60, fill=fg)  # cuerpo
    im.save(path)
    return os.path.relpath(path, DATA_DIR)


def build_project():
    os.makedirs(DATA_DIR, exist_ok=True)
    rel = make_photo(os.path.join(DATA_DIR, "photos", "foto_prueba.png"))
    p = Project(week="9 al 15 de noviembre de 2026")
    order = {"id": "o1", "name": "Prueba", "response": "10999", "day": "Lunes 9",
             "size": "Mediano", "mode": "completa", "gorrito": False}
    pc = new_piece_for_order(order, rel, "ok")
    pc.img_box = {"left": 0, "top": 0, "width": 800, "height": 800}
    p.pieces.append(pc.to_dict())
    order2 = dict(order, id="o2", mode="recortada", size="Mini", response="10998")
    pr = new_piece_for_order(order2, rel, "ok")
    pr.img_box = {"left": 100, "top": 0, "width": 600, "height": 950}
    p.pieces.append(pr.to_dict())
    L.auto_layout(p)
    return p


def test_render_sheet_size_and_pdf_exact_cm():
    p = build_project()
    os.makedirs(OUT, exist_ok=True)
    out = R.export_all(p, OUT)
    assert os.path.exists(out["pdf"])
    for png in out["pngs"]:
        im = Image.open(png)
        assert im.size == (945, 756), im.size
    with open(out["pdf"], "rb") as f:
        raw = f.read()
    boxes = re.findall(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]", raw)
    assert boxes, "sin MediaBox"
    # 25 cm = 708.661 pt, 20 cm = 566.929 pt (a 72 pt/pulgada)
    for b in boxes:
        w = float(b[2]) - float(b[0])
        h = float(b[3]) - float(b[1])
        assert abs(w - 708.661) < 1.0, w
        assert abs(h - 566.929) < 1.0, h


def test_guia_sheet_has_circle_1to1():
    img = R.render_guia("Mediano")
    assert img.size == (945, 756)
    # el círculo guía debe medir Ø 16.8 cm = 635 px: buscar píxeles del contorno en la fila central
    px = img.load()
    y = int(C.SAFE_TOP + C.cm(16.8) / 2)
    xs = [x for x in range(945) if px[x, y] == (138, 138, 138)]
    assert xs, "no se encontró el contorno del círculo guía"
    left_edge = min(xs)
    dia = C.cm(16.8)
    right_edge = left_edge + dia
    assert abs(left_edge - C.SAFE_TOP) < 3, left_edge
    near = [x for x in xs if abs(x - right_edge) < 4]
    assert near, f"borde derecho del círculo no está en {right_edge:.0f}: {sorted(xs)}"


def test_label_and_flags_in_report():
    p = build_project()
    p.pieces[1]["gorrito"] = True
    p.pieces[1]["bn"] = True
    problems = L.check_layout(p)
    rep = R.build_report(p, problems)
    assert "GORRITO" in rep and "B/N" in rep
    assert "conteo" in rep


def test_bn_renders_grayscale():
    p = build_project()
    p.pieces[0]["bn"] = True
    sheet = next(s for s in p.sheets if s["id"] == p.pieces[0]["sheet_id"])
    img = R.render_sheet(p, sheet, guides=False)
    # dentro del círculo debe haber píxeles y ser gris (R≈G≈B)
    pc = p.pieces[0]
    cx, cy = int(pc["x"] + pc["w"] / 2), int(pc["y"] + pc["h"] / 2)
    r, g, b = img.getpixel((cx, cy))[:3]
    assert abs(r - g) < 12 and abs(g - b) < 12, (r, g, b)


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL RENDER TESTS PASSED")
