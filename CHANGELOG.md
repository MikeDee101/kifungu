# Changelog

Notable changes per release. Versions come from git tags; the same version is
written into every Cut and render manifest, so an artefact always names the
engine that produced it.

## Unreleased

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
