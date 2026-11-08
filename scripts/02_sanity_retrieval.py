#!/usr/bin/env python
"""Inspect retrieval before connecting the agent, and calibrate the relevance gate.

    uv run scripts/02_sanity_retrieval.py                       # built-in EN/ES/OOD queries
    uv run scripts/02_sanity_retrieval.py --query "SUSAR timeline" --query "plazo SUSAR"
    uv run scripts/02_sanity_retrieval.py --calibrate           # writes data/kb/calibration.json

Calibration: Gemini cosine relevance scores sit in a narrow band, so the threshold that
separates "the knowledge base covers this" from "it does not" has to be read off the
data. The script prints the max score of every in-domain and out-of-domain query and,
with --calibrate, stores the midpoint of the gap between the two groups (or warns when
they overlap). Only the query embedding API is called (one request per query).
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compliance_assistant.config import load_api_key, load_settings
from compliance_assistant.retrieval import cite, scored_search
from compliance_assistant.vectorstore import TASK_QUERY, build_or_load, get_embeddings

# Paired EN/ES queries (same meaning) to check cross-lingual retrieval, plus OOD queries
# that a compliance assistant must refuse. These are sanity queries, not the golden set.
IN_DOMAIN = [
    (
        "What is the timeline for expedited reporting of fatal or life-threatening unexpected ADRs?",
        "¿Cuál es el plazo de notificación expeditiva de una reacción adversa inesperada mortal o potencialmente mortal?",
    ),
    (
        "How does ICH E2A define a serious adverse event?",
        "¿Cómo define ICH E2A un acontecimiento adverso grave?",
    ),
    (
        "What are the investigator's responsibilities for informed consent under ICH E6(R3)?",
        "¿Qué responsabilidades tiene el investigador sobre el consentimiento informado según ICH E6(R3)?",
    ),
    (
        "What does the Declaration of Helsinki say about research with participants who cannot give consent?",
        "¿Qué dice la Declaración de Helsinki sobre la investigación con participantes que no pueden dar su consentimiento?",
    ),
    (
        "What must an Investigator's Brochure contain?",
        "¿Qué debe contener el manual del investigador (Investigator's Brochure)?",
    ),
    (
        "Which essential records should be kept by the sponsor during a clinical trial?",
        "¿Qué documentos esenciales debe conservar el promotor durante un ensayo clínico?",
    ),
]
OUT_OF_DOMAIN = [
    "Which GLP-1 drug is best for weight loss?",
    "¿Cuál es la mejor receta de paella valenciana?",
    "How do I configure a PostgreSQL star schema for an e-commerce data warehouse?",
    "What is the capital of Bulgaria?",
    "Explain how transformers compute self-attention.",
    "¿Qué equipo ganó la Champions League en 2024?",
]


def show(vs, query: str, k: int) -> float:
    hits = scored_search(vs, query, k)
    print(f"\n### {query}")
    for doc, score in hits:
        snippet = doc.page_content[:110].replace("\n", " ")
        print(f"  {score:.3f}  {cite(doc.metadata):<36} {snippet}")
    return max((s for _, s in hits), default=0.0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--query", action="append", help="ad-hoc query (repeatable); skips the built-in sets"
    )
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--calibrate", action="store_true", help="write data/kb/calibration.json")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)

    settings = load_settings()
    vs = build_or_load(settings, get_embeddings(settings, load_api_key(), TASK_QUERY))
    print(f"Collection '{settings.collection_name}': {vs._collection.count()} chunks")

    if args.query:
        for q in args.query:
            show(vs, q, args.k)
        return 0

    print("\n=============== IN-DOMAIN (EN / ES pairs) ===============")
    in_en, in_es = [], []
    for en, es in IN_DOMAIN:
        in_en.append(show(vs, en, args.k))
        in_es.append(show(vs, es, args.k))
    print("\n=============== OUT-OF-DOMAIN ===============")
    ood = [show(vs, q, args.k) for q in OUT_OF_DOMAIN]

    def summary(name: str, xs: list[float]) -> None:
        print(
            f"{name:<18} n={len(xs)} min={min(xs):.3f} median={statistics.median(xs):.3f} max={max(xs):.3f}"
        )

    print("\n=============== MAX SCORE PER QUERY ===============")
    summary("in-domain EN", in_en)
    summary("in-domain ES", in_es)
    summary("out-of-domain", ood)
    lowest_in = min(in_en + in_es)
    highest_ood = max(ood)
    if lowest_in > highest_ood:
        threshold = round((lowest_in + highest_ood) / 2, 4)
        print(
            f"\nSeparable: lowest in-domain {lowest_in:.3f} > highest OOD {highest_ood:.3f} -> threshold {threshold}"
        )
    else:
        # Overlap: choose the cut that misclassifies the fewest queries, biased towards
        # answering (a refusal on a valid question is the worse failure in a demo).
        candidates = sorted(set(in_en + in_es + ood))
        best = max(
            candidates,
            key=lambda t: (sum(x >= t for x in in_en + in_es) + sum(x < t for x in ood), -t),
        )
        threshold = round(best - 1e-4, 4)
        print(
            f"\nOVERLAP: lowest in-domain {lowest_in:.3f} <= highest OOD {highest_ood:.3f}; best cut {threshold} "
            "(review the queries above before trusting it)"
        )

    if args.calibrate:
        payload = {
            "score_threshold": threshold,
            "embedding_model": settings.embedding_model,
            "k": args.k,
            "in_domain_max_scores": {"en": in_en, "es": in_es},
            "out_of_domain_max_scores": ood,
            "calibrated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        settings.calibration_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {settings.calibration_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
