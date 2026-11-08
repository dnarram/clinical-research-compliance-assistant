"""Cached answers for the scripted demo (last line of defence against API quotas).

`scripts/04_cache_demo_answers.py` runs the demo script's questions once and stores the
answers here. With `OFFLINE_DEMO=1`, `Assistant.ask` serves an exact-match question from
this file without touching any API; everything else still goes to the live agent. The UI
shows a "cached" badge so the audience is never misled.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CachedAnswer:
    question: str
    text: str
    sources: list[dict[str, Any]]
    grounded: bool
    max_score: float
    standalone_question: str
    thread_key: str = ""  # scripted conversations: the previous question in the thread
    metadata: dict[str, Any] = field(default_factory=dict)


class DemoCache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._items: dict[tuple[str, str], CachedAnswer] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    item = CachedAnswer(**d)
                    self._items[(item.thread_key, item.question.strip())] = item

    @staticmethod
    def enabled() -> bool:
        return os.environ.get("OFFLINE_DEMO", "0") == "1"

    def __len__(self) -> int:
        return len(self._items)

    def get(self, question: str, previous_question: str = "") -> CachedAnswer | None:
        """Exact match on the question; scripted follow-ups also match on the previous
        question so a referential turn gets the answer recorded in that context."""
        key = question.strip()
        exact = self._items.get((previous_question.strip(), key)) or self._items.get(("", key))
        if exact is not None:
            return exact
        # Same question asked in a different order than recorded: any recording will do.
        return next((item for (_, q), item in self._items.items() if q == key), None)

    def put(self, item: CachedAnswer) -> None:
        self._items[(item.thread_key, item.question.strip())] = item
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")
