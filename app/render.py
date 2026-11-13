"""Renderiza hojas 945x756 px con Pillow y exporta PDF a tamaño real (25x20 cm)."""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

from . import config as C
from .models import DATA_DIR

_FONT_CACHE = {}


def load_font(size: int = C.LABEL_FONT_PX, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                f = ImageFont.truetype(path, size)
                _FONT_CACHE[key] = f
                return f
            except Exception:
                pass
    try:
        f = ImageFont.load_default(size=size)
    except TypeError:
        f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def _photo_abs(project, piece) -> str | None:
    if not piece.get("photo"):
        return None
    p = piece["photo"]
    return p if os.path.isabs(p) else os.path.join(DATA_DIR, p)


def _img_box(piece, im) -> dict:
    ib = piece.get("img_box") or {}
    if ib.get("width") and ib.get("height"):
        return ib
    W, H = im.size
    if piece.get("kind") == "circle":
        side = min(W, H)
        return {"left": (W - side) / 2, "top": (H - side) / 2, "width": side, "height": side}
    return {"left": 0, "top": 0, "width": W, "height": H}


def _crop_source(im: Image.Image, ib: dict, w: float, h: float, bn: bool) -> Image.Image:
    left = max(0, min(ib["left"], im.width - 1))
    top = max(0, min(ib["top"], im.height - 1))
    width = max(1, min(ib["width"], im.width - left))
    height = max(1, min(ib["height"], im.height - top))
    crop = im.crop((left, top, left + width, top + height))
    crop = crop.resize((max(1, round(w)), max(1, round(h))), Image.LANCZOS)
    if bn:
        crop = crop.convert("L").convert("RGB")
    return crop


def _draw_piece(base: Image.Image, project, piece: dict) -> None:
    path = _photo_abs(project, piece)
    if not path or not os.path.exists(path):
        d = ImageDraw.Draw(base)
        d.rectangle([piece["x"], piece["y"], piece["x"] + piece["w"], piece["y"] + piece["h"]],
                    outline=(200, 60, 60), width=2)
        d.text((piece["x"] + 4, piece["y"] + 4), "SIN FOTO", fill=(200, 60, 60), font=load_font(12))
        return
    im = Image.open(path)
    im.load()
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    ib = _img_box(piece, im)
    w, h = piece["w"], piece["h"]
    crop = _crop_source(im, ib, w, h, piece.get("bn"))
    rot = piece.get("rotation", 0) or 0
    if abs(rot) > 0.5:
        crop = crop.rotate(-rot, expand=True, resample=Image.BICUBIC)
    x, y = piece["x"], piece["y"]
    if piece.get("kind") == "circle":
        cw, ch = max(1, round(w)), max(1, round(h))
        mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, cw - 1, ch - 1), fill=255)
        base.paste(crop.convert("RGBA"), (int(round(x)), int(round(y))), mask)
        d = ImageDraw.Draw(base)
        d.ellipse((x, y, x + w - 1, y + h - 1), outline=(0, 0, 0), width=1)
    else:
        base.paste(crop, (int(round(x)), int(round(y))), crop if crop.mode == "RGBA" else None)


def _draw_label(base: Image.Image, piece: dict) -> None:
    d = ImageDraw.Draw(base)
    font = load_font(C.LABEL_FONT_PX)
    lines = (piece.get("label") or "").split("\n")
    lh = C.LABEL_FONT_PX * C.LABEL_LINE_HEIGHT
    tw = max(d.textlength(t, font=font) for t in lines) if lines else 0
    th = lh * len(lines)
    x, y, w, h = piece["x"], piece["y"], piece["w"], piece["h"]
    rot = abs(piece.get("rotation", 0)) % 180
    if 45 < rot < 135:
        w, h = h, w
    # abajo de la pieza; si no cabe, a la derecha; si no, arriba
    lx, ly = x, y + h + 5
    if ly + th > C.SHEET_H - 2:
        lx, ly = x + w + 5, y
        if lx + tw > C.SHEET_W - 2:
            lx, ly = x, y - th - 4
            if ly < 0:
                lx, ly = max(2, C.SHEET_W - tw - 2), C.SHEET_H - th - 2
    lx = max(2, min(lx, C.SHEET_W - tw - 2))
    for i, t in enumerate(lines):
        d.text((lx, ly + i * lh), t, fill=(0, 0, 0), font=font)


def _dashed_line(d, p1, p2, fill, dash=8, gap=6, width=1):
    x1, y1 = p1
    x2, y2 = p2
    if y1 == y2:
        x = x1
        while x < x2:
            d.line([(x, y1), (min(x + dash, x2), y2)], fill=fill, width=width)
            x += dash + gap
    else:
        y = y1
        while y < y2:
            d.line([(x1, y), (x2, min(y + dash, y2))], fill=fill, width=width)
            y += dash + gap


def render_guia(size: str) -> Image.Image:
    img = Image.new("RGB", (C.SHEET_W, C.SHEET_H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    s = C.SIZES[size]
    circle_cm = s["circle_cm"]
    rec_lo, rec_hi = s["recortada_cm"]
    rec_cm = round((rec_lo + rec_hi) / 2, 2)
    gor_cm = s["gorrito_cm"]
    title = (f"GUÍA {size.upper()} · NO IMPRIMIR · tamaño real 1:1 — "
             f"pastel Ø {circle_cm} cm · recortada ≈ {rec_cm} cm · con gorrito ≈ {gor_cm} cm")
    d.text((C.SAFE_LEFT, 14), title, fill=(0, 0, 0), font=load_font(12, bold=True))
    dia = C.cm(circle_cm)
    cy = min(C.SAFE_TOP, C.SHEET_H - C.PAGE_MIN_MARGIN - dia)
    d.ellipse((C.SAFE_LEFT, cy, C.SAFE_LEFT + dia, cy + dia), fill=(244, 244, 244), outline=(138, 138, 138), width=2)
    d.text((C.SAFE_LEFT + 6, cy + 6), f"COMPLETA Ø {circle_cm} cm", fill=(90, 90, 90), font=load_font(12))
    # rectángulo de la recortada centrado en el círculo
    rh = C.cm(rec_cm)
    rw = 0.5 * rh
    cx = C.SAFE_LEFT + dia / 2
    cyy = cy + dia / 2
    d.rounded_rectangle((cx - rw / 2, cyy - rh / 2, cx + rw / 2, cyy + rh / 2),
                        radius=8, fill=(218, 218, 218), outline=(60, 60, 60), width=1)
    font = load_font(12)
    for i, t in enumerate(["RECORTADA", f"≈ {rec_cm} cm", f"(gorrito {gor_cm})"]):
        tw = d.textlength(t, font=font)
        d.text((cx - tw / 2, cyy - 18 + i * 14), t, fill=(0, 0, 0), font=font)
    # círculos de carita de guirnalda en la GUÍA MINI
    if s.get("cabeza_cm"):
        lo, hi = s["cabeza_cm"]
        x = C.SAFE_LEFT + dia + C.GAP + 20
        y = cy + 10
        for cmv in (lo + 0.3, hi):
            dd = C.cm(cmv)
            d.ellipse((x, y, x + dd, y + dd), fill=(244, 244, 244), outline=(138, 138, 138), width=2)
            d.text((x + 4, y + 4), f"carita Ø {cmv} cm", fill=(90, 90, 90), font=font)
            y += dd + C.GAP + 10
    return img


def render_sheet(project, sheet: dict, guides: bool = True) -> Image.Image:
    if sheet.get("kind") == "guia":
        return render_guia(sheet["size"])
    img = Image.new("RGB", (C.SHEET_W, C.SHEET_H), (255, 255, 255))
    if guides:
        d = ImageDraw.Draw(img)
        _dashed_line(d, (C.GUIDE, 0), (C.GUIDE, C.SHEET_H), (200, 200, 200))
        _dashed_line(d, (0, C.GUIDE), (C.SHEET_W, C.GUIDE), (200, 200, 200))
        _dashed_line(d, (C.SAFE_RIGHT, 0), (C.SAFE_RIGHT, C.SHEET_H), (225, 225, 225))
        _dashed_line(d, (0, C.SAFE_BOTTOM), (C.SHEET_W, C.SAFE_BOTTOM), (225, 225, 225))
    for p in project.pieces:
        if p.get("sheet_id") == sheet["id"] and not p.get("pending"):
            _draw_piece(img, project, p)
    for p in project.pieces:
        if p.get("sheet_id") == sheet["id"] and not p.get("pending"):
            _draw_label(img, p)
    return img


def sheet_title_file(i: int, sheet: dict, total: int) -> str:
    kind = "GUIA" if sheet.get("kind") == "guia" else "hoja"
    return f"{i + 1:02d}_{kind}_{(sheet.get('size') or sheet.get('title') or '').replace(' ', '_')}"


def export_all(project, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    week = project.week or "semana"
    n_hojas = sum(1 for s in project.sheets if s.get("kind") == "hoja")
    n_guias = sum(1 for s in project.sheets if s.get("kind") == "guia")
    base = f"FOTOS COMESTIBLES {week} · {n_hojas} hojas + {n_guias} guías (no imprimir)"
    pdf_path = os.path.join(out_dir, base + ".pdf")
    png_dir = os.path.join(out_dir, base)
    os.makedirs(png_dir, exist_ok=True)
    images = []
    pngs = []
    for i, s in enumerate(project.sheets):
        img = render_sheet(project, s, guides=False)
        images.append(img)
        p = os.path.join(png_dir, sheet_title_file(i, s, len(project.sheets)) + ".png")
        img.save(p)
        pngs.append(p)
    if images:
        images[0].save(pdf_path, save_all=True, append_images=images[1:], resolution=C.PDF_DPI)
    return {"pdf": pdf_path, "pngs": pngs, "base": base}


def build_report(project, layout_problems: list[str]) -> str:
    lines = []
    week = project.week or "semana"
    lines.append(f"# Reporte · FOTOS COMESTIBLES {week}")
    lines.append("")
    n_hojas = sum(1 for s in project.sheets if s.get("kind") == "hoja")
    n_guias = sum(1 for s in project.sheets if s.get("kind") == "guia")
    lines.append(f"**{n_hojas} hojas + {n_guias} guías (no imprimir).** Zona útil 21×16 cm, guías a 2 cm, gap ≥ 0.5 cm.")
    lines.append("")
    lines.append("## Piezas por hoja")
    for i, s in enumerate(project.sheets):
        lines.append(f"### {i + 1}. {s.get('title')}")
        ps = [p for p in project.pieces if p.get("sheet_id") == s["id"]]
        if not ps:
            lines.append("- (vacía)")
        for p in ps:
            flags = []
            if p.get("gorrito"):
                flags.append("GORRITO")
            if p.get("bn"):
                flags.append("B/N")
            fl = (" · " + " · ".join(flags)) if flags else ""
            lines.append(f"- `{p['label'].splitlines()[0]}` @ ({p['x']:.0f},{p['y']:.0f}) "
                         f"{p['w'] / C.PX_PER_CM:.1f}×{p['h'] / C.PX_PER_CM:.1f} cm{flags and fl or ''} — {p['label'].splitlines()[-1] if len(p['label'].splitlines()) > 1 else ''}")
            path = _photo_abs(project, p)
            if path and os.path.exists(path):
                ib = p.get("img_box") or {}
                src_w = ib.get("width") or 0
                if src_w and src_w < p["w"]:
                    lines.append(f"  - ⚠ foto puede salir pixeleada (fuente {src_w:.0f}px < pieza {p['w']:.0f}px); pedir original")
        lines.append("")
    pend = [p for p in project.pieces if p.get("pending")]
    orders_pend = [o for o in project.orders if o.get("status") in ("pendiente",) and (o.get("mode") or o.get("edible_links"))]
    lines.append("## Pedidos con foto comestible: conteo (piezas + hechos + reportados)")
    hechos = [o for o in project.orders if o.get("status") == "hecha"]
    excluidos = [o for o in project.orders if o.get("status") == "excluida"]
    with_photo = [o for o in project.orders if o.get("mode") or o.get("edible_links")]
    lines.append(f"- Pedidos con foto comestible en Craft: **{len(with_photo)}**")
    lines.append(f"- Piezas en hojas: **{len([p for p in project.pieces if not p.get('pending')])}** · "
                 f"hechos aparte: **{len(hechos)}** · reportados fuera: **{len(pend) + len(excluidos)}** "
                 f"(total {len([p for p in project.pieces if not p.get('pending')]) + len(hechos) + len(pend) + len(excluidos)})")
    if pend:
        lines.append("")
        lines.append("## PENDIENTE (foto sin acceso / sin imagen)")
        for p in pend:
            o = project.order(p["order_id"]) or {}
            who = f"{o.get('name')} #{o.get('response')}" if o.get("response") else o.get("name")
            lines.append(f"- {who}: {p.get('photo_status')} — {o.get('edible_links')}")
    if excluidos:
        lines.append("")
        lines.append("## Reportados fuera")
        for o in excluidos:
            who = f"{o.get('name')} #{o.get('response')}" if o.get("response") else o.get("name")
            lines.append(f"- {who}: {o.get('status_reason')}")
    if layout_problems:
        lines.append("")
        lines.append("## ⚠ Problemas de acomodo")
        for pr in layout_problems:
            lines.append(f"- {pr}")
    return "\n".join(lines) + "\n"
