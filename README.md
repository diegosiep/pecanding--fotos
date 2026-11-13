# Pecanding · fotos comestibles (app local)

App personal para preparar las **fotos comestibles** de la semana sin Canva: lee los
pedidos de **Craft** (PEDIDOS PECANDING), baja las fotos (WhatsForm / Google Drive),
las acomoda en hojas comestibles y exporta un **PDF a tamaño real 25 × 20 cm** listo
para imprimir. Corre en **macOS y Linux** con Python 3.10+.

Replica las reglas del flujo de Canva (`pecanding-fotos-comestibles-canva` v5):

- Hoja 945 × 756 px = 25 × 20 cm (37.7953 px/cm), guías a 2 cm, zona útil 21 × 16 cm.
- Tamaños de pastel: Mini Ø 11.2 · Mediano Ø 16.8 · Grande Ø 17.6 · Extra Grande Ø 18.8 cm.
- **Completas**: círculo con contorno negro 1 px. **Recortadas (fotito cake)**: alto del
  sujeto ≈ 75 % del diámetro (Mini 8–9, Mediano 12–12.5, Grande 13–13.5, XL 14.5 cm);
  **con gorrito** un pelito más chicas (8 / 11.5 / 12.5 / 13.5 cm).
- Acomodo compacto por tamaño con ≥ 0.5 cm de separación; cada tamaño abre con su
  **hoja GUÍA 1:1** (no imprimir); dentro del tamaño, por día.
- Etiquetas: `TAMAÑO COMPLETA|RECORTADA[ · GORRITO][ · B/N] · día` + `Nombre #10xxx`.
- Pedidos manuales (WhatsApp, sin #) entran si traen `[foto comestible](…)`.
- Liga de Drive `drive.google.com/file/d/<ID>/view` → se baja con
  `drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`.
  Si no hay acceso público queda como **PENDIENTE: foto en Drive sin acceso** en el reporte.
- B/N: a diferencia de Canva, aquí sí se puede aplicar el filtro (toggle B/N).

## Instalación

```sh
python3 -m venv .venv && source .venv/bin/activate   # igual en macOS y Linux
pip install -r requirements.txt        # pillow + numpy
# opcional, para quitar el fondo de las recortadas (fotito cake) automático:
pip install rembg onnxruntime
```

Sin venv también funciona si ya tienes pillow/numpy en el Python del sistema.

## Uso

```sh
./run.sh                 # Linux / macOS (o doble clic en pecanding-fotos.command en macOS)
# abre http://127.0.0.1:8765
python3 -m app serve --port 8765
```

Flujo en la app:

1. **Importar Craft…** → pega el markdown de `blocks get <pageId> --format markdown`
   de la semana (o exporta la página como Markdown desde Craft), o elige el archivo.
   Si pegas el documento raíz completo, elige la semana en curso automáticamente.
2. **Preparar semana** (con "bajar fotos") → crea las piezas y descarga las fotos.
3. Edita en el canvas: mover, cambiar tamaño, rotar 90°, encuadre (arrastrar/rueda),
   quitar fondo (rembg), solo cabeza, GORRITO, B/N, etiqueta, día, hoja.
4. **Auto acomodar** → acomodo compacto por tamaño con sus GUÍAS.
5. **Exportar PDF** → `out/FOTOS COMESTIBLES <semana> · N hojas + K guías (no imprimir).pdf`
   a 25 × 20 cm exactos por página, PNG por hoja y `reporte.md` con el conteo
   (piezas + hechas + reportadas = pedidos con foto comestible), pendientes y avisos
   de foto pixeleada.

## Modo sin interfaz (corridas programadas)

```sh
python3 -m app run --source semana.md --week "9 al 15 de noviembre de 2026" --fetch --out out/
```

## Leer Craft en vivo (opcional)

Si configuras el MCP remoto de Craft con tu cuenta:

```sh
export CRAFT_MCP_URL=https://mcp.craft.do/my/mcp
export CRAFT_TOKEN=<tu token OAuth de Craft>
```

`app/craft_source.py::fetch_week_live("9 al 15 de noviembre de 2026")` regresa el markdown.
Sin token, usa la importación de archivo/pegado (recomendado).

## Estructura

```
app/
  config.py         medidas (px/cm, tamaños, zona segura)
  parse_orders.py   parser de la página semanal de Craft -> pedidos
  photos.py         descarga de ligas (WhatsForm/Drive), subidas, detección B/N
  remove_bg.py      quita fondo con rembg (opcional) y mide sujeto/cabeza
  layout.py         acomodo compacto (skyline) + verificación de zona/gaps
  render.py         hojas 945x756, GUÍAS 1:1, PDF 25x20 cm, reporte.md
  server.py         servidor local 127.0.0.1 + API JSON
  static/           editor web (canvas)
  __main__.py       CLI: serve | run
tests/              fixtures + tests (python3 tests/test_*.py)
data/               proyecto actual (project.json) y fotos cacheadas (git-ignored)
out/                PDFs/PNGs/reportes exportados (git-ignored)
```

## Pruebas

```sh
python3 tests/test_parse_orders.py
python3 tests/test_layout.py
python3 tests/test_render.py
python3 tests/test_e2e.py
```

## Notas de seguridad

- El servidor solo escucha en `127.0.0.1` (loopback); no expongas el puerto.
- Nada se sube a internet: las fotos se bajan directo de las ligas públicas o se suben
  desde tu máquina. No se escribe en Craft ni en Drive desde esta app.
