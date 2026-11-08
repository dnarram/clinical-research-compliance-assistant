#!/usr/bin/env python
"""LLM-as-judge over answers saved by scripts/03_evaluate.py --with-answers.

    uv run scripts/05_judge.py --answers data/eval/answers.jsonl
    uv run scripts/05_judge.py --answers data/eval/answers_baseline_v3.jsonl
    uv run scripts/05_judge.py --golden data/eval/heldout.jsonl --answers data/eval/heldout_answers.jsonl

Only in-domain items are judged (out-of-domain and not-indexed items are scored by rules in
03_evaluate.py). Verdicts are appended to `<answers>.judge-<model>.jsonl` after every call, so an
interrupted run resumes where it stopped. A markdown summary is printed and, with
--report, written to a file.
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compliance_assistant.agent import make_llm
from compliance_assistant.config import load_api_keys, load_settings
from compliance_assistant.evaluation import load_golden
from compliance_assistant.judge import JUDGE_MODEL, agreement, judge_answer


def summary_markdown(rows: list[dict], title: str) -> str:
    def block(sub: list[dict]) -> str:
        if not sub:
            return "n/a"
        counts = {
            v: sum(r["verdict"] == v for r in sub)
            for v in ("correct", "partially_correct", "incorrect")
        }
        mean = statistics.mean(r["score"] for r in sub)
        return f"{mean:.3f} (correct {counts['correct']}, partial {counts['partially_correct']}, incorrect {counts['incorrect']})"

    lines = [f"## {title}", "", "| scope | mean score · verdicts |", "|---|---|"]
    lines.append(f"| all ({len(rows)}) | {block(rows)} |")
    for lang in ("en", "es"):
        sub = [r for r in rows if r["lang"] == lang]
        lines.append(f"| {lang} ({len(sub)}) | {block(sub)} |")
    lang_ok = sum(r["language_ok"] for r in rows)
    lines.append(f"| answer in the user's language | {lang_ok}/{len(rows)} |")
    lines += ["", "| id | lang | verdict | missing / errors |", "|---|---|---|---|"]
    for r in rows:
        if r["verdict"] != "correct":
            detail = "; ".join(r["missing"] + [f"ERROR: {e}" for e in r["errors"]])[:220]
            lines.append(f"| {r['id']} | {r['lang']} | {r['verdict']} | {detail} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--golden", default="", help="golden-set file (default: data/eval/golden.jsonl)"
    )
    parser.add_argument("--answers", default="data/eval/answers.jsonl")
    parser.add_argument("--model", default=JUDGE_MODEL)
    parser.add_argument("--pause", type=float, default=2.0)
    parser.add_argument("--title", default="")
    parser.add_argument("--report", default="", help="also write the markdown summary here")
    parser.add_argument(
        "--compare", default="", help="another judge's verdict file: print agreement with it"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    settings = load_settings(llm_model=args.model)
    golden = {
        g.id: g for g in load_golden(Path(args.golden) if args.golden else settings.golden_path)
    }
    answers_path = Path(args.answers)
    out_path = answers_path.with_name(f"{answers_path.stem}.judge-{args.model}.jsonl")
    done = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                done[(row["id"], row["lang"])] = row
    llm = make_llm(settings, load_api_keys())

    todo = []
    for line in answers_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        a = json.loads(line)
        item = golden.get(a["id"])
        if item is None or item.type != "in_domain" or (a["id"], a["lang"]) in done:
            continue
        todo.append((a, item))
    print(f"{len(done)} verdicts cached, {len(todo)} to judge with {args.model}")

    with out_path.open("a", encoding="utf-8") as fh:
        for a, item in todo:
            v = judge_answer(llm, a["question"], item.reference, a["answer"], a["lang"])
            row = {
                "id": a["id"],
                "lang": a["lang"],
                **v.model_dump(),
                "score": v.score,
                "judge_model": args.model,
            }
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            done[(a["id"], a["lang"])] = row
            print(f"  {a['id']:<36} {a['lang']}  {v.verdict}")
            time.sleep(args.pause)

    rows = [done[k] for k in sorted(done)]
    md = summary_markdown(rows, args.title or f"LLM judge ({args.model}) — {answers_path.name}")
    print(md)
    if args.compare:
        other = [
            json.loads(x)
            for x in Path(args.compare).read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        stats = agreement(other, rows)
        md += f"\nAgreement with `{Path(args.compare).name}` (a) vs this judge (b): `{json.dumps(stats)}`\n"
        print(json.dumps(stats, indent=2))
    if args.report:
        Path(args.report).write_text(md, encoding="utf-8")
        print(f"Wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
