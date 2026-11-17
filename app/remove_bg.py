"""Quita el fondo de la foto comestible (fotito cake).

Usa `rembg` si está instalado (pip install rembg onnxruntime); si no, devuelve
None y la pieza se usa como foto completa en caja (el usuario puede recortar a
mano el img_box). El sujeto se mide con la máscara alfa para acomodar el alto
del sujeto al tamaño pedido (≈75% del diámetro del pastel)."""

from __future__ import annotations

import numpy as np
from PIL import Image

_SESSION = None
_SESSION_TRIED = False


def _session():
    global _SESSION, _SESSION_TRIED
    if _SESSION_TRIED:
        return _SESSION
    _SESSION_TRIED = True
    try:
        from rembg import new_session
        _SESSION = new_session("u2net")
    except Exception:
        _SESSION = None
    return _SESSION


def available() -> bool:
    return _session() is not None


def remove_background(img: Image.Image) -> Image.Image | None:
    """Devuelve RGBA con alfa 0 en el fondo, o None si rembg no está disponible."""
    sess = _session()
    if sess is None:
        return None
    try:
        from rembg import remove
        out = remove(img.convert("RGB"), session=sess)
        return out.convert("RGBA")
    except Exception:
        return None


def subject_box(rgba: Image.Image) -> tuple[int, int, int, int] | None:
    """Caja (x0,y0,x1,y1) del sujeto según la máscara alfa."""
    a = np.asarray(rgba)
    mask = a[..., 3] > 40
    if not mask.any():
        return None
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def head_box(rgba: Image.Image) -> tuple[int, int, int, int] | None:
    """Caja de la cabeza: franja superior donde el ancho de la máscara se angosta
    bajo los hombros (guirnalda de caritas)."""
    a = np.asarray(rgba)
    mask = a[..., 3] > 40
    if not mask.any():
        return None
    h, w = mask.shape
    rows = mask.sum(axis=1).astype(float)
    body_max = rows[int(h * 0.4):].max() if h > 10 else rows.max()
    if body_max <= 0:
        return None
    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0 = int(ys.min())
    y1 = int(ys.max()) + 1
    # buscar desde arriba el renglón donde el ancho cae bajo 60% del cuerpo y se sostiene
    limit = 0.6 * body_max
    run = 0
    head_end = y0 + max(1, int(h * 0.12))
    for y in range(y0, min(y1, y0 + int(h * 0.7))):
        if rows[y] < limit:
            run += 1
            if run >= 5:
                head_end = y - 4
                break
        else:
            run = 0
            head_end = y + 1
    head_end = max(head_end, y0 + 1)
    col = mask[head_end - 1] if head_end - 1 < h else mask[-1]
    cxs = np.where(col)[0]
    if len(cxs) == 0:
        return (x0, y0, x1, head_end)
    return (int(cxs.min()), y0, int(cxs.max()) + 1, head_end)
