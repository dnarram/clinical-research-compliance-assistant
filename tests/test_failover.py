"""Backup-key failover: only a daily-quota error switches clients."""

from __future__ import annotations

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from compliance_assistant.agent import FailoverChatModel
from compliance_assistant.config import load_api_keys
from compliance_assistant.vectorstore import FailoverEmbeddings, is_daily_quota

DAILY = "429 RESOURCE_EXHAUSTED: Embed content requests per day limit exceeded on Free Tier. Please retry in 22h"
MINUTE = "429 RESOURCE_EXHAUSTED: Quota exceeded for metric: requests per minute"


class Broken(DeterministicFakeEmbedding):
    message: str = DAILY

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError(self.message)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError(self.message)


def test_is_daily_quota() -> None:
    assert is_daily_quota(RuntimeError(DAILY))
    assert not is_daily_quota(RuntimeError(MINUTE))
    assert not is_daily_quota(RuntimeError("401 unauthenticated"))


def test_embeddings_switch_on_daily_quota_only() -> None:
    good = DeterministicFakeEmbedding(size=4)
    fo = FailoverEmbeddings([Broken(size=4), good])
    assert fo.embed_query("x") == good.embed_query("x") and fo.index == 1
    assert fo.embed_documents(["a"]) == good.embed_documents(["a"])

    minute = FailoverEmbeddings([Broken(size=4, message=MINUTE), good])
    with pytest.raises(RuntimeError, match="per minute"):
        minute.embed_query("x")
    assert minute.index == 0


def test_chat_model_switches_on_daily_quota() -> None:
    class Dead(BaseChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            raise RuntimeError(DAILY)

        @property
        def _llm_type(self) -> str:
            return "dead"

    class Alive(BaseChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="alive"))])

        @property
        def _llm_type(self) -> str:
            return "alive"

    fo = FailoverChatModel(models=[Dead(), Alive()])
    assert fo.invoke([HumanMessage(content="hi")]).content == "alive" and fo.index == 1


def test_load_api_keys_dedupes_and_orders(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "primary")
    monkeypatch.setenv("GEMINI_API_KEY_BACKUP", " backup , primary ,, ")
    assert load_api_keys() == ["primary", "backup"]
    # Empty (not deleted): load_dotenv never overrides a variable already in the environment,
    # so a real backup key in the developer's .env cannot leak into the assertion.
    monkeypatch.setenv("GEMINI_API_KEY_BACKUP", "")
    assert load_api_keys() == ["primary"]
