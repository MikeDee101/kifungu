# KIFUNGU — KDIC In-House Content Engine

**Engineering specification, v0.1**
Working name: *Kifungu* (Kiswahili: a clause / section of a statute — which is exactly what the engine points a camera at).

---

## 1. Purpose

A local, offline-first engine that turns institutional documents into broadcast-quality motion graphics.

**Core function (the specialised B-Roller).** Ingest a statutory or institutional document — the Kenya Deposit Insurance Act, 2012, the IADI Core Principles, the Citizens' Service Delivery Charter, the Strategic Plan, a Gazette notice — locate a specific segment by citation or search, and render an *animatic* of that segment: the real page appears, the clause is hunted down, spotlit, marker-swept, lifted off the page, re-typeset kinetically, stamped with its citation, and (optionally) flipped into plain language.

**Secondary function (the general content engine).** The same renderer, driven by the same intermediate format, produces every other recurring KDIC motion asset: Trivia Tuesday question/answer reveals, CEO quote cards, key-figure stings, FAQ answers, InfoBYTES pull-outs, roadshow recap plates, the themed-day openers.

The design principle that makes both true: **the engine does not know what a statute is.** It knows how to render a *Cut* — a JSON storyboard. Statutes are one compiler front-end. Anything else that can emit a Cut gets the whole shot library for free.

**Non-goals.** Not a video editor. Not a timeline GUI. Not a replacement for After Effects — it *feeds* After Effects and Premiere with alpha-channel B-roll. No cloud dependency in the render path.

---

## 2. Architecture

Three hard boundaries. Each stage writes to disk; each is independently runnable, testable and cacheable.

```
  ┌─ INGEST ────────────┐   ┌─ CUT ──────────────┐   ┌─ RENDER ───────────┐
  │ PDF / DOCX / MD /   │   │ cut.json           │   │ Cairo+Pango frames │
  │ pasted text         │──▶│ (storyboard IR)    │──▶│ → FFmpeg           │
  │        ↓            │   │  • verbatim text   │   │  → mp4 / mov+alpha │
  │  corpus/<doc_id>/   │   │  • bbox refs       │   │  → png sequence    │
  │   ├ doc.json (tree) │   │  • scene list      │   │  → srt + manifest  │
  │   ├ pages/*.png     │   │  • profile targets │   │                    │
  │   └ words.jsonl     │   └────────────────────┘   └────────────────────┘
  └─────────────────────┘
        offline               human- or LLM-authored        deterministic
```

**Why the split matters:** a Cut is reviewable by Sarah or by Legal *before* a single frame is rendered. It is a small, readable JSON file containing the exact quoted string and the exact citation. Approval happens on the Cut, not on a 40-second render you have to redo.

---

## 3. Stage 1 — Ingest

Two ingest paths converge on one corpus format.

### 3.1 Authentic-page path (PDF)

Used when the *look of the real document* is part of the message — and for the Act, it always is. Library: **PyMuPDF (`fitz`)**.

Per document, produce `corpus/<doc_id>/`:

| Artefact | Content |
|---|---|
| `doc.json` | Document tree: parts → sections → subsections → paragraphs, each with `citation`, `page`, `char_span`, `bbox_union`, `text` |
| `pages/p{n}@2x.png` | 300 DPI page rasters (`page.get_pixmap(dpi=300)`), rendered once, cached |
| `words.jsonl` | Every word with `(x0, y0, x1, y1, page, word_index)` from `page.get_text("words")` |
| `meta.json` | Title, short title, sha256 of the source file, ingest date, page count, engine version |

**Structure detection** for Kenyan statutes is regex-driven and lives in one swappable module (`parsers/kenya_statute.py`), because the layout convention is stable and predictable:

- Section headings: `^\s*(\d+)\.\s+` with a marginal side-note in the left gutter
- Subsections: `^\s*\((\d+)\)`
- Paragraphs: `^\s*\(([a-z])\)`
- Sub-paragraphs: `^\s*\((i|ii|iii|iv|v|vi|vii|viii|ix|x)+\)`
- Part headings: `^PART\s+([IVXLC]+)\s*[—–-]\s*(.+)$`

Each node gets a canonical citation string (`s.27(1)(a)`) and — critically — the **union of the word bboxes that compose it**, grouped per line. The per-line grouping is what makes a highlighter sweep look like a highlighter sweep rather than one fat rectangle.

Store bboxes in PDF points and convert at render time using the raster's actual scale factor. Never bake pixel coordinates into the corpus.

### 3.2 Synthetic-page path (DOCX / Markdown / pasted text)

For sources with no fixed layout — a press release, a FAQ answer, a CEO quote, a Trivia Tuesday item. Here the engine **typesets its own page** in the KDIC document style (Pango layout onto a Cairo surface at page dimensions), which means it owns the coordinates by construction. The output is the identical corpus format: rasters, word boxes, a node tree. Every downstream shot works unchanged.

This is the mechanism by which the engine stops being an Act-viewer and becomes a content engine.

### 3.3 Search

`words.jsonl` plus a small SQLite FTS5 index over node text. Query returns ranked nodes with citations, so the operator can go from *"the bit about the KES 500,000 cap"* to `s.27(1)` without opening the PDF.

---

## 4. Stage 2 — The Cut (intermediate representation)

The contract between the front-ends and the renderer. One file, one clip.

```jsonc
{
  "cut_id": "kdi-act-s27-coverage-limit",
  "engine_version": "0.1.0",
  "created": "2026-08-31T09:14:00+03:00",
  "operator": "Michael Derrick Okoth",

  "source": {
    "doc_id": "kdi-act-2012",
    "title": "Kenya Deposit Insurance Act, 2012",
    "sha256": "9f2c…",
    "citation": "s.27(1)",
    "page": 34,
    "verbatim": "The Corporation shall pay to every depositor of a deposit-taking institution…",
    "elided": false,
    "emphasis": [[4, 15], [42, 51]]      // char spans within `verbatim` to accent
  },

  "gloss": {
    "en": "If your bank fails, KDIC pays you back — up to KES 500,000.",
    "sw": "Benki ikifungwa, KDIC inakurudishia pesa zako — hadi shilingi 500,000.",
    "approved_by": null                   // must be non-null before public profiles render
  },

  "profiles": ["reel", "square", "broll"],

  "audio": { "bed": "assets/audio/beds/institutional_02.wav", "vo": null, "duck_db": -14 },
  "captions": { "burn_in": true, "sidecar_srt": true, "lang": "en" },

  "scenes": [
    { "shot": "scroll_hunt",     "t_in": 0.00, "dur": 1.80,
      "params": { "from_page": 1, "to_page": 34, "ease": "out_quint", "blur_trail": true } },
    { "shot": "page_establish",  "t_in": 1.60, "dur": 1.40,
      "params": { "drift": 0.03 } },
    { "shot": "spotlight",       "t_in": 2.40, "dur": 2.60,
      "params": { "dim": 0.22, "feather_px": 22, "ramp": 0.45 } },
    { "shot": "marker_sweep",    "t_in": 3.00, "dur": 1.20,
      "params": { "stagger": 0.09, "alpha": 0.35, "wobble_px": 1.5 } },
    { "shot": "clause_lift",     "t_in": 4.60, "dur": 1.10,
      "params": { "scale_to": 0.82, "bg_blur_px": 14 } },
    { "shot": "kinetic_typeset", "t_in": 5.50, "dur": 4.80,
      "params": { "unit": "phrase", "reveal": "mask_up", "stagger": 0.14 } },
    { "shot": "gloss_flip",      "t_in": 10.10, "dur": 3.60,
      "params": { "lang": "en", "label": "In plain terms" } },
    { "shot": "citation_stamp",  "t_in": 12.60, "dur": 1.80, "params": {} },
    { "shot": "endplate",        "t_in": 13.90, "dur": 2.60,
      "params": { "cta": "kdic.go.ke", "handle": "@KDIC_Kenya" } }
  ]
}
```

Notes on the schema:

- **Scenes overlap deliberately.** `t_in + dur` may exceed the next `t_in`; the compositor resolves by shot z-order. Overlap is what makes it read as motion design instead of a slideshow.
- **`verbatim` is the single source of truth for quoted text.** No shot re-types it.
- **Hold-time rule** enforced at authoring time: any shot displaying reading text must satisfy `dur >= max(1.8, 0.35 * word_count + 0.8)`. Legal English at 6 seconds is unreadable and worse than not posting.
- **`profiles`** drive Stage 3 fan-out; one Cut renders to every aspect ratio in one pass.

### 4.1 Cut authoring

Three front-ends, all emitting the same file:

1. **`cut` CLI** — citation + template name → Cut. Templates live in `templates/*.yaml` and are just parameterised scene lists (`clause_spotlight`, `quote_card`, `stat_sting`, `trivia_reveal`, `definition_pullout`, `broll_plain`).
2. **Operator UI** (Phase 4) — click a paragraph on a rendered page, pick a template, adjust hold times, save.
3. **LLM assist** (optional, network-gated) — Claude proposes `emphasis` spans, drafts the `gloss.en` / `gloss.sw`, and suggests which of five candidate clauses is most postable this week. **The engine must run fully with `--offline`, in which case gloss fields are left empty for a human to write.** The LLM never touches `verbatim`.

---

## 5. Stage 3 — The shot library

Each shot is a Python class with `render(ctx, t_local) -> None` drawing onto a Cairo context, plus a declared z-order and a declared set of required corpus artefacts. Adding a shot is the only way the engine grows; nothing else should need editing.

| Shot | Behaviour |
|---|---|
| `scroll_hunt` | Fast vertical scroll through page rasters, decelerating onto the target page with motion-blur trails. The "searching the law" gesture. |
| `page_establish` | Page raster settles, subtle scale drift, soft drop shadow on a brand-tinted ground. |
| `spotlight` | Everything dims to `dim`; the clause's line bboxes stay lit through a feathered mask. Ramp is eased, never a hard cut. |
| `marker_sweep` | Per-line left→right highlighter wipe in the brand accent at low alpha, with staggered starts and 1–2px edge wobble so it reads as a hand, not a rectangle. |
| `underline_draw` | Animated stroke under the operative line; lighter alternative to `marker_sweep`. |
| `clause_lift` | Crops the clause region from the 2x raster, lifts it off the page as a card, blurs and darkens the page behind. |
| `kinetic_typeset` | Re-typesets `verbatim` at display size in the brand face; reveals by word or phrase with mask-up / blur-in; `emphasis` spans in accent colour. |
| `gloss_flip` | Card flip or cross-dissolve from statutory text to the plain-language gloss. **Visually distinct type style, always labelled.** |
| `redaction_reveal` | Text as grey bars that resolve into readable words. Excellent generic B-roll under voiceover. |
| `key_figure` | Odometer/counter roll for figures (`KES 500,000`), with unit and caption. |
| `citation_stamp` | Citation + short title + document date stamps in with a slight overshoot. |
| `endplate` | Logo lockup, handle, CTA. Suppressed in the `broll` profile. |

**Typography is non-negotiable: use PangoCairo, not Cairo's toy text API.** Only Pango gives correct line breaking, kerning, justification, and Kiswahili diacritics. The toy `select_font_face` / `show_text` path will look amateur on justified legal text and must not be used anywhere in this engine.

Easing functions (`out_quint`, `in_out_cubic`, `out_back`, `spring`) live in one module and are the only permitted way to interpolate. No linear motion except deliberate machine-like sweeps.

---

## 6. Stage 4 — Render and output profiles

Frames drawn to numbered PNGs (or straight to a pipe), assembled by FFmpeg.

| Profile | Resolution | Codec | Use |
|---|---|---|---|
| `reel` | 1080×1920 | H.264, yuv420p, 30fps | Reels / TikTok / WhatsApp Status |
| `square` | 1080×1080 | H.264, yuv420p | Feed |
| `portrait` | 1080×1350 | H.264, yuv420p | Feed (4:5) |
| `wide` | 1920×1080 | H.264, yuv420p | YouTube, **visitors' reception screen** |
| `broll` | 1920×1080 | **ProRes 4444 with alpha** + PNG sequence | Import into After Effects / Premiere under a voiceover |

Hard rules:

- **`-pix_fmt yuv420p` on every H.264 output.** Without it the file will not play in browsers, WhatsApp or PowerPoint.
- `broll` strips endplate, captions and background plate — it must deliver a clean, keyable element with a genuine alpha channel, not a black matte.
- Render is **deterministic**: all jitter and wobble seeded from `cut_id`, so a re-render after a copy edit matches frame for frame.
- Page rasters are cached; only the frames actually change. A 16s reel at 30fps is 480 frames — parallelise the frame loop across a process pool, one worker per core.
- Every render emits `<cut_id>.manifest.json` alongside the video (see §8).

Layout adapts per profile via a **safe-area system**, not by scaling: each profile declares margins and a title/body/footer grid, and shots lay out against that grid. Never render 16:9 and crop to 9:16.

---

## 7. Brand tokens

One file, `brand/kdic.json`, consumed by every shot. Nothing hard-codes a colour or a font name.

```jsonc
{
  "colors": {
    "primary": "#______",       // ← from the KDIC brand manual, in writing, before any styling
    "secondary": "#______",
    "accent": "#______",        // highlighter + emphasis spans
    "ink": "#1A1A1A",
    "paper": "#F7F6F2",
    "dim": "#0B1220"
  },
  "type": {
    "display": "…",             // headline face, licensed and installed locally
    "body": "…",
    "mono": "…"                 // citations, section numbers
  },
  "logo": { "primary": "assets/brand/kdic_primary.svg", "reverse": "assets/brand/kdic_reverse.svg" },
  "safe_areas": { "reel": {"top": 220, "bottom": 320, "side": 90 }, "…": {} },
  "motion": { "default_ease": "out_quint", "stagger": 0.12, "beat": 0.4 }
}
```

Blocking prerequisite: the exact hexes and the licensed brand typeface files, from the brand manual, before the first shot is styled. Retrofitting a palette across a shot library is a rebuild, not an edit.

---

## 8. Accuracy and approvals guardrails

This engine quotes an Act of Parliament on public channels under the Corporation's name. The guardrails are part of the spec, not a nicety.

1. **Verbatim lock.** A unit test asserts that the rendered quote string is byte-identical to the substring at `source.char_span` in the ingested document. If someone hand-edits `verbatim`, the render fails.
2. **Elision discipline.** Trimming inserts `…` and sets `elided: true`. `--strict` refuses to render elided quotes at all.
3. **Gloss is never statute.** Plain-language text renders in a different type style, on a different ground, always labelled ("In plain terms" / "Kwa lugha rahisi"). A gloss must never inherit the statutory type treatment.
4. **Citation is mandatory.** No public profile renders without `citation_stamp`, including document short title and year.
5. **Source pinning.** The `sha256` of the source PDF is in the corpus, the Cut and the manifest. If the Act is amended and re-ingested, every prior Cut is flagged stale on the next render.
6. **Approvals manifest.** Each render writes a sidecar containing operator, date, source hash, citation, exact quoted string, gloss text, gloss approver, shot list and output hashes — a single artefact Legal or the AD can sign off and file.
7. **Gate.** Public profiles refuse to render when `gloss.approved_by` is null. `broll` and `--draft` are exempt, so internal iteration stays fast.

---

## 9. CLI

```bash
# One-time per document
kifungu ingest --pdf docs/KDI_Act_2012.pdf --doc-id kdi-act-2012 --parser kenya_statute

# Find the clause
kifungu find "compensation limit" --doc kdi-act-2012
#   s.27(1)  p.34  "The Corporation shall pay to every depositor…"
#   s.28(2)  p.35  "…"

# Author the Cut
kifungu cut --doc kdi-act-2012 --cite "s.27(1)" \
            --template clause_spotlight --profiles reel,square,broll \
            --out cuts/kdi-act-s27-coverage-limit.json

# Review, edit the JSON, then render
kifungu render cuts/kdi-act-s27-coverage-limit.json --out renders/ --jobs 8
kifungu render cuts/*.json --profile broll --draft        # batch, half-res, no gate

# Non-statute front-ends
kifungu quote --text "…" --attrib "Hellen Chepkwony, Chief Executive Officer" --template quote_card
kifungu trivia --q "…" --a "…" --template trivia_reveal
kifungu stat --figure 500000 --unit KES --caption "Maximum coverage per depositor, per institution"
```

`--draft` renders at 540p, 15fps, single-threaded-fast, for approval loops. Ship a `--watch` mode that re-renders a draft on Cut file save; it is the difference between iterating six times a day and twice.

---

## 10. Repository layout

```
kifungu/
├── kifungu/
│   ├── ingest/        pdf.py  synthetic.py  parsers/kenya_statute.py  index.py
│   ├── cut/           schema.py  templates.py  validate.py  llm_assist.py
│   ├── render/
│   │   ├── shots/     scroll_hunt.py  spotlight.py  marker_sweep.py  clause_lift.py
│   │   │              kinetic_typeset.py  gloss_flip.py  redaction_reveal.py
│   │   │              key_figure.py  citation_stamp.py  endplate.py
│   │   ├── text.py    (PangoCairo layout, emphasis spans, line metrics)
│   │   ├── easing.py  compositor.py  profiles.py  encode.py
│   ├── brand.py  manifest.py  cli.py
├── brand/kdic.json
├── templates/*.yaml
├── corpus/            (gitignored, regenerable)
├── cuts/              (committed — these are the reviewable artefacts)
├── renders/           (gitignored)
└── tests/
```

Dependencies: `pymupdf`, `pycairo` + `pygobject` (Pango), `numpy`, `pillow`, `pydantic` (Cut schema), `typer`, `rich`, system `ffmpeg`. Everything else optional. Total install is small enough to run on a KDIC workstation without admin gymnastics.

---

## 11. Beyond the Act

Front-ends that emit Cuts, in rough order of usefulness:

- **IADI Core Principles** — same statute parser with a different heading regex; already the content-idea source for the register.
- **Citizens' Service Delivery Charter** — commitment-per-clip series, straight out of the compliance workbook.
- **Themed-day openers** — the register's five days as five templates; the opener becomes a render, not a design job.
- **CEO quote cards** — text in, quote card out, consistent every time.
- **FAQ / InfoBYTES** — booklet content already exists; each answer is a `definition_pullout`.
- **Key-figure stings** — payout figures, institution counts, coverage limits.
- **Roadshow recaps** — synthetic-page path over a field report.
- **B-roll library** — batch-render `redaction_reveal` and `scroll_hunt` elements with alpha, once, and keep a shelf of them for every future film including *Pesa Zako Ziko Salama Kwa Bank*.

---

## 12. Phasing

| Phase | Deliverable | Definition of done |
|---|---|---|
| **0** | Walking skeleton | Ingest the Act; render `page_establish` + `spotlight` on `s.27(1)` to a 9:16 mp4. Ugly is fine; the pipeline runs end to end. |
| **1** | Authentic-page path | Full statute parser, line-grouped bboxes, FTS search, `find`/`cut` CLI, Cut schema validation. |
| **2** | Shot library + brand | All twelve shots, brand tokens wired, five output profiles, alpha B-roll export, manifests. |
| **3** | Synthetic path | DOCX/Markdown/text ingest, quote/trivia/stat front-ends, template library. Engine is now general. |
| **4** | Operator layer | Local FastAPI + single-page UI: pick document → click paragraph → choose template → adjust holds → render. Non-technical staff can drive it unaided. |
| **5** | Optional LLM assist | Emphasis suggestions, gloss drafting EN/SW, weekly clause shortlist. Strictly additive; `--offline` remains fully functional. |

Phase 4 is the one that matters institutionally. Animation has never been an in-house activity at KDIC; a CLI makes *you* capable, an operator UI makes *the division* capable — and a capability the division owns is far harder to argue away than a skill one intern happens to have.

---

## 13. Test plan

- **Verbatim integrity** — rendered quote equals source substring, byte for byte.
- **Bbox regression** — golden fixtures for ten known clauses in the Act; parser changes that move a box fail the build.
- **Determinism** — two renders of one Cut produce identical output hashes.
- **Playback compatibility** — every H.264 output opens in Chrome, WhatsApp Web and PowerPoint; asserted by checking `pix_fmt` via ffprobe in CI.
- **Alpha integrity** — `broll` output has a real alpha channel with non-trivial transparency (ffprobe + a pixel sample).
- **Readability** — hold-time rule enforced as a schema validator, not a convention.
- **Safe areas** — no rendered ink outside the profile's declared safe area; caught by a bounding-box assertion on the composited frame.

---

## 14. Open items

1. **Brand hexes and licensed typeface files** — blocking for Phase 2, not for Phases 0–1. Start on the skeleton now, style later.
2. **Confirm the authoritative source PDF** of the KDI Act (Kenya Law revised edition vs. the Corporation's own copy) and pin its hash — the corpus is only as trustworthy as the file it was built from.
3. **Music bed licensing** — clear the audio library once, centrally, rather than per-clip.
4. **Approval routing** — who signs `gloss.approved_by`: the AD, or Legal for statutory glosses? Worth settling before the first public post, because the gate enforces whatever you decide.
5. **Kiswahili typography** — confirm the display face carries the full diacritic set before committing to bilingual glosses.
