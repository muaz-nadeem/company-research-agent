import os
import time
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from graph.builder import get_graph


class RunCancelled(Exception):
    pass


class UsageCollector(BaseCallbackHandler):
    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0

    def on_llm_end(self, response, **kwargs):
        self.calls += 1
        for generation in response.generations:
            for item in generation:
                usage = getattr(getattr(item, "message", None), "usage_metadata", None) or {}
                self.input_tokens += usage.get("input_tokens", 0)
                self.output_tokens += usage.get("output_tokens", 0)

    def metrics(self):
        rate_in, rate_out = os.getenv("INPUT_USD_PER_MILLION"), os.getenv("OUTPUT_USD_PER_MILLION")
        return {"llm_calls": self.calls, "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "estimated_llm_cost_usd": (self.input_tokens * float(rate_in) + self.output_tokens * float(rate_out)) / 1_000_000
                if rate_in and rate_out else None}


def missing_api_keys():
    return [key for key in ("GOOGLE_API_KEY", "TAVILY_API_KEY") if not os.getenv(key)]


def execute_run(run, on_event, cancelled, graph=None):
    graph = graph or get_graph()
    usage = UsageCollector()
    config = {"configurable": {"thread_id": run["thread_id"]}, "callbacks": [usage], "recursion_limit": 40}
    started = time.monotonic()
    snapshot = graph.get_state(config)
    values = snapshot.values if snapshot else {}
    same_request = values.get("request_message_id") == run["message_id"]
    if run.get("retry_of") and same_request:
        inputs = None  # Continue pending nodes, or recover a completed-but-unacknowledged report.
    elif run["resume"]:
        if not snapshot or not any(task.interrupts for task in snapshot.tasks):
            raise RuntimeError("No clarification is awaiting a response")
        inputs = Command(resume={"text": run["prompt"], "message_id": run["message_id"]})
    else:
        inputs = {"messages": [HumanMessage(content=run["prompt"], id=run["message_id"])],
                  "request_message_id": run["message_id"], "final_answer": None,
                  "research_attempts": 0, "validation_feedback": None, "validation_result": "",
                  "sources": [], "claims": [], "research_findings": "", "clarification_rounds": 0}
    if cancelled():
        raise RunCancelled()
    if inputs is not None or (snapshot and snapshot.next and not any(t.interrupts for t in snapshot.tasks)):
        for event in graph.stream(inputs, config, stream_mode="custom"):
            if cancelled():
                raise RunCancelled()
            on_event(event)
    if cancelled():
        raise RunCancelled()
    snapshot = graph.get_state(config)
    values = snapshot.values or {}
    metrics = {**usage.metrics(), "duration_ms": round((time.monotonic() - started) * 1000),
               "research_attempts": values.get("research_attempts", 0)}
    for task in snapshot.tasks:
        for intr in task.interrupts or []:
            return {"status": "needs_clarification", "answer": str(intr.value), "sources": [], "metrics": metrics}
    answer = values.get("final_answer")
    if not answer:
        raise RuntimeError("Research finished without a report")
    return {"status": "completed", "answer": answer, "sources": values.get("sources", []), "metrics": metrics}
