from langgraph.graph import StateGraph, START, END
from app.graph.state import AgentState

from app.graph.nodes.extract_entities import extract_entities
from app.graph.nodes.detect_intent import detect_intent
from app.graph.nodes.qualification import qualification
from app.graph.nodes.answer import answer


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("extract_entities", extract_entities)
    builder.add_node("detect_intent", detect_intent)
    builder.add_node("qualification", qualification)
    builder.add_node("answer", answer)

    builder.add_edge(START, "extract_entities")
    builder.add_edge("extract_entities", "detect_intent")
    builder.add_edge("detect_intent", "qualification")
    builder.add_edge("qualification", "answer")
    builder.add_edge("answer", END)

    return builder.compile()