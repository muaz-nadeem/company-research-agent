from graph.state import ResearchState

MAX_RESEARCH_ATTEMPTS = 3


def route_after_clarity(state: ResearchState) -> str:
    if state.get("final_answer"):
        return "end"
    return "clarify" if state.get("clarity_status") == "needs_clarification" else "research"


def route_after_research(state: ResearchState) -> str:
    return "validator"


def route_after_validator(state: ResearchState) -> str:
    if (state.get("validation_result") == "insufficient"
            and state.get("retry_recommended", False)
            and state.get("research_attempts", 0) < MAX_RESEARCH_ATTEMPTS):
        return "research"
    return "synthesis"
