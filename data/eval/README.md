# Golden set

`golden.jsonl` is the ground truth the evaluation (`scripts/03_evaluate.py`) runs
against. It is written by hand from domain knowledge — **not generated** — because the
value of the test is knowing *which document and section* actually answers each question.

**TODO (David):** extend to 12–15 items. Suggested mix: 8–10 `in_domain` (cover all three
documents, at least two that need more than one document to answer, e.g. consent in
E6(R3) + Helsinki, safety reporting in E2A + E6(R3) §3.13), 3–4 `ood` (clinical advice,
unrelated topics, and one *in-domain-looking* question about a document that is not in
the KB, e.g. 21 CFR Part 50).

One JSON object per line:

| field | meaning |
|---|---|
| `id` | short unique slug |
| `type` | `in_domain` (must be answered with sources) or `ood` (must be refused) |
| `question_en` / `question_es` | the same question in both languages; retrieval is scored per language |
| `expected_doc_ids` | `doc_id`s from `data/kb/sources.yaml` that should appear in the top-k (any one counts as a hit) |
| `expected_sections` | optional; section numbers that should appear among the retrieved chunks (ICH "3.13.2", Helsinki paragraph "28") |
| `expected_keywords` | optional; phrases the *answer* should contain, checked only with `--with-answers` (costs LLM calls) |
| `notes` | where the answer lives, for the reviewer |

Metrics reported: retrieval hit-rate@k per language, section hit-rate, refusal accuracy on
`ood`, false-refusal rate on `in_domain`, and keyword coverage when answers are generated.
