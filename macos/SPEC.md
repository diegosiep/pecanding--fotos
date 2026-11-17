# SPEC — PecandingFotos (app nativa macOS, Xcode)

Especificación completa del proyecto para armarlo en Xcode (o para que cualquier IA lo
arme desde cero). La implementación de referencia ya vive en `macos/PecandingFotos/`
(12 archivos Swift + `PecandingFotos.xcodeproj` generado por `scripts/generate_xcodeproj.py`);
este documento es la descripción a santo y seña de TODO: datos, medidas, algoritmos, UI y reglas.

**Objetivo**: app local nativa de macOS (SwiftUI/AppKit, macOS 13+) que prepare las
**fotos comestibles** de la semana de Pecanding sin Canva: lee los pedidos de Craft,
baja las fotos, las edita, las acomoda en hojas comestibles y exporta un PDF listo para
imprimir a tamaño real. La app Python del repo raíz (`app/`) es la referencia funcional
con tests; esta spec describe la misma funcionalidad para la versión nativa.

---

## 1. Fuentes de datos

### 1.1 Pedidos — Craft (documento `PEDIDOS PECANDING`, rootBlockId `eb716803-3714-b7f0-c398-941de1d16a2f`)
Una sub-página por semana con título tipo `9 al 15 de noviembre de 2026` (o
`30 de noviembre al 6 de diciembre de 2026`). Se importa pegando el markdown de
`blocks get <pageId> --format markdown` (o exportando la página como Markdown), o el
documento raíz completo (entonces se elige la semana en curso). Opcional: lectura viva
vía MCP remoto `https://mcp.craft.do/my/mcp` con `CRAFT_TOKEN` (OAuth de la cuenta).

Formato real de la página (ejemplos tomados de la semana 9–15 nov 2026):

```
## Lunes 9 de noviembre

**1. Ximena Trueba (#10640) —** Mini redondo; para 4 personas; ...; sin foto comestible; cake toppers de varias fotos (8 piezas, tamaño chico); [foto de referencia](https://files.whatsform.com/Rfc0JMR2k16VZWQg0zkS2.jpeg); [cake topper](https://files.whatsform.com/IaLtP1U2gAKdSum7_GtR-.jpeg); entrega: lunes 9 de noviembre de 2026.

**3. Inés Gómez Robledo (#10698) —** Mediano redondo; ...; foto comestible recortada (fotito cake); ...; [foto de referencia](https://files.whatsform.com/VAnmGZYRMjPoQj1TItnUg.png); [foto comestible](https://files.whatsform.com/-rJAo_gZElPGjDfOfgs5p.png); entrega: lunes 9 de noviembre de 2026.

**8. Isabela Winckelmann (#10704) —** Mediano redondo; ...; foto comestible completa (cubre la circunferencia del pastel); [foto comestible](https://files.whatsform.com/4YC8halkYDk2_3ndWk-4k.jpeg); entrega: miércoles 11 de noviembre de 2026.

**16. Michelle Aizpuru (#10696) —** Grande redondo; ...; foto comestible completa (cubre la circunferencia del pastel); [foto comestible](https://drive.google.com/file/d/1p1-Os9nsGFp3sglU2i1COxlxluMK2y5L/view?usp=sharing); entrega: jueves 12 de noviembre de 2026.

**29. Ana De Haro (#10717) —** ...; foto comestible recortada (fotito cake); [foto comestible](https://files.whatsform.com/zdNYmllvYMMkaFu-DydMl.jpeg); [foto comestible 2](https://drive.google.com/file/d/16CKJR2iteJ5NvmFMmkQsNJrXYLaA1JBy/view?usp=sharing); entrega: viernes 13 de noviembre de 2026.

4. Tay Xacur

Mediano de chocolate Ferrero betún rosita foto comestible con gorrito que diga felicidades [foto comestible](https://files.whatsform.com/tayxacur.jpeg)

**19. Maria Del Bosque (#10722-2) —** Mediano redondo; sin foto comestible; ...
```

### 1.2 Reglas del parser (obligatorias)
- Los bloques se separan por líneas en blanco; un renglón nuevo empieza con `**N.` (formal)
  o `N.` (manual, sin asteriscos). Los bloques siguientes que no sean formal se agregan al
  manual en curso. Los bloques sueltos sin número entran solo si contienen `foto comestible`
  Y un link `[foto comestible](…)`; el resto son notas internas.
- Campos formales separados por `;`. Del primer campo sale el tamaño:
  `Mini | Mediano | Grande | Extra Grande` (búsqueda fuzzy, p. ej. "oGrande" → Grande).
  Forma: `redondo` vs otro (corazón/rectangular → marcar "forma no redonda").
- Modo: `sin foto comestible` → none; `foto comestible recortada` / `fotito cake` →
  recortada; `foto comestible completa` → completa; si solo dice "foto comestible" con
  link → recortada marcada "revisar". `(el formulario no trae la imagen…)` → sin imagen.
- GORRITO solo si la MISMA campo que dice "foto comestible" trae "gorrito"
  (¡"cake toppers con gorrito" NO cuenta!).
- Links: regex `\[([^\]]+)\]\((https?://[^)\s]+)\)`; etiqueta que empieza con
  "foto comestible" → foto comestible (pueden ser varias: `[foto comestible 2]` →
  "pastel 2 de 2"); "foto de referencia" → referencia; "cake topper…" → ignorar.
- Día: del campo `entrega: …` (`lunes 9 de noviembre de 2026` → "Lunes 9"); si no, del
  encabezado `## …`.
- Números repetidos en Drive vienen con sufijo: `#10722-2`.
- Pedidos manuales (sin #) entran si traen `[foto comestible](…)`; se identifican por
  nombre (sin #) en etiqueta.
- Semana en curso: lunes–domingo hora CDMX; **en domingo la semana en curso es la que
  empieza mañana**. Títulos: `D al D de <mes> de AAAA` y `D de <mes> al D de <mes> de AAAA`.

### 1.3 Fotos
- WhatsForm: `https://files.whatsform.com/…` (descarga directa con User-Agent de
  navegador; si falla → estado `sin_acceso`).
- Google Drive `https://drive.google.com/file/d/<ID>/view…` → probar en orden:
  1. `https://drive.usercontent.google.com/download?id=<ID>&export=download&confirm=t`
  2. `https://lh3.googleusercontent.com/d/<ID>=s0`
  3. `https://drive.google.com/uc?export=download&id=<ID>`
  Si ninguna da 200 → `sin_acceso` → **PENDIENTE: foto en Drive sin acceso** en el
  reporte (nunca inventar ni dejar fuera en silencio).
- Subida manual de archivo local (file picker) → estado `subida`.
- Cache en `Application Support/PecandingFotos/photos/`; registro en `project.json`.
- Detección B/N: media de saturación HSV < 0.08 en píxeles brillantes (bajar a ~128 px).

---

## 2. Medidas exactas (NO inventar; si falta un tamaño, reportar y pedir medida)

- Hoja comestible: **945 × 756 px = 25 × 20 cm** → **37.7953 px = 1 cm**.
- Guías: vertical y horizontal a **2.0 cm** del borde izquierdo/superior (x=75.6, y=75.6).
  Zona útil por seguridad: **21 × 16 cm** → x 75.6–869.4, y 75.6–680.4.
- Separación entre piezas ≥ **0.5 cm** (18.9 px) para la tijera. Las esquinas de la caja
  de un círculo no cuentan (círculo = redondo).
- Círculos mediano/grande/XL no caben en 16 cm de alto: se pegan a la guía de
  arriba-izquierda (top=75.6, left=75.6) y **pueden sobresalir hacia abajo** (nunca
  fuera de la hoja; margen físico mínimo 10 px → XL top = 756−710.6−10).
- Etiquetas: nunca en el margen de arriba ni izquierdo, nunca encima de otra pieza,
  nunca fuera del borde derecho (left+width ≤ 945). Van abajo o a la derecha de la pieza.
  Fuente **12 px**, interlineado 1.15.

| Tamaño pastel | COMPLETA (círculo, contorno negro 1 px) | RECORTADA (alto del sujeto ≈75 % del Ø) | RECORTADA con gorrito | solo cabeza (guirnalda) |
|---|---|---|---|---|
| Mini | Ø 11.2 cm (423.3 px) | 8–9 cm (def 8.5) | 8 cm | caritas Ø 4.3–5.4 cm |
| Mediano | Ø 16.8 cm (635 px) | 12–12.5 cm (def 12.25) | 11.5 cm | 8.5–9 cm |
| Grande | Ø 17.6 cm (665 px) | 13–13.5 cm (def 13.25) | 12.5 cm | — |
| Extra Grande | Ø 18.8 cm (710.6 px) | 14.5 cm | 13.5 cm | — |

- Con gorrito van "un pelito más chiquitas" (columna 4); NO se dibuja el gorro.
- La foto de referencia manda: si trae gorrito o está en B/N, se marca en la etiqueta
  aunque Craft/Drive no lo digan. El filtro B/N aquí SÍ se puede aplicar (a diferencia
  de Canva): toggle B/N → render en escala de grises.
- Si la foto es de un pastel/diseño (no persona/mascota) → no entra; reportar.
- Si la resolución de la foto es menor que los px de la pieza → aviso "puede salir
  pixeleada; pedir original" en el reporte.

---

## 3. Modelo de datos (JSON, compartido con la app Python)

`Application Support/PecandingFotos/project.json`:

```json
{
  "week": "9 al 15 de noviembre de 2026",
  "source_name": "semana.md",
  "orders": [{"id", "num", "name", "response", "day", "size", "shape", "mode",
              "gorrito", "edible_links": [], "ref_links": [], "image_missing",
              "manual", "needs_review", "note", "status", "status_reason", "bn"}],
  "pieces": [{"id", "order_id", "kind": "circle|cutout", "size", "gorrito", "bn",
              "head_only", "day", "label", "photo", "photo_status",
              "img_box": {"left","top","width","height"}, "has_mask",
              "x","y","w","h","rotation", "sheet_id", "pending"}],
  "sheets": [{"id", "title", "kind": "hoja|guia", "size"}],
  "photos": {"<url>": {"status": "ok|subida|sin_acceso", "path", "w", "h", "bn", "src_url"}}
}
```

- `img_box` = rectángulo de la foto FUENTE (px) que se mapea a la caja de la pieza.
  Por defecto círculo: cuadrado centrado de lado min(W,H); cutout: foto completa.
- Etiqueta por defecto: `<TAMAÑO> COMPLETA|RECORTADA[ · GORRITO][ · B/N] · <día>[ · pastel N de M]\n<Nombre> #10xxx`
  (sin # para manuales).
- `pending=true` → no se acomoda ni se exporta; va al reporte como PENDIENTE.

---

## 4. Quitar fondo (fotito cake) — Vision

`VNGeneratePersonSegmentationRequest` (qualityLevel .balanced) sobre el CGImage:
- máscara `pixelBuffer` (OneComponent8, >40 = persona).
- **subject box** = bbox de la máscara; **head box** = franja superior donde el ancho de
  fila cae bajo 0.6×(máx ancho en el 60 % inferior), sostenido 5 filas.
- Aplicar máscara → CGImage RGBA con alfa 0 en el fondo; guardar PNG en `photos/cut_*.png`.
- Al medir: margen de 2 % por lado; `scale = h_pieza / alto_caja`; `w = ancho_caja × scale`;
  `img_box` = caja con margen. Si Vision no encuentra persona → fallback: foto completa
  en caja a la altura pedida (nunca inventar corte).

---

## 5. Acomodo automático (skyline bottom-left, igual que la app Python)

1. Piezas `pending` fuera. Orden: por tamaño (`Mini, Mediano, Grande, Extra Grande`);
   dentro de cada tamaño, por día (Lunes…Domingo) y etiqueta.
2. Por cada tamaño con piezas: primero una hoja **GUÍA** (`GUÍA <TAMAÑO>`), luego las
   hojas de acomodo.
3. Skyline sobre la zona útil [75.6, 869.4] × [75.6, 680.4]; candidatos x = {safeLeft} ∪
   {inicios de segmento} ∪ {right de colocada + gap}; y = max(perfil en [x, x+w]); elegir
   (y, x) mínimo; rechazar si colisiona (cajas expandidas por gap) o sale de zona.
   Círculos grandes (Ø > alto de zona): bottom límite = 756−10, top = min(75.6, bottom−Ø).
   Si una pieza no cabe en ninguna hoja → hoja nueva; si no cabe ni sola → pegada
   arriba-izquierda.
4. Rotación 90° de recortadas: caja efectiva = (h, w) al colisionar.
5. **Verificación** (`checkLayout`): toda caja dentro de zona (salvo círculos grandes por
   abajo), nada fuera de la hoja (≤945/≤756), gaps ≥ 0.4 cm entre pares, nada encimado.
   Los problemas se listan en el reporte.

---

## 6. Render de hojas (945×756, origen arriba-izquierda)

- Fondo blanco. En preview: guías punteadas en x=75.6, y=75.6 (y líneas tenues de zona
  segura derecha/inferior). En export: sin guías.
- **Círculo (completa)**: recortar `img_box` de la fuente, escalar a (w,h), recortar a
  elipse, pegar en (x,y), contorno negro 1 px.
- **Cutout (recortada)**: recortar `img_box`, escalar a (w,h); si `has_mask` la foto ya
  trae alfa; pegar en (x,y). Rotación: rotar alrededor del centro antes de pegar.
- **B/N**: filtro de saturación 0 sobre el recorte.
- **Etiqueta**: 12 px, abajo de la pieza (y+h+5); si no cabe abajo → a la derecha
  (x+w+5, y); si no cabe a la derecha → arriba (y−th−4); clamp a la hoja.
- **Hoja GUÍA 1:1** (una por tamaño, al inicio del grupo; título `… NO IMPRIMIR`):
  título en (75.6, 14) 12 px bold: `GUÍA <TAMAÑO> · NO IMPRIMIR · tamaño real 1:1 —
  pastel Ø X cm · recortada ≈ Y cm · con gorrito ≈ Z cm`; círculo Ø del pastel en
  (75.6, min(75.6, 756−10−Ø)) relleno #f4f4f4 contorno #8a8a8a 2 px; rectángulo de la
  recortada centrado en el círculo (alto=Y×37.7953, ancho=0.5×alto, #dadada, contorno
  1 px, radio 8) con texto `RECORTADA / ≈ Y cm / (gorrito Z)`; en la GUÍA MINI además
  dos círculos de carita Ø 4.6 y Ø 5.4 cm a la derecha con su etiqueta.

---

## 7. Exportación

- Nombre: `FOTOS COMESTIBLES <semana> · N hojas + K guías (no imprimir).pdf` en
  `Application Support/PecandingFotos/out/`.
- **PDF a tamaño real**: cada página MediaBox = **708.661 × 566.929 pt** (25×20 cm);
  la imagen de 945×756 px se dibuja escalada a esa página (equivalente a 96 dpi).
  Páginas = hojas en orden (GUÍAS incluidas; el "no imprimir" va en el nombre).
- PNG por hoja: `NN_hoja|GUIA_<tamaño>.png` en subcarpeta con el mismo nombre base.
- `reporte.md`: piezas por hoja con posición y medidas en cm, flags GORRITO/B/N, avisos
  de pixelación, lista PENDIENTE (sin acceso/sin imagen con sus ligas), reportados fuera
  con motivo, conteo estilo sobrechequeo:
  `pedidos con foto comestible en Craft = piezas en hojas + hechos aparte + reportados`.

---

## 8. UI (SwiftUI, ventana ≥ 1100×700)

- **Toolbar**: Importar Craft… (pegar markdown o archivo .md; si hay varias semanas,
  picker y auto-selección de la semana en curso), toggle "bajar fotos", Preparar semana,
  Auto acomodar, + hoja, Exportar PDF (prominente; muestra ruta y problemas, y revela en Finder).
- **Columna izquierda — pedidos** (solo los que tienen `mode` o links comestibles):
  nombre + #, tamaño/forma/modo/día, badges (GORRITO, B/N, manual, sin imagen), ligas,
  píldora de estado (pendiente/lista/hecha/excluida + motivo), botones: bajar foto,
  subir…, crear pieza, hecha, excluir.
- **Centro — hojas**: tabs numerados por hoja; lienzo AppKit (`NSViewRepresentable`)
  que dibuja el render a escala, con selección (borde rojo + manija SE 12 px). Ratón:
  mover (drag), tamaño (manija SE; círculo mantiene w=h), modo "encuadre" (drag mueve
  `img_box`, rueda hace zoom alrededor del centro). Solapa inferior: picker
  mover/encuadre + conteo de piezas de la hoja.
- **Derecha — inspector** de la pieza seleccionada: etiqueta (TextEditor), día,
  tamaño pastel, modo (círculo/cutout), ancho×alto px (círculo liga w=h), toggles
  GORRITO / B/N / solo cabeza, rotar 90°, quitar fondo (Vision, con headOnly), picker
  de hoja, quitar pieza, info del pedido y estado de la foto.
- Diálogos: importar (TextEditor + archivo + semana + error), exportar (alerta con ruta).

---

## 9. Estructura de archivos (target único `PecandingFotos`, macOS 13+)

```
macos/PecandingFotos/
  PecandingFotosApp.swift   @main App + WindowGroup
  Config.swift              medidas (px/cm, tabla de tamaños, zona segura)
  Models.swift              Order/Piece/Sheet/Project/PhotoRec (Codable, snake_case) + newPieceForOrder
  CraftParser.swift         markdown de Craft → semanas/pedidos (regexes de §1.2)
  PhotoStore.swift          descarga WhatsForm/Drive, subidas, cache, B/N
  VisionCutout.swift        segmentación de persona, cajas sujeto/cabeza, aplicar máscara
  LayoutEngine.swift        skyline + autoLayout + checkLayout
  SheetRenderer.swift       render 945×756 (piezas, etiquetas, guías, GUÍA 1:1)
  Export.swift              PDF 25×20 cm exacto, PNGs, reporte.md
  ProjectStore.swift        ObservableObject: estado, persistencia, acciones (preparar, fetch, subir, quitar fondo, exportar)
  ContentView.swift         NavigationSplitView: pedidos | lienzo | inspector + diálogos
  SheetCanvasView.swift     NSView del lienzo (hit-test, drag, resize, encuadre, rueda)
  Info.plist                bundle id com.pecanding.PecandingFotos, ATS arbitrary loads
```

Proyecto: `macos/PecandingFotos.xcodeproj` (objectVersion 56), generado por
`macos/scripts/generate_xcodeproj.py` — al agregar un .swift, rerun el script.
Build settings: `MACOSX_DEPLOYMENT_TARGET=13.0`, `SWIFT_VERSION=5.0`,
`INFOPLIST_FILE=PecandingFotos/Info.plist`, `PRODUCT_BUNDLE_IDENTIFIER=com.pecanding.PecandingFotos`.
Frameworks del sistema (autolink): SwiftUI, AppKit, Vision, CoreImage, CoreGraphics.

---

## 10. Guardarraíles (obligatorios)

- Nada se escribe en Craft ni en Drive desde la app. La app solo LEE pedidos.
- No inventar medidas: si falta un tamaño/forma, reportar y pedir.
- No borrar nada del proyecto del usuario; los `pending` nunca se exportan en silencio:
  van al reporte con su liga y motivo.
- Servidor/red: la app nativa no abre puertos; solo descarga de las ligas públicas.
- Las observaciones/textos del equipo en Craft se respetan tal cual (nunca "corregir").
- Cancelados: un pedido que desaparece de Drive se marca fuera, no se re-crea.

## 11. Verificación mínima antes de entregar

1. Parser sobre el fixture real (`tests/fixtures/semana_9_al_15.md` de la app Python):
   #10698 → Mediano recortada; #10704 → completa; #10696 → link Drive; #10717 → 2 fotos
   ("pastel 1 de 2 / 2 de 2"); manual "Tay Xacur" → gorrito; #10722-2 presente.
2. Layout: checkLayout sin problemas; XL dentro de la hoja; guías primero por tamaño.
3. Render: hoja 945×756; círculo Ø 635 px en Mediano; etiqueta visible.
4. Export: PDF con MediaBox 708.661×566.929 pt por página; PNGs; reporte con el conteo.
5. UI: importar → preparar → acomodar → editar una pieza → exportar.
