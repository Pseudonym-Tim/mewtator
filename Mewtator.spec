# -*- mode: python ; coding: utf-8 -*-

import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT_ROOT = Path(SPECPATH).resolve()

a = Analysis(
    ['app\\main.py'],
    pathex=[],
    binaries=[],
    # Keep these available through sys._MEIPASS for bundled resource lookups.
    datas=[
        (str(PROJECT_ROOT / 'locales'), 'locales'),
        (str(PROJECT_ROOT / 'assets'), 'assets'),
    ] + collect_data_files('sv_ttk'),
    hiddenimports=collect_submodules('sv_ttk') + collect_submodules('pywinstyles'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Mewtator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icons\\mewtator.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Mewtator',
)


# PyInstaller 6+ places bundled data under _internal by default. Mewtator's
# locales are intentionally external/editable, and both folders are useful in
# the distributable directory, so mirror them beside Mewtator.exe as well.
DIST_DIR = Path(DISTPATH) / 'Mewtator'
for folder_name in ('locales', 'assets'):
    source_dir = PROJECT_ROOT / folder_name
    target_dir = DIST_DIR / folder_name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
