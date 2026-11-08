#!/usr/bin/env python
"""Run the golden set (data/eval/golden.jsonl) and write docs/evaluation.md.

uv run scripts/03_evaluate.py                       # retrieval metrics only (embeddings)
uv run scripts/03_evaluate.py --with-answers        # also generate answers (LLM calls)
uv run scripts/03_evaluate.py --prompt-version v1 --with-answers
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compliance_assistant.agent import Assistant
from compliance_assistant.config import load_settings
from compliance_assistant.evaluation import evaluate_retrieval, load_golden, summarise


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--with-answers", action="store_true", help="generate answers (LLM calls)")
    parser.add_argument("--prompt-version", default=None, help="v1 | v2 | v3 (default: settings)")
    parser.add_argument("--out", default="docs/evaluation.md")
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between LLM calls")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    overrides = {"prompt_version": args.prompt_version} if args.prompt_version else {}
    settings = load_settings(**overrides)
    items = load_golden(settings.golden_path)
    print(f"{len(items)} golden items, prompt {settings.prompt_version}, k={settings.k}")

    assistant = Assistant.from_settings(settings)

    def answer(question: str) -> str:
        time.sleep(args.pause)
        return assistant.ask(question).text

    report = evaluate_retrieval(
        assistant.vectorstore,
        items,
        settings,
        assistant.threshold,
        answer_fn=answer if args.with_answers else None,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.to_markdown(), encoding="utf-8")
    print(json.dumps(summarise(report), indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
