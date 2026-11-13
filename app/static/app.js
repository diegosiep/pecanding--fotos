/* Pecanding · fotos comestibles — editor. El servidor renderiza cada hoja como PNG
   (fuente de verdad); aquí se pintan selección, manijas y se editan piezas por API. */
const S = { project: null, sheetId: null, selected: null, mode: "mover", drag: null, scale: 1 };
const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const r = await fetch(path, opts.body && typeof opts.body !== "string"
    ? { ...opts, body: JSON.stringify(opts.body), headers: { "Content-Type": "application/json", ...(opts.headers || {}) } }
    : opts);
  return r.json();
};

async function reload() {
  S.project = await api("/api/state");
  $("weekLabel").textContent = S.project.week || "sin semana";
  renderOrders();
  renderTabs();
  if (!S.project.sheets.find(s => s.id === S.sheetId)) S.sheetId = S.project.sheets[0]?.id || null;
  await renderSheet();
}

function renderOrders() {
  const el = $("orders");
  el.innerHTML = "";
  for (const o of S.project.orders) {
    if (!(o.mode || (o.edible_links && o.edible_links.length))) continue;
    const div = document.createElement("div");
    div.className = "order";
    const flags = [o.gorrito ? '<span class="tag g">GORRITO</span>' : "", o.bn ? '<span class="tag bn">B/N</span>' : "",
      o.image_missing ? '<span class="badge warn">sin imagen</span>' : "", o.manual ? '<span class="badge">manual</span>' : ""].join("");
    div.innerHTML = `
      <div class="nm">${esc(o.num ? o.num + ". " : "")}${esc(o.name)} ${o.response ? "#" + esc(o.response) : ""} ${flags}</div>
      <div class="meta">${esc(o.size || "?")} ${o.shape === "otro" ? "· forma no redonda" : ""} · ${esc(o.mode || "?")} · ${esc(o.day)}</div>
      <div class="meta">${(o.edible_links || []).map(u => `<div class="links">🖼 ${esc(short(u))}</div>`).join("")}</div>
      <div class="meta"><span class="st ${esc(o.status)}">${esc(o.status)}${o.status_reason ? ": " + esc(o.status_reason) : ""}</span></div>
      <div class="btns">
        <button data-a="fetch">bajar foto</button>
        <button data-a="upload">subir…</button>
        <button data-a="piece">crear pieza</button>
        <button data-a="hecha">ya hecha</button>
        <button data-a="excl">excluir</button>
      </div>
      <input type="file" accept="image/*" style="display:none">`;
    div.querySelector('[data-a="fetch"]').onclick = async () => { setStatus("bajando…"); await api(`/api/order/${o.id}/fetch`, { method: "POST", body: {} }); reload(); };
    div.querySelector('[data-a="upload"]').onclick = () => div.querySelector('input[type=file]').click();
    div.querySelector('input[type=file]').onchange = async (e) => {
      const f = e.target.files[0]; if (!f) return;
      setStatus("subiendo…");
      await fetch(`/api/order/${o.id}/upload`, { method: "POST", body: f, headers: { "X-Filename": f.name } });
      reload();
    };
    div.querySelector('[data-a="piece"]').onclick = async () => {
      const url = (o.edible_links || [])[0] || "";
      const rec = S.project.photos[url];
      await api("/api/pieces", { method: "POST", body: { order_id: o.id, photo: rec?.path || "", photo_status: rec?.status || "sin_acceso" } });
      await api("/api/layout/auto", { method: "POST", body: {} });
      reload();
    };
    div.querySelector('[data-a="hecha"]').onclick = () => setOrderStatus(o.id, "hecha", "hecha en otro diseño");
    div.querySelector('[data-a="excl"]').onclick = () => { const r = prompt("motivo:"); if (r !== null) setOrderStatus(o.id, "excluida", r); };
    el.appendChild(div);
  }
}

async function setOrderStatus(id, st, reason) {
  await api(`/api/order/${id}`, { method: "POST", body: { status: st, status_reason: reason } });
  reload();
}

function renderTabs() {
  const el = $("tabs");
  el.innerHTML = "";
  S.project.sheets.forEach((s, i) => {
    const b = document.createElement("button");
    b.className = "tab" + (s.id === S.sheetId ? " active" : "");
    b.textContent = `${i + 1}. ${s.title}`;
    b.onclick = () => { S.sheetId = s.id; S.selected = null; renderTabs(); renderSheet(); };
    el.appendChild(b);
  });
}

async function renderSheet() {
  const cv = $("canvas");
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, cv.width, cv.height);
  if (!S.sheetId) { setStatus("sin hojas — prepara la semana o agrega una hoja"); return; }
  const img = new Image();
  img.src = `/api/sheet/${S.sheetId}/render.png?guides=1&t=${Date.now()}`;
  await img.decode();
  ctx.drawImage(img, 0, 0);
  const ps = S.project.pieces.filter(p => p.sheet_id === S.sheetId);
  for (const p of ps) {
    if (p.id === S.selected) {
      ctx.strokeStyle = "#b3543e"; ctx.lineWidth = 2;
      const rot = Math.abs(p.rotation || 0) % 180;
      const w = (rot > 45 && rot < 135) ? p.h : p.w, h = (rot > 45 && rot < 135) ? p.w : p.h;
      ctx.strokeRect(p.x, p.y, w, h);
      ctx.fillStyle = "#b3543e";
      ctx.fillRect(p.x + w - 6, p.y + h - 6, 12, 12); // manija de tamaño
    }
  }
  setStatus(`${ps.length} pieza(s) en esta hoja · hoja ${S.project.sheets.findIndex(s => s.id === S.sheetId) + 1}/${S.project.sheets.length}`);
}

/* ---- interacción en el canvas ---- */
function canvasPos(e) {
  const r = $("canvas").getBoundingClientRect();
  return { x: (e.clientX - r.left) * (945 / r.width), y: (e.clientY - r.top) * (756 / r.height) };
}
function hitPiece(x, y) {
  const ps = S.project.pieces.filter(p => p.sheet_id === S.sheetId);
  for (let i = ps.length - 1; i >= 0; i--) {
    const p = ps[i];
    const rot = Math.abs(p.rotation || 0) % 180;
    const w = (rot > 45 && rot < 135) ? p.h : p.w, h = (rot > 45 && rot < 135) ? p.w : p.h;
    if (x >= p.x && x <= p.x + w && y >= p.y && y <= p.y + h) return p;
  }
  return null;
}
function pieceIsResizeHandle(p, x, y) {
  const rot = Math.abs(p.rotation || 0) % 180;
  const w = (rot > 45 && rot < 135) ? p.h : p.w, h = (rot > 45 && rot < 135) ? p.w : p.h;
  return x >= p.x + w - 10 && x <= p.x + w + 2 && y >= p.y + h - 10 && y <= p.y + h + 2;
}

$("canvas").addEventListener("mousedown", (e) => {
  const { x, y } = canvasPos(e);
  const p = hitPiece(x, y);
  if (p) {
    S.selected = p.id;
    renderSheet();
    renderPanel();
    if (pieceIsResizeHandle(p, x, y)) S.drag = { type: "resize", id: p.id, ox: x, oy: y };
    else if (S.mode === "encadre" && p.photo) S.drag = { type: "frame", id: p.id, ox: x, oy: y, ib: { ...(p.img_box || {}) } };
    else S.drag = { type: "move", id: p.id, ox: x - p.x, oy: y - p.y };
  } else { S.selected = null; renderSheet(); $("panel").classList.add("hidden"); }
});
window.addEventListener("mousemove", (e) => {
  if (!S.drag) return;
  const { x, y } = canvasPos(e);
  const p = S.project.pieces.find(q => q.id === S.drag.id);
  if (!p) return;
  if (S.drag.type === "move") {
    p.x = Math.max(0, Math.min(945 - p.w, x - S.drag.ox));
    p.y = Math.max(0, Math.min(756 - p.h, y - S.drag.oy));
  } else if (S.drag.type === "resize") {
    const nw = Math.max(30, x - p.x), nh = Math.max(30, y - p.y);
    if (p.kind === "circle") { const d = Math.max(nw, nh); p.w = p.h = d; }
    else { p.w = nw; p.h = nh; }
  } else if (S.drag.type === "frame") {
    const ib = S.drag.ib;
    const W = p._srcW || ib.width, H = p._srcH || ib.height;
    ib.left = Math.max(0, Math.min(W - ib.width, S.drag.ib.left + (S.drag.ox - x) * (ib.width / p.w)));
    ib.top = Math.max(0, Math.min(H - ib.height, S.drag.ib.top + (S.drag.oy - y) * (ib.height / p.h)));
    p.img_box = ib;
  }
  renderSheet();
});
window.addEventListener("mouseup", async () => {
  if (!S.drag) return;
  const p = S.project.pieces.find(q => q.id === S.drag.id);
  S.drag = null;
  if (p) await api(`/api/piece/${p.id}`, { method: "POST", body: { x: p.x, y: p.y, w: p.w, h: p.h, img_box: p.img_box } });
  reload();
});
$("canvas").addEventListener("wheel", async (e) => {
  if (S.mode !== "encadre" || !S.selected) return;
  e.preventDefault();
  const p = S.project.pieces.find(q => q.id === S.selected);
  if (!p || !p.img_box || !p.img_box.width) return;
  const f = e.deltaY < 0 ? 1.1 : 1 / 1.1;
  const ib = p.img_box;
  const cx = ib.left + ib.width / 2, cy = ib.top + ib.height / 2;
  ib.width = Math.max(20, ib.width * f); ib.height = Math.max(20, ib.height * f);
  ib.left = Math.max(0, cx - ib.width / 2); ib.top = Math.max(0, cy - ib.height / 2);
  await api(`/api/piece/${p.id}`, { method: "POST", body: { img_box: ib } });
  renderSheet();
}, { passive: false });

/* ---- panel de pieza ---- */
function renderPanel() {
  const p = S.project.pieces.find(q => q.id === S.selected);
  const panel = $("panel");
  if (!p) { panel.classList.add("hidden"); return; }
  panel.classList.remove("hidden");
  const o = S.project.orders.find(q => q.id === p.order_id) || {};
  $("panelBody").innerHTML = `
    <label>etiqueta</label><textarea id="pLabel" rows="2">${esc(p.label || "")}</textarea>
    <label>día</label><input id="pDay" type="text" value="${esc(p.day || "")}">
    <label>tamaño pastel</label><select id="pSize">${["Mini", "Mediano", "Grande", "Extra Grande"].map(s => `<option ${s === p.size ? "selected" : ""}>${s}</option>`).join("")}</select>
    <label>modo</label><select id="pKind"><option value="circle" ${p.kind === "circle" ? "selected" : ""}>COMPLETA (círculo)</option><option value="cutout" ${p.kind === "cutout" ? "selected" : ""}>RECORTADA (fotito)</option></select>
    <label>ancho × alto (px = cm×37.7953)</label>
    <div style="display:flex;gap:4px"><input id="pW" type="number" value="${Math.round(p.w)}" style="width:50%"><input id="pH" type="number" value="${Math.round(p.h)}" style="width:50%"></div>
    <div class="rowbtns">
      <button id="pGorrito" class="${p.gorrito ? "primary" : ""}">GORRITO</button>
      <button id="pBn" class="${p.bn ? "primary" : ""}">B/N</button>
      <button id="pHead" class="${p.head_only ? "primary" : ""}">solo cabeza</button>
      <button id="pRot">rotar 90°</button>
    </div>
    <div class="rowbtns">
      <button id="pRmbg">quitar fondo</button>
      <button id="pModeMover" class="${S.mode === "mover" ? "primary" : ""}">mover</button>
      <button id="pModeEnc" class="${S.mode === "encadre" ? "primary" : ""}">encuadre (arrastrar/rueda)</button>
    </div>
    <label>mover a hoja</label><select id="pSheet">${S.project.sheets.map(s => `<option value="${s.id}" ${s.id === p.sheet_id ? "selected" : ""}>${esc(s.title)}</option>`).join("")}</select>
    <div class="rowbtns"><button id="pDel" style="color:#a00">quitar pieza</button></div>
    <div class="hint">pedido: ${esc(o.name || "")} ${o.response ? "#" + o.response : ""} · foto: ${esc(p.photo_status)}</div>`;
  const upd = (body) => api(`/api/piece/${p.id}`, { method: "POST", body });
  $("pLabel").onchange = async (e) => { await upd({ label: e.target.value }); reload(); };
  $("pDay").onchange = async (e) => { await upd({ day: e.target.value }); reload(); };
  $("pSize").onchange = async (e) => { await upd({ size: e.target.value }); reload(); };
  $("pKind").onchange = async (e) => { await upd({ kind: e.target.value }); reload(); };
  $("pW").onchange = async (e) => { await upd({ w: +e.target.value, ...(p.kind === "circle" ? { h: +e.target.value } : {}) }); reload(); };
  $("pH").onchange = async (e) => { await upd({ h: +e.target.value, ...(p.kind === "circle" ? { w: +e.target.value } : {}) }); reload(); };
  $("pGorrito").onclick = async () => { await upd({ gorrito: !p.gorrito }); reload(); };
  $("pBn").onclick = async () => { await upd({ bn: !p.bn }); reload(); };
  $("pHead").onclick = async () => { await upd({ head_only: !p.head_only }); reload(); };
  $("pRot").onclick = async () => { await upd({ rotation: ((p.rotation || 0) + 90) % 360 }); reload(); };
  $("pModeMover").onclick = () => { S.mode = "mover"; renderPanel(); };
  $("pModeEnc").onclick = () => { S.mode = "encadre"; renderPanel(); };
  $("pRmbg").onclick = async () => { setStatus("quitando fondo… (puede tardar la primera vez)"); const r = await api(`/api/piece/${p.id}/removebg`, { method: "POST", body: { head_only: p.head_only } }); setStatus(r.error || "fondo quitado"); reload(); };
  $("pSheet").onchange = async (e) => { await upd({ sheet_id: e.target.value }); reload(); };
  $("pDel").onclick = async () => { await fetch(`/api/piece/${p.id}`, { method: "DELETE" }); S.selected = null; reload(); };
}

/* ---- botones principales ---- */
$("btnImport").onclick = () => $("dlgImport").showModal();
$("btnCloseImport").onclick = () => $("dlgImport").close();
$("importFile").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  $("importText").value = await f.text();
};
$("btnDoImport").onclick = async () => {
  setStatus("importando…");
  const r = await api("/api/import", { method: "POST", body: { text: $("importText").value, source_name: $("importFile").files[0]?.name || "pegado" } });
  if (r.error) { setStatus(r.error + " · semanas: " + (r.weeks || []).join(" | ")); return; }
  $("dlgImport").close(); setStatus(`semana ${r.week}: ${r.orders} pedidos con foto`); reload();
};
$("btnPrepare").onclick = async () => {
  setStatus("preparando…");
  const r = await api("/api/prepare", { method: "POST", body: { fetch: $("chkFetch").checked } });
  setStatus(`piezas: ${r.pieces} · hojas: ${r.layout?.hojas} + guías ${r.layout?.guias} · problemas: ${(r.problems || []).length}`);
  reload();
};
$("btnAuto").onclick = async () => {
  const r = await api("/api/layout/auto", { method: "POST", body: {} });
  setStatus(`acomodado: ${(r.problems || []).length} problema(s)`); reload();
};
$("btnAddSheet").onclick = async () => {
  const title = prompt("título de la hoja:", "hoja nueva");
  if (!title) return;
  await api("/api/sheets", { method: "POST", body: { title } }); reload();
};
$("btnExport").onclick = async () => {
  setStatus("exportando…");
  const r = await api("/api/export", { method: "POST", body: {} });
  if (r.ok) {
    setStatus(`listo: ${r.base}`);
    $("reportText").textContent = r.report + (r.problems?.length ? "\n\nPROBLEMAS:\n" + r.problems.join("\n") : "");
    $("dlgReport").showModal();
    const a = document.createElement("a");
    a.href = "/out/" + encodeURIComponent(r.base) + "/reporte.md";
    a.textContent = "";
    console.log("PDF:", "/out/" + encodeURIComponent(r.pdf));
  } else setStatus("error al exportar");
};
$("btnCloseReport").onclick = () => $("dlgReport").close();

function setStatus(t) { $("statusbar").textContent = t; }
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function short(u) { return u.length > 60 ? u.slice(0, 57) + "…" : u; }

reload();
