# -*- mode: python ; coding: utf-8 -*-
import os
import janome
from pathlib import Path

ext_dir = Path("monotonic_align/monotonic_align")
ext_files = list(ext_dir.glob("core.*.pyd")) + list(ext_dir.glob("core.*.so"))

if not ext_files:
    raise FileNotFoundError("core extension not found")

core_binary = str(ext_files[0])

janome_base = os.path.dirname(janome.__file__)
janome_sysdic = os.path.join(janome_base, 'sysdic')

datas = [
    ('monotonic_align', 'monotonic_align'),
    (janome_sysdic, 'janome/sysdic'),
    ('commons.py', '.')
]

binaries = [
    (core_binary, "monotonic_align/monotonic_align")
]

a = Analysis(
    ['PJSK-MultiGUI.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=['monotonic_align.core'],
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
    name='PJSK-MultiGUI',
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
    icon=['favicon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PJSK-MultiGUI',
)
app = BUNDLE(
    coll,
    name='PJSK-MultiGUI.app',
    icon='favicon.ico',
    bundle_identifier=None,
)
