#!/usr/bin/env python3
"""Compare the papers page with the author's public ORCID record.

The page mirrors ORCID: every work on the record gets a card, and a card for a
work the record does not carry is either a record that has not caught up (the
arXiv -> DataCite -> ORCID auto-update can lag or never fire) or a card that
should not be there. Either way it is reported, and the exit status is 1 until
the two agree. Matching is by normalized title, which is the only field every
ORCID work is guaranteed to have.

Reads the public API, so it needs the network and no token. Deliberately not
part of `make check`: a deploy should not depend on ORCID being reachable.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ORCID = "0009-0007-3198-2712"
PAPERS = Path(__file__).resolve().parent.parent / "sections" / "papers" / "papers.json"


def norm(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def orcid_titles() -> dict[str, str]:
    req = urllib.request.Request(
        f"https://pub.orcid.org/v3.0/{ORCID}/works", headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        groups = json.load(r).get("group", [])
    titles = {}
    for g in groups:
        t = g["work-summary"][0]["title"]["title"]["value"]
        titles[norm(t)] = t
    return titles


def main() -> int:
    on_orcid = orcid_titles()
    on_page = {norm(p["title"]): p["title"] for p in json.loads(PAPERS.read_text(encoding="utf-8"))}

    missing = [on_orcid[k] for k in on_orcid if k not in on_page]
    extra = [on_page[k] for k in on_page if k not in on_orcid]

    print(f"ORCID {ORCID}: {len(on_orcid)} works · page: {len(on_page)} cards")
    for t in missing:
        print(f"  on ORCID, not on the page: {t}")
    for t in extra:
        print(f"  on the page, not on ORCID: {t}")
    if not missing and not extra:
        print("  in sync")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
