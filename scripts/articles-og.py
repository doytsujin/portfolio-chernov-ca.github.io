#!/usr/bin/env python3
"""Write the link-preview tags into the built articles book (docs/articles), after mdBook.

mdBook's template is one for every page and leaves `<meta name="description" content="">`
empty, so a shared reprint previewed with no text and no image. This fills, per article:
the description (the article's opening paragraph, cut to a whole sentence), og:title, og:url
(the reprint), og:image (the article's LinkedIn cover, cut to 1200x630 by import-articles.py),
its size and alt text, article:published_time and twitter:card. The book's index and welcome
page, and an article with no cover, use the Writing card (docs/og/articles.png, make_og.py).

Refuses an article page that is missing, a page whose empty description is not there exactly
once (a template change, or a second run on the same build), an empty description, and an
image that is not 1200x630.

    python3 scripts/articles-og.py [docs/articles]
"""
import html
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import preview_text  # noqa: E402  the same cut the project pages' descriptions use

ENTRIES = ROOT / "sections" / "articles" / "articles.json"
SRC = ROOT / "sections" / "articles" / "src"
CARD_FILE = ROOT / "docs" / "og" / "articles.png"
SITE = "https://portfolio.chernov.ca/"
BASE = SITE + "articles/"
CARD = SITE + "og/articles.png"
PLACEHOLDER = '<meta name="description" content="">'
BOOK_WORDS = ("Articles by Alexander Chernov, first published on LinkedIn and reprinted here. "
              "Each page links to the original, which remains the canonical version.")


def fail(msg):
    sys.exit(f"refusing: {msg}")


def opening(md: str) -> str:
    """The first ordinary paragraph after the byline: not a heading, an image, or a wholly
    italic line such as "Part 2 of two" or an update note."""
    body = md.split("\n---\n", 1)[1] if "\n---\n" in md else md
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if not p or p.startswith(("#", "!", "<", "|", "-", "```")):
            continue
        if re.fullmatch(r"\*[^*].*\*", p, re.S):
            continue
        p = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", p)
        p = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", p)
        p = re.sub(r"\*\*|__|`|(?<!\w)\*|\*(?!\w)", "", p)
        return re.sub(r"\s+", " ", p).strip()
    return ""


def sized(path: Path) -> None:
    if not path.is_file():
        fail(f"{path} is missing")
    if Image.open(path).size != (1200, 630):
        fail(f"{path} is {Image.open(path).size}, not 1200x630")


def tags(title, desc, url, image, alt, kind="website", date=None):
    rows = [("description", desc, "name")] + [
        (k, v, "property") for k, v in [
            ("og:type", kind), ("og:title", title), ("og:description", desc), ("og:url", url),
            ("og:image", image), ("og:image:width", "1200"), ("og:image:height", "630"), ("og:image:alt", alt)]]
    if date:
        rows.append(("article:published_time", date, "property"))
    rows.append(("twitter:card", "summary_large_image", "name"))
    return "\n        ".join(f'<meta {a}="{k}" content="{html.escape(v, quote=True)}">' for k, v, a in rows)


def write(page: Path, block: str) -> None:
    if not page.is_file():
        fail(f"{page} is missing")
    text = page.read_text(encoding="utf-8")
    if text.count(PLACEHOLDER) != 1:
        fail(f"{page.name}: the empty description is there {text.count(PLACEHOLDER)} times, not once")
    page.write_text(text.replace(PLACEHOLDER, block, 1), encoding="utf-8")


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "articles"
    sized(CARD_FILE)
    entries = json.loads(ENTRIES.read_text(encoding="utf-8"))
    covers = 0
    for e in entries:
        slug, title = e["slug"], e["title"]
        desc = preview_text(opening((SRC / f"{slug}.md").read_text(encoding="utf-8")))
        if not desc:
            fail(f"{slug}: no opening paragraph to describe it")
        cover = out / slug / "og.jpg"
        if cover.is_file():
            sized(cover)
            image, alt = f"{BASE}{slug}/og.jpg", f"Cover of “{title}”, an article by Alexander Chernov"
            covers += 1
        else:
            image, alt = CARD, "Writing: articles by Alexander Chernov, reprinted from LinkedIn"
        write(out / f"{slug}.html", tags(title, desc, f"{BASE}{slug}.html", image, alt, "article", e["date"]))
    for name, url in (("index.html", BASE), ("welcome.html", BASE + "welcome.html")):
        write(out / name, tags("Articles — Alexander Chernov", BOOK_WORDS, url, CARD,
                               "Writing: articles by Alexander Chernov, reprinted from LinkedIn"))
    print(f"✓ link previews: {len(entries)} articles ({covers} with their cover, "
          f"{len(entries) - covers} with the Writing card), index and welcome")


if __name__ == "__main__":
    main()
