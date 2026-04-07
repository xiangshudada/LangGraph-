# LangGraph 学习与实践

本仓库用于学习 [LangGraph](https://github.com/langchain-ai/langgraph) 与 LangChain，结合阿里云通义千问（OpenAI 兼容接口）搭建简单 Agent、ReAct 工具调用与本地代理等示例。

## 环境要求

- Python 3.10+（建议）
- 通义千问 API：在 [DashScope](https://dashscope.aliyun.com/) 开通并获取 `DASHSCOPE_API_KEY`

## 依赖说明

各子目录依赖相近，主要包括：

- `langgraph`、`langchain-core`、`langchain-openai`
- `python-dotenv`
- `proxy` 另需：`fastapi`、`uvicorn`、`httpx`

建议在虚拟环境中按需安装，例如：

```bash
pip install langgraph langchain-core langchain-openai python-dotenv
# 若使用 proxy
pip install fastapi uvicorn httpx
```

（仓库根目录未提供 `requirements.txt`，可按运行报错补全版本。）

## 配置

在各示例使用的 `model` 目录或项目根下配置 `.env`（勿将密钥提交到 Git），例如：

```env
DASHSCOPE_API_KEY=你的密钥
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## 目录结构

| 路径 | 说明 |
|------|------|
| `main.py` | 根目录最小 LangGraph `StateGraph` 示例入口 |
| `agent/` | 单轮对话 Agent：状态图 + 千问，会话追加写入 `conversation_history.txt` |
| `react/` | ReAct 风格：绑定加减乘工具，`ToolNode` 与条件边路由 |
| `tools/` | 文档类工具示例（更新文档、保存文件等） |
| `proxy/` | Cursor CLI / OpenAI 兼容客户端与上游 LLM 之间的本地日志代理（FastAPI） |
| `Looping/`、`conditional/`、`multiNode/`、`multInput/`、`test-01/` | Jupyter Notebook：循环、条件、多节点、多输入等 LangGraph 练习 |

运行某示例如（在对应目录下，并保证 Python 能找到 `model` 包）：

```bash
cd agent
python main.py
```

`proxy` 的启动与 Cursor 侧 Base URL 配置见 `proxy/main.py` 文件顶部文档字符串。

## 许可证

若未单独声明，以仓库所有者约定为准；第三方库遵循其各自许可证。
