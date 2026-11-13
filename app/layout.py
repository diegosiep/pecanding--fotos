"""Acomodo compacto de las piezas en hojas de 945x756 px.

Reglas (skill v5): zona útil 21x16 cm desde (75.6, 75.6); separación >= 0.5 cm
entre cajas; círculos mediano/grande/XL se pegan a la guía de arriba-izquierda y
pueden sobresalir hacia abajo (nunca fuera de la hoja); orden por tamaño de
pastel, cada tamaño abre con su hoja GUÍA 1:1; dentro del tamaño, por día.
"""

from __future__ import annotations

from . import config as C
from .models import Sheet

DAY_ORDER = ["Lunes", "Martes", "Miércoles", "Miercoles", "Jueves", "Viernes", "Sábado", "Sabado", "Domingo"]


def eff_dims(p: dict) -> tuple[float, float]:
    rot = abs(p.get("rotation", 0)) % 180
    if rot > 45 and rot < 135:
        return p["h"], p["w"]
    return p["w"], p["h"]


def _bottom_limit(p: dict) -> float:
    w, h = eff_dims(p)
    if p.get("kind") == "circle" and max(w, h) > (C.SAFE_BOTTOM - C.SAFE_TOP):
        return C.SHEET_H - C.PAGE_MIN_MARGIN
    return C.SAFE_BOTTOM


def _top_for(p: dict) -> float:
    w, h = eff_dims(p)
    if p.get("kind") == "circle":
        return min(C.SAFE_TOP, _bottom_limit(p) - max(w, h))
    return C.SAFE_TOP


def _collides(x, y, w, h, placed, gap) -> bool:
    for q in placed:
        qx, qy, qw, qh = q
        if x < qx + qw + gap and x + w + gap > qx and y < qy + qh + gap and y + h + gap > qy:
            return True
    return False


def pack_into_sheets(pieces: list[dict]) -> list[list[dict]]:
    """Devuelve lista de hojas; cada hoja es la lista de piezas que van en ella."""
    gap = C.GAP
    left, right = C.SAFE_LEFT, C.SAFE_RIGHT
    sheets: list[list[dict]] = []
    placed: list[tuple] = []
    skyline: list[list] = [[left, C.SAFE_TOP, right - left]]  # [x, y, width]

    def profile(x0, x1):
        y = C.SAFE_TOP
        for sx, sy, sw in skyline:
            if sx < x1 and sx + sw > x0:
                y = max(y, sy)
        return y

    def update_skyline(x, y, w, h):
        top = y + h
        new = []
        for sx, sy, sw in skyline:
            xe = sx + sw
            if xe <= x or sx >= x + w:
                new.append([sx, sy, sw])
            else:
                if sx < x:
                    new.append([sx, sy, x - sx])
                new.append([max(sx, x), top, min(xe, x + w) - max(sx, x)])
                if xe > x + w:
                    new.append([x + w, sy, xe - (x + w)])
        # fusionar adyacentes con misma y
        new.sort()
        merged = []
        for seg in new:
            if merged and abs(merged[-1][1] - seg[1]) < 0.5 and abs(merged[-1][0] + merged[-1][2] - seg[0]) < 0.5:
                merged[-1][2] += seg[2]
            else:
                merged.append(seg)
        skyline[:] = merged

    def place(p) -> bool:
        w, h = eff_dims(p)
        bl = _bottom_limit(p)
        top_min = _top_for(p)
        cands = {left}
        for sx, sy, sw in skyline:
            cands.add(sx)
        for q in placed:
            cands.add(q[0] + q[2] + gap)
        best = None
        for x in sorted(cands):
            if x + w > right + 0.5:
                continue
            y = max(profile(x, x + w), top_min)
            if y + h > bl + 0.5:
                continue
            if _collides(x, y, w, h, placed, gap):
                continue
            if best is None or (y, x) < (best[1], best[0]):
                best = (x, y)
        if best is None:
            return False
        x, y = best
        p["x"], p["y"] = x, y
        placed.append((x, y, w, h))
        update_skyline(x, y, w, h)
        return True

    for p in pieces:
        if sheets and place(p):
            sheets[-1].append(p)
            continue
        sheets.append([])
        placed = []
        skyline[:] = [[left, C.SAFE_TOP, right - left]]
        if not place(p):
            # pieza más grande que la zona útil: va sola, pegada arriba-izquierda
            w, h = eff_dims(p)
            p["x"] = C.SAFE_LEFT
            p["y"] = min(C.SAFE_TOP, C.SHEET_H - C.PAGE_MIN_MARGIN - h)
            placed.append((p["x"], p["y"], w, h))
            update_skyline(p["x"], p["y"], w, h)
        sheets[-1].append(p)
    return sheets


def _day_key(p: dict) -> tuple:
    d = (p.get("day") or "").split()[0].capitalize()
    try:
        di = DAY_ORDER.index(d)
    except ValueError:
        di = 99
    return (di, p.get("day", ""), p.get("label", ""))


def auto_layout(project) -> dict:
    """Reconstruye hojas GUÍA + acomodo por tamaño. Devuelve resumen."""
    pieces = [p for p in project.pieces if not p.get("pending")]
    for p in pieces:
        p["rotation"] = 0
    project.sheets = []
    by_size: dict[str, list[dict]] = {}
    for p in pieces:
        by_size.setdefault(p.get("size") or "Mediano", []).append(p)
    summary = {"sizes": {}, "guias": 0, "hojas": 0}
    for size in C.SIZE_ORDER:
        group = by_size.get(size)
        if not group:
            continue
        group.sort(key=_day_key)
        g = Sheet(title=f"GUÍA {size.upper()}", kind="guia", size=size)
        project.sheets.append(g.to_dict())
        summary["guias"] += 1
        packed = pack_into_sheets(group)
        for i, hoja in enumerate(packed):
            s = Sheet(title=f"{size} · hoja {i + 1}", kind="hoja", size=size)
            project.sheets.append(s.to_dict())
            for p in hoja:
                p["sheet_id"] = s.id
            summary["hojas"] += 1
        summary["sizes"][size] = len(group)
    for p in project.pieces:
        if p.get("pending"):
            p["sheet_id"] = ""
    return summary


def check_layout(project) -> list[str]:
    """Verificación de acomodo: cajas dentro de zona (salvo círculos grandes por
    abajo), gaps >= 0.4 cm entre pares, nada fuera de la hoja."""
    problems = []
    gap_min = 0.4 * C.PX_PER_CM
    by_sheet: dict[str, list[dict]] = {}
    for p in project.pieces:
        if p.get("sheet_id"):
            by_sheet.setdefault(p["sheet_id"], []).append(p)
    for sid, ps in by_sheet.items():
        for p in ps:
            w, h = eff_dims(p)
            x, y = p["x"], p["y"]
            if x < C.SAFE_LEFT - 0.5 and not (p.get("kind") == "circle" and max(w, h) > C.SHEET_H - 2 * C.SAFE_TOP):
                problems.append(f"{p['id']}: inicia antes de la guía izquierda (x={x:.0f})")
            if y < C.SAFE_TOP - 0.5 and not (p.get("kind") == "circle" and h > C.SAFE_BOTTOM - C.SAFE_TOP):
                problems.append(f"{p['id']}: inicia antes de la guía de arriba (y={y:.0f})")
            if x + w > C.SHEET_W + 0.5 or y + h > C.SHEET_H + 0.5:
                problems.append(f"{p['id']}: sale de la hoja")
            if x + w > C.SAFE_RIGHT + 0.5:
                problems.append(f"{p['id']}: cruza la zona segura derecha")
            if y + h > C.SAFE_BOTTOM + 0.5 and not (p.get("kind") == "circle" and h > C.SAFE_BOTTOM - C.SAFE_TOP):
                problems.append(f"{p['id']}: cruza la zona segura inferior (y+h={y + h:.0f})")
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                a, b = ps[i], ps[j]
                aw, ah = eff_dims(a)
                bw, bh = eff_dims(b)
                ax, ay, bx, by = a["x"], a["y"], b["x"], b["y"]
                ox = min(ax + aw, bx + bw) - max(ax, bx)
                oy = min(ay + ah, by + bh) - max(ay, by)
                if ox > 0 and oy > 0:
                    problems.append(f"se enciman {a['id']} y {b['id']}")
                elif ox > -gap_min and oy > -gap_min and not (ox > 0 or oy > 0):
                    problems.append(f"gap < 0.4 cm entre {a['id']} y {b['id']}")
    return problems
