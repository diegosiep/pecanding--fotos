"""Fuentes de pedidos.

Principal: importar el Markdown exportado de Craft (blocks get <pageId> --format
markdown, o Exportar como Markdown desde la app de Craft) — archivo o texto
pegado. Opcional: lectura viva del MCP remoto de Craft si se configuran
CRAFT_MCP_URL y CRAFT_TOKEN (OAuth bearer de la cuenta de Diego).
"""

from __future__ import annotations

import json
import os
import urllib.request

ROOT_BLOCK_ID = "eb716803-3714-b7f0-c398-941de1d16a2f"  # PEDIDOS PECANDING


def read_file_source(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _rpc(url: str, token: str, method: str, params: dict, session_id: str | None = None) -> tuple[dict, str | None]:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        sid = r.headers.get("Mcp-Session-Id")
        raw = r.read().decode("utf-8", "replace")
    # el MCP remoto responde SSE: buscar la línea data: con el resultado
    for line in raw.splitlines():
        if line.startswith("data:"):
            payload = json.loads(line[5:].strip())
            if "result" in payload:
                return payload["result"], sid
    return json.loads(raw), sid


def fetch_week_live(week_title: str, mcp_url: str | None = None, token: str | None = None) -> str:
    """Lee la sub-página de la semana desde el MCP remoto de Craft y regresa el markdown."""
    mcp_url = mcp_url or os.environ.get("CRAFT_MCP_URL", "https://mcp.craft.do/my/mcp")
    token = token or os.environ.get("CRAFT_TOKEN", "")
    if not token:
        raise RuntimeError("Falta CRAFT_TOKEN (OAuth de la cuenta de Craft de Diego)")
    res, sid = _rpc(mcp_url, token, "initialize", {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "pecanding-fotos", "version": "0.1"},
    })
    _rpc(mcp_url, token, "notifications/initialized", {}, sid)
    # buscar la página de la semana dentro del documento raíz
    res, _ = _rpc(mcp_url, token, "tools/call", {
        "name": "search",
        "arguments": {"query": week_title, "limit": 5},
    }, sid)
    text = json.dumps(res, ensure_ascii=False)
    import re
    m = re.search(r'"blockId"\s*:\s*"([0-9a-f-]{36})"', text) or re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text)
    if not m:
        raise RuntimeError(f"No se encontró la página «{week_title}» en Craft")
    page_id = m.group(1)
    res, _ = _rpc(mcp_url, token, "tools/call", {
        "name": "blocks_get",
        "arguments": {"rootBlockId": page_id, "format": "markdown"},
    }, sid)
    content = res.get("content", [])
    if isinstance(content, list):
        return "\n".join(c.get("text", "") for c in content)
    return str(content)
