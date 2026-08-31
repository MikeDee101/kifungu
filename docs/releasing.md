# Releasing

Releases are cheap on purpose: this engine is meant to grow a shot at a time,
and a shot that ships the day it lands is worth more than five that queue up.

## Cut a release

```bash
git tag -a v0.2.0 -m "kinetic_typeset and marker_sweep"
git push origin v0.2.0
```

That is the whole process. The `Release (Windows)` workflow then:

1. runs lint and the full test suite — a failure here stops the release;
2. resolves the version from the tag via `hatch-vcs`;
3. fetches an LGPL ffmpeg build;
4. builds the portable bundle with PyInstaller;
5. **runs `kifungu.exe --version`, `shots` and `templates` inside the bundle**,
   because a release that cannot start is worse than no release;
6. zips it with a `.sha256` and publishes it with generated notes.

## Versioning

Semantic versioning. The version is never typed into a file — `hatch-vcs`
derives it from the tag, and it flows into `kifungu.__version__`, every Cut's
`engine_version` and every render manifest. That is what makes stale-Cut
detection (spec §8.5) meaningful.

Between tags, builds report a development version such as `0.1.1.dev4+g1a2b3c4`.

## Adding a shot

Adding a shot should touch nothing but the shot (spec §5):

1. write `kifungu/render/shots/<name>.py` with `render(ctx, t_local)`, a
   `z_order`, and `requires`;
2. set `displays_reading_text = True` if it puts text on screen to be read —
   this is what subjects it to the hold-time rule;
3. register it in `kifungu/render/shots/__init__.py` and remove it from
   `PLANNED`;
4. add it to a template in `templates/`;
5. tag and push.

If a shot needs to import Skia's text or filter APIs directly, that is a signal
the abstraction in `render/text.py` or `render/effects.py` is missing something —
extend those rather than reaching past them.

## Checklist before tagging

- [ ] `uv run pytest -q` green on Windows
- [ ] `uv run ruff check .` clean
- [ ] `CHANGELOG.md` updated
- [ ] a real render eyeballed, not just a passing test
