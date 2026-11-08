"""Conversation memory helpers.

The LangGraph checkpointer (`InMemorySaver`) persists the *whole* thread; the window is
applied when the prompt is built, so nothing is lost from the record while the context
sent to the model stays bounded.
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import InMemorySaver


def make_checkpointer() -> InMemorySaver:
    return InMemorySaver()


def new_thread_config(thread_id: str | None = None) -> dict[str, Any]:
    """The `config` LangGraph needs to route a call to a conversation thread."""
    return {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}


def window_history(messages: list[BaseMessage], n: int) -> list[BaseMessage]:
    """Last `n` messages, trimmed so the window starts with a human turn (a dangling
    assistant message at the start confuses the model about who said what)."""
    if n <= 0:
        return []
    recent = list(messages[-n:])
    while recent and recent[0].type != "human":
        recent.pop(0)
    return recent
