#!/usr/bin/env python
"""Fetch the knowledge-base PDFs listed in data/kb/sources.yaml into data/kb/raw/.

Each download is verified against the sha256 recorded in sources.yaml. On the very
first fetch there is no hash yet: run with --record to write the observed hash back
into sources.yaml, then commit that file — it is the provenance record.

    uv run scripts/00_download_sources.py            # download missing, verify all
    uv run scripts/00_download_sources.py --record   # also fill in missing sha256 values
    uv run scripts/00_download_sources.py --doc-id ich_e2a
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from compliance_assistant.config import load_settings
from compliance_assistant.ingestion import load_sources, sha256_of

USER_AGENT = "Mozilla/5.0 (compatible; compliance-assistant/0.1; academic project)"


def download(url: str, dest: Path) -> None:
    """Fetch to a temporary name and rename on success, so an interrupted download never
    leaves a half file that the next run would treat as present."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=60) as resp, tmp.open("wb") as out:
        while block := resp.read(1 << 16):
            out.write(block)
    tmp.replace(dest)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--doc-id", action="append", help="limit to these doc_ids (repeatable)")
    parser.add_argument(
        "--record", action="store_true", help="write missing sha256 values back to sources.yaml"
    )
    parser.add_argument("--force", action="store_true", help="re-download even if the file exists")
    args = parser.parse_args()

    settings = load_settings()
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    sources = load_sources(settings)
    if args.doc_id:
        sources = [s for s in sources if s.doc_id in set(args.doc_id)]

    recorded: dict[str, str] = {}
    failures = 0
    for src in sources:
        dest = src.pdf_path(settings)
        if not src.url:
            print(f"[skip] {src.doc_id}: no url in sources.yaml")
            continue
        if args.force or not dest.exists():
            print(f"[get ] {src.doc_id} <- {src.url}")
            download(src.url, dest)
        digest = sha256_of(dest)
        if src.sha256 is None:
            print(f"[new ] {src.doc_id}: sha256={digest[:16]}... (not yet recorded)")
            recorded[src.doc_id] = digest
        elif digest != src.sha256:
            print(
                f"[FAIL] {src.doc_id}: sha256 mismatch — expected {src.sha256[:16]}..., got {digest[:16]}... "
                "(the publisher changed the file; review it, then re-run with --force --record)"
            )
            failures += 1
        else:
            print(f"[ ok ] {src.doc_id}: {dest.name} ({dest.stat().st_size // 1024} KB)")

    if args.record and recorded:
        # Targeted text edit rather than a YAML dump: the file carries comments that
        # explain each field and a dump would discard them.
        text = settings.sources_path.read_text(encoding="utf-8")
        for doc_id, digest in recorded.items():
            pattern = re.compile(
                rf"(doc_id:\s*{re.escape(doc_id)}\b(?:(?!doc_id:).)*?sha256:\s*)null", re.S
            )
            text, n = pattern.subn(rf"\g<1>{digest}", text, count=1)
            if n == 0:
                print(f"[warn] could not record sha256 for {doc_id}; edit sources.yaml by hand")
        settings.sources_path.write_text(text, encoding="utf-8")
        print(f"[rec ] wrote {len(recorded)} sha256 value(s) to {settings.sources_path.name}")
    elif recorded:
        print("hint: re-run with --record to store these hashes in sources.yaml")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
