from typing import TypedDict, Union, List

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.constants import START, END
from langgraph.graph import StateGraph

from model import qwen

class AgentState(TypedDict):
    message: List[Union[HumanMessage,AIMessage]]

graph = StateGraph(AgentState)

def process_action(state: AgentState) -> AgentState:
    msgs = state["message"]
    result = qwen.invoke(msgs)
    state["message"] =  [*msgs, result]
    return state

graph.add_node("process_node", process_action)

graph.add_edge(START,"process_node")
graph.add_edge("process_node",END)

app = graph.compile()

userMsg = input("Enter your message: ")

conversition_history = []

while userMsg != "exit":
    human_msg = HumanMessage(content=userMsg)
    conversition_history.append(human_msg)

    result = app.invoke({"message": conversition_history})

    print(result["message"][-1].content)
    ai_msg = AIMessage(content=result["message"][-1].content)
    conversition_history.append(ai_msg)
    userMsg = input("Enter your message: ")

lines = []
for m in conversition_history:
    role = "用户" if m.type == "human" else "助手"
    lines.append(f"[{role}]\n{m.content}\n")
text = "\n".join(lines) + "\n" + ("-" * 40) + "\n"  # 每次会话加分隔线
with open("./conversation_history.txt", "a", encoding="utf-8") as f:
    f.write(text)