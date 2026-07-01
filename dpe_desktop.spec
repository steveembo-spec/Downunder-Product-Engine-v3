# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Downunder Product Engine
Build with: pyinstaller dpe_desktop.spec

This creates a single windowed .exe with no console window.
"""

import sys
from pathlib import Path

# Get project root (where this spec file is located)
spec_root = Path(SPEC).resolve().parent if SPEC else Path.cwd()

a = Analysis(
    ['desktop/app.py'],
    pathex=[str(spec_root)],
    binaries=[],
    datas=[
        ('config', 'config'),
        ('assets', 'assets'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'core.product.master_product_service',
        'core.product_database',
        'dpe_v3.supplier_plugins.a1',
        'dpe_v3.supplier_plugins.cassons',
        'dpe_v3.supplier_plugins.serco',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Downunder Product Engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    icon='assets/logo.ico',  # Application icon
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
