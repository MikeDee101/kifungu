"""The accuracy and approvals guardrails of spec §8, and the §4 hold-time rule."""

from __future__ import annotations

import pytest

from kifungu.corpus import Corpus
from kifungu.cut.schema import Cut, Scene, Source
from kifungu.cut.templates import cut_from_template
from kifungu.cut.validate import hold_time_required, validate
from kifungu.ingest.pdf import ScannedDocumentError, ingest_pdf


def errors(problems) -> list[str]:
    return [p.rule for p in problems if p.level == "error"]


def base_cut(corpus: Corpus) -> Cut:
    return cut_from_template(corpus, "s.12(1)", "clause_spotlight")


# ---- §8.1 verbatim lock ----------------------------------------------------


def test_verbatim_matches_the_source_byte_for_byte(corpus: Corpus):
    cut = base_cut(corpus)
    start, end = cut.source.char_span
    assert corpus.full_text[start:end] == cut.source.verbatim
    assert "verbatim_lock" not in errors(validate(cut, corpus))


def test_hand_edited_quote_is_refused(corpus: Corpus):
    cut = base_cut(corpus)
    cut.source.verbatim = cut.source.verbatim.replace("shall", "must")
    assert "verbatim_lock" in errors(validate(cut, corpus))


def test_every_node_verifies_against_the_document(corpus: Corpus):
    assert all(corpus.verify_verbatim(node) for node in corpus.nodes.values())


# ---- §8.2 elision discipline -----------------------------------------------


def test_ellipsis_must_be_declared(corpus: Corpus):
    cut = base_cut(corpus)
    cut.source.verbatim = "The Corporation shall pay…"
    cut.source.char_span = None
    assert "elision" in errors(validate(cut, corpus))
    cut.source.elided = True
    assert "elision" not in errors(validate(cut, corpus))


def test_strict_refuses_elided_quotes(corpus: Corpus):
    cut = base_cut(corpus)
    cut.source.elided = True
    assert "elision" in errors(validate(cut, corpus, strict=True))


# ---- §8.4 citation mandatory -----------------------------------------------


def test_public_profile_requires_a_citation_stamp(corpus: Corpus):
    cut = base_cut(corpus)
    cut.scenes = [s for s in cut.scenes if s.shot != "citation_stamp"]
    assert "citation" in errors(validate(cut, corpus, profiles=["reel"]))
    # broll is not a public profile, so it is exempt.
    assert "citation" not in errors(validate(cut, corpus, profiles=["broll"]))


# ---- §8.5 source pinning ---------------------------------------------------


def test_amended_source_flags_the_cut_stale(corpus: Corpus):
    cut = base_cut(corpus)
    cut.source.sha256 = "0" * 64
    assert "source_pinning" in errors(validate(cut, corpus))


# ---- §8.7 approval gate ----------------------------------------------------


def test_public_profiles_gate_on_gloss_approval(corpus: Corpus):
    cut = base_cut(corpus)
    cut.gloss.en = "If your bank fails, you are paid back."
    assert "approval_gate" in errors(validate(cut, corpus, profiles=["reel"]))

    cut.gloss.approved_by = "Legal"
    assert "approval_gate" not in errors(validate(cut, corpus, profiles=["reel"]))


def test_draft_and_broll_are_exempt_from_the_gate(corpus: Corpus):
    cut = base_cut(corpus)
    cut.gloss.en = "Plain language."
    assert "approval_gate" not in errors(validate(cut, corpus, profiles=["reel"], draft=True))
    assert "approval_gate" not in errors(validate(cut, corpus, profiles=["broll"]))


# ---- §4 hold-time rule -----------------------------------------------------


def test_hold_time_formula():
    assert hold_time_required(0) == pytest.approx(1.8)
    assert hold_time_required(30) == pytest.approx(0.35 * 30 + 0.8)


def test_unreadably_short_hold_is_refused(corpus: Corpus):
    cut = base_cut(corpus)
    for scene in cut.scenes:
        if scene.shot == "spotlight":
            scene.dur = 1.0
    assert "hold_time" in errors(validate(cut, corpus))


def test_templates_derive_holds_that_satisfy_the_rule(corpus: Corpus):
    """A template must never emit a Cut that its own validator rejects."""
    cut = base_cut(corpus)
    assert "hold_time" not in errors(validate(cut, corpus))


# ---- schema shape ----------------------------------------------------------


def test_unknown_shot_is_reported(corpus: Corpus):
    cut = base_cut(corpus)
    cut.scenes.append(Scene(shot="teleport", t_in=0.0, dur=1.0))
    assert "shot" in errors(validate(cut, corpus))


def test_planned_shot_reports_as_unimplemented(corpus: Corpus):
    cut = base_cut(corpus)
    cut.scenes.append(Scene(shot="marker_sweep", t_in=0.0, dur=1.0))
    problems = [p for p in validate(cut, corpus) if p.rule == "shot"]
    assert any("not implemented yet" in p.message for p in problems)


def test_emphasis_span_outside_verbatim_is_rejected():
    with pytest.raises(ValueError, match="outside verbatim"):
        Source(
            doc_id="d", title="t", sha256="x", citation="s.1", page=1,
            verbatim="short", emphasis=[(0, 99)],
        )


def test_empty_verbatim_is_rejected():
    with pytest.raises(ValueError, match="nothing to quote"):
        Source(doc_id="d", title="t", sha256="x", citation="s.1", page=1, verbatim="   ")


# ---- ingest guard ----------------------------------------------------------


def test_scanned_pdf_is_refused(tmp_path):
    """Verbatim lock is vacuous without a text layer, so ingest must refuse."""
    import pymupdf

    path = tmp_path / "scan.pdf"
    document = pymupdf.open()
    document.new_page(width=595, height=842)
    document.save(path)
    document.close()

    with pytest.raises(ScannedDocumentError, match="looks like a scan"):
        ingest_pdf(path, "scan", tmp_path / "corpus", "generic")
