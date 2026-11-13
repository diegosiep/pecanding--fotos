"""Constantes medidas del equipo Pecanding (fuente: skill pecanding-fotos-comestibles-canva v5).

Hoja comestible: 945 x 756 px = 25 x 20 cm  ->  37.7953 px = 1 cm.
Guías: vertical y horizontal a 2.0 cm del borde izquierdo/superior.
Zona útil por seguridad: 21 x 16 cm (x 75.6-869.4, y 75.6-680.4).
"""

PX_PER_CM = 37.7953
SHEET_W = 945
SHEET_H = 756
SHEET_W_CM = 25.0
SHEET_H_CM = 20.0

GUIDE = 2.0 * PX_PER_CM            # 75.6 px
SAFE_LEFT = GUIDE
SAFE_TOP = GUIDE
SAFE_RIGHT = SHEET_W - GUIDE       # 869.4
SAFE_BOTTOM = SHEET_H - GUIDE      # 680.4

GAP_CM = 0.5
GAP = GAP_CM * PX_PER_CM           # ~18.9 px de separación para la tijera

# Margen físico mínimo de la hoja (los círculos grandes sobresalen de la zona
# segura hacia abajo; nunca pueden salir de la hoja).
PAGE_MIN_MARGIN = 10               # px

# Tamaños aprobados por Diego (6-oct-2026). Círculo = diámetro del pastel en cm;
# recortada = alto del sujeto (≈75% del diámetro); gorrito = un pelito más chica.
SIZES = {
    "Mini": {
        "circle_cm": 11.2,
        "recortada_cm": (8.0, 9.0),      # rango; default = medio
        "gorrito_cm": 8.0,
        "cabeza_cm": (4.3, 5.4),         # guirnalda de caritas
    },
    "Mediano": {
        "circle_cm": 16.8,
        "recortada_cm": (12.0, 12.5),
        "gorrito_cm": 11.5,
        "cabeza_cm": (8.5, 9.0),         # solo cabeza
    },
    "Grande": {
        "circle_cm": 17.6,
        "recortada_cm": (13.0, 13.5),
        "gorrito_cm": 12.5,
        "cabeza_cm": None,
    },
    "Extra Grande": {
        "circle_cm": 18.8,
        "recortada_cm": (14.5, 14.5),
        "gorrito_cm": 13.5,
        "cabeza_cm": None,
    },
}
SIZE_ORDER = ["Mini", "Mediano", "Grande", "Extra Grande"]

# Etiquetas: 12 px, interlineado 1.15 (regla del equipo en Canva).
LABEL_FONT_PX = 12
LABEL_LINE_HEIGHT = 1.15

# Exportación PDF a tamaño real: 945 px a 96 dpi = 25 cm exactos.
PDF_DPI = 96.0


def cm(v: float) -> float:
    return v * PX_PER_CM


def px(v_cm: float) -> float:
    return v_cm * PX_PER_CM


def recortada_default_cm(size: str, gorrito: bool = False) -> float:
    s = SIZES[size]
    if gorrito:
        return s["gorrito_cm"]
    lo, hi = s["recortada_cm"]
    return round((lo + hi) / 2, 2)


def circle_px(size: str) -> float:
    return cm(SIZES[size]["circle_cm"])
