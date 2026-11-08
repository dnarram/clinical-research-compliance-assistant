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
    parser.add_argument("--prompt-version", default=None, help="v1 .. v4 (default: settings)")
    parser.add_argument("--out", default="docs/evaluation.md")
    parser.add_argument(
        "--golden", default="", help="golden-set file (default: data/eval/golden.jsonl)"
    )
    parser.add_argument("--pause", type=float, default=2.0, help="seconds between LLM calls")
    parser.add_argument(
        "--ids", default="", help="comma-separated golden ids to run (default: all)"
    )
    parser.add_argument(
        "--answers-in",
        default="",
        help="rescore answers saved by an earlier --with-answers run (no LLM calls)",
    )
    parser.add_argument("--no-expand", action="store_true", help="disable context expansion")
    parser.add_argument("--no-routing", action="store_true", help="disable document routing")
    parser.add_argument(
        "--answers-out",
        default="data/eval/answers.jsonl",
        help="where generated answers are written (with --with-answers)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    overrides: dict[str, object] = {}
    if args.prompt_version:
        overrides["prompt_version"] = args.prompt_version
    if args.no_expand:
        overrides["expand_context"] = False
    if args.no_routing:
        overrides["doc_routing"] = False
    settings = load_settings(**overrides)
    golden_path = Path(args.golden) if args.golden else settings.golden_path
    items = load_golden(golden_path)
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",") if i.strip()}
        items = [i for i in items if i.id in wanted]
        missing = wanted - {i.id for i in items}
        if missing:
            print(f"unknown ids: {', '.join(sorted(missing))}")
            return 1
    print(
        f"{len(items)} golden items, prompt {settings.prompt_version}, k={settings.k}, "
        f"expand={settings.expand_context}, routing={settings.doc_routing}"
    )

    assistant = Assistant.from_settings(settings)
    saved: dict[str, str] = {}
    if args.answers_in:
        for line in Path(args.answers_in).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                saved[row["question"]] = row["answer"]
        args.with_answers = True
        print(f"rescoring {len(saved)} saved answers from {args.answers_in} (no LLM calls)")

    def answer(question: str) -> str:
        if saved:
            return saved[question]
        time.sleep(args.pause)
        return assistant.ask(question).text

    report = evaluate_retrieval(
        assistant.vectorstore,
        items,
        settings,
        assistant.threshold,
        answer_fn=answer if args.with_answers else None,
    )
    if args.with_answers:
        answers_path = Path(args.answers_out)
        answers_path.parent.mkdir(parents=True, exist_ok=True)
        with answers_path.open("w", encoding="utf-8") as fh:
            for r in report.results:
                if r.answer is not None:
                    fh.write(
                        json.dumps(
                            {
                                "id": r.id,
                                "lang": r.language,
                                "question": r.question,
                                "keyword_coverage": r.keyword_coverage,
                                "honest_not_found": r.honest_not_found,
                                "answer": r.answer,
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
        print(f"Wrote {answers_path}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    title, _, body = report.to_markdown().partition("\n")
    config = (
        f"Configuration: prompt `{settings.prompt_version}`, context expansion "
        f"{'on' if settings.expand_context else 'off'}, document routing "
        f"{'on' if settings.doc_routing else 'off'}, embeddings `{settings.embedding_model}`, "
        f"LLM `{settings.llm_model}`. Generated by `scripts/03_evaluate.py`."
    )
    out.write_text(f"{title}\n\n{config}\n{body}", encoding="utf-8")
    print(json.dumps(summarise(report), indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
