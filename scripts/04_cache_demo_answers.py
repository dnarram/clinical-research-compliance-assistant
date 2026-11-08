#!/usr/bin/env python
"""Record the scripted demo conversation so OFFLINE_DEMO=1 can replay it without any API.

    uv run scripts/04_cache_demo_answers.py          # runs docs/demo_script questions live, stores answers
    OFFLINE_DEMO=1 uv run scripts/chat.py            # replays exact-match questions from the cache

The scripted questions are listed below; follow-ups are recorded together with the question
that preceded them so a referential turn replays in the right context.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compliance_assistant.agent import Assistant

DEMO_THREAD = [
    "What is the timeline for expedited reporting of a fatal unexpected ADR?",
    "¿Y para las demás reacciones graves e inesperadas?",
    "¿Qué exigen ICH E6(R3) y la Declaración de Helsinki para incluir a participantes que no pueden dar su consentimiento?",
    "¿Qué fármaco GLP-1 es mejor para perder peso?",
]
STANDALONE = [
    "What is the difference between a serious adverse event and a SUSAR?",
    "Under ICH E6(R3), what must the investigator do when a serious adverse event occurs?",
    "What does 21 CFR Part 50 say about informed consent?",
    "¿Qué debe contener el consentimiento informado según ICH E6(R3)?",
    "Compare ICH E6(R3) and the Declaration of Helsinki on participants who cannot consent.",
]


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    assistant = Assistant.from_settings()
    if assistant.demo_cache.enabled():
        print("Unset OFFLINE_DEMO before recording.")
        return 1
    thread = assistant.new_thread()
    previous = ""
    for q in DEMO_THREAD:
        ans = assistant.ask(q, thread)
        assistant.record_for_demo(ans, previous_question=previous)
        print(f"[thread] {q[:60]}… -> {len(ans.text)} chars, {len(ans.sources)} sources")
        previous = q
        time.sleep(3)
    for q in STANDALONE:
        ans = assistant.ask(q)
        assistant.record_for_demo(ans)
        print(f"[single] {q[:60]}… -> {len(ans.text)} chars, {len(ans.sources)} sources")
        time.sleep(3)
    print(f"{len(assistant.demo_cache)} cached answers in {assistant.settings.demo_cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
