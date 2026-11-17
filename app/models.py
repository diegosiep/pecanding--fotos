"""Modelo de proyecto: pedidos, piezas (fotos a imprimir) y hojas, con persistencia JSON."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field, asdict

from . import config as C

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PROJECT_FILE = os.path.join(DATA_DIR, "project.json")
PHOTOS_DIR = os.path.join(DATA_DIR, "photos")
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")


@dataclass
class Piece:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    order_id: str = ""
    kind: str = "circle"               # circle (completa) | cutout (recortada)
    size: str = "Mediano"              # tamaño del pastel
    gorrito: bool = False
    bn: bool = False
    head_only: bool = False            # solo cabeza (guirnalda)
    day: str = ""
    label: str = ""
    photo: str = ""                    # ruta relativa en data/photos
    photo_status: str = "pendiente"    # ok | sin_acceso | sin_imagen | subida
    img_box: dict = field(default_factory=dict)   # {left, top, width, height} en px de la foto fuente
    has_mask: bool = False             # cutout con fondo quitado (alpha)
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    rotation: float = 0.0              # grados (recortadas se pueden girar 90°)
    sheet_id: str = ""
    pending: bool = False              # no exportar (foto sin acceso, etc.)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Sheet:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    title: str = "hoja"
    kind: str = "hoja"                 # hoja | guia
    size: str = ""                     # para guías: Mini/Mediano/...

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Project:
    week: str = ""
    source_name: str = ""
    orders: list = field(default_factory=list)   # list[Order dict]
    pieces: list = field(default_factory=list)   # list[Piece dict]
    sheets: list = field(default_factory=list)   # list[Sheet dict]
    photos: dict = field(default_factory=dict)   # link -> {path, w, h, status, bn, src_url}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def load(cls, path: str = PROJECT_FILE) -> "Project":
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
                p = cls()
                p.week = d.get("week", "")
                p.source_name = d.get("source_name", "")
                p.orders = d.get("orders", [])
                p.pieces = d.get("pieces", [])
                p.sheets = d.get("sheets", [])
                p.photos = d.get("photos", {})
                return p
            except Exception:
                pass
        return cls()

    def save(self, path: str = PROJECT_FILE) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.to_dict(), f, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    # helpers -------------------------------------------------------------
    def order(self, oid: str) -> dict | None:
        for o in self.orders:
            if o.get("id") == oid:
                return o
        return None

    def piece(self, pid: str) -> dict | None:
        for p in self.pieces:
            if p.get("id") == pid:
                return p
        return None

    def sheet(self, sid: str) -> dict | None:
        for s in self.sheets:
            if s.get("id") == sid:
                return s
        return None

    def photo_path(self, link: str) -> str | None:
        rec = self.photos.get(link)
        if rec and rec.get("status") in ("ok", "subida") and rec.get("path"):
            p = rec["path"]
            return p if os.path.isabs(p) else os.path.join(DATA_DIR, p)
        return None


def new_piece_for_order(order: dict, photo_rel: str | None, photo_status: str, index: int = 0, total: int = 1) -> Piece:
    """Crea la pieza con geometría por defecto según tamaño/modo del pedido."""
    size = order.get("size") or "Mediano"
    mode = order.get("mode") or "recortada"
    p = Piece(order_id=order["id"], size=size, day=order.get("day", ""),
              gorrito=bool(order.get("gorrito")), head_only=False)
    p.kind = "circle" if mode == "completa" else "cutout"
    p.photo = photo_rel or ""
    p.photo_status = photo_status
    p.pending = photo_status != "ok" and photo_status != "subida"
    if total > 1:
        suffix = f" · pastel {index + 1} de {total}"
    else:
        suffix = ""
    if p.kind == "circle":
        d = C.circle_px(size)
        p.w = p.h = d
    else:
        h_cm = C.recortada_default_cm(size, p.gorrito)
        p.h = C.cm(h_cm)
        # ancho provisional (se ajusta al medir el sujeto); proporción 1:1 temporal
        p.w = p.h
    base = f"{size.upper()} {'COMPLETA' if p.kind == 'circle' else 'RECORTADA'}"
    flags = []
    if p.gorrito:
        flags.append("GORRITO")
    if order.get("bn"):
        flags.append("B/N")
        p.bn = True
    head = f"{base}{(' · ' + ' · '.join(flags)) if flags else ''} · {p.day}"
    who = f"{order.get('name', '')} #{order.get('response')}" if order.get("response") else order.get("name", "")
    p.label = f"{head}{suffix}\n{who}"
    return p
