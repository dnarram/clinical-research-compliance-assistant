# System prompt iterations

The four versions live in `src/compliance_assistant/prompts.py` and can be selected with
`PROMPT_VERSION=v1|v2|v3|v4` (or `load_settings(prompt_version=...)`). The notebook
(section 5) runs the same question through v1 and v4 so the difference is visible. This
page separates what was **observed** on the live model from what each version was
**designed** to fix, so nothing is claimed that was not seen.

## v1 — "answer from the documents" (class baseline)

```
Use the following information from the documents provided to answer the question
concisely and clearly.
```

**Observed** (notebook §5, `gemini-3.5-flash-lite`, question *Who is responsible for
reporting a SUSAR to the regulatory authorities, and how fast?*): a correct and fluent
answer — sponsor responsibility, 7 calendar days plus 8 for the complete report, the
minimum criteria — but **without citation markers**. The sources panel lists six passages
(retrieval is the same for every prompt), yet nothing in the text says which passage
supports which sentence, and the wording is paraphrased rather than quoted. For a CRA
that means re-reading the guideline to verify every claim.

**Structural gaps** (by construction, not separately measured): no role or audience; no
instruction for the case where the passages do not contain the answer, so nothing stops
the model from completing from general knowledge; no language policy; no scope limit.

## v2 — role, audience, scope, insufficiency rule

Added: role (*regulatory compliance assistant for clinical research*), the audience
(CRAs, coordinators, data managers, PV staff), the explicit rule to answer only from the
context, the "I could not find this in my knowledge base" behaviour, and the
not-legal-advice disclaimer.

v2 was an intermediate design step and was **not evaluated on its own**; its remaining
gaps are structural: no citation protocol (traceability still rests on a trailing
sources list), no rule for passages from different documents that disagree, and no
language policy for Spanish questions over an English corpus.

## v3 — citation protocol, differing sources, language policy, format

Added: numbered `[n]` citations on every factual sentence (the numbers map to the sources
panel built by `retrieval.format_context`); the rule to attribute differing positions to
their documents; the language policy (answer in the user's language, quote regulatory
wording verbatim in English, keep SAE/SUSAR/IB/IMP untranslated); and the output format
(direct answer first, then detail, no closing summary).

**Observed** on the live model (`gemini-3.5-flash-lite`, 2026-11-08, notebook §§5, 7, 8):

- E2A timelines answered with `[n]` citations and verbatim quotes ("as soon as possible
  but no later than 7 calendar days…" [2]).
- A Spanish referential follow-up ("¿Dice lo mismo la Declaración de Helsinki sobre esa
  situación?") produced a Spanish answer that **contrasts** E6(R3) §2.8.13 with Helsinki
  ¶28 and attributes each position.
- *What does 21 CFR Part 50 say about informed consent?* — retrieval is grounded (consent
  passages score 0.77), and the model answered "I could not find this in my knowledge
  base… It does not contain information on 21 CFR Part 50" instead of inventing FDA
  content. This is the behaviour the insufficiency rule exists for.
- Out-of-domain questions never reach the model: the calibrated retrieval gate routes
  them to the templated refusal.

**Observed failure that the prompt alone did not fix:** on the first end-to-end run an
English question came back in Spanish, despite the language rule. The deterministic
`Reply in English.` / `Responde en español.` line that `prompts.build_messages` appends to
the user message closed that gap — hard constraints belong in code, the prompt carries
the judgement calls.

**Known residue:** the model often appends a closing "this is regulatory information, not
legal or medical advice" line although the format rule says not to add disclaimers unless
required. Harmless, arguably desirable in this domain; left as is.

## v4 — graded refusals, multi-step answers, complete lists (in use)

**Observed on v3** in the first full golden-set run (25 items × EN/ES; answers saved in
`data/eval/answers_baseline_v3.jsonl`):

- *From the investigator to the regulatory authority: who reports a serious adverse reaction
  to whom, and within which timelines?* was **refused outright** ("I could not find this in
  my knowledge base…") although E6(R3) §2.7.2 (investigator → sponsor, immediately), §3.13.2
  (sponsor → regulators per E2A) and E2A §III.B (7 and 15 days) were all retrievable. The
  insufficiency rule was all-or-nothing.
- Spanish questions were refused **in English**: the rule quoted the English sentence and
  the model copied it, overriding the language line. It happened to the reporting-chain
  question in the first v3 run and to both not-indexed-document questions (21 CFR Part 50,
  EU CTR) in the baseline re-run — the symptom is intermittent, the cause is the same.
- Lists cut by chunking — the E2A definition of *serious* (2 of 5 criteria) and the E6(R3)
  consent elements ((a)–(d) of (a)–(v)) — were **presented as complete**.

**Changes:** answer the covered part and name the uncovered part; refuse fully only when
nothing is relevant, in the user's language; build multi-step answers step by step, citing
each step; give every list item the passages contain or say the list continues. The
truncation itself was fixed in retrieval (section-level context expansion), not in the
prompt — see `docs/decisions.md`.

**Measured** (same golden set and scoring for both, `docs/evaluation_baseline_v3.md` vs
`docs/evaluation.md`): answer keyword coverage 0.815 → 0.974; no in-domain question refused,
all out-of-domain questions refused and both not-indexed documents answered honestly in both
configurations. The reporting-chain question is now answered step by step (investigator →
sponsor immediately; sponsor → regulators within 7 days for fatal or life-threatening
SUSARs) but still misses the 15-day timeline: one retrieval pass does not bring every hop.
With v4 the Spanish answers to the two not-indexed documents and to the reporting chain are
written in Spanish (in v3's baseline re-run the first two were in English).

Judged correctness against expert references (LLM judge, same judge for both): golden set
0.776 → 0.947; held-out set written after v4 was frozen 0.950 → 1.000 (`README.md`,
*Evaluation*).

Not attributable to v4 alone: the comparison changes the prompt, context expansion and
document routing together, because the failures they address appeared together. The
notebook (section 5) shows v1 vs v4 on a single question; a prompt-only ablation (v4 with
expansion and routing off) is a cheap next measurement with `scripts/03_evaluate.py
--prompt-version v4 --no-expand --no-routing --with-answers`.
