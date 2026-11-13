import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.parse_orders import parse_craft_markdown, parse_week_title, current_week_title
from datetime import date

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "semana_9_al_15.md")


def load():
    with open(FIX, encoding="utf-8") as f:
        return parse_craft_markdown(f.read())


def by_response(pages, week, resp):
    return next(o for o in pages[week]["orders"] if o.response == resp)


def test_pages_and_week():
    pages = load()
    assert "9 al 15 de noviembre de 2026" in pages
    b = parse_week_title("9 al 15 de noviembre de 2026")
    assert b == (date(2026, 11, 9), date(2026, 11, 15))
    b2 = parse_week_title("30 de noviembre al 6 de diciembre de 2026")
    assert b2 == (date(2026, 11, 30), date(2026, 12, 6))
    # jueves 12-nov-2026 -> semana en curso
    assert current_week_title(list(pages.keys()), date(2026, 11, 12)) == "9 al 15 de noviembre de 2026"
    # domingo 15 -> semana que empieza mañana (16 al 22, si existiera); aquí no está -> None o futura
    assert current_week_title(list(pages.keys()), date(2026, 11, 15)) is None


def test_formal_recortada():
    pages = load()
    o = by_response(pages, "9 al 15 de noviembre de 2026", "10698")
    assert o.size == "Mediano"
    assert o.mode == "recortada"
    assert o.gorrito is False
    assert o.day.startswith("Lunes")
    assert o.edible_links == ["https://files.whatsform.com/-rJAo_gZElPGjDfOfgs5p.png"]
    assert o.ref_links and "whatsform" in o.ref_links[0]
    assert o.manual is False


def test_completa():
    pages = load()
    o = by_response(pages, "9 al 15 de noviembre de 2026", "10704")
    assert o.mode == "completa"
    assert o.size == "Mediano"


def test_drive_link_and_two_photos():
    pages = load()
    o = by_response(pages, "9 al 15 de noviembre de 2026", "10696")
    assert o.size == "Grande" and o.mode == "completa"
    assert o.edible_links[0].startswith("https://drive.google.com/file/d/1p1-Os9nsGFp3sglU2i1COxlxluMK2y5L/view")
    o2 = by_response(pages, "9 al 15 de noviembre de 2026", "10717")
    assert len(o2.edible_links) == 2
    assert "drive.google.com" in o2.edible_links[1]


def test_manual_with_gorrito():
    pages = load()
    manuals = [o for o in pages["9 al 15 de noviembre de 2026"]["orders"] if o.manual]
    assert any(o.name == "Tay Xacur" and o.gorrito and o.mode == "recortada" and o.size == "Mediano" for o in manuals)


def test_sin_foto_comestible_excluded_or_named():
    pages = load()
    orders = pages["9 al 15 de noviembre de 2026"]["orders"]
    # los "sin foto comestible" no deben aparecer con mode
    for o in orders:
        if o.response in ("10640", "10722-2", "10723", "10733"):
            assert o.mode is None
    # duplicado con sufijo
    assert any(o.response == "10722-2" for o in orders)
    # la nota manual de menú (sin foto comestible) no crea pedido con foto
    assert not any("Loreto" in (o.name or "") and o.mode for o in orders)


def test_notes_captured():
    pages = load()
    notes = pages["9 al 15 de noviembre de 2026"]["notes"]
    assert any("Loreto" in n for n in notes)


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
    print("ALL PARSE TESTS PASSED")
