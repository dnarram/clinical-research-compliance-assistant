# Golden set

`golden.jsonl` is the ground truth the evaluation (`scripts/03_evaluate.py`) runs
against. It is written by hand from domain knowledge — **not generated** — because the
value of the test is knowing *which document and section* actually answers each question.

**Status:** 25 items (19 in-domain incl. two multi-source, 4 out-of-domain, 2 not-in-KB), drafted by Claude from the indexed text and reviewed by the author — extend or correct freely. Suggested mix: 8–10 `in_domain` (cover all three
documents, at least two that need more than one document to answer, e.g. consent in
E6(R3) + Helsinki, safety reporting in E2A + E6(R3) §3.13), 3–4 `ood` (clinical advice,
unrelated topics, and one *in-domain-looking* question about a document that is not in
the KB, e.g. 21 CFR Part 50).

One JSON object per line:

| field | meaning |
|---|---|
| `id` | short unique slug |
| `type` | `in_domain` (must be answered with sources), `ood` (must be refused by the retrieval gate) or `not_in_kb` (looks in-domain but asks about a document not indexed: the *answer* must say it is not in the knowledge base; scored only with `--with-answers`) |
| `question_en` / `question_es` | the same question in both languages; retrieval is scored per language |
| `expected_doc_ids` | `doc_id`s from `data/kb/sources.yaml` that should appear in the top-k (any one counts as a hit, unless `all_docs_required: true` for multi-source items) |
| `expected_sections` | optional; section numbers that should appear among the retrieved chunks (ICH "3.13.2", Helsinki paragraph "28"). Prefix with the document (`ich_e6_r3:2.8.13`) to bind a section to one document; multi-source items must tag a section for every document and need a hit **from each** |
| `all_docs_required` | multi-source items: every expected document must be retrieved |
| `expected_keywords` | optional; phrases the *answer* should contain, checked only with `--with-answers` (costs LLM calls). Variants separated by `\|` (British/US spelling, the Spanish rendering a Spanish answer uses); matched as whole words after lower-casing and normalising typographic quotes |
| `reference` | in-domain items: the expert reference answer the LLM judge compares against (`scripts/05_judge.py`) |
| `notes` | where the answer lives, for the reviewer |

Metrics reported: retrieval hit-rate@k per language, section hit-rate, refusal accuracy on
`ood`, false-refusal rate on `in_domain`, and — when answers are generated — keyword
coverage and honesty on `not_in_kb` items. Generated answers are saved to
`data/eval/answers.jsonl` (and `answers_baseline_v3.jsonl` for the baseline run) so every
score can be checked against the text that produced it.

## Held-out set

`heldout.jsonl` (12 items × EN/ES) was written **after** prompt v4, context expansion and
document routing were frozen, on topics the golden set does not touch (unblinding, active
comparator and placebo, post-study events, IRB/IEC composition, investigator
qualifications, monitoring, protocol deviations, publication of results, biobanks,
compensation for harm; plus one clinical-dosing question that must be refused and one
question about ICH E9(R1), which is not indexed). It was run once for each configuration
and nothing was changed afterwards; its purpose is to show whether the improvements
measured on the golden set generalise. `tests/test_golden_consistency.py` checks both
files and that the held-out set repeats no golden question.

## LLM judge

`scripts/05_judge.py --model <judge>` compares each in-domain answer with its `reference`: `correct` (1),
`partially_correct` (0.5) or `incorrect` (0), with the missing points and errors listed.
Verdicts are saved next to the answers (`*.judge-<model>.jsonl`) with a markdown summary
(`*.judge-<model>.md`). The intended judge, `gemini-3.5-flash`, allows 20 requests/day on the
free tier, so the four answer sets were judged with `gemini-3.5-flash-lite`; `--compare` measures
agreement between judges (78.9 % on the 38 v3 golden answers both scored). The judge checks correctness against the expert reference, not faithfulness
to the retrieved passages.
