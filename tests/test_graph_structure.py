from langgraph.checkpoint.memory import InMemorySaver
from graph.builder import build_graph


def test_graph_nodes_and_edges():
    graph = build_graph(InMemorySaver())
    assert {'clarity', 'clarify', 'research', 'validator', 'synthesis'} <= set(graph.nodes)
