#!/usr/bin/env python3
"""Import published LinkedIn articles into the articles mdBook.

Reprints, not first publication. Every article here has already appeared on
LinkedIn, and each page says so and links to the original — the reprint is the
copy, so it carries the canonical pointer rather than competing with it.

An entry without a `url` is refused. The rule for this site is that nothing
appears before it has been published somewhere, and for articles that somewhere
is LinkedIn; an article with no URL has not been published yet and belongs in
the queue in the articles repository, not here.

Usage:
    scripts/import-articles.py <path-to-articles-repository>

Reads sections/articles/articles.json, copies each article's markdown and the images
it references, and writes sections/articles/src/. The result is committed, so the
book builds without the source repository present.
"""

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "sections" / "articles"
SRC = DOCS / "src"

LINK_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

# `{: .caption }`, `{: width="70%" }` and the like are Python-Markdown attr_list
# blocks. They style the print PDF built in the articles repository; mdBook has no
# attr_list, so left in place they render as literal braces in the reprint.
# Stripping them loses the styling and keeps the text, which is the right trade
# for a reprint: a caption stays a caption, and a figure takes the page width.
ATTR_RE = re.compile(r"[ \t]*\{:[^{}\n]*\}[ \t]*")

# Images are re-encoded to WebP on the way in. The originals are what LinkedIn
# was given and are sized for it — one figure is 8220 pixels wide — which came
# to 3.6 MB across three pages. At this bound the same three pages are under
# 500 KB, and the widest diagram is still 2000 pixels across, which is more than
# a reader's screen.
#
# The bound is on width rather than on file size so that the result is
# predictable from the source: an image narrower than this is re-encoded and not
# resampled, so nothing is upscaled and nothing is sharpened.
MAX_WIDTH = 2000
WEBP_QUALITY = 85

# Every page carries a byline and a copyright line. mdBook renders neither the
# `authors` field in book.toml nor any footer of its own, so before this the
# reprints appeared with no indication of who wrote them or who holds the
# rights. The notice is emitted per page rather than added to a template so it
# survives a rebuild from scratch and so the year tracks the article.
AUTHOR = "Alexander Chernov"
AUTHOR_URL = "https://www.linkedin.com/in/thedoytsujin/"


def to_webp(source: Path, destination_dir: Path) -> str:
    """Re-encode one image, returning the filename to reference.

    Falls back to copying the original if Pillow is not installed, because a
    missing image optimiser should not stop the site from building — and says
    so, rather than silently shipping the heavy version.
    """
    try:
        from PIL import Image
    except ImportError:
        print(
            f"  ! Pillow not installed: copying {source.name} unconverted",
            file=sys.stderr,
        )
        shutil.copy2(source, destination_dir / source.name)
        return source.name

    name = source.stem + ".webp"
    image = Image.open(source).convert("RGB")
    if image.width > MAX_WIDTH:
        height = round(image.height * MAX_WIDTH / image.width)
        image = image.resize((MAX_WIDTH, height), Image.LANCZOS)
    image.save(destination_dir / name, "WEBP", quality=WEBP_QUALITY, method=6)
    return name


# The link-preview image of each reprint is the article's LinkedIn cover, cut the way LinkedIn
# shows it: the centre of the banner at 1200x630. The first file found is used; an article with
# none gets the Writing card instead (scripts/articles-og.py), rather than a guessed figure.
COVERS = ("images/banner_16x9.png", "images/cover.png")
OG_SIZE = (1200, 630)


def import_cover(repo: Path, slug: str, assets: Path) -> str:
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit("refusing: Pillow is needed to cut the link-preview covers")
    for rel in COVERS:
        found = repo / "articles" / slug / rel
        if found.is_file():
            image = Image.open(found).convert("RGB")
            w, h = image.size
            target = OG_SIZE[0] / OG_SIZE[1]
            if w / h > target:
                cw, ch = round(h * target), h
            else:
                cw, ch = w, round(w / target)
            left, top = (w - cw) // 2, (h - ch) // 2
            image = image.crop((left, top, left + cw, top + ch)).resize(OG_SIZE, Image.LANCZOS)
            assets.mkdir(parents=True, exist_ok=True)
            image.save(assets / "og.jpg", "JPEG", quality=88, optimize=True, progressive=True)
            return rel
    stale = assets / "og.jpg"
    if stale.exists():
        stale.unlink()
    return ""


def import_one(repo: Path, entry: dict) -> str:
    slug = entry["slug"]
    if not entry.get("url"):
        raise SystemExit(
            f"refusing {slug!r}: no URL. Only articles already published on "
            "LinkedIn are reprinted here."
        )
    source = repo / "articles" / slug / "draft" / "article.md"
    if not source.is_file():
        raise SystemExit(f"refusing {slug!r}: {source} not found")

    text = source.read_text(encoding="utf-8")

    # The title becomes the page heading below, so drop the source's own H1
    # rather than rendering it twice.
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body = "\n".join(lines).lstrip("\n")
    body = ATTR_RE.sub("", body)
    # The drafts write the tags as "Hashtags: #A #B" because a line starting
    # with "#" becomes a heading in their print PDF. LinkedIn shows the tags
    # alone, and so does the reprint; "#A" with no space is not a Markdown
    # heading, so mdBook renders it as text.
    body = re.sub(r"(?m)^Hashtags: (?=#)", "", body)

    assets = SRC / slug
    rewritten = []
    for match in LINK_RE.finditer(body):
        target = match.group(2)
        if target.startswith(("http://", "https://", "/")):
            continue
        found = repo / "articles" / slug / target
        if not found.is_file():
            raise SystemExit(f"refusing {slug!r}: image {target} not found at {found}")
        assets.mkdir(parents=True, exist_ok=True)
        name = to_webp(found, assets)
        rewritten.append((target, f"{slug}/{name}"))

    for old, new in rewritten:
        body = body.replace(f"]({old})", f"]({new})")

    year = entry["date"][:4]
    page = (
        f"# {entry['title']}\n\n"
        f"*By [{AUTHOR}]({AUTHOR_URL}). "
        f"First published on LinkedIn, {entry['date']}. "
        f"[Read the original]({entry['url']}).*\n\n"
        f"---\n\n"
        f"{body}\n\n"
        f"---\n\n"
        f"<small>© {year} {AUTHOR}. All rights reserved. "
        f"First published on [LinkedIn]({entry['url']}), which remains the "
        f"canonical version; this page is a reprint by the author.</small>\n"
    )
    (SRC / f"{slug}.md").write_text(page, encoding="utf-8")
    cover = import_cover(repo, slug, assets)
    return f"{slug} ({len(rewritten)} image(s), cover: {cover or 'none, the Writing card'})"


def main():
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    repo = Path(sys.argv[1]).expanduser().resolve()
    entries = json.loads((DOCS / "articles.json").read_text(encoding="utf-8"))

    SRC.mkdir(parents=True, exist_ok=True)
    done = [import_one(repo, e) for e in entries]

    # Newest first: this is a feed, not a curriculum.
    ordered = sorted(entries, key=lambda e: e["date"], reverse=True)
    summary = ["# Summary", "", "- [Articles](./welcome.md)", "", "---", ""]
    summary += [f"- [{e['title']}](./{e['slug']}.md)" for e in ordered]
    (SRC / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    welcome = [
        "# Articles",
        "",
        f"Articles by [{AUTHOR}]({AUTHOR_URL}), first published on LinkedIn and",
        "reprinted here. Each page links to the original, which remains the",
        "canonical version.",
        "",
        "| Article | First published |",
        "|---|---|",
    ]
    welcome += [
        f"| [{e['title']}](./{e['slug']}.md) | [{e['date']}]({e['url']}) |" for e in ordered
    ]
    years = sorted({e["date"][:4] for e in entries})
    span = years[0] if len(years) == 1 else f"{years[0]}–{years[-1]}"
    welcome += [
        "",
        f"<small>© {span} {AUTHOR}. All rights reserved. Each article was first",
        "published on LinkedIn; the linked original remains the canonical",
        "version.</small>",
    ]
    (SRC / "welcome.md").write_text("\n".join(welcome) + "\n", encoding="utf-8")

    for line in done:
        print(f"✓ {line}")
    print(f"✓ {len(done)} article(s) imported")


if __name__ == "__main__":
    main()
