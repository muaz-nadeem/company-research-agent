import json
import os
import re

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

load_dotenv()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def get_llm(temperature: float = 0.2, json_mode: bool = False):
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=temperature,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        timeout=60,
        max_retries=1,
        response_mime_type="application/json" if json_mode else None,
    )


def format_messages_for_prompt(messages: list[BaseMessage], limit: int = 12) -> str:
    recent = messages[-limit:] if len(messages) > limit else messages
    lines: list[str] = []
    for msg in recent:
        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
        content = getattr(msg, "content", str(msg))
        if isinstance(content, list):
            content = str(content)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _extract_json_text(text: str) -> str:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        return fence_match.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _escape_control_chars_in_strings(text: str) -> str:
    """LLMs often emit literal newlines inside JSON string values."""
    out: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string and ch in "\n\r\t":
            if ch == "\n":
                out.append("\\n")
            elif ch == "\r":
                out.append("\\r")
            else:
                out.append("\\t")
            continue
        out.append(ch)
    return "".join(out)


def _repair_json(text: str) -> str:
    try:
        from json_repair import repair_json

        return repair_json(text)
    except Exception:
        return text


def parse_json_response(text: str | list) -> dict:
    if isinstance(text, list):
        text = ''.join(block.get('text', '') for block in text if isinstance(block, dict) and block.get('type') == 'text')
    raw = _extract_json_text(text if isinstance(text, str) else str(text))
    candidates = [
        raw,
        _escape_control_chars_in_strings(raw),
        _repair_json(raw),
        _repair_json(_escape_control_chars_in_strings(raw)),
    ]
    seen: set[str] = set()
    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    raise ValueError("Model did not return a JSON object")
