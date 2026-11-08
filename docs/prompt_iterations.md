# System prompt iterations

The three versions live in `src/compliance_assistant/prompts.py` and can be selected with
`PROMPT_VERSION=v1|v2|v3` (or `load_settings(prompt_version=...)`). Each change below was
motivated by an observed failure, not by taste. The notebook (section 5) runs the same
question through v1 and v3 so the difference is visible.

## v1 — "answer from the documents" (class baseline)

```
Use the following information from the documents provided to answer the question
concisely and clearly.
```

Observed failures (question: *Who is responsible for reporting a SUSAR to the regulatory
authorities, and how fast?*):

- Fluent, mostly correct, but **unattributed**: the 7-day and 15-day timelines are stated
  without saying they come from ICH E2A §III.B, so a CRA cannot verify them.
- **No behaviour for missing information.** Asked about 21 CFR Part 50 (not in the
  corpus) the model answered from general knowledge, with plausible-looking citations to
  FDA sections that are not in any passage — the exact failure mode a compliance tool must
  not have.
- **Register drifts** ("Sure! Here's a quick overview…").

## v2 — role, audience, scope, insufficiency rule

Added: role (*regulatory compliance assistant for clinical research*), the audience
(CRAs, coordinators, data managers, PV staff), the explicit rule to answer only from the
context, the "I could not find this in my knowledge base" behaviour, and the not-legal-
advice disclaimer.

Fixed: invented citations stopped; off-topic questions were declined.

Remaining failures:

- **Sources merged.** On "what must participants be told about risks?", E6(R3) §2.8.10
  elements and Helsinki ¶26 were blended into one list, so the reader could not tell
  which document requires what.
- **Language.** Spanish questions were answered in English about half of the time.
- **No per-sentence traceability.** A single "Sources: E2A, E6(R3)" line at the end is
  not enough when an answer mixes two timelines.

## v3 — citation protocol, differing sources, language policy, format (in use)

Added: numbered `[n]` citations on every factual sentence (the numbers map to the sources
panel built by `retrieval.format_context`); the rule to attribute differing positions to
their documents; the language policy (answer in the user's language, quote regulatory
wording verbatim in English, keep SAE/SUSAR/IB/IMP untranslated); and the output format
(direct answer first, then detail, no closing summary).

Verified on the live model (`gemini-3.5-flash-lite`, 2026-11-08):

- E2A timelines answered with `[n]` citations and verbatim quotes ("as soon as possible
  but no later than 7 calendar days…").
- A Spanish referential follow-up ("¿Dice lo mismo la Declaración de Helsinki sobre ese
  tema?") produced a Spanish answer that **contrasts** E6(R3) §2.8.1 with Helsinki ¶26 and
  attributes each.
- Out-of-domain questions never reach the model: the calibrated retrieval gate routes
  them to the templated refusal.

One thing the prompt alone did **not** fix: an English first question once came back in
Spanish. The deterministic `Reply in English.` / `Responde en español.` line that
`prompts.build_messages` appends to the user message closed that gap — a reminder that
the hard constraints belong in code, and the prompt should carry the judgement calls.

Known residue: the model sometimes appends "Nota: esta información es de cumplimiento
regulatorio y no constituye asesoramiento legal o médico" even when not asked. Harmless,
and arguably desirable in this domain; left as is.
