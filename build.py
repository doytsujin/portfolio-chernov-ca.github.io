#!/usr/bin/env python3
"""Render content/*.json into docs/.

Standard library only, same as the other tools in this account. The content
files are hand-authored and trusted, so body strings may carry inline markup
(<em>, <code>, entities) and are emitted verbatim. What is NOT trusted is that
they are *correct*: every render is parsed back and checked before it is
written, because a static page fails silently -- a stray unclosed tag swallows
the rest of the document and the build would otherwise report success.

Output:
  docs/index.html         the whole portfolio
  docs/p/<slug>.html      one page per project

Each project gets its own URL because LinkedIn strips the fragment before it
fetches a link, so ten anchors into one page would all preview as the same
card. Its own URL is what gives it its own title, description and image.
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

SITE = "https://portfolio.chernov.ca"
TITLE = "Alexander Chernov — Portfolio"
DESCRIPTION = (
    "Projects, publications, talks and writing: control planes, admission "
    "gates and observable decisions for scientific and regulated systems."
)
QUESTION = "Something proposes under uncertainty — what decides whether it may act?"

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
    parts = [f'<{tag} class="project"{"" if standalone else f' id="{slug}"'}>']

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
        parts.append(
            f'<figure><img src="{prefix}img/{esc(p["image"])}" alt="{alt}" '
            f'loading="lazy" decoding="async">'
        )
        if p.get("caption"):
            parts.append(f"<figcaption>{p['caption']}</figcaption>")
        parts.append("</figure>")

    for para in p["body"]:
        parts.append(f"<p>{para}</p>")

    if p.get("no_url_reason"):
        parts.append(f'<p class="no-url">{esc(p["no_url_reason"])}</p>')
    parts.append(link_list(p.get("links", [])))
    parts.append(f"</{tag}>")
    return "\n".join(parts)


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
    reprint = f"https://brainapi.org/articles/{a['slug']}.html"
    extra = ""
    if a.get("linkedin"):
        extra = (
            f'<span class="links inline"><a class="lnk" href="{esc(a["linkedin"])}" '
            f'target="_blank" rel="noopener noreferrer">LinkedIn</a></span>'
        )
    return (
        '<li class="entry">'
        f'<span class="when">{esc(a["date"] or "")}</span>'
        f'<span class="what">'
        f'<a class="title-link" href="{esc(reprint)}" target="_blank" '
        f'rel="noopener noreferrer">{esc(a["title"])}</a>{extra}'
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
.lede{margin:0 0 .7rem;font-size:1.02em;font-style:italic}
.summary{margin:0 0 1.1rem;padding-left:.9rem;border-left:2px solid var(--line);
font-size:.94em;color:var(--muted)}
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
  function paint(){
    var cur=root.dataset.theme||'light';
    document.querySelectorAll('.theme button').forEach(function(b){
      b.setAttribute('aria-pressed',String(b.dataset.theme===cur));});
  }
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
})();
"""


def shell(*, title: str, description: str, canonical: str, og_image: str,
          og_type: str, prefix: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
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
    <p class="role">Associate Principal Data Engineer · Agentic AI &amp; scientific data systems ·
      IEEE member</p>
    <p class="question">{esc(QUESTION)}<span>Ten systems, one question. Two of the ten are not
      neural networks, which is the point rather than an omission.</span></p>
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
    <p class="section-note">Peer-reviewed, newest first.</p>
    <ul class="entries">{"".join(render_publication(x) for x in data["publications"])}</ul>
  </section>

  <section id="talks">
    {section_head("talks", "Talks &amp; sessions", p)}
    <p class="section-note">Conference and community talks, newest first.</p>
    <ul class="entries">{"".join(render_talk(x) for x in data["talks"])}</ul>
  </section>

  <section id="writing">
    {section_head("writing", "Writing", p)}
    <p class="section-note">Long-form articles. Each title links to the reprint at
      <a href="https://brainapi.org/articles/" target="_blank" rel="noopener noreferrer">brainapi.org/articles</a>;
      where the piece also ran on LinkedIn, that original is linked beside it.</p>
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
    <p class="role">Associate Principal Data Engineer · Agentic AI &amp; scientific data systems</p>
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
    return shell(
        title=f'{p["title"]} — Alexander Chernov',
        description=strip_tags(p.get("summary") or p.get("lede") or p["body"][0])[:300],
        canonical=f'{SITE}/p/{p["slug"]}.html',
        og_image=f'{SITE}/og/{p["slug"]}.png',
        og_type="article", prefix=pre, body=body,
    )


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

    for src in re.findall(r'<img src="([^"]*)"', doc):
        if not (base / src).resolve().is_file():
            problems.append(f"{name}: image referenced but not present: {src}")

    # A card with no image is the failure LinkedIn shows the world, so the
    # referenced file has to exist on disk, not merely be named.
    for og in re.findall(r'<meta property="og:image" content="([^"]*)"', doc):
        rel = og[len(SITE) + 1:] if og.startswith(SITE) else None
        if rel is None:
            problems.append(f"{name}: og:image is not on {SITE}: {og}")
        elif not (DOCS / rel).is_file():
            problems.append(f"{name}: og:image missing on disk: docs/{rel}")

    for tag in re.findall(r"<a [^>]*>", doc):
        if 'target="_blank"' in tag and "noopener" not in tag:
            problems.append(f"{name}: target=_blank without rel=noopener: {tag[:60]}")

    # Every copy button must name something that exists, or it hands out a 404.
    for target in re.findall(r'data-copy="([^"]*)"', doc):
        path = (base / target.split("#")[0]).resolve()
        if not path.is_file():
            problems.append(f"{name}: copy button targets a missing page: {target}")

    return problems


def main() -> None:
    data = {k: load(k) for k in
            ("projects", "publications", "talks", "articles", "artifacts")}
    projects = data["projects"]

    (DOCS / "p").mkdir(parents=True, exist_ok=True)

    pages: list[tuple[pathlib.Path, str, pathlib.Path]] = []
    for i, p in enumerate(projects, start=1):
        pages.append((DOCS / "p" / f'{p["slug"]}.html',
                      build_project_page(p, i), DOCS / "p"))
    pages.append((DOCS / "index.html", build_index(data), DOCS))

    # Write first, then check: copy-button and inter-page links point at files
    # this same run produces, so a check before the write would fail on pages
    # that are about to exist. Nothing is served from here -- the deploy is a
    # separate step, and it is gated on this exiting zero.
    for path, doc, _ in pages:
        path.write_text(doc, encoding="utf-8")

    problems: list[str] = []
    for path, doc, base in pages:
        problems.extend(check(path.relative_to(DOCS).as_posix(), doc, base))

    if problems:
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        sys.exit(f"BUILD FAILED -- {len(problems)} problem(s); do not deploy")

    total = sum(len(d.encode()) for _, d, _ in pages) / 1024
    print(f"wrote {len(pages)} pages ({total:.1f} kB): index + {len(projects)} projects")


if __name__ == "__main__":
    main()
