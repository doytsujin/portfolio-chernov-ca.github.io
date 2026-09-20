# portfolio.chernov.ca

The long-form portfolio behind [chernov.ca](https://chernov.ca): projects,
publications, talks and writing, each with room for the full description and
as many links as it actually has.

It exists because LinkedIn's Projects section truncates every entry after a
line and a half and gives each one a single URL field. Several of these
projects have three addresses — a DOI, a repository, and a running page — and
the ones that have none say so here rather than pointing at a link that
returns 404.

## Build

```sh
make build      # render content/*.json -> docs/
make og         # re-render the link-preview cards (needs Chrome)
make serve      # build, then serve docs/ on 127.0.0.1:8000
```

`build.py` is standard library only. There is no framework, no bundler and no
install step: the output is self-contained HTML plus the images it references.

    docs/index.html      the whole portfolio
    docs/p/<slug>.html   one page per project
    docs/og/<slug>.png   its 1200x630 link-preview card

## Two hostnames, one canonical

`portfolio.chernov.ca` and `portfolio.alexander.chernov.ca` serve the same tree
from one Caddy block. Every page carries `<link rel="canonical">` pointing at
`portfolio.chernov.ca`, so a crawler or a link preview arriving by the alias
still resolves to one address.

## Why each project has its own page

LinkedIn strips the fragment before it fetches a link. Ten anchors into one
page would all preview as the same card, which defeats the point of linking to
a particular project from a profile. Its own URL is what gives a project its
own title, description and image.

`make og` renders the cards in Chrome rather than drawing them with PIL, so
they use the same Roboto Slab as the site without vendoring a copy of the font.
They are committed, so an ordinary build never needs Chrome; rerun it when a
title, lede or image changes.

## Theme

Light by default. The light tokens sit on bare `:root`, so a visitor with no
stored choice gets light whatever their OS reports — dark arrives only by being
asked for. The toggle offers Light, Dark and System, and stores the choice in
`localStorage`; `System` is the setting that defers to `prefers-color-scheme`.

A pre-paint inline script applies the stored value before first paint, or the
page flashes light and then corrects itself.

## Copy link

Every section heading and every project carries a copy button. A project's
button copies its own page URL, not an anchor, because that is the link worth
pasting into a profile. Section buttons copy `index.html#<section>`.

The async clipboard needs a secure context and permission; where it is refused
the button falls back to a hidden textarea, and to a prompt if even that fails,
because a copy button that silently does nothing is worse than none.

## The build refuses rather than publishes something broken

A static page fails silently. A stray unclosed tag swallows the rest of the
document, a mistyped image path renders as nothing at all, and the build would
otherwise report success either way. So `build.py` parses its own output back
before writing it and exits non-zero on:

- unbalanced or crossed tags (void elements excepted),
- an `href` that is neither `https:`, a same-page anchor, nor a local path,
- an `<img>` whose file is not present under `docs/`,
- a `target="_blank"` link missing `rel="noopener"`,
- an `og:image` that is not on the canonical origin or not present on disk,
- a copy button pointing at a page that does not exist.

Verified by sabotage rather than by assumption: an unclosed `<em>`, an
`http://` link and a missing image produced nine errors and no output; removing
one preview card produced the `og:image` error and exit 1.

## Content

One JSON file per section under `content/`. Adding an entry means adding an
object, not touching the renderer.

| File | Section |
|---|---|
| `projects.json` | Projects — ordered public-first |
| `artifacts.json` | Live & installable |
| `publications.json` | Peer-reviewed publications |
| `talks.json` | Talks & sessions |
| `articles.json` | Writing |

Body paragraphs are emitted verbatim, so they may carry inline `<em>`, `<code>`
and entities. Everything else — titles, labels, captions, URLs — is escaped.

### What belongs here

Only material that is already public. Project copy is kept in step with
`dk-linkedin-profile/profile/10-projects.md`, which is written under two rules
that carry over unchanged: **no codenames**, and **no internal system, dataset,
tenant or person is named**. Where a project touches employer infrastructure it
is described by its shape — "a laboratory asset platform's REST API" — never by
its name.

A URL appears only where the artifact is genuinely public.

## Deploy

```sh
make deploy-dry   # show what would change, transfer nothing
make deploy       # build, check, rsync to the edge, write DEPLOYED
```

`make deploy` publishes to `/var/www/portfolio-chernov` on the Linode edge and
does **not** push to GitHub — that is a separate `git push`. It writes a
`DEPLOYED` provenance file after the rsync recording the commit it was built
from; `dirty=YES` there means it was published from a tree with uncommitted
changes, so commit before deploying.

`docs/CNAME` carries the domain, and `make check` refuses to deploy without it.
