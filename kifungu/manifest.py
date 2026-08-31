"""The approvals manifest (spec §8.6).

Every render writes a sidecar recording operator, date, source hash, citation,
the exact quoted string, gloss and approver, the shot list and output hashes —
a single artefact Legal or the AD can sign off and file.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from kifungu import __version__
from kifungu.corpus import Corpus
from kifungu.cut.schema import Cut


class OutputRecord(BaseModel):
    profile: str
    filename: str
    bytes: int
    sha256: str
    frames: int
    duration: float


class Manifest(BaseModel):
    cut_id: str
    engine_version: str
    rendered: str
    operator: str
    draft: bool = False

    source_doc_id: str
    source_title: str
    source_sha256: str
    citation: str
    page: int
    verbatim: str
    elided: bool

    gloss_en: str = ""
    gloss_sw: str = ""
    gloss_approved_by: str | None = None

    shots: list[str] = Field(default_factory=list)
    outputs: list[OutputRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    corpus_stale: bool = False

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(json.loads(self.model_dump_json()), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(
    cut: Cut,
    corpus: Corpus | None,
    results: list,
    *,
    draft: bool = False,
    warnings: list[str] | None = None,
) -> Manifest:
    outputs = [
        OutputRecord(
            profile=result.profile,
            filename=Path(result.path).name,
            bytes=Path(result.path).stat().st_size,
            sha256=sha256_file(result.path),
            frames=result.frames,
            duration=result.duration,
        )
        for result in results
    ]
    stale = bool(
        corpus is not None and cut.source.sha256 and corpus.meta.sha256 != cut.source.sha256
    )
    return Manifest(
        cut_id=cut.cut_id,
        engine_version=__version__,
        rendered=datetime.now(UTC).isoformat(),
        operator=cut.operator,
        draft=draft,
        source_doc_id=cut.source.doc_id,
        source_title=cut.source.title,
        source_sha256=cut.source.sha256,
        citation=cut.source.citation,
        page=cut.source.page,
        verbatim=cut.source.verbatim,
        elided=cut.source.elided,
        gloss_en=cut.gloss.en,
        gloss_sw=cut.gloss.sw,
        gloss_approved_by=cut.gloss.approved_by,
        shots=[scene.shot for scene in cut.scenes],
        outputs=outputs,
        warnings=warnings or [],
        corpus_stale=stale,
    )


def manifest_path(out_dir: Path, cut_id: str) -> Path:
    return Path(out_dir) / f"{cut_id}.manifest.json"
