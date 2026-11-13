"""E2E: fixture de Craft -> proyecto -> piezas con fotos locales -> acomodo -> PDF + reporte.
Y smoke test del servidor HTTP local."""

import json
import os
import re
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from app import config as C
from app.models import Project, DATA_DIR, OUT_DIR, PROJECT_FILE
from app.parse_orders import parse_craft_markdown
from app.__main__ import prepare_pieces
from app import layout as L
from app import render as R

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "semana_9_al_15.md")
E2E_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_out_e2e")


def fake_photo(path, seed):
    im = Image.new("RGB", (900, 1100), (210, 225, 235))
    d = ImageDraw.Draw(im)
    cx = 450 + seed * 7
    d.ellipse((cx - 160, 90, cx + 160, 410), fill=(235, 180, 125))
    d.rounded_rectangle((cx - 240, 430, cx + 240, 1050), radius=70, fill=(235, 180, 125))
    d.rectangle((0, 0, 60, 1100), fill=(30, 30, 30))
    im.save(path)
    return os.path.relpath(path, DATA_DIR)


def test_e2e_cli_flow():
    with open(FIX, encoding="utf-8") as f:
        pages = parse_craft_markdown(f.read())
    week = "9 al 15 de noviembre de 2026"
    p = Project(week=week, source_name="fixture")
    p.orders = [o.to_dict() for o in pages[week]["orders"]]
    # simular fotos ya bajadas/subidas para todas las ligas comestibles
    os.makedirs(os.path.join(DATA_DIR, "photos"), exist_ok=True)
    seed = 0
    for o in p.orders:
        for url in o.get("edible_links", []):
            seed += 1
            rel = fake_photo(os.path.join(DATA_DIR, "photos", f"e2e_{seed}.png"), seed)
            p.photos[url] = {"status": "ok", "path": rel, "w": 900, "h": 1100, "bn": False, "src_url": url}
    prepare_pieces(p, fetch=False)
    with_photo = [o for o in p.orders if o.get("mode") or o.get("edible_links")]
    n_pieces = len([q for q in p.pieces if not q.get("pending")])
    assert n_pieces == sum(len(o.get("edible_links", [])) for o in with_photo), (n_pieces, with_photo)
    summary = L.auto_layout(p)
    problems = L.check_layout(p)
    assert not problems, problems
    out = R.export_all(p, E2E_OUT)
    report = R.build_report(p, problems)
    rpath = os.path.join(E2E_OUT, out["base"], "reporte.md")
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(report)
    with open(out["pdf"], "rb") as f:
        raw = f.read()
    boxes = re.findall(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]", raw)
    n_pages = raw.count(b"/Type /Page") - raw.count(b"/Type /Pages")
    assert len(boxes) >= 1 and n_pages == len(p.sheets), (n_pages, len(p.sheets))
    for b in boxes:
        assert abs((float(b[2]) - float(b[0])) - 708.661) < 1.0
        assert abs((float(b[3]) - float(b[1])) - 566.929) < 1.0
    # conteo estilo paso 8b
    m = re.search(r"Pedidos con foto comestible en Craft: \*\*(\d+)\*\*", report)
    assert m and int(m.group(1)) == len(with_photo)
    assert "GORRITO" in report  # Tay Xacur manual
    # la pieza del pedido con 2 fotos trae "pastel 1 de 2" / "2 de 2"
    labels = " ".join(q["label"] for q in p.pieces)
    assert "pastel 1 de 2" in labels and "pastel 2 de 2" in labels
    # tamaños: completa Mediano = círculo 635 px
    circle = next(q for q in p.pieces if q["kind"] == "circle" and q["size"] == "Mediano")
    assert abs(circle["w"] - 635) < 1
    print("e2e ok:", len(p.sheets), "hojas/guías,", n_pieces, "piezas,", n_pages, "páginas PDF")


def test_server_smoke():
    from app.server import serve
    import app.server as srv
    port = 8899
    t = threading.Thread(target=serve, kwargs={"port": port, "host": "127.0.0.1"}, daemon=True)
    t.start()
    time.sleep(0.6)
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state", timeout=5) as r:
        state = json.loads(r.read())
    assert "orders" in state and "sheets" in state
    with open(FIX, encoding="utf-8") as f:
        text = f.read()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/import",
                                 data=json.dumps({"text": text, "source_name": "smoke"}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        res = json.loads(r.read())
    assert res.get("ok") and res["week"].startswith("9 al 15"), res
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
        html = r.read().decode()
    assert "Pecanding" in html
    print("server smoke ok")


if __name__ == "__main__":
    test_e2e_cli_flow()
    test_server_smoke()
    print("ALL E2E TESTS PASSED")
