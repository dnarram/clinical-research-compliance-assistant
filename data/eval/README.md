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
| `notes` | where the answer lives, for the reviewer |

Metrics reported: retrieval hit-rate@k per language, section hit-rate, refusal accuracy on
`ood`, false-refusal rate on `in_domain`, and — when answers are generated — keyword
coverage and honesty on `not_in_kb` items. Generated answers are saved to
`data/eval/answers.jsonl` (and `answers_baseline_v3.jsonl` for the baseline run) so every
score can be checked against the text that produced it.
