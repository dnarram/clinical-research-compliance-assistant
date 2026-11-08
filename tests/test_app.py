"""Streamlit app, offline: it loads, and a deploy that changes the package code replaces both
the imported modules and the cached Assistant (the bug seen on Streamlit Cloud: new app.py
running against an Assistant built by the previous deploy). No question is asked, so no API
call is made; a placeholder key is enough to construct the clients."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def placeholder_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder-key-for-tests")
    monkeypatch.setenv("GEMINI_API_KEY_BACKUP", "")


def test_app_loads_without_errors() -> None:
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.chat_input, "chat input rendered"


def test_stale_package_from_a_previous_deploy_is_reloaded() -> None:
    at = AppTest.from_file(APP, default_timeout=120).run()
    first = sys.modules["compliance_assistant.agent"]
    # Simulate a deploy: the modules in memory belong to another code version.
    sys.modules["compliance_assistant"].CODE_VERSION = "previous-deploy"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert sys.modules["compliance_assistant.agent"] is not first, "package was re-imported"
    assert sys.modules["compliance_assistant"].CODE_VERSION != "previous-deploy"
