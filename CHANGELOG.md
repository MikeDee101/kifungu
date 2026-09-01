# Changelog

Notable changes per release. Versions come from git tags; the same version is
written into every Cut and render manifest, so an artefact always names the
engine that produced it.

## Unreleased

## v0.2.0 - 2026-09-01

### Added
- `scroll_hunt` — opens on the cover of the Act and races down through the
  pages, decelerating onto the one holding the clause, with motion-blur trails
  derived from the scroll's own velocity.
- `clause_zoom` — pushes in on the clause, with the zoom computed from the
  clause's bounding box so short and long clauses both fill the frame sensibly.
- `clause_select` plus a **selection-style registry**: `marker_sweep`,
  `underline`, `hand_circle`, `bounding_box`, `marquee`, `brackets`. Choose one
  with `kifungu cut --style <name>`; list them with `kifungu styles`.
- `marker_sweep` and `underline_draw` registered as the spec's named shots.
- `clause_hunt` template chaining the whole gesture.
- Camera clamping, so a zoomed page never reveals its own edge.
- `Node.dominant_page` and `Node.page_bbox()` for clauses crossing a page break.

### Fixed
- **Kenya Law revised editions now parse.** Part headings are mixed case with an
  en-dash (`Part I - PRELIMINARY`), and section numbers stand alone on their
  line above the marginal side-note; neither matched the spec's regexes. Table
  of contents entries are skipped, having previously produced phantom sections
  whose text was a row of dots. The KDI Act went from 180 nodes and no Parts to
  554 nodes and all 8 Parts.
- **Running headers and footers are stripped at ingest.** A clause spanning a
  page break previously quoted the page furniture mid-sentence.
- Selection geometry no longer unions boxes across pages, which described a
  rectangle present on neither.

## v0.1.0 - 2026-08-31

Phases 0 and 1 of the spec: ingest a statute, find a clause, author a reviewable
Cut, render it. Walking skeleton plus the authentic-page path.

### Added
- Corpus format: page rasters, word geometry in PDF points, node tree, canonical
  text, FTS5 index.
- Kenyan statute parser with citation nesting, including the `(i)`/`(v)`
  ambiguity between lettered paragraphs and roman sub-paragraphs.
- Generic parser for documents with no statutory structure.
- Cut schema, YAML templates, and hold-time derivation from word count.
- Guardrails: verbatim lock, elision discipline, mandatory citation, source
  pinning with stale detection, gloss approval gate.
- Shots: `page_establish`, `spotlight`, `citation_stamp`.
- Output profiles `reel`, `square`, `portrait`, `wide`, `broll`, with a
  safe-area grid and a `--draft` mode.
- Approvals manifest written beside every render.
- CLI: `ingest`, `find`, `cut`, `render`, `templates`, `shots`.
- Windows portable release, built and published from a tag.

### Notes
- Brand tokens are **provisional**, pending the KDIC brand manual.
