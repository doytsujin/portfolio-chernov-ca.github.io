#!/usr/bin/env python3
"""Render content/*.json into docs/index.html.

Standard library only, same as the other tools in this account. The content
files are hand-authored and trusted, so body strings may carry inline markup
(<em>, <code>, entities) and are emitted verbatim. What is NOT trusted is that
they are *correct*: every render is parsed back and checked before it is
written, because a static page fails silently -- a stray unclosed tag swallows
the rest of the document and the build would otherwise report success.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent
CONTENT = ROOT / "content"
DOCS = ROOT / "docs"

SITE_URL = "https://portfolio.chernov.ca/"
TITLE = "Alexander Chernov — Portfolio"
DESCRIPTION = (
    "Projects, publications, talks and writing: control planes, admission "
    "gates and observable decisions for scientific and regulated systems."
)

# Void elements never close, so a well-formedness check that expects a closing
# tag for every opening one has to know them. Missing this list is how the
# check would reject its own correct output.
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


def load(name: str):
    path = CONTENT / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"refusing: {path} does not exist")
    except json.JSONDecodeError as e:
        sys.exit(f"refusing: {path} is not valid JSON -- {e}")


def link_list(links: list[dict]) -> str:
    if not links:
        return ""
    items = []
    for link in links:
        cls = "lnk mono" if link.get("mono") else "lnk"
        items.append(
            f'<a class="{cls}" href="{esc(link["url"])}" target="_blank" '
            f'rel="noopener noreferrer">{esc(link["label"])}</a>'
        )
    return f'<p class="links">{"".join(items)}</p>'


def render_project(p: dict, index: int) -> str:
    parts = [f'<article class="project" id="{esc(p["slug"])}">']
    parts.append('<div class="project-head">')
    parts.append(f'<span class="num">{index:02d}</span>')
    parts.append("<div>")
    parts.append(f'<h3>{esc(p["title"])}</h3>')
    meta = [esc(p["period"])]
    if p.get("affiliation"):
        meta.append(esc(p["affiliation"]))
    parts.append(f'<p class="meta">{" · ".join(meta)}</p>')
    parts.append("</div></div>")

    if p.get("lede"):
        parts.append(f'<p class="lede">{p["lede"]}</p>')

    if p.get("image"):
        alt = esc(p.get("caption") or p["title"])
        parts.append(
            f'<figure><img src="img/{esc(p["image"])}" alt="{alt}" loading="lazy" '
            f'decoding="async">'
        )
        if p.get("caption"):
            parts.append(f"<figcaption>{p['caption']}</figcaption>")
        parts.append("</figure>")

    for para in p["body"]:
        parts.append(f"<p>{para}</p>")

    if p.get("no_url_reason"):
        parts.append(f'<p class="no-url">{esc(p["no_url_reason"])}</p>')
    parts.append(link_list(p.get("links", [])))
    parts.append("</article>")
    return "\n".join(parts)


def render_publication(pub: dict) -> str:
    links = "".join(
        f'<a class="lnk" href="{esc(l["url"])}" target="_blank" '
        f'rel="noopener noreferrer">{esc(l["label"])}</a>'
        for l in pub.get("links", [])
    )
    note = f'<span class="note">{esc(pub["note"])}</span>' if pub.get("note") else ""
    return (
        '<li class="entry">'
        f'<span class="when">{esc(pub["date"])}</span>'
        f'<span class="what"><strong>{esc(pub["title"])}</strong>'
        f'<span class="where">{esc(pub["venue"])}</span>'
        f'{note}{f'<span class="links inline">{links}</span>' if links else ""}'
        "</span></li>"
    )


def render_talk(t: dict) -> str:
    links = "".join(
        f'<a class="lnk" href="{esc(l["url"])}" target="_blank" '
        f'rel="noopener noreferrer">{esc(l["label"])}</a>'
        for l in t.get("links", [])
    )
    flag = '<span class="tag">upcoming</span>' if t.get("upcoming") else ""
    return (
        '<li class="entry">'
        f'<span class="when">{esc(t["date"])}{flag}</span>'
        f'<span class="what"><strong>{esc(t["title"])}</strong>'
        f'<span class="where">{esc(t["venue"])}</span>'
        f'{f'<span class="links inline">{links}</span>' if links else ""}'
        "</span></li>"
    )


def render_article(a: dict) -> str:
    reprint = f"https://brainapi.org/articles/{a['slug']}.html"
    extra = ""
    if a.get("linkedin"):
        extra = (
            f'<a class="lnk" href="{esc(a["linkedin"])}" target="_blank" '
            f'rel="noopener noreferrer">LinkedIn</a>'
        )
    return (
        '<li class="entry">'
        f'<span class="when">{esc(a["date"] or "")}</span>'
        f'<span class="what">'
        f'<a class="title-link" href="{esc(reprint)}" target="_blank" '
        f'rel="noopener noreferrer">{esc(a["title"])}</a>'
        f'{f'<span class="links inline">{extra}</span>' if extra else ""}'
        "</span></li>"
    )


def render_artifact(a: dict) -> str:
    cls = "name mono" if a.get("mono") else "name"
    return (
        '<li class="artifact">'
        f'<a class="{cls}" href="{esc(a["url"])}" target="_blank" '
        f'rel="noopener noreferrer">{esc(a["name"])}</a>'
        f'<span class="kind">{esc(a["kind"])}</span>'
        f'<span class="blurb">{esc(a["blurb"])}</span>'
        "</li>"
    )


CSS = """
:root{--bg:#000;--panel:#0f172a;--card:#1e293b;--ink:#f8fafc;--muted:#94a3b8;
--line:#1e293b;--accent:#ff2d2d;--link:#93c5fd;--radius:.5rem}
@media (prefers-color-scheme:light){:root{--bg:#f1f5f9;--panel:#fff;--card:#f8fafc;
--ink:#0f172a;--muted:#475569;--line:#e2e8f0;--accent:#dc2626;--link:#1d4ed8}}
*{box-sizing:border-box}
html{font-size:clamp(15px,.5vw+11px,19px);scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
font:1rem/1.65 "Roboto Slab",Georgia,"Times New Roman",serif;
-webkit-font-smoothing:antialiased}
.wrap{width:min(60rem,100% - 2rem);margin-inline:auto}
a{color:var(--link)}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.92em}
code{background:rgba(148,163,184,.16);padding:.1em .35em;border-radius:.25rem}

header.top{background:var(--panel);border-bottom:1px solid var(--line);
padding-block:clamp(2.5rem,6vw,4.5rem)}
.eyebrow{margin:0 0 .5rem;font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;
color:var(--muted)}
h1{margin:0 0 .4rem;font-size:clamp(2rem,6vw,3.4rem);font-weight:700;letter-spacing:-.02em;
line-height:1.1}
h1 .sur{color:var(--accent)}
.role{margin:0 0 1.4rem;font-size:clamp(1rem,2.2vw,1.3rem);color:var(--muted)}
.question{margin:0 0 1.6rem;padding-left:1rem;border-left:3px solid var(--accent);
font-size:clamp(1.05rem,2.4vw,1.35rem);font-style:italic}
.question span{display:block;margin-top:.5rem;font-size:.86rem;font-style:normal;
color:var(--muted)}
nav.jump{display:flex;flex-wrap:wrap;gap:.5rem}
nav.jump a{display:inline-block;padding:.4rem .8rem;border:1px solid var(--line);
border-radius:var(--radius);background:var(--card);color:var(--ink);text-decoration:none;
font-size:.85rem}
nav.jump a:hover{border-color:var(--accent)}

main{padding-block:clamp(2rem,4vw,3.5rem)}
section{margin-bottom:clamp(2.5rem,6vw,4.5rem);scroll-margin-top:1rem}
h2{font-size:clamp(1.35rem,3vw,1.9rem);margin:0 0 .3rem;letter-spacing:-.01em}
.section-note{margin:0 0 1.6rem;color:var(--muted);font-size:.92rem}

.project{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
padding:clamp(1rem,2.5vw,1.8rem);margin-bottom:1.2rem}
.project-head{display:flex;gap:.9rem;align-items:baseline;margin-bottom:.6rem}
.num{color:var(--accent);font-size:.9rem;font-weight:700;flex-shrink:0}
.project h3{margin:0;font-size:clamp(1.1rem,2.4vw,1.45rem);line-height:1.25}
.meta{margin:.2rem 0 0;font-size:.82rem;color:var(--muted)}
.lede{margin:0 0 1rem;font-size:1.02em;color:var(--ink);font-style:italic}
.project p{margin:0 0 .9rem}
.project figure{margin:0 0 1rem}
.project img{display:block;width:100%;height:auto;border:1px solid var(--line);
border-radius:var(--radius);background:var(--card)}
figcaption{margin-top:.45rem;font-size:.8rem;color:var(--muted)}
.no-url{font-size:.85rem;color:var(--muted);font-style:italic}
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
.what strong{font-weight:700}
.where{display:block;color:var(--muted);font-size:.87rem;margin-top:.15rem}
.note{display:block;color:var(--muted);font-size:.82rem;margin-top:.15rem}
.tag{display:inline-block;margin-left:.5rem;padding:.05rem .4rem;border-radius:.25rem;
background:var(--accent);color:#fff;font-size:.68rem;letter-spacing:.04em;
text-transform:uppercase;vertical-align:middle}
.title-link{text-decoration:none;font-weight:700}
.title-link:hover{text-decoration:underline}

ul.artifacts{list-style:none;margin:0;padding:0;display:grid;gap:.8rem;
grid-template-columns:repeat(auto-fit,minmax(17rem,1fr))}
.artifact{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
padding:.9rem 1rem}
.artifact .name{font-weight:700;text-decoration:none}
.artifact .kind{display:inline-block;margin-left:.5rem;font-size:.7rem;color:var(--muted);
text-transform:uppercase;letter-spacing:.06em}
.artifact .blurb{display:block;margin-top:.35rem;font-size:.87rem;color:var(--muted)}

footer.bottom{border-top:1px solid var(--line);padding-block:2.5rem;color:var(--muted);
font-size:.85rem}
footer.bottom p{margin:0 0 .5rem}
footer.bottom a{color:var(--link)}

@media (max-width:34rem){
.entry{flex-direction:column;gap:.15rem}
.when{flex:none}
.project-head{flex-direction:column;gap:.15rem}
}
"""


def build() -> str:
    projects = load("projects")
    publications = load("publications")
    talks = load("talks")
    articles = load("articles")
    artifacts = load("artifacts")

    project_html = "\n".join(
        render_project(p, i) for i, p in enumerate(projects, start=1)
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(TITLE)}</title>
<meta name="description" content="{esc(DESCRIPTION)}">
<link rel="canonical" href="{SITE_URL}">
<link rel="icon" type="image/x-icon" href="favicon.ico">
<meta property="og:type" content="profile">
<meta property="og:title" content="{esc(TITLE)}">
<meta property="og:description" content="{esc(DESCRIPTION)}">
<meta property="og:url" content="{SITE_URL}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@400;700&display=swap">
<style>{CSS}</style>
</head>
<body>

<header class="top">
  <div class="wrap">
    <p class="eyebrow">Portfolio</p>
    <h1>Alexander <span class="sur">CHERNOV</span></h1>
    <p class="role">Associate Principal Data Engineer · Agentic AI &amp; scientific data systems ·
      IEEE member</p>
    <p class="question">Something proposes under uncertainty &mdash; what decides whether it may
      act?<span>Ten systems, one question. Two of the ten are not neural networks, which is the
      point rather than an omission.</span></p>
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
    <h2>Projects</h2>
    <p class="section-note">The public ones first &mdash; they are the only entries a reader can
      verify, and a verifiable entry earns the ones that follow it. Where a project has no public
      URL that is stated rather than hidden behind a link that returns 404.</p>
    {project_html}
  </section>

  <section id="live">
    <h2>Live &amp; installable</h2>
    <p class="section-note">Running pages and published packages. Nothing here needs an
      introduction from me to be checked.</p>
    <ul class="artifacts">
      {"".join(render_artifact(a) for a in artifacts)}
    </ul>
  </section>

  <section id="publications">
    <h2>Publications</h2>
    <p class="section-note">Peer-reviewed, newest first.</p>
    <ul class="entries">
      {"".join(render_publication(p) for p in publications)}
    </ul>
  </section>

  <section id="talks">
    <h2>Talks &amp; sessions</h2>
    <p class="section-note">Conference and community talks, newest first.</p>
    <ul class="entries">
      {"".join(render_talk(t) for t in talks)}
    </ul>
  </section>

  <section id="writing">
    <h2>Writing</h2>
    <p class="section-note">Long-form articles. Each title links to the reprint at
      <a href="https://brainapi.org/articles/" target="_blank" rel="noopener noreferrer">brainapi.org/articles</a>;
      where the piece also ran on LinkedIn, that original is linked beside it.</p>
    <ul class="entries">
      {"".join(render_article(a) for a in articles)}
    </ul>
  </section>

</main>

<footer class="bottom">
  <div class="wrap">
    <p><a href="https://chernov.ca">chernov.ca</a> &middot;
      <a href="https://github.com/doytsujin" target="_blank" rel="noopener noreferrer">github.com/doytsujin</a> &middot;
      <a href="https://orcid.org/0009-0007-3198-2712" target="_blank" rel="noopener noreferrer">ORCID 0009-0007-3198-2712</a> &middot;
      <a href="https://www.linkedin.com/in/thedoytsujin" target="_blank" rel="noopener noreferrer">LinkedIn</a></p>
    <p>Employer-associated entries describe work done in that role and are not published by or on
      behalf of an employer. Entries marked as independent are unaffiliated with any employer.</p>
    <p>&copy; 2024&ndash;2026 Alexander Chernov. All rights reserved.</p>
  </div>
</footer>

</body>
</html>
"""


def check(doc: str) -> None:
    """Fail the build rather than publish a page that is quietly broken."""
    problems: list[str] = []

    parser = WellFormed()
    parser.feed(doc)
    parser.close()
    problems.extend(parser.errors)
    problems.extend(f"unclosed <{t}> opened on line {ln}" for t, ln in parser.stack)

    # Every href must be absolute https, a same-page anchor, or a local asset.
    for href in re.findall(r'href="([^"]*)"', doc):
        if not href:
            problems.append("empty href")
        elif not (href.startswith(("https://", "#")) or re.fullmatch(r"[\w./-]+", href)):
            problems.append(f"href is neither https, an anchor, nor a local path: {href}")

    # Images must exist on disk; a broken <img> renders as nothing at all.
    for src in re.findall(r'<img src="([^"]*)"', doc):
        if not (DOCS / src).is_file():
            problems.append(f"image referenced but not present: docs/{src}")

    # Every external link opens in a new tab, so every one needs the opener guard.
    for tag in re.findall(r"<a [^>]*>", doc):
        if 'target="_blank"' in tag and "noopener" not in tag:
            problems.append(f"target=_blank without rel=noopener: {tag[:70]}")

    if problems:
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        sys.exit(f"refusing to write docs/index.html -- {len(problems)} problem(s)")


def main() -> None:
    doc = build()
    check(doc)
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(doc, encoding="utf-8")
    kb = len(doc.encode("utf-8")) / 1024
    print(f"wrote docs/index.html ({kb:.1f} kB)")


if __name__ == "__main__":
    main()
