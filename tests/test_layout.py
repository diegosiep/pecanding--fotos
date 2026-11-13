import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config as C
from app.models import Project, new_piece_for_order
from app import layout as L


def mk_piece(size, kind, day="Lunes 9", w=None, h=None):
    order = {"id": "o1", "name": "Prueba", "response": "10000", "day": day, "size": size,
             "mode": "completa" if kind == "circle" else "recortada", "gorrito": False}
    p = new_piece_for_order(order, None, "ok")
    if w:
        p.w = w
    if h:
        p.h = h
    return p.to_dict()


def test_sizes_px():
    assert abs(C.circle_px("Mini") - 423.3) < 1
    assert abs(C.circle_px("Mediano") - 635) < 1
    assert abs(C.circle_px("Grande") - 665) < 1
    assert abs(C.circle_px("Extra Grande") - 710.6) < 1
    assert C.recortada_default_cm("Mediano") == 12.25 or C.recortada_default_cm("Mediano") == 12.5
    assert C.recortada_default_cm("Mini", True) == 8.0


def test_packing_respects_safe_zone_and_gaps():
    p = Project(week="t")
    for i in range(6):
        p.pieces.append(mk_piece("Mini", "cutout", day=f"Lunes {9 + i % 3}", w=300, h=300))
    p.pieces.append(mk_piece("Mediano", "circle"))
    p.pieces.append(mk_piece("Grande", "circle"))
    p.pieces.append(mk_piece("Extra Grande", "circle"))
    summary = L.auto_layout(p)
    problems = L.check_layout(p)
    assert not problems, problems
    kinds = [s["kind"] for s in p.sheets]
    assert kinds[0] == "guia"  # GUÍA Mini primero
    # XL debe caber en la hoja aunque rompa la guía de arriba
    xl = next(q for q in p.pieces if q["size"] == "Extra Grande")
    assert xl["y"] + xl["h"] <= C.SHEET_H
    assert summary["guias"] >= 3


def test_gap_between_pieces():
    p = Project(week="t")
    p.pieces.append(mk_piece("Mini", "cutout", w=390, h=390))
    p.pieces.append(mk_piece("Mini", "cutout", w=390, h=390))
    L.auto_layout(p)
    a, b = p.pieces
    if a["sheet_id"] == b["sheet_id"]:
        ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
        oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
        gap = min(ox if ox > 0 else 999, oy if oy > 0 else 999)
        # si no se enciman, la separación en el eje que se traslapa debe ser >= ~0.4cm
        if ox <= 0 or oy <= 0:
            sep = ox if ox <= 0 else oy
            assert -sep >= 0.4 * C.PX_PER_CM - 1, f"gap {sep}"


def test_pending_not_laid_out():
    p = Project(week="t")
    q = mk_piece("Mini", "cutout", w=300, h=300)
    q["pending"] = True
    p.pieces.append(q)
    L.auto_layout(p)
    assert q["sheet_id"] == ""
    assert p.sheets == []


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL LAYOUT TESTS PASSED")
