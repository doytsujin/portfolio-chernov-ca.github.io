#!/usr/bin/env python3
"""Generate papers/index.html from template + papers.json manifest.

**Abstracts only.** This page lists work that has already appeared at a
conference, in a journal, or on Zenodo or arXiv, and links to the publisher's
record. It never carries the paper itself.

That is a policy, so it is enforced here rather than remembered. An earlier
version of this script emitted `<a href="{topic_id}/{paper_id}.pdf">Download
PDF</a>` for every entry in the manifest, and the manifest at the time included
two items that had no venue at all — one marked "Preprint" with no preprint
anywhere. Had the page ever deployed, it would have published the full text of
unpublished work. `require_published` is why that cannot happen again by
forgetting: an entry without `published: true` and a citation is a build
failure, not a quieter card.
"""

import json
import sys
from pathlib import Path
from html import escape

CARD_TEMPLATE = """\
        <div class="paper-card">
            <div class="paper-card-header">
                <h2>{title}</h2>
            </div>
            <div class="paper-card-body">
                <div class="paper-meta">
                    <span class="badge">{venue}</span>
                    <span>{authors} · {year}</span>
                </div>
                <p class="paper-abstract">{abstract}</p>
                <p class="paper-citation">{citation}</p>
                <div class="paper-links">{links}</div>
            </div>
        </div>"""

RECORD_LINK = '<a href="{url}" class="btn btn-primary" rel="noopener">Publisher record</a>'
NO_LINK = '<span class="paper-note">Publisher record pending.</span>'

PLACEHOLDER = "<!-- {{PAPER_CARDS}} -->"

REQUIRED = ("title", "authors", "year", "venue", "citation", "abstract")


def require_published(paper, index):
    """Refuse anything that has not actually been published somewhere.

    The check is deliberately dumb and total: every field must be present and
    non-empty, and `published` must be exactly True. A missing venue is not an
    entry to render without a badge — it is an entry that does not belong on
    this page.
    """
    where = paper.get("title") or f"entry {index}"
    if paper.get("published") is not True:
        raise SystemExit(
            f"refusing to render {where!r}: not published.\n"
            "This page lists only work that has appeared at a conference, in a "
            "journal, or on Zenodo or arXiv. Remove the entry, or publish it "
            "first and record the venue."
        )
    for field in REQUIRED:
        value = paper.get(field)
        if value is None or (hasattr(value, "__len__") and len(value) == 0):
            raise SystemExit(f"refusing to render {where!r}: {field} is missing or empty")


def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <template.html> <papers.json> <output.html>",
              file=sys.stderr)
        sys.exit(1)

    template_path = Path(sys.argv[1])
    config_path = Path(sys.argv[2])
    output_path = Path(sys.argv[3])

    template = template_path.read_text(encoding="utf-8")
    papers = json.loads(config_path.read_text(encoding="utf-8"))

    cards = []
    for i, paper in enumerate(papers):
        require_published(paper, i)
        url = paper.get("url")
        links = RECORD_LINK.format(url=escape(url, quote=True)) if url else NO_LINK
        cards.append(CARD_TEMPLATE.format(
            title=escape(paper["title"]),
            authors=escape(", ".join(paper["authors"])),
            year=escape(str(paper["year"])),
            venue=escape(paper["venue"]),
            citation=escape(paper["citation"]),
            abstract=escape(paper["abstract"]),
            links=links,
        ))

    html = template.replace(PLACEHOLDER, "\n\n".join(cards))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"✓ Generated {output_path} ({len(cards)} published, abstracts only)")


if __name__ == "__main__":
    main()
