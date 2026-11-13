"""Servidor local (solo 127.0.0.1) con API JSON + editor web estático. Solo stdlib."""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

from . import config as C
from .models import Project, DATA_DIR, OUT_DIR, PROJECT_FILE, new_piece_for_order
from .parse_orders import parse_craft_markdown, current_week_title
from . import photos as PH
from . import layout as L
from . import render as R
from . import remove_bg as RB

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
_LOCK = threading.Lock()


def get_project() -> Project:
    with _LOCK:
        return Project.load()


def save_project(p: Project) -> None:
    with _LOCK:
        p.save()


# ---------- acciones ----------

def api_import(text: str, source_name: str, week: str | None) -> dict:
    pages = parse_craft_markdown(text)
    if week is None:
        week = current_week_title(list(pages.keys()))
    if week not in pages:
        return {"error": f"Semana «{week}» no encontrada", "weeks": list(pages.keys())}
    p = Project(week=week, source_name=source_name)
    p.orders = [o.to_dict() for o in pages[week]["orders"]]
    save_project(p)
    return {"ok": True, "week": week, "weeks": list(pages.keys()),
            "orders": len(p.orders), "notes": pages[week]["notes"][:20]}


def api_prepare(p: Project, fetch: bool) -> dict:
    from .__main__ import prepare_pieces
    prepare_pieces(p, fetch=fetch)
    summary = L.auto_layout(p)
    problems = L.check_layout(p)
    save_project(p)
    return {"ok": True, "layout": summary, "problems": problems,
            "pieces": len(p.pieces), "orders": len(p.orders)}


def api_fetch_order(p: Project, oid: str) -> dict:
    o = p.order(oid)
    if not o:
        return {"error": "pedido no encontrado"}
    results = {}
    for url in o.get("edible_links", []):
        rec = PH.download_photo(url)
        p.photos[url] = rec
        results[url] = rec["status"]
        if rec.get("bn"):
            o["bn"] = True
    for url in o.get("ref_links", []):
        if url not in p.photos:
            rec = PH.download_photo(url)
            p.photos[url] = rec
            if rec.get("bn") and rec["status"] == "ok":
                o["bn"] = True  # la referencia manda: si es B/N se marca B/N
    # actualizar piezas de ese pedido con la foto ya bajada
    for piece in p.pieces:
        if piece["order_id"] == oid:
            src = None
            for url, rec in p.photos.items():
                if rec.get("status") in ("ok", "subida") and rec.get("src_url") in o.get("edible_links", []):
                    src = rec
            if src:
                piece["photo"] = src["path"]
                piece["photo_status"] = src["status"]
                piece["pending"] = False
    if any(r in ("ok", "subida") for r in results.values()) or not o.get("edible_links"):
        o["status"] = "lista"
    save_project(p)
    return {"ok": True, "results": results}


def api_upload(p: Project, oid: str, data: bytes, filename: str) -> dict:
    rec = PH.save_upload(data, filename)
    o = p.order(oid)
    url = f"local://{filename}"
    p.photos[url] = rec
    if o is not None and url not in o.get("edible_links", []):
        o.setdefault("edible_links", []).append(url)
    for piece in p.pieces:
        if piece["order_id"] == oid and piece.get("pending"):
            piece["photo"] = rec["path"]
            piece["photo_status"] = "subida"
            piece["pending"] = False
            if o and rec.get("bn"):
                o["bn"] = True
                piece["bn"] = True
            break
    if o is not None:
        o["status"] = "lista"
    save_project(p)
    return {"ok": True, "status": rec["status"], "w": rec["w"], "h": rec["h"], "bn": rec["bn"]}


def api_removebg(p: Project, pid: str, head_only: bool) -> dict:
    piece = p.piece(pid)
    if not piece or not piece.get("photo"):
        return {"error": "pieza sin foto"}
    path = piece["photo"]
    path = path if os.path.isabs(path) else os.path.join(DATA_DIR, path)
    im = PH.open_photo(path)
    rgba = RB.remove_background(im)
    if rgba is None:
        return {"error": "rembg no instalado (pip install rembg onnxruntime); la pieza queda como foto en caja", "available": False}
    box = RB.head_box(rgba) if head_only else RB.subject_box(rgba)
    if not box:
        return {"error": "no encontré sujeto en la máscara"}
    x0, y0, x1, y1 = box
    W, H = im.size
    mw, mh = (x1 - x0) * 0.02, (y1 - y0) * 0.02
    ib = {"left": max(0, x0 - mw), "top": max(0, y0 - mh),
          "width": min(W, (x1 - x0) + 2 * mw), "height": min(H, (y1 - y0) + 2 * mh)}
    # guardar el cutout como PNG con alfa
    out = os.path.join(os.path.dirname(path), "cut_" + os.path.basename(path))
    if not out.lower().endswith(".png"):
        out += ".png"
    rgba.save(out)
    piece["photo"] = os.path.relpath(out, DATA_DIR)
    piece["has_mask"] = True
    piece["head_only"] = head_only
    scale = piece["h"] / ib["height"]
    piece["img_box"] = ib
    piece["w"] = max(10, ib["width"] * scale)
    save_project(p)
    return {"ok": True, "img_box": ib, "w": piece["w"], "h": piece["h"]}


def api_export(p: Project) -> dict:
    problems = L.check_layout(p)
    out = R.export_all(p, OUT_DIR)
    report = R.build_report(p, problems)
    os.makedirs(os.path.join(OUT_DIR, out["base"]), exist_ok=True)
    rpath = os.path.join(OUT_DIR, out["base"], "reporte.md")
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(report)
    save_project(p)
    return {"ok": True, "pdf": os.path.basename(out["pdf"]), "base": out["base"],
            "report": report, "problems": problems}


# ---------- HTTP ----------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            return {}

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        if path == "/" or path == "/index.html":
            return self._static("index.html", "text/html")
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if path.startswith("/out/"):
            return self._serve_out(urllib.parse.unquote(path[len("/out/"):]))
        if path == "/api/state":
            return self._send(200, get_project().to_dict())
        m = re.match(r"^/api/sheet/([\w-]+)/render\.png$", path)
        if m:
            p = get_project()
            s = p.sheet(m.group(1))
            if not s:
                return self._send(404, {"error": "hoja no encontrada"})
            guides = urllib.parse.parse_qs(u.query).get("guides", ["1"])[0] == "1"
            from io import BytesIO
            img = R.render_sheet(p, s, guides=guides)
            buf = BytesIO()
            img.save(buf, "PNG")
            return self._send(200, buf.getvalue(), "image/png")
        return self._send(404, {"error": "not found"})

    def do_DELETE(self):
        m = re.match(r"^/api/piece/([\w-]+)$", urllib.parse.urlparse(self.path).path)
        if m:
            p = get_project()
            p.pieces = [x for x in p.pieces if x.get("id") != m.group(1)]
            save_project(p)
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        p = get_project()
        if path == "/api/import":
            b = self._json_body()
            text = b.get("text") or ""
            if b.get("path"):
                text = open(b["path"], encoding="utf-8").read()
            if not text.strip():
                return self._send(400, {"error": "texto vacío"})
            return self._send(200, api_import(text, b.get("source_name") or "pegado", b.get("week")))
        if path == "/api/prepare":
            b = self._json_body()
            return self._send(200, api_prepare(p, fetch=bool(b.get("fetch"))))
        m = re.match(r"^/api/order/([\w-]+)/fetch$", path)
        if m:
            return self._send(200, api_fetch_order(p, m.group(1)))
        m = re.match(r"^/api/order/([\w-]+)/upload$", path)
        if m:
            n = int(self.headers.get("Content-Length") or 0)
            data = self.rfile.read(n) if n else b""
            fn = self.headers.get("X-Filename") or "foto.jpg"
            return self._send(200, api_upload(p, m.group(1), data, fn))
        m = re.match(r"^/api/order/([\w-]+)$", path)
        if m:
            b = self._json_body()
            o = p.order(m.group(1))
            if o:
                for k in ("status", "status_reason", "mode", "size", "gorrito", "day", "bn", "name"):
                    if k in b:
                        o[k] = b[k]
                # reflejar cambios en sus piezas
                for piece in p.pieces:
                    if piece["order_id"] == o["id"]:
                        piece["size"] = o.get("size") or piece["size"]
                        piece["day"] = o.get("day") or piece["day"]
                        piece["gorrito"] = bool(o.get("gorrito"))
                        piece["bn"] = bool(o.get("bn"))
                save_project(p)
            return self._send(200, {"ok": True, "order": o})
        m = re.match(r"^/api/piece/([\w-]+)/removebg$", path)
        if m:
            b = self._json_body()
            return self._send(200, api_removebg(p, m.group(1), bool(b.get("head_only"))))
        m = re.match(r"^/api/piece/([\w-]+)$", path)
        if m:
            b = self._json_body()
            piece = p.piece(m.group(1))
            if piece:
                for k in ("x", "y", "w", "h", "rotation", "label", "sheet_id", "bn", "gorrito",
                          "head_only", "kind", "size", "day", "img_box", "pending", "photo", "photo_status"):
                    if k in b:
                        piece[k] = b[k]
                save_project(p)
            return self._send(200, {"ok": True, "piece": piece})
        if path == "/api/pieces":
            b = self._json_body()
            o = p.order(b.get("order_id", ""))
            if o:
                piece = new_piece_for_order(o, b.get("photo"), b.get("photo_status", "pendiente"))
                for k, v in b.items():
                    if k not in ("order_id", "photo", "photo_status") and hasattr(piece, k):
                        setattr(piece, k, v)
                p.pieces.append(piece.to_dict())
                save_project(p)
                return self._send(200, {"ok": True, "piece": piece.to_dict()})
            return self._send(400, {"error": "pedido no encontrado"})
        if path == "/api/layout/auto":
            summary = L.auto_layout(p)
            problems = L.check_layout(p)
            save_project(p)
            return self._send(200, {"ok": True, "layout": summary, "problems": problems})
        if path == "/api/sheets":
            from .models import Sheet
            b = self._json_body()
            s = Sheet(title=b.get("title") or "hoja", kind=b.get("kind") or "hoja", size=b.get("size") or "")
            p.sheets.append(s.to_dict())
            save_project(p)
            return self._send(200, {"ok": True, "sheet": s.to_dict()})
        m = re.match(r"^/api/sheet/([\w-]+)$", path)
        if m:
            b = self._json_body()
            s = p.sheet(m.group(1))
            if s and "title" in b:
                s["title"] = b["title"]
                save_project(p)
            return self._send(200, {"ok": True})
        if path == "/api/sheet/delete":
            b = self._json_body()
            sid = b.get("id")
            p.sheets = [s for s in p.sheets if s.get("id") != sid]
            for piece in p.pieces:
                if piece.get("sheet_id") == sid:
                    piece["sheet_id"] = ""
            save_project(p)
            return self._send(200, {"ok": True})
        if path == "/api/export":
            return self._send(200, api_export(p))
        if path == "/api/save":
            save_project(p)
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})

    def _static(self, name: str, ctype: str | None = None):
        name = os.path.basename(name)
        path = os.path.join(STATIC_DIR, name)
        if not os.path.exists(path):
            return self._send(404, {"error": "not found"})
        if ctype is None:
            ctype = {".js": "text/javascript", ".css": "text/css", ".html": "text/html"}.get(
                os.path.splitext(name)[1], "application/octet-stream")
        with open(path, "rb") as f:
            self._send(200, f.read(), ctype)

    def _serve_out(self, rel: str):
        base = os.path.realpath(OUT_DIR)
        full = os.path.realpath(os.path.join(OUT_DIR, rel))
        if not full.startswith(base) or not os.path.isfile(full):
            return self._send(404, {"error": "not found"})
        ctype = "application/pdf" if full.endswith(".pdf") else (
            "image/png" if full.endswith(".png") else "text/markdown; charset=utf-8")
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)


def serve(port: int = 8765, host: str = "127.0.0.1"):
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Pecanding · fotos comestibles → http://{host}:{port}  (Ctrl+C para salir)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
