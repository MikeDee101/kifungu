"""Command line interface (spec §9)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from kifungu import __version__
from kifungu.platform import configure_stdio

configure_stdio()

app = typer.Typer(
    add_completion=False,
    help="Turn institutional documents into broadcast-quality motion graphics.",
)
console = Console()


def _corpus_root(doc_id: str, base: Path | None) -> Path:
    return (base or Path.cwd() / "corpus") / doc_id


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Print the engine version and exit."),
) -> None:
    if version:
        console.print(f"kifungu {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def ingest(
    pdf: Path = typer.Option(..., "--pdf", exists=True, help="Source PDF."),
    doc_id: str = typer.Option(..., "--doc-id", help="Short identifier, e.g. kdi-act-2012."),
    parser: str = typer.Option("kenya_statute", "--parser", help="Structure parser."),
    dpi: int = typer.Option(300, "--dpi", help="Page raster resolution."),
    title: str | None = typer.Option(None, "--title"),
    corpus_dir: Path | None = typer.Option(None, "--corpus-dir"),
) -> None:
    """Ingest a document into the corpus."""
    from kifungu.ingest.index import build_index
    from kifungu.ingest.pdf import ScannedDocumentError, ingest_pdf

    root = _corpus_root(doc_id, corpus_dir)
    try:
        with console.status(f"Ingesting {pdf.name}..."):
            corpus = ingest_pdf(pdf, doc_id, root, parser, dpi=dpi, title=title)
            build_index(corpus, root)
    except ScannedDocumentError as error:
        console.print(f"[red]Refused:[/red] {error}")
        raise typer.Exit(code=2) from None

    console.print(
        f"[green]Ingested[/green] {corpus.meta.title} -> {root}\n"
        f"  {corpus.meta.page_count} pages, {len(corpus.nodes)} nodes, "
        f"sha256 {corpus.meta.sha256[:16]}"
    )


@app.command()
def find(
    query: str = typer.Argument(..., help="Free text to search for."),
    doc: str = typer.Option(..., "--doc", help="Document id."),
    limit: int = typer.Option(10, "--limit"),
    corpus_dir: Path | None = typer.Option(None, "--corpus-dir"),
) -> None:
    """Locate a clause by search rather than by page number."""
    from kifungu.ingest.index import search

    hits = search(_corpus_root(doc, corpus_dir), query, limit=limit)
    if not hits:
        console.print(f"[yellow]No matches for {query!r} in {doc}.[/yellow]")
        raise typer.Exit(code=1)

    table = Table(show_header=True, header_style="bold")
    table.add_column("citation", style="cyan")
    table.add_column("page", justify="right")
    table.add_column("kind")
    table.add_column("text")
    for hit in hits:
        table.add_row(hit.citation, str(hit.page), hit.kind, hit.snippet.replace("\n", " ")[:74])
    console.print(table)


@app.command()
def cut(
    doc: str = typer.Option(..., "--doc"),
    cite: str = typer.Option(..., "--cite", help="Canonical citation, for example s.27(1)."),
    template: str = typer.Option("clause_spotlight", "--template"),
    style: str | None = typer.Option(
        None, "--style", help="Selection style; see `kifungu styles`."
    ),
    profiles: str | None = typer.Option(None, "--profiles", help="Comma-separated."),
    operator: str = typer.Option("", "--operator"),
    out: Path | None = typer.Option(None, "--out"),
    corpus_dir: Path | None = typer.Option(None, "--corpus-dir"),
) -> None:
    """Author a Cut for review."""
    from kifungu.corpus import Corpus
    from kifungu.cut.templates import cut_from_template
    from kifungu.cut.validate import validate

    corpus = Corpus.load(_corpus_root(doc, corpus_dir))
    try:
        the_cut = cut_from_template(
            corpus,
            cite,
            template,
            profiles=[p.strip() for p in profiles.split(",")] if profiles else None,
            operator=operator,
            style=style,
        )
    except KeyError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=2) from None

    destination = out or Path.cwd() / "cuts" / f"{the_cut.cut_id}.json"
    the_cut.write(destination)

    console.print(
        f"[green]Wrote[/green] {destination}\n"
        f"  {the_cut.source.citation}  p.{the_cut.source.page}  "
        f"{the_cut.source.word_count} words  {the_cut.duration:.1f}s  "
        f"profiles={','.join(the_cut.profiles)}"
    )
    for problem in validate(the_cut, corpus):
        colour = "red" if problem.level == "error" else "yellow"
        console.print(f"  [{colour}]{problem}[/{colour}]")


@app.command()
def render(
    cuts: list[Path] = typer.Argument(..., help="One or more Cut JSON files."),
    out: Path = typer.Option(Path("renders"), "--out"),
    profile: str | None = typer.Option(None, "--profile", help="Override the Cut's profiles."),
    draft: bool = typer.Option(False, "--draft", help="540p/15fps for approval loops."),
    strict: bool = typer.Option(False, "--strict", help="Refuse elided quotes."),
    corpus_dir: Path | None = typer.Option(None, "--corpus-dir"),
) -> None:
    """Render a Cut to every profile it declares."""
    from kifungu import manifest as manifest_module
    from kifungu.brand import load_brand
    from kifungu.corpus import Corpus
    from kifungu.cut.schema import Cut
    from kifungu.cut.validate import ValidationError, raise_for, validate
    from kifungu.render import compositor
    from kifungu.render import profiles as profile_module

    for cut_path in cuts:
        the_cut = Cut.load(cut_path)
        corpus = None
        root = _corpus_root(the_cut.source.doc_id, corpus_dir)
        if (root / "meta.json").is_file():
            corpus = Corpus.load(root)

        names = [profile] if profile else the_cut.profiles
        problems = validate(the_cut, corpus, strict=strict, draft=draft, profiles=names)
        try:
            raise_for(problems)
        except ValidationError as error:
            console.print(f"[red]Refusing to render {the_cut.cut_id}:[/red]\n{error}")
            raise typer.Exit(code=3) from None

        warnings = [str(p) for p in problems if p.level == "warning"]
        for warning in warnings:
            console.print(f"  [yellow]{warning}[/yellow]")

        brand = load_brand(the_cut.brand)
        if brand.provisional:
            console.print(
                "  [yellow]Brand tokens are marked provisional - "
                "not yet reconciled with the brand manual.[/yellow]"
            )

        results = []
        for name in names:
            target = profile_module.get(name)
            if draft:
                target = profile_module.draft(target)
            with console.status(f"Rendering {the_cut.cut_id} [{target.name}]..."):
                result = compositor.render(the_cut, corpus, target, out, brand)
            results.append(result)
            console.print(
                f"[green]Rendered[/green] {result.path}  "
                f"({result.frames} frames, {result.duration:.1f}s)"
            )

        record = manifest_module.build(the_cut, corpus, results, draft=draft, warnings=warnings)
        path = record.write(manifest_module.manifest_path(out, the_cut.cut_id))
        console.print(f"  manifest: {path}")


@app.command()
def templates() -> None:
    """List available Cut templates."""
    from kifungu.cut.templates import available_templates, load_template

    table = Table(show_header=True, header_style="bold")
    table.add_column("template", style="cyan")
    table.add_column("profiles")
    table.add_column("description")
    for name in available_templates():
        entry = load_template(name)
        table.add_row(name, ",".join(entry.profiles), " ".join(entry.description.split())[:60])
    console.print(table)


@app.command()
def styles() -> None:
    """List the selection styles a Cut can point at a clause with."""
    from kifungu.render.selection import STYLES

    table = Table(show_header=True, header_style="bold")
    table.add_column("style", style="cyan")
    table.add_column("looks like")
    for name, style in STYLES.items():
        table.add_row(name, style.description)
    console.print(table)
    console.print("  Pick one with [cyan]kifungu cut --style <name>[/cyan].")


@app.command()
def shots() -> None:
    """List implemented shots and those still to come."""
    from kifungu.render.shots import PLANNED, REGISTRY

    table = Table(show_header=True, header_style="bold")
    table.add_column("shot", style="cyan")
    table.add_column("z", justify="right")
    table.add_column("status")
    table.add_column("requires")
    for name, shot in sorted(REGISTRY.items(), key=lambda kv: kv[1].z_order):
        table.add_row(
            name, str(shot.z_order), "[green]ready[/green]", ",".join(sorted(shot.requires)) or "-"
        )
    for name in sorted(PLANNED):
        table.add_row(name, "-", "[dim]planned[/dim]", "-")
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
