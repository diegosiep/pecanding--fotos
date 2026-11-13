"""Baja fotos comestibles de las ligas de Craft (WhatsForm / Google Drive) y
analiza si van en blanco y negro. También guarda subidas locales."""

from __future__ import annotations

import hashlib
import os
import re
import urllib.request
import urllib.error
from io import BytesIO

from .models import PHOTOS_DIR

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 30


def drive_id(url: str) -> str | None:
    m = re.search(r"drive\.google\.com/file/d/([^/]+)/", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([^&]+)", url)
    if m:
        return m.group(1)
    return None


def candidate_urls(url: str) -> list[str]:
    """URLs de descarga a probar, en orden (regla del skill: usercontent+confirm=t)."""
    did = drive_id(url)
    if did:
        return [
            f"https://drive.usercontent.google.com/download?id={did}&export=download&confirm=t",
            f"https://lh3.googleusercontent.com/d/{did}=s0",
            f"https://drive.google.com/uc?export=download&id={did}",
        ]
    return [url]


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "image/*,*/*;q=0.8"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        if r.status != 200:
            raise urllib.error.URLError(f"HTTP {r.status}")
        return r.read()


def _ext_for(data: bytes, url: str) -> str:
    head = data[:12]
    if head.startswith(b"\xff\xd8"):
        return ".jpg"
    if head.startswith(b"\x89PNG"):
        return ".png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return ".webp"
    m = re.search(r"\.(jpe?g|png|gif|webp|bmp)(\?|$)", url, re.IGNORECASE)
    return "." + m.group(1).lower().replace("jpeg", "jpg") if m else ".img"


def download_photo(url: str, dest_dir: str = PHOTOS_DIR) -> dict:
    """Descarga una foto. Devuelve {status: ok|sin_acceso, path, w, h, bn, src_url}."""
    os.makedirs(dest_dir, exist_ok=True)
    key = hashlib.sha1(url.encode()).hexdigest()[:16]
    for cand in candidate_urls(url):
        try:
            data = _fetch(cand)
            if len(data) < 2000:
                continue
            from PIL import Image
            im = Image.open(BytesIO(data))
            im.load()
            ext = _ext_for(data, cand)
            path = os.path.join(dest_dir, key + ext)
            with open(path, "wb") as f:
                f.write(data)
            rel = os.path.relpath(path, os.path.dirname(PHOTOS_DIR))
            return {"status": "ok", "path": rel, "w": im.width, "h": im.height,
                    "bn": suggest_bn(path), "src_url": url}
        except Exception:
            continue
    return {"status": "sin_acceso", "path": "", "w": 0, "h": 0, "bn": False, "src_url": url}


def save_upload(data: bytes, filename: str, dest_dir: str = PHOTOS_DIR) -> dict:
    os.makedirs(dest_dir, exist_ok=True)
    ext = os.path.splitext(filename)[1].lower() or _ext_for(data, filename)
    key = hashlib.sha1(data + filename.encode()).hexdigest()[:16]
    path = os.path.join(dest_dir, key + ext)
    with open(path, "wb") as f:
        f.write(data)
    from PIL import Image
    im = Image.open(path)
    im.load()
    rel = os.path.relpath(path, os.path.dirname(PHOTOS_DIR))
    return {"status": "subida", "path": rel, "w": im.width, "h": im.height,
            "bn": suggest_bn(path), "src_url": filename}


def suggest_bn(path: str) -> bool:
    """Heurística: foto en blanco y negro (baja saturación) -> marcar B/N."""
    try:
        import numpy as np
        from PIL import Image
        im = Image.open(path).convert("RGB")
        im.thumbnail((256, 256))
        import colorsys
        a = np.asarray(im).astype(np.float32) / 255.0
        mx = a.max(axis=2)
        mn = a.min(axis=2)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
        bright = mx > 0.25
        if bright.sum() < 100:
            return False
        return float(sat[bright].mean()) < 0.08
    except Exception:
        return False


def open_photo(path: str):
    from PIL import Image
    im = Image.open(path)
    im.load()
    return im
