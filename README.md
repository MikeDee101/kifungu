# Kifungu

*Kiswahili: a clause, or a section of a statute — which is exactly what this engine points a camera at.*

A local, offline-first engine that turns institutional documents into broadcast-quality motion
graphics. Point it at a statute, name a clause by its citation, and it renders an animatic: the real
page appears, the clause is hunted down, spotlit, marker-swept, lifted off the page, re-typeset
kinetically, and stamped with its citation.

The engine does not know what a statute is. It knows how to render a **Cut** — a JSON storyboard.
Statutes are one compiler front-end; anything else that can emit a Cut gets the whole shot library
for free.

See [`KIFUNGU_ENGINE_SPEC.md`](KIFUNGU_ENGINE_SPEC.md) for the full engineering specification.

## Status

Early. See the [milestones](#roadmap) below for what works today.

## Install (Windows)

Download the latest `kifungu-<version>-win64.zip` from
[Releases](https://github.com/MikeDee101/kifungu/releases), unzip it anywhere, and run
`kifungu.exe`. No installer, no admin rights, no Python required — `ffmpeg` is bundled.

Verify the download against the published `.sha256` if you care to.

## Install (from source)

```bash
git clone https://github.com/MikeDee101/kifungu.git
cd kifungu
uv sync --extra dev
uv run kifungu --version
```

Requires Python 3.11+ and `ffmpeg` on `PATH`.

## Use

```bash
# One-time per document
kifungu ingest --pdf "KDI_Act_2012.pdf" --doc-id kdi-act-2012 --parser kenya_statute

# Find the clause
kifungu find "compensation limit" --doc kdi-act-2012

# Author a Cut, review the JSON, then render
kifungu cut --doc kdi-act-2012 --cite "s.27(1)" --template clause_spotlight \
            --profiles reel,square --out cuts/coverage-limit.json
kifungu render cuts/coverage-limit.json --out renders/
```

A Cut is a small, readable JSON file holding the exact quoted string and the exact citation. It is
reviewable — by an editor, or by Legal — *before* a single frame is rendered. Approval happens on the
Cut, not on a forty-second render you would otherwise have to redo.

## Accuracy guardrails

This engine quotes Acts of Parliament on public channels. The guardrails are part of the design, not
a nicety:

- **Verbatim lock** — the rendered quote is asserted byte-identical to the source substring. Hand-edit
  it and the render fails.
- **Source pinning** — the sha256 of the source PDF travels in the corpus, the Cut and the manifest.
  Re-ingest an amended document and every prior Cut is flagged stale.
- **Gloss is never statute** — plain-language text renders in a distinct style, always labelled.
- **Citation is mandatory** on every public profile.
- **Approvals manifest** — every render writes a sidecar recording operator, date, source hash,
  citation, exact quoted string, gloss and approver, for filing.

## Roadmap

| Phase | Deliverable |
|---|---|
| 0 | Walking skeleton — ingest, `page_establish` + `spotlight`, 9:16 mp4 |
| 1 | Authentic-page path — statute parser, line-grouped bboxes, FTS search, `find`/`cut` |
| 2 | Full shot library, brand tokens, five output profiles, alpha B-roll |
| 3 | Synthetic path — DOCX/Markdown/text, quote/trivia/stat front-ends |
| 4 | Operator UI — pick document, click paragraph, choose template, render |
| 5 | Optional LLM assist — strictly additive; `--offline` stays fully functional |

## Licence

[AGPL-3.0-or-later](LICENSE). Third-party components and their licences are recorded in
[`packaging/NOTICE-thirdparty.md`](packaging/NOTICE-thirdparty.md).
