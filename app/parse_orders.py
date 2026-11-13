"""Parsea la página semanal de pedidos de Craft (PEDIDOS PECANDING) a pedidos.

Formatos soportados (salida de `blocks get <pageId> --format markdown` o export
Markdown de Craft):
  <page id="..."><pageTitle>9 al 15 de noviembre de 2026</pageTitle><content> ...
  ## Lunes 9 de noviembre
  **1. Ximena Trueba (#10640) —** Mini redondo; ...; foto comestible recortada (fotito cake); ...; [foto comestible](https://...); entrega: lunes 9 de noviembre de 2026.
  4. Tay Xacur            <- pedido manual (WhatsApp), sin #Response
  Mediano de chocolate ... foto comestible con gorrito ...
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, timedelta

MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
DIAS = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado", "domingo"]

SIZE_RE = re.compile(r"(extra\s*grande|grande|mediano|mini)", re.IGNORECASE)
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s*(.*)$")
NUM_RE = re.compile(r"^\s*\*{0,2}\s*(\d{1,3})\.\s*(.*)$")
FORMAL_HEAD_RE = re.compile(r"^\s*\*\*\s*(\d{1,3})\.\s*(.+?)\s*\(#([0-9]{4,6}(?:-\d+)?)\)\s*—\s*\*\*(.*)$")
PLAIN_HEAD_RE = re.compile(r"^\s*\*{0,2}\s*(\d{1,3})\.\s*(.+?)\s*(?:—|-)\s*(.*)$")
ENTREGA_RE = re.compile(r"entrega:\s*([^;.]+)", re.IGNORECASE)
DAY_IN_TEXT_RE = re.compile(r"\b(lunes|martes|mi[eé]rcoles|jueves|viernes|s[áa]bado|domingo)\s+(\d{1,2})\b", re.IGNORECASE)


@dataclass
class Order:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    num: str | None = None
    name: str = ""
    response: str | None = None
    day: str = ""                      # etiqueta corta: "Lunes 9"
    size: str = ""                     # Mini | Mediano | Grande | Extra Grande
    shape: str = "redondo"             # redondo | otro
    mode: str | None = None            # completa | recortada | None
    gorrito: bool = False
    edible_links: list = field(default_factory=list)
    ref_links: list = field(default_factory=list)
    image_missing: bool = False        # "(el formulario no trae la imagen ...)"
    manual: bool = False
    needs_review: bool = False
    note: str = ""
    status: str = "pendiente"          # pendiente | lista | hecha | excluida
    status_reason: str = ""

    def label_id(self) -> str:
        return f"{self.name} #{self.response}" if self.response else self.name

    def to_dict(self) -> dict:
        return asdict(self)


def _norm_size(raw: str) -> str:
    s = re.sub(r"\s+", " ", raw.strip().lower())
    if "extra" in s and "grande" in s:
        return "Extra Grande"
    if "grande" in s:
        return "Grande"
    if "mediano" in s or "mediana" in s:
        return "Mediano"
    if "mini" in s:
        return "Mini"
    return ""


def _split_blocks(text: str) -> list[list[str]]:
    blocks, cur = [], []
    for line in text.splitlines():
        if line.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append(cur)
    return blocks


def _day_from_heading(h: str) -> str:
    m = DAY_IN_TEXT_RE.search(h.lower())
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"
    return h.strip()


def _day_from_text(text: str, fallback: str) -> str:
    m = ENTREGA_RE.search(text)
    if m:
        d = _day_from_heading(m.group(1))
        if d:
            return d
    m = DAY_IN_TEXT_RE.search(text)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"
    return fallback


def _links(text: str) -> tuple[list[str], list[str]]:
    edible, ref = [], []
    for label, url in LINK_RE.findall(text):
        l = label.lower()
        if l.startswith("foto comestible"):
            edible.append((l, url))
        elif "referencia" in l:
            ref.append(url)
    edible.sort(key=lambda t: t[0])
    return [u for _, u in edible], ref


def _parse_entry(num, head, body_lines, day, formal) -> Order | None:
    text = " ".join([head] + body_lines).strip()
    o = Order(num=str(num) if num else None, day=day, manual=not formal)
    m = FORMAL_HEAD_RE.match(f"**{num}. {head}** {body_lines[0] if body_lines else ''}") if False else None
    # nombre y response
    head_full = head
    m = re.match(r"^(.*?)\s*\(#([0-9]{4,6}(?:-\d+)?)\)\s*(?:—|-)?\s*(.*)$", head_full)
    if m and m.group(2):
        o.name = m.group(1).strip(" *")
        o.response = m.group(2)
        rest = m.group(3)
    else:
        o.name = head_full.strip(" *-")
        rest = ""
    full = " ".join(x for x in [rest, *body_lines] if x).strip()
    # tamaño: buscar en las primeras palabras del renglón
    head_fields = full.split(";")[:4] if formal else [full]
    for f in head_fields:
        sm = SIZE_RE.search(f)
        if sm:
            o.size = _norm_size(sm.group(1))
            break
    if not o.size:
        sm = SIZE_RE.search(full)
        if sm:
            o.size = _norm_size(sm.group(1))
    # forma
    if re.search(r"coraz[oó]n|rectangular|cuadrado|forma de", full, re.IGNORECASE) and not re.search(r"\bredondo\b", full.split(";")[0] if formal else full, re.IGNORECASE):
        o.shape = "otro"
    # modo foto comestible
    low = full.lower()
    if "sin foto comestible" in low:
        o.mode = None
    else:
        if re.search(r"foto comestible\s*recortada|fotito\s*cake", low):
            o.mode = "recortada"
        elif re.search(r"foto comestible\s*completa", low):
            o.mode = "completa"
        elif "foto comestible" in low:
            o.mode = "recortada"
            o.needs_review = True
            o.note = "modo no explícito; se tomó recortada (fotito cake) — revisar"
    # gorrito (solo si tiene que ver con la foto comestible, no con cake toppers)
    for field in full.split(";"):
        fl = field.lower()
        if "foto comestible" in fl and "sin foto" not in fl and "gorrito" in fl:
            o.gorrito = True
    if not formal and "foto comestible" in low and "gorrito" in low:
        o.gorrito = True
    if "no trae la imagen" in low or "no trae las im" in low:
        o.image_missing = True
    o.edible_links, o.ref_links = _links(text if not formal else " ".join([head, *body_lines]))
    if formal:
        o.day = _day_from_text(full, day)
    else:
        o.day = _day_from_text(full, day)
    return o


def parse_week_page(title: str, markdown: str) -> tuple[str, list[Order], list[str]]:
    """Devuelve (week_title, orders, notas_internas)."""
    # quitar envoltura <page>/<content> si viene de `blocks get`
    body = re.sub(r"</?page[^>]*>|</?pageTitle>|</?content>", "", markdown)
    body = re.sub(r'<page id="[^"]*">', "", body)
    orders: list[Order] = []
    notes: list[str] = []
    day = ""
    current: dict | None = None  # {'num','head','lines','formal'}

    def flush():
        nonlocal current
        if current is None:
            return
        o = _parse_entry(current["num"], current["head"], current["lines"], day or current.get("day", ""), current["formal"])
        if o and (o.name or o.mode or o.edible_links):
            orders.append(o)
        current = None

    for block in _split_blocks(body):
        first = block[0]
        hm = HEADING_RE.match(first)
        if hm:
            flush()
            day = _day_from_heading(hm.group(1))
            continue
        nm = NUM_RE.match(first)
        if nm:
            flush()
            formal = first.lstrip().startswith("**")
            current = {"num": nm.group(1), "head": nm.group(2).strip(), "lines": block[1:], "formal": formal, "day": day}
            if formal and len(block) == 1:
                current["lines"] = []
                current["head"] = nm.group(2).strip()
            continue
        if current is not None and not current["formal"]:
            current["lines"].extend(block)
        else:
            txt = " ".join(block)
            if "foto comestible" in txt.lower() and "[foto comestible]" in txt.lower():
                flush()
                current = {"num": None, "head": txt, "lines": [], "formal": False, "day": day}
            else:
                notes.append(txt)
    flush()
    # solo nos interesan los que pueden traer foto comestible; el resto quedan en notas
    return title.strip(), orders, notes


def parse_craft_markdown(text: str) -> dict[str, dict]:
    """Soporta una página (blocks get de la semana) o el documento raíz con
    sub-páginas anidadas. Devuelve {week_title: {'orders': [...], 'notes': [...]}}."""
    pages = {}
    chunks = re.split(r'<page id="[^"]*">', text)
    for chunk in chunks:
        tm = re.search(r"<pageTitle>(.*?)</pageTitle>", chunk, re.S)
        if not tm:
            continue
        title = tm.group(1).strip()
        if title in pages:
            continue
        _, orders, notes = parse_week_page(title, chunk)
        pages[title] = {"orders": orders, "notes": notes}
    if not pages:
        title, orders, notes = parse_week_page("semana", text)
        pages[title] = {"orders": orders, "notes": notes}
    return pages


# ---------- semanas ----------

def parse_week_title(title: str) -> tuple[date, date] | None:
    t = title.lower().strip()
    m = re.match(r"(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", t)
    if m:
        d1, d2, mon, y = int(m.group(1)), int(m.group(2)), MONTHS.get(m.group(3), 0), int(m.group(4))
        if mon:
            return date(y, mon, d1), date(y, mon, d2)
    m = re.match(r"(\d{1,2})\s+de\s+(\w+)\s+al\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", t)
    if m:
        d1, mon1, d2, mon2, y = int(m.group(1)), MONTHS.get(m.group(2), 0), int(m.group(3)), MONTHS.get(m.group(4), 0), int(m.group(5))
        if mon1 and mon2:
            return date(y, mon1, d1), date(y, mon2, d2)
    return None


def current_week_title(titles: list[str], today: date | None = None) -> str | None:
    """Semana en curso (hora CDMX): lunes-domingo; en domingo, la que empieza mañana."""
    today = today or date.today()
    if today.weekday() == 6:  # domingo
        today = today + timedelta(days=1)
    best = None
    for t in titles:
        b = parse_week_title(t)
        if not b:
            continue
        start, end = b
        if start <= today <= end:
            return t
        if start > today and (best is None or start < parse_week_title(best)[0]):
            best = t
    return best
