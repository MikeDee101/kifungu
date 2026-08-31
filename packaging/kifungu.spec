# PyInstaller spec for the Windows portable build.
#
# onedir rather than onefile: an operator unzips it and runs kifungu.exe with no
# admin rights, and onefile would re-extract ~200MB of Skia to a temp directory
# on every invocation.
#
# Run from the repository root:
#   pyinstaller packaging/kifungu.spec --noconfirm --distpath packaging/dist
#
# ruff: noqa

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

datas = [
    (str(ROOT / "brand"), "brand"),
    (str(ROOT / "templates"), "templates"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "packaging" / "NOTICE-thirdparty.md"), "."),
]

# Skia looks for icudtl.dat beside the running executable. Shipping it next to
# kifungu.exe gives the frozen build the real ICU line-breaking data.
for site in sys.path:
    candidate = Path(site) / "icudtl.dat"
    if candidate.is_file():
        datas.append((str(candidate), "."))
        break

a = Analysis(
    [str(ROOT / "kifungu" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "kifungu.render.shots.page_establish",
        "kifungu.render.shots.spotlight",
        "kifungu.render.shots.citation_stamp",
        "kifungu.ingest.parsers.kenya_statute",
        "kifungu.ingest.parsers.generic",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PySide6", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="kifungu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="kifungu",
)
