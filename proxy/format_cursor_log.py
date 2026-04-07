"""Parse cursor_cli_proxy.log and emit cursor_cli_proxy.formatted.md"""
import json
import re
from pathlib import Path


def main() -> None:
    log_path = Path(__file__).with_name("cursor_cli_proxy.log")
    text = log_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    body_start = None
    for i, line in enumerate(lines):
        if line.strip() == "body:":
            body_start = i + 1
            break
    if body_start is None:
        raise SystemExit("no body:")

    raw_body: list[str] = []
    depth = 0
    started = False
    for j in range(body_start, len(lines)):
        line = lines[j]
        if not started and line.strip().startswith("{"):
            started = True
        if started:
            raw_body.append(line)
            depth += line.count("{") - line.count("}")
            if depth == 0 and j > body_start:
                break

    req = json.loads("\n".join(raw_body))

    sys_content = ""
    for m in req.get("messages", []):
        if m.get("role") == "system":
            sys_content = m.get("content") or ""
            break

    idx = text.find("LLM -> CURSOR_CLI (response)")
    resp_text = text[idx:] if idx >= 0 else ""
    sse_lines = [
        ln
        for ln in resp_text.splitlines()
        if ln.startswith("data: ") and not ln.startswith("data: [DONE]")
    ]
    assembled: list[str] = []
    usage_final = None
    for ln in sse_lines:
        payload = ln[6:].strip()
        if not payload:
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        ch = obj.get("choices") or []
        if ch and ch[0].get("delta", {}).get("content") is not None:
            assembled.append(ch[0]["delta"]["content"])
        if obj.get("usage"):
            usage_final = obj["usage"]

    assistant_full = "".join(assembled)

    def fenced_block(s: str, lang: str = "text") -> str:
        """用足够长的反引号围栏包裹全文，避免提示词内的 ``` 破坏 Markdown。"""
        n = 3
        while True:
            fence = "`" * n
            if fence not in s:
                return f"{fence}{lang}\n{s}\n{fence}"
            n += 1
            if n > 200:
                raise ValueError("无法找到不与正文冲突的围栏长度")

    out: list[str] = []
    out.append("# Cursor CLI ↔ LLM 代理日志（格式化）")
    out.append("")
    out.append("源文件：`cursor_cli_proxy.log`")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 1. 请求概要（Cline → 代理 → DashScope）")
    out.append("")
    m_req = re.search(r"CURSOR_CLI -> LLM \(request\)\s+(\S+)", text)
    out.append(f"- **时间**: {m_req.group(1) if m_req else '（未知）'}")
    out.append("- **方法 / 路径**: `POST /v1/chat/completions`")
    out.append(
        "- **转发目标**: `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`"
    )
    m_h = re.search(
        r"headers \(redacted Authorization\): (\{.*?\})\n", text, re.DOTALL
    )
    if m_h:
        try:
            h = json.loads(m_h.group(1))
            out.append(f"- **User-Agent**: `{h.get('user-agent', '')}`")
        except json.JSONDecodeError:
            pass
    out.append(f"- **模型**: `{req.get('model')}`")
    out.append(f"- **stream**: `{req.get('stream')}`")
    out.append(
        f"- **stream_options**: `{json.dumps(req.get('stream_options'), ensure_ascii=False)}`"
    )
    out.append("")
    out.append("### 1.1 完整 messages（不省略，便于学习 Cline 提示词）")
    out.append("")
    for i, m in enumerate(req.get("messages", [])):
        role = m.get("role")
        out.append(f"#### [{i}] `{role}`")
        c = m.get("content")
        if role == "system":
            out.append(f"- 字符数: **{len(sys_content)}**")
            out.append("")
            out.append(fenced_block(sys_content, "text"))
        elif role == "user" and isinstance(c, list):
            titles = ["任务", "task_progress 提示", "environment_details"]
            for k, block in enumerate(c):
                t = block.get("text", "") if isinstance(block, dict) else str(block)
                title = titles[k] if k < len(titles) else f"块 {k}"
                out.append(f"##### 用户消息 · {title}（{len(t)} 字）")
                out.append("")
                out.append(fenced_block(t, "text"))
                out.append("")
        else:
            body = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False, indent=2)
            out.append(fenced_block(body, "json" if not isinstance(c, str) else "text"))
        out.append("")

    out.append("---")
    out.append("")
    out.append("## 2. 响应概要（LLM → 代理 → Cline）")
    out.append("")
    m_resp = re.search(r"LLM -> CURSOR_CLI \(response\)\s+(\S+)", text)
    out.append(f"- **时间**: {m_resp.group(1) if m_resp else '（未知）'}")
    out.append("- **HTTP**: `200`")
    out.append("- **格式**: SSE（`chat.completion.chunk`）")
    if usage_final:
        out.append("- **usage**（末包）:")
        out.append("")
        out.append("```json")
        out.append(json.dumps(usage_final, ensure_ascii=False, indent=2))
        out.append("```")
    out.append("")
    out.append("### 2.1 合并后的助手输出（所有 `delta.content` 拼接）")
    out.append("")
    out.append("```")
    out.append(assistant_full)
    out.append("```")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 3. 统计")
    out.append("")
    out.append(f"- SSE `data:` 行数（不含 `[DONE]`）: **{len(sse_lines)}**")
    out.append("- 逐行原始流仍见 `cursor_cli_proxy.log`")
    out.append("")

    out_path = log_path.with_name("cursor_cli_proxy.formatted.md")
    out_path.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {out_path}")

    # 另存完整 messages 为 JSON，避免 Markdown 围栏与提示词内反引号冲突时仍可查阅
    json_path = log_path.with_name("cursor_cli_proxy.messages.json")
    json_path.write_text(
        json.dumps(req.get("messages", []), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {json_path}")


if __name__ == "__main__":
    main()