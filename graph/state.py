from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class ResearchState(TypedDict, total=False):
    request_message_id: str
    messages: Annotated[list, add_messages]
    intent: str
    company_name: str | None
    user_question: str
    clarity_status: str
    clarification_question: str | None
    clarification_rounds: int
    research_findings: str
    sources: list[dict]
    claims: list[dict]
    validation_result: str
    validation_feedback: str | None
    retry_recommended: bool
    research_attempts: int
    final_answer: str | None

