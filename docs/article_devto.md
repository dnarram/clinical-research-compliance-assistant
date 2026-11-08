# How I built a GCP compliance assistant that cites every sentence — my Generative AI project at Evolve

*Draft for Dev.to (Evolve organization). ~900 words. Tags: ai, python, rag, langgraph, healthtech.*

Five years ago I was on the other side of this problem. Supporting clinical-trial software
for Medidata, Pfizer and Novo Nordisk, the questions that landed on my desk were rarely
about the software: *is this a SUSAR? who reports it, and by when? what has to be in the
consent form?* The answers live in ICH guidelines and the Declaration of Helsinki, and they
have to be quoted — not paraphrased — because an auditor will ask where you got them.

For the final project of the Generative AI module at Evolve I built an assistant for
exactly that: a retrieval-augmented agent on **ICH E6(R3)** (Good Clinical Practice, 2025),
**ICH E2A** (expedited safety reporting) and the **WMA Declaration of Helsinki (2024)**,
with Google Gemini, ChromaDB and LangGraph.

## What makes a compliance assistant different from a chatbot

Three requirements shaped every decision:

1. **Traceability.** Every factual sentence carries a citation like `ICH E6(R3) §2.8.10,
   p.24` or `Declaration of Helsinki (2024) ¶28`, and the user can open the passage.
2. **Honest refusals.** A question the sources do not cover must be refused, not
   completed from the model's general knowledge. "What does 21 CFR Part 50 say?" gets
   "that regulation is not in my knowledge base", never an invented FDA citation.
3. **Two languages, one corpus.** The guidelines are English; my colleagues ask in
   Spanish. The answer comes back in the user's language, but regulatory wording is
   quoted verbatim in English.

## The pipeline, and the three decisions I would defend in a code review

The agent is an explicit LangGraph `StateGraph`: `rewrite_query → retrieve → route →
generate | refuse`. The LLM never decides whether to consult the knowledge base; it only
rewrites the question (resolving "that situation" from the conversation history and
translating it to English) and writes the answer. Refusals are templated and cost no
model call.

**A versioned embedding cache instead of a committed vector database.** The 801 chunks
are embedded once with `gemini-embedding-2`; the vectors live in a small gzipped JSONL
file in the repository, with a manifest recording file hash, model and chunking. ChromaDB
is rebuilt from that cache in seconds with zero API calls — on my laptop, in CI, and on
Streamlit Cloud. I learned why this matters the hard way: the free tier allows 1,000
embedded texts per day, and the corpus build alone uses 800.

**A calibrated refusal threshold.** Gemini cosine relevance scores sit in a narrow band.
I measured six in-domain questions in English and Spanish and six out-of-domain ones:
in-domain maxima 0.75–0.88, out-of-domain 0.52–0.63. The gate is the midpoint of that
gap, stored next to the embedding model name so a model change forces a recalibration.
A fixed "0.5" would never refuse anything; "0.8" would refuse half the Spanish questions.

**Hard constraints in code, judgement in the prompt.** The system prompt went through
three versions (role and audience, grounding and citation protocol, how to handle
documents that disagree). But the one failure the prompt could not reliably fix — an
English question answered in Spanish — was solved by a deterministic "Reply in English /
Responde en español" line appended in code.

## What the numbers say

Before wiring the model I checked retrieval on its own: Spanish queries find the same
passages as English ones, about 0.04 lower in score. Then a golden set of 25 questions, each
in English and Spanish (19 in-domain including two that need more than one document, 4
out-of-domain, 2 about documents deliberately not indexed): 50 runs.

Retrieval looked perfect — the right document in the top-6 every time, every off-topic
question refused, nothing in-domain refused. Reading every answer told a different story.
ICH E2A's definition of *serious* came back with two of its five criteria, because the
definition straddles two 500-character chunks; the consent elements of E6(R3) stopped at
(d) of (v), presented as complete; a question about the reporting chain from investigator
to regulator was refused outright although every step was retrievable; and some Spanish
refusals came back in English.

Three fixes, each aimed at one of those: widen every retrieved chunk to its whole section
when the section is short (read from the vector store, no extra API calls); when a question
names documents, share the retrieval slots between them with a metadata filter; and a
prompt that answers the covered part of a question instead of refusing all of it. With the
same golden set and the same scoring, answer keyword coverage went from 0.82 to 0.97. Two
things did not improve, and I report them rather than tune against my own test set: a
multi-hop question still misses one timeline (one retrieval pass cannot bring every hop),
and routing cost one section hit on a Spanish question.

## What I would do next

Query decomposition for multi-hop questions, then EMA GVP Module VI and the EU Clinical
Trials Regulation (the ingestion is per document and idempotent), an LLM-as-judge
faithfulness check over the golden set — keyword coverage is only a proxy — and hybrid
BM25 + vector retrieval for exact section numbers.

The repository, the executed notebook and the live app are here:
<https://github.com/dnarram/clinical-research-compliance-assistant>.

*Built during the Master in Data Science & AI at [Evolve](https://evolveacademy.es).*
