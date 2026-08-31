# Third-party components

Kifungu is licensed under the **AGPL-3.0-or-later** (see `LICENSE`). The Windows
release bundles the components below. Each remains under its own licence.

| Component | Licence | Notes |
|---|---|---|
| [PyMuPDF](https://pymupdf.readthedocs.io/) | AGPL-3.0 or Artifex commercial | PDF ingest. Its AGPL terms are the reason this project is AGPL-3.0; an Artifex commercial licence would be required to distribute Kifungu under different terms. |
| [skia-python](https://github.com/kyamagu/skia-python) / Skia | BSD-3-Clause | Rendering and text shaping. |
| HarfBuzz, FreeType, ICU | MIT / FTL / Unicode-3.0 | Bundled inside Skia; `icudtl.dat` ships beside `kifungu.exe`. |
| [FFmpeg](https://ffmpeg.org/) | **LGPL-2.1-or-later** | Encoding. The release bundles an LGPL build in `_bin/`. A GPL or non-free FFmpeg build must not be substituted without re-checking the licence combination. |
| [Pillow](https://python-pillow.org/) | MIT-CMU | Image helpers. |
| [NumPy](https://numpy.org/) | BSD-3-Clause | Frame buffers. |
| [pydantic](https://docs.pydantic.dev/) | MIT | Cut and corpus schemas. |
| [typer](https://typer.tiangolo.com/) / [click](https://click.palletsprojects.com/) | MIT / BSD-3-Clause | CLI. |
| [rich](https://rich.readthedocs.io/) | MIT | Terminal output. |
| [PyYAML](https://pyyaml.org/) | MIT | Templates. |

## Content

No statutory text is distributed with this software. Source documents are
supplied by the operator and are pinned by sha256 in the corpus, the Cut and the
render manifest.

Brand assets (logos, licensed typefaces) are **not** included in this repository
and must be supplied locally under their own licences.

## Obtaining source

The complete corresponding source is at <https://github.com/MikeDee101/kifungu>.
