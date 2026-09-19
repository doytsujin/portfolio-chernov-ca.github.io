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
make build      # render content/*.json -> docs/index.html
make serve      # build, then serve docs/ on 127.0.0.1:8000
```

`build.py` is standard library only. There is no framework, no bundler and no
install step: the output is one self-contained HTML file plus the images it
references.

## The build refuses rather than publishes something broken

A static page fails silently. A stray unclosed tag swallows the rest of the
document, a mistyped image path renders as nothing at all, and the build would
otherwise report success either way. So `build.py` parses its own output back
before writing it and exits non-zero on:

- unbalanced or crossed tags (void elements excepted),
- an `href` that is neither `https:`, a same-page anchor, nor a local path,
- an `<img>` whose file is not present under `docs/`,
- a `target="_blank"` link missing `rel="noopener"`.

Verified by sabotage rather than by assumption: introducing an unclosed
`<em>`, an `http://` link and a missing image produced nine errors and no
output file.

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
