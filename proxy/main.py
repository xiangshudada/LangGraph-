"""
Cursor CLI / OpenAI 兼容客户端 与 上游 LLM 之间的本地代理（非 LangGraph agent 内代理）。

作用：拦截 HTTP 请求与响应，将「单条」请求体、响应体追加写入日志文件。

用法概要：
  1. 安装：pip install fastapi uvicorn httpx python-dotenv
  2. 配置环境变量（可与现有 .env 共用）：
     - CURSOR_PROXY_UPSTREAM：上游 API 根地址，与你在 Cursor/CLI 里直连时一致
       例如：https://dashscope.aliyuncs.com/compatible-mode/v1
     - 可选 CURSOR_PROXY_BIND：监听地址，默认 127.0.0.1:8765
  3. 启动：在项目根目录执行
       python -m proxy.main
  4. 在 Cursor 设置或 CLI 中，将 API Base URL 改为：
       http://127.0.0.1:8765/v1
     （若监听端口不同，按实际修改；需与上游路径结构一致，避免重复 /v1）

日志文件：proxy/cursor_cli_proxy.log（UTF-8 追加）
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

load_dotenv()

_PROXY_DIR = Path(__file__).resolve().parent
_LOG_FILE = _PROXY_DIR / "cursor_cli_proxy.log"

# 与直连 LLM 时相同的 Base URL（通常含 /v1）
_DEFAULT_UPSTREAM = os.getenv(
    "CURSOR_PROXY_UPSTREAM",
    os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
)
_BIND = os.getenv("CURSOR_PROXY_BIND", "127.0.0.1:8765")

# 不向浏览器/客户端转发的 hop-by-hop 头
_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)


def _join_upstream(upstream: str, path: str) -> str:
    """避免 upstream 已以 /v1 结尾时与 path 里 v1/ 重复拼接。"""
    up = upstream.rstrip("/")
    p = path.lstrip("/")
    if up.endswith("/v1") and p.startswith("v1/"):
        p = p[len("v1/") :]
    return f"{up}/{p}"


def _safe_json_preview(raw: bytes, limit: int = 200_000) -> str:
    if not raw:
        return "(empty body)"
    if len(raw) > limit:
        return raw[:limit].decode("utf-8", errors="replace") + f"\n... (truncated, total {len(raw)} bytes)"
    try:
        obj: Any = json.loads(raw.decode("utf-8"))
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def _append_log(title: str, lines: list[str]) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    sep = "=" * 72
    block = "\n".join([sep, f"{title}  {stamp}", sep, *lines, "", ""])
    print(block, flush=True)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(block)


app = FastAPI(title="Cursor CLI LLM proxy", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "upstream": _DEFAULT_UPSTREAM}


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy_all(path: str, request: Request) -> Response:
    upstream = os.getenv("CURSOR_PROXY_UPSTREAM", _DEFAULT_UPSTREAM)
    query = request.url.query
    target = _join_upstream(upstream, path)
    if query:
        target = f"{target}?{query}"

    body = await request.body()
    req_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_HEADERS and k.lower() != "host"
    }

    _append_log(
        "CURSOR_CLI -> LLM (request)",
        [
            f"{request.method} {request.url.path}",
            f"forward_to: {target}",
            "headers (redacted Authorization): "
            + json.dumps(
                {k: ("***" if k.lower() == "authorization" else v) for k, v in req_headers.items()},
                ensure_ascii=False,
            ),
            "body:",
            _safe_json_preview(body),
        ],
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            resp = await client.request(
                request.method,
                target,
                content=body if body else None,
                headers=req_headers,
            )
    except httpx.RequestError as e:
        _append_log("LLM -> CURSOR_CLI (upstream error)", [repr(e)])
        return JSONResponse({"error": str(e), "proxy": "cursor_cli_proxy"}, status_code=502)

    resp_body = resp.content
    out_headers = {
        k: v for k, v in resp.headers.items() if k.lower() not in _HOP_HEADERS
    }

    _append_log(
        "LLM -> CURSOR_CLI (response)",
        [
            f"status: {resp.status_code}",
            "body:",
            _safe_json_preview(resp_body),
        ],
    )

    return Response(
        content=resp_body,
        status_code=resp.status_code,
        headers=dict(out_headers),
    )


def main() -> None:
    try:
        import uvicorn
    except ImportError:
        print("请先安装: pip install uvicorn[standard] fastapi httpx python-dotenv", file=sys.stderr)
        raise SystemExit(1)

    host, _, port_s = _BIND.partition(":")
    port = int(port_s or "8765")
    print(f"Cursor CLI 代理监听 http://{host}:{port}")
    print(f"上游 CURSOR_PROXY_UPSTREAM = {os.getenv('CURSOR_PROXY_UPSTREAM', _DEFAULT_UPSTREAM)}")
    print(f"日志文件: {_LOG_FILE}")
    uvicorn.run(
        "proxy.main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
