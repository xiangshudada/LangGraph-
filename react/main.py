from typing import TypedDict, Annotated, Sequence

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.tools import tool
from langgraph.constants import START, END
from langgraph.graph import StateGraph, add_messages
from langgraph.prebuilt import ToolNode

from model import qwen


class AgentState(TypedDict):
    message: Annotated[Sequence[BaseMessage], add_messages]


graph = StateGraph(AgentState)


@tool
def add_two_numbers(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b

@tool
def subtract_two_numbers(a: int, b: int) -> int:
    """Subtract two numbers together"""
    return a - b

@tool
def multiply_two_numbers(a: int, b: int) -> int:
    """Multiply two numbers together"""
    return a * b

# 工具列表
qwen_tools = [add_two_numbers, subtract_two_numbers, multiply_two_numbers]

# 绑定工具
qwen_llm = qwen.bind_tools(qwen_tools)


def process_action(state: AgentState) -> AgentState:
    result = qwen_llm.invoke(state["message"])
    return {"message": [result]}


graph.add_node("process_Node", process_action)
graph.add_edge(START, "process_Node")
# 工具调用节点
tool_node = ToolNode(tools=qwen_tools, messages_key="message")
graph.add_node("tool_node", tool_node)


def should_call_tool(state: AgentState) -> bool:
    last = state["message"][-1]
    calls = getattr(last, "tool_calls", None)
    return bool(calls)

# 路由返回值 True/False 必须与 path_map 的键一致
graph.add_conditional_edges(
    "process_Node",
    should_call_tool,
    {True: "tool_node", False: END},
)

graph.add_edge("tool_node", "process_Node")

app = StateGraph.compile(graph)

def print_stream(stream: str):
    for s in stream:
        message = s["message"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()
        # for msg in s["message"]:
        #     msg.pretty_print()  # 或 print(msg)
        # print("-------------------------------------------------------------------")  # 可选：每步之间分隔

input_msg = input("Enter a message: ")
while input_msg.lower() != "exit":
    result = app.stream({"message": [HumanMessage(content=input_msg)]},stream_mode="values")
    print_stream(result)
    input_msg = input("Enter a message: ")
