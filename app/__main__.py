"""CLI de pecanding-fotos.

  python3 -m app serve [--port 8765]                 # app web local (macOS/Linux)
  python3 -m app run --source craft_semana.md [--week "9 al 15 de noviembre de 2026"] [--fetch] [--out out]
                                                      # modo sin interfaz: parsea, acomoda y exporta
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config as C
from app.models import Project, DATA_DIR, OUT_DIR, new_piece_for_order
from app.parse_orders import parse_craft_markdown, current_week_title
from app import photos as PH
from app import layout as L
from app import render as R


def cmd_serve(args):
    from app.server import serve
    serve(port=args.port, host="127.0.0.1")


def _build_project_from_source(text: str, week: str | None, source_name: str) -> Project:
    pages = parse_craft_markdown(text)
    if week is None:
        week = current_week_title(list(pages.keys()))
    if week not in pages:
        raise SystemExit(f"Semana «{week}» no encontrada. Disponibles: {list(pages.keys())}")
    p = Project(week=week, source_name=source_name)
    p.orders = [o.to_dict() for o in pages[week]["orders"]]
    return p


def prepare_pieces(p: Project, fetch: bool) -> None:
    """Crea piezas para los pedidos con foto comestible y descarga fotos."""
    for o in p.orders:
        if not (o.get("mode") or o.get("edible_links")):
            continue
        if o.get("status") in ("hecha", "excluida"):
            continue
        links = o.get("edible_links") or []
        if o.get("image_missing") and not links:
            o["status"] = "pendiente"
            o["status_reason"] = "el formulario no trae la imagen"
        for i, url in enumerate(links):
            rec = p.photos.get(url)
            if rec is None:
                if fetch:
                    rec = PH.download_photo(url)
                else:
                    rec = {"status": "sin_acceso", "path": "", "w": 0, "h": 0, "bn": False, "src_url": url}
                p.photos[url] = rec
            if rec.get("bn") and not o.get("bn"):
                o["bn"] = True
            piece = new_piece_for_order(o, rec.get("path") if rec.get("status") in ("ok", "subida") else None,
                                        rec.get("status", "sin_acceso"), i, len(links)).to_dict()
            # medir sujeto si hay foto y es recortada
            if piece["kind"] == "cutout" and piece["photo"]:
                _fit_cutout(p, piece)
            p.pieces.append(piece)
        if links:
            o["status"] = "lista"


def _fit_cutout(p: Project, piece: dict) -> None:
    from app import remove_bg as RB
    path = os.path.join(DATA_DIR, piece["photo"])
    try:
        im = RB and PH.open_photo(path)
    except Exception:
        return
    W, H = im.size
    rgba = RB.remove_background(im)
    if rgba is not None:
        box = RB.head_box(rgba) if piece.get("head_only") else RB.subject_box(rgba)
        if box:
            x0, y0, x1, y1 = box
            margin = 0.02
            mw = (x1 - x0) * margin
            mh = (y1 - y0) * margin
            ib = {"left": max(0, x0 - mw), "top": max(0, y0 - mh),
                  "width": min(W, (x1 - x0) + 2 * mw), "height": min(H, (y1 - y0) + 2 * mh)}
            scale = piece["h"] / ib["height"]
            piece["img_box"] = ib
            piece["w"] = max(10, ib["width"] * scale)
            piece["has_mask"] = True
            return
    # sin rembg: caja con la foto completa a la altura pedida
    ib = {"left": 0, "top": 0, "width": W, "height": H}
    scale = piece["h"] / H
    piece["img_box"] = ib
    piece["w"] = max(10, W * scale)


def cmd_run(args):
    text = open(args.source, encoding="utf-8").read()
    p = _build_project_from_source(text, args.week, os.path.basename(args.source))
    prepare_pieces(p, fetch=args.fetch)
    summary = L.auto_layout(p)
    problems = L.check_layout(p)
    out = R.export_all(p, args.out or OUT_DIR)
    report = R.build_report(p, problems)
    rpath = os.path.join(args.out or OUT_DIR, out["base"], "reporte.md")
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(report)
    p.save()
    print(json.dumps({"week": p.week, "orders": len(p.orders), "pieces": len(p.pieces),
                      "layout": summary, "problems": problems,
                      "pdf": out["pdf"], "report": rpath}, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser(prog="pecanding-fotos")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))
    s.set_defaults(fn=cmd_serve)
    r = sub.add_parser("run")
    r.add_argument("--source", required=True)
    r.add_argument("--week", default=None)
    r.add_argument("--fetch", action="store_true")
    r.add_argument("--out", default=None)
    r.set_defaults(fn=cmd_run)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
