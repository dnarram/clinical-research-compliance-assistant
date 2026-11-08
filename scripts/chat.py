#!/usr/bin/env python
"""Terminal chat with the assistant (one conversation thread; `/new` starts another).

uv run scripts/chat.py
uv run scripts/chat.py --trace      # print the graph nodes as they run
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compliance_assistant.agent import Assistant


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--trace", action="store_true", help="log each graph node")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.trace else logging.WARNING, format="%(message)s")
    for noisy in ("httpx", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    assistant = Assistant.from_settings()
    thread = assistant.new_thread()
    print(
        f"Model {assistant.settings.llm_model} · threshold {assistant.threshold} · thread {thread[:8]}"
    )
    print("Ask in English or Spanish. Commands: /new (new thread), /sources, /quit\n")
    last = None
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            continue
        if question in {"/quit", "/exit"}:
            return 0
        if question == "/new":
            thread = assistant.new_thread()
            print(f"(new thread {thread[:8]})")
            continue
        if question == "/sources":
            for s in last.sources if last else []:
                print(
                    f"  [{s.n}] {s.citation}  (score {s.score:.3f})"
                    if s.score
                    else f"  [{s.n}] {s.citation}"
                )
            continue
        last = assistant.ask(question, thread)
        print(f"\nassistant> {last.text}\n")
        if last.sources:
            print("  sources: " + "; ".join(f"[{s.n}] {s.citation}" for s in last.sources))
        else:
            print(f"  (no passages above the threshold; max score {last.max_score:.3f})")
        print()


if __name__ == "__main__":
    raise SystemExit(main())
