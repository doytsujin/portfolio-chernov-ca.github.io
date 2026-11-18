#!/usr/bin/env python3
"""Render content/*.json into docs/.

Standard library only, same as the other tools in this account. The content
files are hand-authored and trusted, so body strings may carry inline markup
(<em>, <code>, entities) and are emitted verbatim. What is NOT trusted is that
they are *correct*: every render is parsed back and checked before it is
written, because a static page fails silently -- a stray unclosed tag swallows
the rest of the document and the build would otherwise report success.

Output:
  docs/index.html            the whole portfolio
  docs/p/<slug>.html         one page per project
  docs/featured/<kind>.html  the web version of each Featured PDF beside it

Writing (docs/articles/) and Papers (docs/papers/) are built by their own
Makefile targets; this script only links to them and checks that every local
link it writes resolves to a file.

Each project gets its own URL because LinkedIn strips the fragment before it
fetches a link, so ten anchors into one page would all preview as the same
card. Its own URL is what gives it its own title, description and image.
"""

from __future__ import annotations

import datetime
import hashlib
import html
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent
CONTENT = ROOT / "content"
DOCS = ROOT / "docs"

SITE = "https://portfolio.chernov.ca"
TITLE = "Alexander Chernov — Portfolio"
DESCRIPTION = (
    "Projects, publications, talks and writing: control planes, admission "
    "gates and observable decisions for scientific and regulated systems."
)
QUESTION = "Something proposes under uncertainty — what decides whether it may act?"

# A small logo shown before an affiliation's name in a project's date line.
# The name stays as text beside it, so the logo is decorative (alt="").
# AstraZeneca: the gold symbol cut from its logo SVG, the wordmark left out
# because the name follows; gold reads on both the light and dark themes.
AFFILIATION_LOGOS = {
    "AstraZeneca": "img/logo/astrazeneca-symbol.svg",
}

# The quick filter above the project list, in the order its buttons appear.
# "affiliated" and "independent" are read off the affiliation line, so a tag
# can never disagree with what the entry says about who it was done for; the
# others are set by hand in content/projects.json under "tags".
TAGS = {
    "independent": "Independent",
    "affiliated": "Affiliated",
    "research": "Research",
    "engineering": "Engineering",
    "product": "Product",
    "demo": "Demo",
    "fun": "Fun",
}
DERIVED_TAGS = {"independent", "affiliated"}


def project_tags(p: dict) -> list[str]:
    """Derived tags first, then the entry's own, in TAGS order."""
    aff = p.get("affiliation") or ""
    derived = set()
    if aff.startswith("Independent"):
        derived.add("independent")
    elif aff in AFFILIATION_LOGOS:
        derived.add("affiliated")
    have = derived | set(p.get("tags", []))
    return [t for t in TAGS if t in have]

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}


class WellFormed(HTMLParser):
    """Rejects unbalanced or crossed tags. Not a validator -- a tripwire."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append(f"line {self.getpos()[0]}: </{tag}> with nothing open")
            return
        open_tag, line = self.stack.pop()
        if open_tag != tag:
            self.errors.append(
                f"line {self.getpos()[0]}: </{tag}> closes <{open_tag}> opened on line {line}"
            )


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def strip_tags(s: str) -> str:
    """Plain text for a meta description -- markup there is shown literally."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()


def preview_text(s: str, limit: int = 300) -> str:
    """The description a link preview prints: plain text with entities decoded
    (the meta tag escapes it again), cut to the last whole sentence that keeps
    most of the limit, or else at a word boundary with an ellipsis -- never
    mid-word."""
    t = html.unescape(strip_tags(s))
    if len(t) <= limit:
        return t
    head = t[:limit]
    ends = [m.end() for m in re.finditer(r'[.!?…]["”’)\]]*(?=\s)', head)]
    if ends and ends[-1] >= 0.6 * limit:
        return head[:ends[-1]]
    head = head[:limit - 1]
    cut = head.rfind(" ")
    return (head[:cut] if cut > 0 else head).rstrip(" ,;:—–-") + "…"


def load(name: str):
    path = CONTENT / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"refusing: {path} does not exist")
    except json.JSONDecodeError as e:
        sys.exit(f"refusing: {path} is not valid JSON -- {e}")


# --------------------------------------------------------------------------
# Pieces
# --------------------------------------------------------------------------

def copy_button(target: str, what: str) -> str:
    """A button that copies an absolute URL. `target` is relative to the page."""
    return (
        f'<button class="copy" type="button" data-copy="{esc(target)}" '
        f'aria-label="Copy link to {esc(what)}" title="Copy link to {esc(what)}">'
        '<span class="copy-icon" aria-hidden="true">#</span>'
        '<span class="copy-text">Copy link</span></button>'
    )


def link_list(links: list[dict]) -> str:
    if not links:
        return ""
    items = [
        f'<a class="{"lnk mono" if l.get("mono") else "lnk"}" href="{esc(l["url"])}" '
        f'target="_blank" rel="noopener noreferrer">{esc(l["label"])}</a>'
        for l in links
    ]
    return f'<p class="links">{"".join(items)}</p>'


def render_project(p: dict, index: int, *, prefix: str, standalone: bool) -> str:
    """One project. `prefix` is the path back to docs/ from the page."""
    slug = esc(p["slug"])
    tag = "div" if standalone else "article"
    attrs = "" if standalone else f' id="{slug}" data-tags="{" ".join(project_tags(p))}"'
    parts = [f'<{tag} class="project"{attrs}>']

    parts.append('<div class="project-head">')
    parts.append(f'<span class="num">{index:02d}</span>')
    parts.append('<div class="project-title">')
    if standalone:
        parts.append(f'<h1>{esc(p["title"])}</h1>')
    else:
        parts.append(
            f'<h3><a class="self" href="{prefix}p/{slug}.html">{esc(p["title"])}</a></h3>'
        )
    meta = [esc(p["period"])]
    if p.get("affiliation"):
        logo = AFFILIATION_LOGOS.get(p["affiliation"])
        if logo:
            meta.append(
                f'<span class="aff"><img src="{prefix}{logo}" alt="" class="aff-logo" '
                f'width="37" height="47" decoding="async">{esc(p["affiliation"])}</span>'
            )
        else:
            meta.append(esc(p["affiliation"]))
    parts.append(f'<p class="meta">{" · ".join(meta)}</p>')
    parts.append("</div>")
    parts.append(copy_button(f"{prefix}p/{slug}.html", p["title"]))
    parts.append("</div>")

    if p.get("lede"):
        parts.append(f'<p class="lede">{p["lede"]}</p>')
    if p.get("summary"):
        parts.append(f'<p class="summary">{p["summary"]}</p>')

    if p.get("image"):
        alt = esc(p.get("caption") or p["title"])
        # The file's own size, so the browser reserves the figure's height
        # before the lazy image arrives. Without it the page grew under a
        # reader who had just jumped to a project further down.
        w, h = image_size(DOCS / "img" / p["image"])
        parts.append(
            f'<figure><img src="{prefix}img/{esc(p["image"])}" alt="{alt}" '
            f'width="{w}" height="{h}" loading="lazy" decoding="async">'
        )
        if p.get("caption"):
            parts.append(f"<figcaption>{p['caption']}</figcaption>")
        parts.append("</figure>")

    # "video" is one clip or a list of them, shown in order.
    videos = p.get("video") or []
    for v in [videos] if isinstance(videos, dict) else videos:
        parts.append(project_video(v, prefix))

    if p.get("carousel"):
        parts.append(slide_carousel(p["carousel"], prefix))

    for para in p["body"]:
        parts.append(f"<p>{para}</p>")

    parts.append(use_case_list(p.get("use_cases", []), prefix))
    parts.append(reference_list(p.get("references", [])))

    if p.get("no_url_reason"):
        parts.append(f'<p class="no-url">{esc(p["no_url_reason"])}</p>')
    parts.append(link_list(p.get("links", [])))
    parts.append(f"</{tag}>")
    return "\n".join(parts)


def image_size(path: pathlib.Path) -> tuple[int, int]:
    """Width and height read from a PNG, JPEG or WebP header. Refuses any other
    file, or one whose header cannot be read, rather than emitting a guess."""
    try:
        data = path.read_bytes()
    except OSError:
        sys.exit(f"refusing: image not present: {path}")
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            return (int.from_bytes(data[26:28], "little") & 0x3FFF,
                    int.from_bytes(data[28:30], "little") & 0x3FFF)
        if chunk == b"VP8L" and data[20] == 0x2F:
            b0, b1, b2, b3 = data[21:25]
            return (1 + (((b1 & 0x3F) << 8) | b0),
                    1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6)))
        if chunk == b"VP8X":
            return (1 + int.from_bytes(data[24:27], "little"),
                    1 + int.from_bytes(data[27:30], "little"))
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg = int.from_bytes(data[i + 2:i + 4], "big")
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                return (int.from_bytes(data[i + 7:i + 9], "big"),
                        int.from_bytes(data[i + 5:i + 7], "big"))
            i += 2 + seg
    sys.exit(f"refusing: cannot read the size of {path} (PNG, JPEG or WebP only)")


def project_video(v: dict, prefix: str) -> str:
    """A short silent screen recording, looped like an image. It does not
    autoplay for readers who ask for reduced motion; the script gives them
    controls instead."""
    src = f'{prefix}{v["src"]}'
    poster = f'{prefix}{v["poster"]}'
    # "autoplay": false keeps a second clip on its poster with controls, so two
    # recordings that open on the same title card do not loop it side by side.
    autoplay = v.get("autoplay", True)
    if not isinstance(autoplay, bool):
        sys.exit(f'refusing: video {v["src"]}: "autoplay" must be true or false')
    play = "autoplay muted loop" if autoplay else "controls muted"
    w, h = int(v["width"]), int(v["height"])
    # A portrait clip at full width would be taller than the screen; like a
    # portrait deck, it is held to 80% of the viewport's height and centered.
    fit = f' style="max-width:calc(80vh * {w} / {h})"' if h > w else ""
    return (
        '<figure class="clip">'
        f'<video data-clip src="{esc(src)}" poster="{esc(poster)}" '
        f'width="{w}" height="{h}"{fit} '
        f'{play} playsinline preload="metadata" '
        f'aria-label="{esc(v["alt"])}"></video>'
        f'<figcaption>{v["caption"]}</figcaption>'
        '</figure>'
    )


def slide_carousel(c: dict, prefix: str) -> str:
    """A deck shown one slide at a time. Slides are numbered NN.webp under
    c["dir"]; only the current one is in the markup, and the script fetches the
    next on demand. Without script the first slide and the source link remain."""
    base = f'{prefix}{c["dir"]}/'
    n = int(c["count"])
    title = esc(c["title"])
    src = c.get("source")
    source = (
        f' <a href="{esc(src["url"])}" target="_blank" rel="noopener noreferrer">'
        f'{esc(src["label"])}</a>.' if src else ""
    )
    return (
        f'<figure class="deck" data-deck data-base="{esc(base)}" data-count="{n}" '
        f'data-title="{title}">'
        # The frame takes the slides' own shape (16:9 for a talk deck, 4:5 for a
        # LinkedIn carousel) and never grows taller than 80% of the viewport.
        f'<div class="deck-frame" style="aspect-ratio:{int(c["width"])}/{int(c["height"])};'
        f'max-width:calc(80vh * {int(c["width"])} / {int(c["height"])});margin-inline:auto" '
        f'tabindex="0" role="region" aria-roledescription="carousel" '
        f'aria-label="{title}, {n} slides; use the arrow keys">'
        f'<img src="{esc(base)}01.webp" alt="{title}, slide 1 of {n}" '
        f'width="{int(c["width"])}" height="{int(c["height"])}" loading="lazy" decoding="async">'
        '</div>'
        '<div class="deck-nav">'
        '<button type="button" data-step="-1" aria-label="Previous slide" disabled>&larr;</button>'
        f'<span class="deck-count" aria-live="polite">1 / {n}</span>'
        '<button type="button" data-step="1" aria-label="Next slide">&rarr;</button>'
        '</div>'
        f'<figcaption>{c["caption"]}{source}</figcaption>'
        '</figure>'
    )


# slug -> position on the index, filled by main() before any page renders, so a
# use case can name the entry it points at by its number.
PROJECT_NUMBERS: dict[str, int] = {}


def use_case_list(cases: list, prefix: str) -> str:
    """A platform's applications, each with its live site and its own entry here.
    Empty when a project carries none."""
    if not cases:
        return ""
    items = []
    for c in cases:
        n = PROJECT_NUMBERS[c["page"]]
        items.append(
            f'<li><p class="uc-name"><span class="uc-kind">{esc(c["kind"])}</span>'
            f'{esc(c["name"])}</p><p>{c["text"]}</p>'
            '<p class="links inline">'
            f'<a class="lnk" href="{prefix}p/{esc(c["page"])}.html">Project {n:02d}</a>'
            f'<a class="lnk" href="{esc(c["site"])}" target="_blank" rel="noopener noreferrer">'
            f'{esc(c["site"].removeprefix("https://").rstrip("/"))}</a></p></li>'
        )
    return (
        '<section class="uses" aria-label="Use cases"><h4>Use cases</h4>'
        f'<ol>{"".join(items)}</ol></section>'
    )


def reference_list(refs: list) -> str:
    """Supporting literature under a project: author (year), title, venue, and a
    resolvable identifier. Empty when a project carries none."""
    if not refs:
        return ""
    items = []
    for r in refs:
        year = f" ({r['year']})" if r.get("year") else ""
        items.append(
            f'<li>{esc(r["authors"])}{year}. {esc(r["title"])}. '
            f'<span class="venue">{esc(r["venue"])}</span>. '
            f'<a href="{esc(r["url"])}" target="_blank" rel="noopener noreferrer">'
            f'{esc(r["label"])}</a></li>'
        )
    return (
        '<section class="refs" aria-label="References"><h4>References</h4>'
        f'<ol>{"".join(items)}</ol></section>'
    )


def render_publication(pub: dict) -> str:
    links = "".join(
        f'<a class="lnk" href="{esc(l["url"])}" target="_blank" '
        f'rel="noopener noreferrer">{esc(l["label"])}</a>'
        for l in pub.get("links", [])
    )
    note = f'<span class="note">{esc(pub["note"])}</span>' if pub.get("note") else ""
    links_html = f'<span class="links inline">{links}</span>' if links else ""
    return (
        '<li class="entry">'
        f'<span class="when">{esc(pub["date"])}</span>'
        f'<span class="what"><strong>{esc(pub["title"])}</strong>'
        f'<span class="where">{esc(pub["venue"])}</span>{note}{links_html}'
        "</span></li>"
    )


def render_talk(t: dict) -> str:
    links = "".join(
        f'<a class="lnk" href="{esc(l["url"])}" target="_blank" '
        f'rel="noopener noreferrer">{esc(l["label"])}</a>'
        for l in t.get("links", [])
    )
    flag = '<span class="tag">upcoming</span>' if t.get("upcoming") else ""
    links_html = f'<span class="links inline">{links}</span>' if links else ""
    return (
        '<li class="entry">'
        f'<span class="when">{esc(t["date"])}{flag}</span>'
        f'<span class="what"><strong>{esc(t["title"])}</strong>'
        f'<span class="where">{esc(t["venue"])}</span>{links_html}'
        "</span></li>"
    )


def render_article(a: dict) -> str:
    reprint = f"articles/{a['slug']}.html"
    extra = ""
    if a.get("linkedin"):
        extra = (
            f'<span class="links inline"><a class="lnk" href="{esc(a["linkedin"])}" '
            f'target="_blank" rel="noopener noreferrer">LinkedIn</a></span>'
        )
    return (
        '<li class="entry">'
        f'<span class="when">{esc(a["date"])}</span>'
        f'<span class="what">'
        f'<a class="title-link" href="{esc(reprint)}">{esc(a["title"])}</a>{extra}'
        "</span></li>"
    )


def render_artifact(a: dict) -> str:
    cls = "name mono" if a.get("mono") else "name"
    links = "".join(
        f'<a class="lnk" href="{esc(l["url"])}" target="_blank" '
        f'rel="noopener noreferrer">{esc(l["label"])}</a>'
        for l in a.get("links", [])
    )
    links_html = f'<span class="links inline">{links}</span>' if links else ""
    return (
        '<li class="artifact">'
        f'<a class="{cls}" href="{esc(a["url"])}" target="_blank" '
        f'rel="noopener noreferrer">{esc(a["name"])}</a>'
        f'<span class="kind">{esc(a["kind"])}</span>'
        f'<span class="blurb">{esc(a["blurb"])}</span>{links_html}'
        "</li>"
    )


# --------------------------------------------------------------------------
# Featured: web versions of the three PDF documents
# --------------------------------------------------------------------------

# The PDFs, the data they were rendered from and a manifest come from the
# profile kit's export step; nothing here decides which entries appear. The
# manifest carries both hashes, so a page rendered from other data than the
# PDF beside it is refused rather than published under the same name.
FEATURED = ("projects", "publications", "writing")
FEATURED_DIR = CONTENT / "featured"
FEATURED_HUB_LABEL = {
    "projects": "Every project in full",
    "publications": "Abstracts",
    "writing": "All reprints",
}


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_featured() -> tuple[dict, dict, list[str]]:
    problems: list[str] = []
    try:
        manifest = json.loads((FEATURED_DIR / "manifest.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}, {}, ["content/featured/manifest.json does not exist; run the kit's export"]
    rows: dict = {}
    for kind in FEATURED:
        m = manifest.get(kind)
        if not m:
            problems.append(f"featured: the manifest has no {kind!r}")
            continue
        data = FEATURED_DIR / f"{kind}.json"
        pdf = DOCS / "featured" / f"{kind}.pdf"
        cover = DOCS / "img" / "featured" / f"{kind}-cover.png"
        missing = [x for x in (data, pdf, cover) if not x.is_file()]
        if missing:
            problems += [f"featured: missing {x.relative_to(ROOT)}" for x in missing]
            continue
        if sha256_file(data) != m["data_sha256"]:
            problems.append(f"featured: content/featured/{kind}.json is not the data its PDF was rendered from")
        if sha256_file(pdf) != m["pdf_sha256"]:
            problems.append(f"featured: docs/featured/{kind}.pdf is not the PDF the manifest records")
        rows[kind] = json.loads(data.read_text(encoding="utf-8"))
        if len(rows[kind]) != m["entries"]:
            problems.append(f"featured: {kind} has {len(rows[kind])} entries, the manifest {m['entries']}")
    return manifest, rows, problems


def addr(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def featured_link_text(label: str, url: str) -> str:
    if not label:
        return esc(addr(url))
    if label.endswith(" at"):
        return f"{esc(label)} {esc(addr(url))}"
    return esc(label)


def featured_links(links: list[dict]) -> str:
    items = "".join(
        f'<a class="lnk" href="{esc(l["url"])}" target="_blank" rel="noopener noreferrer">'
        f'{featured_link_text(l["label"], l["url"])}</a>'
        for l in links
    )
    return f'<span class="links inline">{items}</span>'


def us_date(iso: str) -> str:
    d = datetime.date.fromisoformat(iso)
    return f"{d:%B} {d.day}, {d.year}"


def featured_entry(kind: str, x: dict) -> str:
    if kind == "projects":
        return (
            f'<li class="fcard" id="{esc(x["slug"])}">'
            f'<p class="fmeta"><span class="ftag">{esc(x["tag"])}</span><span>{esc(x["period"])}</span></p>'
            f'<h3><a class="self" href="../p/{esc(x["slug"])}.html">{esc(x["name"])}</a></h3>'
            f'<p>{esc(x["desc"])}</p>{featured_links(x["links"])}</li>'
        )
    if kind == "publications":
        status = f'<span class="ftag">{esc(x["status"])}</span>' if x["status"] else "<span></span>"
        note = f'<p class="note">{esc(x["note"])}</p>' if x.get("note") else ""
        first = x["links"][0]["url"]
        return (
            f'<li class="fcard"><p class="fmeta">{status}<span>{esc(x["date"])}</span></p>'
            f'<h3><a class="self" href="{esc(first)}" target="_blank" rel="noopener noreferrer">'
            f'{esc(x["title"])}</a></h3>'
            f'<p class="where">{esc(x["venue"])}</p><p>{esc(x["line"])}</p>{note}'
            f'{featured_links(x["links"])}</li>'
        )
    return (
        f'<li class="fcard"><p class="fmeta"><span>{esc(us_date(x["date"]))}</span></p>'
        f'<h3><a class="self" href="../articles/{esc(x["slug"])}.html">{esc(x["title"])}</a></h3>'
        f'{featured_links([{"label": "Read on LinkedIn", "url": x["url"]}])}</li>'
    )


def featured_expected_links(kind: str, x: dict) -> list[str]:
    return [x["url"]] if kind == "writing" else [l["url"] for l in x["links"]]


def featured_title(kind: str, x: dict) -> str:
    return x["name"] if kind == "projects" else x["title"]


def featured_meta(kind: str, m: dict) -> dict:
    n, what = m["stats"][0]
    return dict(
        title=f'{m["name"]} — Alexander Chernov',
        description=f'{m["sub"]} {n} {what} with their links, as a web page and a PDF.',
        canonical=f"{SITE}/featured/{kind}.html",
        og_image=f"{SITE}/og/featured-{kind}.png",
        og_type="article",
    )


def build_featured_page(kind: str, m: dict, rows: list[dict]) -> str:
    pre = "../"
    current = ' aria-current="page"'
    nav = "".join(
        f'<a href="{k}.html"{current if k == kind else ""}>{esc(k.capitalize())}</a>'
        for k in FEATURED
    )
    hub = m["hub"]
    hub_href = pre + hub[len(SITE) + 1:] if hub.startswith(SITE + "/") else hub
    if hub_href == pre:
        hub_href = f"{pre}index.html"
    stats = " · ".join(f"{n} {esc(t)}" for n, t in m["stats"])
    size = (DOCS / "featured" / f"{kind}.pdf").stat().st_size
    entries = "".join(featured_entry(kind, x) for x in rows)
    body = f"""
<header class="top">
  <div class="wrap">
    <div class="topbar"><p class="eyebrow">Portfolio · Featured</p>{THEME_WIDGET}</div>
    <h1>Alexander <span class="sur">CHERNOV</span></h1>
    <p class="role">🤖 Link-Think-Act · Principal Engineer · AI &amp; Data Infrastructure · Agentic Datasets · Semantic Gateways · Agentic AI &amp; Scientific Data Systems · IEEE Member · Research &amp; Technical Speaker</p>
    <nav class="jump">
      {nav}
      <a href="{pre}index.html">Portfolio</a>
      <a href="https://chernov.ca">chernov.ca</a>
    </nav>
  </div>
</header>

<main class="wrap">
  <a class="backlink" href="{pre}index.html">&larr; the whole portfolio</a>
  <section id="{kind}">
    <div class="section-head"><h2>{esc(m["name"])}</h2>{copy_button(f"{kind}.html", m["name"])}</div>
    <p class="section-note">{esc(m["sub"])}<span class="fstats">{stats}</span></p>
    <p class="fdoc"><a class="lnk" href="{kind}.pdf">PDF · {m["pages"]} pages · {round(size / 1024)} kB</a><a class="lnk" href="{esc(hub_href)}">{esc(FEATURED_HUB_LABEL[kind])}</a></p>
    <ol class="fentries">{entries}</ol>
  </section>
</main>
{FOOTER}
"""
    return shell(**featured_meta(kind, m), prefix=pre, body=body)


def check_featured(name: str, kind: str, rows: list[dict], doc: str) -> list[str]:
    """The page lists exactly the entries and links of the data its PDF was
    rendered from: same count, every title, and no link more or less."""
    problems: list[str] = []
    found = doc.count('<li class="fcard"')
    if found != len(rows):
        problems.append(f"{name}: {found} entries, the data has {len(rows)}")
    m = re.search(r'<ol class="fentries">(.*?)</ol>', doc, re.S)
    listed = m.group(1) if m else ""
    for x in rows:
        if esc(featured_title(kind, x)) not in listed:
            problems.append(f"{name}: title missing: {featured_title(kind, x)[:50]!r}")
    got = {html.unescape(h) for h in re.findall(r'href="(https://[^"]*)"', listed)}
    want = {u for x in rows for u in featured_expected_links(kind, x)}
    if got != want:
        problems.append(f"{name}: links differ from the data: missing {sorted(want - got)}, "
                        f"extra {sorted(got - want)}")
    return problems


# --------------------------------------------------------------------------
# Shell
# --------------------------------------------------------------------------

# Light is the default: the light tokens sit on bare :root, so a visitor with
# no stored choice gets light whatever their OS says. Dark arrives only by
# asking for it -- explicitly, or by choosing "System" and having a dark OS.
CSS = """
:root{--bg:#f1f5f9;--panel:#fff;--card:#f8fafc;--ink:#0f172a;--muted:#475569;
--line:#e2e8f0;--accent:#dc2626;--link:#1d4ed8;--radius:.5rem;color-scheme:light}
:root[data-theme="dark"],
:root[data-theme="system"]:is(.prefers-dark){--bg:#000;--panel:#0f172a;--card:#1e293b;
--ink:#f8fafc;--muted:#94a3b8;--line:#1e293b;--accent:#ff2d2d;--link:#93c5fd;
color-scheme:dark}
@media (prefers-color-scheme:dark){
:root[data-theme="system"]{--bg:#000;--panel:#0f172a;--card:#1e293b;--ink:#f8fafc;
--muted:#94a3b8;--line:#1e293b;--accent:#ff2d2d;--link:#93c5fd;color-scheme:dark}}
*{box-sizing:border-box}
html{font-size:clamp(15px,.5vw+11px,19px);scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
font:1rem/1.65 "Roboto Slab",Georgia,"Times New Roman",serif;
-webkit-font-smoothing:antialiased}
.wrap{width:min(60rem,100% - 2rem);margin-inline:auto}
a{color:var(--link)}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.92em}
code{background:rgba(148,163,184,.2);padding:.1em .35em;border-radius:.25rem}

header.top{background:var(--panel);border-bottom:1px solid var(--line);
padding-block:clamp(2rem,5vw,3.6rem)}
.topbar{display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;
margin-bottom:.6rem}
.eyebrow{margin:0;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;
color:var(--muted)}
.theme{display:inline-flex;border:1px solid var(--line);border-radius:var(--radius);
overflow:hidden;flex-shrink:0}
.theme button{font:inherit;font-size:.72rem;padding:.3rem .65rem;cursor:pointer;
background:transparent;color:var(--muted);border:0}
.theme button+button{border-left:1px solid var(--line)}
.theme button[aria-pressed="true"]{background:var(--accent);color:#fff;font-weight:700}
h1{margin:0 0 .4rem;font-size:clamp(1.8rem,5.5vw,3.2rem);font-weight:700;
letter-spacing:-.02em;line-height:1.15}
h1 .sur{color:var(--accent)}
.role{margin:0 0 1.4rem;font-size:clamp(1rem,2.2vw,1.25rem);color:var(--muted)}
.motto{margin:-.8rem 0 1.4rem;font-size:clamp(.92rem,1.9vw,1.05rem);font-style:italic;color:var(--muted)}
.question{margin:0 0 1.6rem;padding-left:1rem;border-left:3px solid var(--accent);
font-size:clamp(1.02rem,2.3vw,1.3rem);font-style:italic}
.question span{display:block;margin-top:.5rem;font-size:.85rem;font-style:normal;
color:var(--muted)}
nav.jump{display:flex;flex-wrap:wrap;gap:.5rem}
nav.jump a{display:inline-block;padding:.4rem .8rem;border:1px solid var(--line);
border-radius:var(--radius);background:var(--card);color:var(--ink);
text-decoration:none;font-size:.85rem}
nav.jump a:hover{border-color:var(--accent)}

main{padding-block:clamp(2rem,4vw,3.5rem)}
section{margin-bottom:clamp(2.5rem,6vw,4.5rem);scroll-margin-top:1rem}
.section-head{display:flex;align-items:baseline;gap:.75rem;margin:0 0 .3rem}
h2{font-size:clamp(1.35rem,3vw,1.9rem);margin:0;letter-spacing:-.01em}
.section-note{margin:0 0 1.6rem;color:var(--muted);font-size:.92rem}

.copy{font:inherit;font-size:.72rem;line-height:1;padding:.32rem .55rem;cursor:pointer;
background:var(--card);color:var(--muted);border:1px solid var(--line);
border-radius:var(--radius);display:inline-flex;align-items:center;gap:.3rem;
flex-shrink:0;white-space:nowrap}
.copy:hover{border-color:var(--accent);color:var(--ink)}
.copy-icon{font-weight:700;color:var(--accent)}
.copy.done{border-color:var(--accent);color:var(--ink)}
.copy.done .copy-icon{content:""}

.project{background:var(--panel);border:1px solid var(--line);
border-radius:var(--radius);padding:clamp(1rem,2.5vw,1.8rem);margin-bottom:1.2rem;
scroll-margin-top:1rem}
.project-head{display:flex;gap:.9rem;align-items:flex-start;margin-bottom:.6rem}
.num{color:var(--accent);font-size:.9rem;font-weight:700;flex-shrink:0;
padding-top:.35rem}
.project-title{flex:1;min-width:0}
.project h1,.project h3{margin:0;font-size:clamp(1.1rem,2.4vw,1.45rem);line-height:1.25}
.project h1{font-size:clamp(1.5rem,4vw,2.2rem)}
a.self{color:inherit;text-decoration:none}
a.self:hover{color:var(--accent)}
.meta{margin:.2rem 0 0;font-size:.82rem;color:var(--muted)}
.aff{white-space:nowrap}
.meta .aff-logo{display:inline;height:1.25em;width:auto;vertical-align:-.3em;margin-right:.3em;
border:0;border-radius:0;background:none}
.lede{margin:0 0 .7rem;font-size:1.02em;font-style:italic}
.summary{margin:0 0 1.1rem;padding-left:.9rem;border-left:2px solid var(--line);
font-size:.94em;color:var(--muted)}
.project p{margin:0 0 .9rem}
.project figure{margin:0 0 1rem}
.project img{display:block;width:100%;height:auto;border:1px solid var(--line);
border-radius:var(--radius);background:var(--card)}
figcaption{margin-top:.45rem;font-size:.8rem;color:var(--muted)}
.no-url{font-size:.85rem;color:var(--muted);font-style:italic}
.clip{margin:0 0 1rem}
.clip video{display:block;width:100%;height:auto;margin:0 auto;
border:1px solid var(--line);border-radius:var(--radius);background:#f5f5f4}
.deck{margin:0 0 1rem}
.deck-frame{position:relative;aspect-ratio:16/9;border:1px solid var(--line);
border-radius:var(--radius);background:#fff;overflow:hidden;touch-action:pan-y}
.deck-frame:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.project .deck-frame img{width:100%;height:100%;object-fit:contain;border:0;border-radius:0}
.deck-nav{display:none;align-items:center;justify-content:center;gap:.8rem;margin:.55rem 0 0}
.js .deck-nav{display:flex}
.deck-nav button{font:inherit;font-size:1rem;line-height:1;padding:.4rem .8rem;cursor:pointer;
border:1px solid var(--line);border-radius:var(--radius);background:var(--card);color:inherit}
.deck-nav button:hover:not(:disabled){border-color:var(--accent)}
.deck-nav button:disabled{opacity:.35;cursor:default}
.deck-count{min-width:4.5rem;text-align:center;font-size:.85rem;color:var(--muted);
font-variant-numeric:tabular-nums}
.uses{margin:1.1rem 0 .9rem;padding-top:.7rem;border-top:1px solid var(--line)}
.uses h4{margin:0 0 .6rem;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;
color:var(--muted);font-weight:600}
.uses ol{margin:0;padding:0;list-style:none;counter-reset:uc}
.uses li{counter-increment:uc;margin:0 0 .9rem;padding:0 0 .9rem 2rem;position:relative;
border-bottom:1px solid var(--line)}
.uses li:last-child{border-bottom:0;padding-bottom:0}
.uses li::before{content:counter(uc);position:absolute;left:0;top:.05rem;color:var(--accent);
font-weight:700;font-size:.9rem}
.project .uses p{margin:0 0 .35rem}
.uc-name{font-weight:600}
.uc-kind{display:block;font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;
color:var(--muted);font-weight:600}
.refs{margin:1.1rem 0 .9rem;padding-top:.7rem;border-top:1px solid var(--line)}
.refs h4{margin:0 0 .35rem;font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;
color:var(--muted);font-weight:600}
.refs ol{margin:0;padding-left:1.3rem;font-size:.8rem;color:var(--muted);line-height:1.5}
.refs li{margin:0 0 .25rem;overflow-wrap:anywhere}
.refs .venue{font-style:italic}
.links{display:flex;flex-wrap:wrap;gap:.5rem;margin:.9rem 0 0}
.links.inline{margin:.35rem 0 0}
.lnk{display:inline-block;padding:.28rem .6rem;border:1px solid var(--line);
border-radius:var(--radius);background:var(--card);text-decoration:none;font-size:.82rem}
.lnk:hover{border-color:var(--accent)}

ul.entries{list-style:none;margin:0;padding:0}
.entry{display:flex;gap:1rem;padding:.8rem 0;border-top:1px solid var(--line)}
.entry:first-child{border-top:0}
.when{flex:0 0 9.5rem;color:var(--muted);font-size:.85rem}
.what{flex:1;min-width:0}
.where{display:block;color:var(--muted);font-size:.87rem;margin-top:.15rem}
.note{display:block;color:var(--muted);font-size:.82rem;margin-top:.15rem}
.tag{display:inline-block;margin-left:.5rem;padding:.05rem .4rem;border-radius:.25rem;
background:var(--accent);color:#fff;font-size:.68rem;letter-spacing:.04em;
text-transform:uppercase;vertical-align:middle}
.title-link{text-decoration:none;font-weight:700}
.title-link:hover{text-decoration:underline}

ul.artifacts{list-style:none;margin:0;padding:0;display:grid;gap:.8rem;
grid-template-columns:repeat(auto-fit,minmax(17rem,1fr))}
.artifact{background:var(--panel);border:1px solid var(--line);
border-radius:var(--radius);padding:.9rem 1rem}
.artifact .name{font-weight:700;text-decoration:none}
.artifact .kind{display:inline-block;margin-left:.5rem;font-size:.7rem;
color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.artifact .blurb{display:block;margin-top:.35rem;font-size:.87rem;color:var(--muted)}

.backlink{display:inline-block;margin-bottom:1.2rem;font-size:.85rem}
/* Featured: the web version of a PDF document, one card per entry. */
nav.jump a[aria-current="page"]{border-color:var(--accent);color:var(--accent);font-weight:700}
.fstats{display:block;margin-top:.3rem;color:var(--ink);font-variant-numeric:tabular-nums}
.fdoc{display:flex;flex-wrap:wrap;gap:.5rem;margin:0 0 1.6rem}
ol.fentries{list-style:none;margin:0;padding:0}
.fcard{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
padding:clamp(1rem,2.5vw,1.4rem);margin-bottom:1rem;scroll-margin-top:1rem}
.fmeta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:.2rem 1rem;
margin:0 0 .35rem;font-size:.8rem;color:var(--muted)}
.ftag{color:var(--accent);font-weight:700;letter-spacing:.06em;text-transform:uppercase}
.fcard h3{margin:0 0 .4rem;font-size:clamp(1.05rem,2.3vw,1.3rem);line-height:1.3}
.fcard p{margin:0 0 .45rem}
.fcard .where{margin:0 0 .45rem}
.fcard .note{margin:0 0 .45rem}
.fcard .lnk{overflow-wrap:anywhere}
/* Projects: one link per project, under the section's heading. */
.tag-filter{display:none;flex-wrap:wrap;align-items:center;gap:.4rem;margin:0 0 1rem}
.js .tag-filter{display:flex}
.tag-filter button{font:inherit;font-size:.82rem;line-height:1;padding:.42rem .7rem;cursor:pointer;
border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink)}
.tag-filter button:hover{border-color:var(--accent)}
.tag-filter button[aria-pressed="true"]{border-color:var(--accent);background:var(--accent);color:#fff}
.tag-filter .tf-n{opacity:.7;font-size:.75rem;margin-left:.15rem;font-variant-numeric:tabular-nums}
.tf-count{font-size:.8rem;color:var(--muted);margin-left:.3rem}
[hidden]{display:none!important}
.project-index{margin:0 0 2rem}
.project-index ol{list-style:none;margin:0;padding:0;display:grid;
grid-template-columns:repeat(auto-fill,minmax(17rem,1fr));gap:.2rem .9rem}
.project-index a{display:flex;gap:.6rem;align-items:baseline;padding:.3rem .55rem;
border-radius:var(--radius);text-decoration:none;color:var(--ink);font-size:.88rem;line-height:1.35}
.project-index a:hover{background:var(--panel);color:var(--link)}
.pi-n{flex:none;min-width:1.5rem;color:var(--accent);font-weight:700;font-size:.78rem}
.project{scroll-margin-top:1rem}
/* Up: fixed on the right, shown once the page has been scrolled. */
.to-top{position:fixed;right:max(1rem,env(safe-area-inset-right));bottom:max(1.25rem,env(safe-area-inset-bottom));
z-index:50;display:grid;place-items:center;width:2.9rem;height:2.9rem;padding:0;border-radius:50%;
border:1px solid var(--line);background:var(--panel);color:var(--accent);cursor:pointer;
box-shadow:0 4px 14px rgba(15,23,42,.18);opacity:0;visibility:hidden;transform:translateY(.5rem);
transition:opacity .2s,transform .2s,visibility .2s}
.to-top.on{opacity:1;visibility:visible;transform:none}
.to-top:hover{border-color:var(--accent)}
.to-top:focus-visible{outline:2px solid var(--link);outline-offset:3px}
.to-top svg{width:1.3rem;height:1.3rem}
@media (prefers-reduced-motion:reduce){.to-top{transition:none}}

footer.bottom{border-top:1px solid var(--line);padding-block:2.5rem;
color:var(--muted);font-size:.85rem}
footer.bottom p{margin:0 0 .5rem}

@media (max-width:34rem){
.entry{flex-direction:column;gap:.15rem}
.when{flex:none}
.copy-text{display:none}
}
"""

# Runs before first paint. Absence of a stored value means LIGHT, not system:
# the default was asked for explicitly, so it cannot be left to the OS.
THEME_SCRIPT = """
(function(){try{var t=localStorage.getItem('pf-theme');
document.documentElement.dataset.theme=(t==='dark'||t==='system')?t:'light';}
catch(e){document.documentElement.dataset.theme='light';}})();
"""

BEHAVIOUR = """
(function(){
  var root=document.documentElement;

  // Tag filter: one tag at a time, or All. The list and the entries are hidden
  // together, so a visible link never points at a hidden project.
  var tf=document.querySelector('.tag-filter');
  if(tf){
    var tfCount=tf.querySelector('.tf-count');
    tf.addEventListener('click',function(e){
      var b=e.target.closest('button[data-tag]');if(!b)return;
      var want=b.dataset.tag,shown=0,total=0;
      tf.querySelectorAll('button[data-tag]').forEach(function(x){
        x.setAttribute('aria-pressed',x===b?'true':'false');});
      document.querySelectorAll('.project-index li[data-tags], article.project[data-tags]').forEach(function(el){
        var on=!want||(' '+el.dataset.tags+' ').indexOf(' '+want+' ')>=0;
        el.hidden=!on;
        if(el.tagName==='ARTICLE'){total++;if(on)shown++;}
      });
      tfCount.textContent=want?('Showing '+shown+' of '+total):'';
    });
  }
  function paint(){
    var cur=root.dataset.theme||'light';
    document.querySelectorAll('.theme button').forEach(function(b){
      b.setAttribute('aria-pressed',String(b.dataset.theme===cur));});
  }
  // In-page links (the project list, the top links): straight to the target, then held
  // there while the page settles. A smooth scroll aims at where the target was when the
  // link was pressed, and media loading on the way lengthened the page: measured
  // 2026-11-09, project 19 ended 4,096 px below the top. The hold lets go the moment
  // anything else moves the page or the reader presses anything: held through a press
  // of the up control, it scrolled the page back down to the project (owner, 2026-11-09).
  var hold=null;
  ['wheel','touchstart','keydown','pointerdown'].forEach(function(k){
    window.addEventListener(k,function(){hold=null;},{passive:true,capture:true});});
  document.addEventListener('click',function(e){
    var a=e.target.closest('.project-index a[href^="#"], nav.jump a[href^="#"]');
    if(!a||e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey)return;
    var el=document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
    if(!el)return;
    e.preventDefault();
    history.pushState(null,'',a.getAttribute('href'));
    var mine=hold={},at=0,root=document.documentElement;
    // An instant jump. behavior 'auto' defers to the stylesheet, and html has
    // scroll-behavior:smooth, so 'auto' alone animated across the whole page,
    // the hold read the animation as the reader scrolling, let go, and the
    // project landed thousands of pixels off (owner, 2026-11-15).
    var go=function(){var was=root.style.scrollBehavior;root.style.scrollBehavior='auto';
      el.scrollIntoView({behavior:'instant',block:'start'});
      root.style.scrollBehavior=was;at=window.scrollY;};
    go();
    [150,400,800,1500,2500].forEach(function(ms){setTimeout(function(){
      if(hold!==mine)return;
      // The page was moved by something other than this hold: let go.
      if(Math.abs(window.scrollY-at)>2){hold=null;return;}
      if(Math.abs(el.getBoundingClientRect().top)>24)go();},ms);});
  });
  document.addEventListener('click',function(e){
    var t=e.target.closest('.theme button');
    if(t){root.dataset.theme=t.dataset.theme;
      try{localStorage.setItem('pf-theme',t.dataset.theme);}catch(err){}
      paint();return;}

    var c=e.target.closest('[data-copy]');
    if(!c)return;
    var url=new URL(c.dataset.copy,location.href).href;
    var done=function(){var s=c.querySelector('.copy-text');var was=s?s.textContent:'';
      c.classList.add('done');if(s)s.textContent='Copied';
      setTimeout(function(){c.classList.remove('done');if(s)s.textContent=was;},1600);};
    // The async clipboard needs a secure context and permission; where it is
    // refused the link still has to end up on the clipboard, so fall back
    // rather than failing silently.
    if(navigator.clipboard&&window.isSecureContext){
      navigator.clipboard.writeText(url).then(done,function(){legacy(url,done);});
    }else{legacy(url,done);}
  });
  function legacy(text,ok){
    var ta=document.createElement('textarea');ta.value=text;
    ta.setAttribute('readonly','');ta.style.position='fixed';ta.style.opacity='0';
    document.body.appendChild(ta);ta.select();
    try{document.execCommand('copy');ok();}catch(e){window.prompt('Copy this link:',text);}
    document.body.removeChild(ta);
  }
  paint();

  // Up: shown once the page is scrolled past most of a screen; a press goes back to
  // the top, at once where the reader has asked for reduced motion.
  var up=document.querySelector('.to-top');
  if(up){
    var calm=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
    var seen=function(){up.classList.toggle('on',window.scrollY>window.innerHeight*0.8);};
    window.addEventListener('scroll',seen,{passive:true});seen();
    up.addEventListener('click',function(){
      hold=null;
      window.scrollTo({top:0,behavior:calm?'auto':'smooth'});
      var h=document.querySelector('header.top h1');if(h){h.setAttribute('tabindex','-1');h.focus({preventScroll:true});}
    });
  }

  // Clips: no autoplay for reduced motion; controls instead.
  if(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches){
    document.querySelectorAll('video[data-clip]').forEach(function(v){
      v.removeAttribute('autoplay');v.pause();v.controls=true;});
  }

  // Slide decks: one slide in the DOM, the neighbours prefetched.
  root.classList.add('js');
  document.querySelectorAll('[data-deck]').forEach(function(deck){
    var base=deck.dataset.base, n=+deck.dataset.count, title=deck.dataset.title, i=1;
    var img=deck.querySelector('img'), count=deck.querySelector('.deck-count');
    var prev=deck.querySelector('[data-step="-1"]'), next=deck.querySelector('[data-step="1"]');
    var frame=deck.querySelector('.deck-frame');
    function url(k){return base+(k<10?'0':'')+k+'.webp';}
    function warm(k){if(k>=1&&k<=n){var p=new Image();p.src=url(k);}}
    function show(k){
      i=Math.max(1,Math.min(n,k));
      img.src=url(i);img.alt=title+', slide '+i+' of '+n;
      count.textContent=i+' / '+n;prev.disabled=i===1;next.disabled=i===n;
      warm(i+1);warm(i-1);
    }
    deck.addEventListener('click',function(e){
      var b=e.target.closest('[data-step]');if(b)show(i+ +b.dataset.step);});
    frame.addEventListener('keydown',function(e){
      if(e.key==='ArrowRight'){show(i+1);e.preventDefault();}
      else if(e.key==='ArrowLeft'){show(i-1);e.preventDefault();}
      else if(e.key==='Home'){show(1);e.preventDefault();}
      else if(e.key==='End'){show(n);e.preventDefault();}});
    var x0=null;
    frame.addEventListener('touchstart',function(e){x0=e.touches[0].clientX;},{passive:true});
    frame.addEventListener('touchend',function(e){
      if(x0===null)return;var dx=e.changedTouches[0].clientX-x0;x0=null;
      if(Math.abs(dx)>40)show(i+(dx<0?1:-1));},{passive:true});
    frame.addEventListener('click',function(e){
      var r=frame.getBoundingClientRect();show(i+(e.clientX-r.left>r.width/2?1:-1));});
  });
})();
"""


def shell(*, title: str, description: str, canonical: str, og_image: str,
          og_type: str, prefix: str, body: str, head_extra: str = "") -> str:
    return f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{head_extra}<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="icon" type="image/x-icon" href="{prefix}favicon.ico">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Alexander Chernov — Portfolio">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(og_image)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{esc(title)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{esc(og_image)}">
<script>{THEME_SCRIPT}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@400;700&display=swap">
<style>{CSS}</style>
</head>
<body>
{body}
<button type="button" class="to-top" aria-label="Back to the top" title="Back to the top">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
</button>
<script>{BEHAVIOUR}</script>
</body>
</html>
"""


THEME_WIDGET = """<div class="theme" role="group" aria-label="Color scheme">
<button type="button" data-theme="light" aria-pressed="true">Light</button>
<button type="button" data-theme="dark" aria-pressed="false">Dark</button>
<button type="button" data-theme="system" aria-pressed="false">System</button>
</div>"""


FOOTER = """<footer class="bottom">
  <div class="wrap">
    <p><a href="https://chernov.ca">chernov.ca</a> &middot;
      <a href="https://github.com/doytsujin" target="_blank" rel="noopener noreferrer">github.com/doytsujin</a> &middot;
      <a href="https://orcid.org/0009-0007-3198-2712" target="_blank" rel="noopener noreferrer">ORCID 0009-0007-3198-2712</a> &middot;
      <a href="https://www.linkedin.com/in/thedoytsujin" target="_blank" rel="noopener noreferrer">LinkedIn</a></p>
    <p>Employer-associated entries describe work done in that role and are not published by or on
      behalf of an employer. Entries marked as independent are unaffiliated with any employer.</p>
    <p>&copy; 2024&ndash;2026 Alexander Chernov. All rights reserved.</p>
  </div>
</footer>"""


def section_head(anchor: str, heading: str, prefix: str) -> str:
    return (
        f'<div class="section-head"><h2>{heading}</h2>'
        f'{copy_button(f"{prefix}index.html#{anchor}", strip_tags(heading))}</div>'
    )


def index_title(title: str) -> str:
    """The full title, so every line says what the project does; a name before
    the colon is set in bold so the list can still be scanned by name."""
    name, sep, rest = title.partition(":")
    if not sep:
        return esc(title)
    return f"<strong>{esc(name.strip())}</strong>: {esc(rest.strip())}"


def project_index(projects: list[dict]) -> str:
    """One link per project, to its entry below, by its full title."""
    items = "".join(
        f'<li data-tags="{" ".join(project_tags(p))}"><a href="#{esc(p["slug"])}">'
        f'<span class="pi-n">{i:02d}</span>'
        f'<span>{index_title(p["title"])}</span></a></li>'
        for i, p in enumerate(projects, start=1)
    )
    return f'<nav class="project-index" aria-label="Projects on this page"><ol>{items}</ol></nav>'


def tag_filter(projects: list[dict]) -> str:
    """Buttons that narrow the list and the entries to one tag. Shown only when
    the script runs, so without it every project stays on the page."""
    counts = {t: sum(t in project_tags(p) for p in projects) for t in TAGS}
    buttons = [f'<button type="button" data-tag="" aria-pressed="true">All '
               f'<span class="tf-n">{len(projects)}</span></button>']
    buttons += [
        f'<button type="button" data-tag="{t}" aria-pressed="false">{esc(label)} '
        f'<span class="tf-n">{counts[t]}</span></button>'
        for t, label in TAGS.items() if counts[t]
    ]
    return (
        '<div class="tag-filter" role="group" aria-label="Show projects by tag">'
        f'{"".join(buttons)}'
        f'<span class="tf-count" aria-live="polite"></span></div>'
    )


def build_index(data: dict) -> str:
    p = ""  # index sits at docs/, so nothing to prefix
    projects = "\n".join(
        render_project(pr, i, prefix=p, standalone=False)
        for i, pr in enumerate(data["projects"], start=1)
    )
    body = f"""
<header class="top">
  <div class="wrap">
    <div class="topbar"><p class="eyebrow">Portfolio</p>{THEME_WIDGET}</div>
    <h1>Alexander <span class="sur">CHERNOV</span></h1>
    <p class="role">🤖 Link-Think-Act · Principal Engineer · AI &amp; Data Infrastructure · Agentic Datasets · Semantic Gateways · Agentic AI &amp; Scientific Data Systems · IEEE Member · Research &amp; Technical Speaker</p>
    <p class="motto">While with AstraZeneca, guided by its motto &ldquo;What science can
      do,&rdquo; I have had the opportunity to contribute to research in data, AI and
      applied AI.</p>
    <p class="question">{esc(QUESTION)}<span>Twenty-six systems, one question.
      <a href="p/agent-scope.html">Agent Scope</a> answers it on a live cluster: the agent
      proposes, the gate decides, and every decision leaves a record.
      <a href="p/grafferene.html">Grafferene</a> answers it for a cache: a stored answer
      reaches a user only when every check passes.
      <a href="p/agentic-crawl.html">Agentic Crawl</a> answers it for a crawler: a request
      is sent only when the site&rsquo;s rules allow it.
      <a href="p/adam.html">adam</a> answers it for a clinical program: a model&rsquo;s column
      is accepted only when it reproduces the reference exactly.
      <a href="p/agentic-loom.html">Agentic Loom</a> answers it on the plant floor: a recipe
      step runs only when it is admitted or a person takes responsibility for it.
      <a href="p/agentic-delivery.html">Agentic Delivery</a> answers it for software delivery:
      a change ships only when the gate has checked the evidence itself.
      <a href="p/agentic-lims.html">Agentic LIMS</a> answers it for laboratory data: a result
      enters a report only when it can be traced to its source and the dataset&rsquo;s policy admits it.</span></p>
    <nav class="jump">
      <a href="#projects">Projects</a>
      <a href="#live">Live &amp; installable</a>
      <a href="#publications">Publications</a>
      <a href="#talks">Talks</a>
      <a href="#writing">Writing</a>
      <a href="https://chernov.ca">chernov.ca</a>
    </nav>
  </div>
</header>

<main class="wrap">
  <section id="projects">
    {section_head("projects", "Projects", p)}
    <p class="section-note">The public ones first &mdash; they are the only entries a reader can
      verify, and a verifiable entry earns the ones that follow it. Where a project has no public
      URL that is stated rather than hidden behind a link that returns 404. Each title is also a
      page of its own, which is what the copy button hands you.</p>
    {tag_filter(data["projects"])}
    {project_index(data["projects"])}
    {projects}
  </section>

  <section id="live">
    {section_head("live", "Live &amp; installable", p)}
    <p class="section-note">Running pages and published packages. Nothing here needs an
      introduction from me to be checked.</p>
    <ul class="artifacts">{"".join(render_artifact(a) for a in data["artifacts"])}</ul>
  </section>

  <section id="publications">
    {section_head("publications", "Publications", p)}
    <p class="section-note">Peer-reviewed, newest first. The abstracts are on the
      <a href="papers/">papers page</a>.</p>
    <ul class="entries">{"".join(render_publication(x) for x in data["publications"])}</ul>
  </section>

  <section id="talks">
    {section_head("talks", "Talks &amp; sessions", p)}
    <p class="section-note">Conference and community talks, newest first.</p>
    <ul class="entries">{"".join(render_talk(x) for x in data["talks"])}</ul>
  </section>

  <section id="writing">
    {section_head("writing", "Writing", p)}
    <p class="section-note">Long-form articles. Each title links to its reprint in
      <a href="articles/">the articles book</a> on this site; where the piece also ran on
      LinkedIn, that original is linked beside it.</p>
    <ul class="entries">{"".join(render_article(x) for x in data["articles"])}</ul>
  </section>
</main>
{FOOTER}
"""
    return shell(
        title=TITLE, description=DESCRIPTION, canonical=f"{SITE}/",
        og_image=f"{SITE}/og/site.png", og_type="profile", prefix="", body=body,
    )


def build_project_page(p: dict, index: int) -> str:
    pre = "../"
    body = f"""
<header class="top">
  <div class="wrap">
    <div class="topbar"><p class="eyebrow">Portfolio · Project {index:02d}</p>{THEME_WIDGET}</div>
    <h1>Alexander <span class="sur">CHERNOV</span></h1>
    <p class="role">🤖 Link-Think-Act · Principal Engineer · AI &amp; Data Infrastructure · Agentic Datasets · Semantic Gateways · Agentic AI &amp; Scientific Data Systems · IEEE Member · Research &amp; Technical Speaker</p>
    <nav class="jump">
      <a href="{pre}index.html">All projects</a>
      <a href="{pre}index.html#publications">Publications</a>
      <a href="{pre}index.html#talks">Talks</a>
      <a href="{pre}index.html#writing">Writing</a>
      <a href="https://chernov.ca">chernov.ca</a>
    </nav>
  </div>
</header>

<main class="wrap">
  <a class="backlink" href="{pre}index.html">&larr; the whole portfolio</a>
  {render_project(p, index, prefix=pre, standalone=True)}
</main>
{FOOTER}
"""
    return shell(**project_meta(p), prefix=pre, body=body)


def project_meta(p: dict) -> dict:
    return dict(
        title=f'{p["title"]} — Alexander Chernov',
        description=preview_text(p.get("summary") or p.get("lede") or p["body"][0]),
        canonical=f'{SITE}/p/{p["slug"]}.html',
        og_image=f'{SITE}/og/{p["slug"]}.png',
        og_type="article",
    )


def build_alias_page(p: dict) -> str:
    """A renamed project's old address. LinkedIn keeps the URL it was given, so
    the old page stays: it carries the new page's title and card, names the new
    page as canonical, and sends the reader on to it."""
    target = f'{p["slug"]}.html'
    body = f"""
<main class="wrap">
  <p class="backlink">This project now lives at
    <a href="{esc(target)}">{esc(p["title"])}</a>.</p>
</main>
"""
    return shell(
        **project_meta(p), prefix="../", body=body,
        head_extra=(f'<meta http-equiv="refresh" content="0; url={esc(target)}">\n'
                    '<meta name="robots" content="noindex">\n'),
    )


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------

def check_articles(articles: list[dict]) -> list[str]:
    """Every article carries its publication date. An undated entry once went
    live as a blank cell at the top of Writing, so a missing date is refused
    here rather than rendered."""
    problems: list[str] = []
    for a in articles:
        d = a.get("date")
        try:
            ok = isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) \
                and datetime.date.fromisoformat(d)
        except ValueError:
            ok = False
        if not ok:
            problems.append(f'articles.json: "{a.get("title")}" has no valid date '
                            f"(got {d!r}); give the publication date as YYYY-MM-DD")
    return problems


def check_tags(projects: list[dict]) -> list[str]:
    """Every project carries at least one hand-set tag, so a new entry cannot
    reach the page invisible to every filter but All; only known tags; and
    never a hand-set affiliated/independent, which the affiliation line decides."""
    problems: list[str] = []
    for p in projects:
        own = p.get("tags", [])
        for t in own:
            if t not in TAGS:
                problems.append(f'projects.json: {p["slug"]}: unknown tag {t!r} '
                                f'(known: {", ".join(TAGS)})')
            elif t in DERIVED_TAGS:
                problems.append(f'projects.json: {p["slug"]}: tag {t!r} is read from the '
                                'affiliation line; do not set it by hand')
        if not [t for t in own if t in TAGS and t not in DERIVED_TAGS]:
            problems.append(f'projects.json: {p["slug"]}: no tag; give it one of '
                            f'{", ".join(t for t in TAGS if t not in DERIVED_TAGS)}')
    return problems


def check_use_cases(projects: list[dict]) -> list[str]:
    """A use case points at another entry on this site and at a live page. An
    entry that is not here would render as a link to a missing page, and a
    use case that points at its own entry links the reader in a circle."""
    problems: list[str] = []
    for p in projects:
        for c in p.get("use_cases", []):
            missing = [k for k in ("kind", "name", "text", "page", "site") if not c.get(k)]
            if missing:
                problems.append(f'projects.json: {p["slug"]}: use case {c.get("name")!r} '
                                f'lacks {", ".join(missing)}')
                continue
            if c["page"] not in PROJECT_NUMBERS:
                problems.append(f'projects.json: {p["slug"]}: use case {c["name"]!r} names '
                                f'no project here: {c["page"]}')
            elif c["page"] == p["slug"]:
                problems.append(f'projects.json: {p["slug"]}: use case {c["name"]!r} '
                                'points at its own entry')
            if not c["site"].startswith("https://"):
                problems.append(f'projects.json: {p["slug"]}: use case {c["name"]!r} '
                                f'site is not https: {c["site"]}')
    return problems


# --------------------------------------------------------------------------
# Output validation
# --------------------------------------------------------------------------

def check(name: str, doc: str, base: pathlib.Path) -> list[str]:
    problems: list[str] = []

    parser = WellFormed()
    parser.feed(doc)
    parser.close()
    problems.extend(f"{name}: {e}" for e in parser.errors)
    problems.extend(f"{name}: unclosed <{t}> opened on line {ln}" for t, ln in parser.stack)

    for href in re.findall(r'href="([^"]*)"', doc):
        if not href:
            problems.append(f"{name}: empty href")
        elif not (href.startswith(("https://", "#")) or re.fullmatch(r"[\w./#-]+", href)):
            problems.append(f"{name}: href is neither https, an anchor, nor a local path: {href}")
        elif not href.startswith(("https://", "#")):
            # A local link must land on a file this site serves; a directory
            # means its index.html, as the server answers it.
            path = base / href.split("#")[0]
            if href.split("#")[0].endswith("/"):
                path = path / "index.html"
            if not path.resolve().is_file():
                problems.append(f"{name}: local link to a missing file: {href}")

    for src in re.findall(r'<img src="([^"]*)"', doc):
        if not (base / src).resolve().is_file():
            problems.append(f"{name}: image referenced but not present: {src}")

    # An image without its size takes no room until it loads, so everything
    # below it moves -- including a project the reader just jumped to.
    for tag in re.findall(r"<img [^>]*>", doc):
        if not (re.search(r'\swidth="\d+"', tag) and re.search(r'\sheight="\d+"', tag)):
            problems.append(f"{name}: image without width and height: {tag[:70]}")

    # A clip whose file is missing renders as an empty box with no error, so
    # both the video and its poster have to exist on disk.
    for tag in re.findall(r"<video [^>]*>", doc):
        for attr in ("src", "poster"):
            m = re.search(rf'{attr}="([^"]*)"', tag)
            if not m:
                problems.append(f"{name}: video without {attr}: {tag[:60]}")
            elif not (base / m.group(1)).resolve().is_file():
                problems.append(f"{name}: video {attr} referenced but not present: {m.group(1)}")

    # The description is what a link preview prints under the title. Cut
    # mid-word it reads as a broken page, so it must end like a sentence or
    # with an ellipsis.
    for desc in re.findall(r'<meta property="og:description" content="([^"]*)"', doc):
        if not re.search(r'[.!?…]["”’)\]]*$', html.unescape(desc).strip()):
            problems.append(f"{name}: og:description ends mid-sentence: ...{html.unescape(desc)[-40:]!r}")
        if re.search(r"&(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);", html.unescape(desc)):
            problems.append(f"{name}: og:description shows a literal entity: {html.unescape(desc)[:60]!r}...")

    # A card with no image is the failure LinkedIn shows the world, so the
    # referenced file has to exist on disk, not merely be named.
    for og in re.findall(r'<meta property="og:image" content="([^"]*)"', doc):
        rel = og[len(SITE) + 1:] if og.startswith(SITE) else None
        if rel is None:
            problems.append(f"{name}: og:image is not on {SITE}: {og}")
        elif not (DOCS / rel).is_file():
            problems.append(f"{name}: og:image missing on disk: docs/{rel}")

    if '<span class="when"></span>' in doc:
        problems.append(f"{name}: an entry renders with an empty date")

    for tag in re.findall(r"<a [^>]*>", doc):
        if 'target="_blank"' in tag and "noopener" not in tag:
            problems.append(f"{name}: target=_blank without rel=noopener: {tag[:60]}")

    # A forwarding page must forward to a page this build wrote.
    for target in re.findall(r'http-equiv="refresh" content="0; url=([^"]*)"', doc):
        if not (base / target).resolve().is_file():
            problems.append(f"{name}: forwards to a missing page: {target}")

    # Every copy button must name something that exists, or it hands out a 404.
    for target in re.findall(r'data-copy="([^"]*)"', doc):
        path = (base / target.split("#")[0]).resolve()
        if not path.is_file():
            problems.append(f"{name}: copy button targets a missing page: {target}")

    return problems


def fail(problems: list[str]) -> None:
    for p in problems:
        print(f"  {p}", file=sys.stderr)
    sys.exit(f"BUILD FAILED -- {len(problems)} problem(s); do not deploy")


def main() -> None:
    data = {k: load(k) for k in
            ("projects", "publications", "talks", "articles", "artifacts")}
    projects = data["projects"]

    PROJECT_NUMBERS.update({p["slug"]: i for i, p in enumerate(projects, start=1)})

    manifest, featured, featured_problems = load_featured()
    problems = (check_articles(data["articles"]) + check_use_cases(projects)
                + check_tags(projects) + featured_problems)
    if problems:
        fail(problems)

    (DOCS / "p").mkdir(parents=True, exist_ok=True)

    pages: list[tuple[pathlib.Path, str, pathlib.Path]] = []
    for i, p in enumerate(projects, start=1):
        pages.append((DOCS / "p" / f'{p["slug"]}.html',
                      build_project_page(p, i), DOCS / "p"))
        for old in p.get("aliases", []):
            pages.append((DOCS / "p" / f"{old}.html", build_alias_page(p), DOCS / "p"))
    pages.append((DOCS / "index.html", build_index(data), DOCS))
    for kind in FEATURED:
        pages.append((DOCS / "featured" / f"{kind}.html",
                      build_featured_page(kind, manifest[kind], featured[kind]), DOCS / "featured"))

    # Write first, then check: copy-button and inter-page links point at files
    # this same run produces, so a check before the write would fail on pages
    # that are about to exist. Nothing is served from here -- the deploy is a
    # separate step, and it is gated on this exiting zero.
    for path, doc, _ in pages:
        path.write_text(doc, encoding="utf-8")

    for path, doc, base in pages:
        problems.extend(check(path.relative_to(DOCS).as_posix(), doc, base))
    for kind in FEATURED:
        doc = (DOCS / "featured" / f"{kind}.html").read_text(encoding="utf-8")
        problems.extend(check_featured(f"featured/{kind}.html", kind, featured[kind], doc))

    if problems:
        fail(problems)

    total = sum(len(d.encode()) for _, d, _ in pages) / 1024
    print(f"wrote {len(pages)} pages ({total:.1f} kB): index + {len(projects)} projects "
          f"+ {len(FEATURED)} featured")


if __name__ == "__main__":
    main()
